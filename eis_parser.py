#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Production parser for EIS contract pages ("Объекты закупки").

Key properties:
- Uses Playwright for stable DOM interaction
- Parses by table headers instead of brittle fixed indices
- Saves debug archive (raw HTML, parse JSON, screenshots)
- Supports single URL and batch mode
- Exports CSV always, XLSX optionally (if pandas/openpyxl installed)
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import tkinter as tk
from tkinter import ttk, messagebox

from playwright.async_api import Browser, BrowserContext, Error, Frame, Page, async_playwright


FIELD_ORDER = [
    "name",
    "category_ls",
    "okpd2",
    "country",
    "trade_name",
    "ru",
    "release_form",
    "dose",
    "qty_need",
    "price_per_unit",
    "sum_rub",
    "holder_name",
    "manufacturer_name",
    "manufacturer_country",
    "primary_package_type",
    "qty_forms_primary",
    "qty_primary_packages",
    "qty_consumer_units",
    "consumer_package_completeness",
]

EXPORT_HEADERS_RU = {
    "name": "Наименование",
    "category_ls": "Категории ЛС",
    "okpd2": "ОКПД2",
    "country": "Страна происхождения",
    "trade_name": "Торговое наименование",
    "ru": "РУ",
    "release_form": "Форма выпуска",
    "dose": "Дозировка",
    "qty_need": "Количество товара, объем работы, услуги, Единица измерения",
    "price_per_unit": "Цена за единицу измерения, ₽",
    "sum_rub": "Сумма, ₽",
    "holder_name": "Наименование держателя или владельца РУ",
    "manufacturer_name": "Наименование производителя",
    "manufacturer_country": "Страна производителя",
    "primary_package_type": "Вид первичной упаковки",
    "qty_forms_primary": "Количество лекарственных форм в первичной упаковке",
    "qty_primary_packages": "Количество первичных упаковок в потребительской упаковке",
    "qty_consumer_units": "Количество потребительских единиц в потребительской упаковке",
    "consumer_package_completeness": "Комплектность потребительской упаковки",
}


@dataclass
class ParseRecord:
    name: str = ""
    category_ls: str = ""
    okpd2: str = ""
    country: str = ""
    trade_name: str = ""
    ru: str = ""
    release_form: str = ""
    dose: str = ""
    qty_need: str = ""
    price_per_unit: str = ""
    sum_rub: str = ""
    holder_name: str = ""
    manufacturer_name: str = ""
    manufacturer_country: str = ""
    primary_package_type: str = ""
    qty_forms_primary: str = ""
    qty_primary_packages: str = ""
    qty_consumer_units: str = ""
    consumer_package_completeness: str = ""

    def as_row(self) -> dict[str, str]:
        return {k: getattr(self, k, "") for k in FIELD_ORDER}


class EISParser:
    def __init__(self, timeout_ms: int = 60000, expand_rounds: int = 4) -> None:
        self.timeout_ms = timeout_ms
        self.expand_rounds = expand_rounds

    async def parse_url(
        self,
        page: Page,
        url: str,
        archive_dir: Path,
        save_trace: bool = False,
    ) -> list[dict[str, str]]:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        job_dir = archive_dir / f"job_{ts}"
        raw_dir = job_dir / "raw"
        parsed_dir = job_dir / "parsed"
        raw_dir.mkdir(parents=True, exist_ok=True)
        parsed_dir.mkdir(parents=True, exist_ok=True)

        await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        await page.wait_for_timeout(1200)

        await self._close_overlays(page)
        frame = await self._find_frame_with_objects(page)
        if frame is None:
            raise RuntimeError("Не найден контекст с блоком 'Объекты закупки'")

        await self._expand_objects(frame)
        await page.wait_for_timeout(800)

        html = await frame.content()
        (raw_dir / "objects_frame.html").write_text(html, encoding="utf-8")

        payload = await frame.evaluate(EXTRACT_SCRIPT)
        records = [self._normalize_record(item) for item in payload or []]
        records = self._merge_split_records(records)
        records = [self._finalize_record(rec) for rec in records]
        rows = [r.as_row() for r in records]

        (parsed_dir / "rows.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if save_trace:
            # trace is started in outer layer (context), this only marks run folder
            (job_dir / "trace_requested.txt").write_text("trace enabled", encoding="utf-8")

        return rows

    async def _close_overlays(self, page: Page) -> None:
        candidates = [
            "button:has-text('Принять')",
            "button:has-text('Согласен')",
            "button:has-text('Закрыть')",
            "[aria-label='close']",
            "[aria-label='Close']",
        ]
        for selector in candidates:
            loc = page.locator(selector)
            count = min(await loc.count(), 3)
            for i in range(count):
                try:
                    await loc.nth(i).click(timeout=800)
                except Error:
                    pass

    async def _find_frame_with_objects(self, page: Page) -> Optional[Frame]:
        for frame in page.frames:
            try:
                if await frame.locator("text=Объекты закупки").count() > 0:
                    return frame
            except Error:
                continue
        return None

    async def _expand_objects(self, frame: Frame) -> None:
        try:
            anchor = frame.locator("text=Объекты закупки").first
            await anchor.scroll_into_view_if_needed(timeout=4000)
        except Error:
            pass

        for _ in range(self.expand_rounds):
            toggles = frame.locator(
                "[aria-expanded='false'], button[aria-expanded='false'], [role='button'][aria-expanded='false']"
            )
            cnt = await toggles.count()
            if cnt == 0:
                break

            clicked = 0
            for i in range(min(cnt, 120)):
                item = toggles.nth(i)
                try:
                    await item.scroll_into_view_if_needed(timeout=1200)
                    await item.click(timeout=1200)
                    clicked += 1
                except Error:
                    continue

            if clicked == 0:
                break
            await frame.page.wait_for_timeout(500)

    def _normalize_record(self, raw: dict) -> ParseRecord:
        rec = ParseRecord(**{k: _clean(raw.get(k, "")) for k in FIELD_ORDER})

        # Stage 2 normalization: keep raw extraction, then reshape columns from mixed blocks.
        blob = " | ".join(_clean(raw.get(k, "")) for k in FIELD_ORDER if _clean(raw.get(k, "")))

        # Name must not be equal to OKPD2 code.
        if _looks_like_okpd2_code(rec.name) or (rec.okpd2 and _clean(rec.name) == _clean(rec.okpd2)):
            rec.name = ""

        # Fallback for legacy payloads where one compact block is stored in country.
        if "|" in rec.country and (not rec.category_ls or not rec.okpd2):
            self._split_compact_top_block(rec)

        # Parse compact pipe blocks from any spilled field (country/qty/name blobs).
        self._split_compact_top_block(rec, source_text=blob)

        # Recover the item name when it leaked into other columns.
        if not rec.name or len(rec.name) < 6:
            parsed_name = _extract_name_from_blob(blob)
            if parsed_name:
                rec.name = parsed_name

        # Fix legacy column shift: RU -> trade_name, form -> RU, dose -> form, qty -> dose.
        if rec.ru and not _looks_like_ru_code(rec.ru) and _looks_like_ru_code(rec.release_form):
            if not rec.trade_name:
                rec.trade_name = rec.ru
            rec.ru = rec.release_form
            rec.release_form = rec.dose
            rec.dose = ""

        # Additional shift case: trade_name is empty, RU stores trade text, release_form stores RU.
        if not rec.trade_name and rec.ru and _looks_like_ru_code(rec.release_form):
            rec.trade_name = rec.ru
            rec.ru = rec.release_form
            if rec.dose and not rec.release_form:
                rec.release_form = rec.dose
            rec.dose = _extract_dose(rec.dose) or ""

        # Pull detailed fields from long GRLS block when it was flattened into one cell.
        if _looks_like_meta_blob(blob):
            meta = _extract_meta_fields(blob)
            for field, value in meta.items():
                if getattr(rec, field, "") == "" and value:
                    setattr(rec, field, value)

            # If qty column contains a long block, keep only real qty text.
            if len(rec.qty_need) > 80:
                qty_candidate = _extract_qty_from_blob(blob)
                if qty_candidate:
                    rec.qty_need = qty_candidate

        # Sometimes completeness contains a tail with item title and compact top-row values.
        if rec.consumer_package_completeness and (
            re.search(r"\d+\.\s+", rec.consumer_package_completeness)
            or "СТРАНА ПРОИСХОЖДЕНИЯ" in rec.consumer_package_completeness.upper()
        ):
            carried_name = _extract_name_from_blob(rec.consumer_package_completeness)
            if carried_name and (not rec.name or _looks_like_okpd2_code(rec.name)):
                rec.name = carried_name

            rec.consumer_package_completeness = "~"

        if not rec.okpd2:
            rec.okpd2 = _extract_okpd2(rec.name) or _extract_okpd2(rec.category_ls)

        dose_candidates = [_extract_dose(rec.dose), _extract_dose(rec.name), _extract_dose(blob)]
        dose_candidates = [d for d in dose_candidates if d]
        dose_candidate = ""
        if dose_candidates:
            # Prefer complex dosage chains (with '+') and then the longest variant.
            complex_candidates = [d for d in dose_candidates if "+" in d]
            dose_candidate = max(complex_candidates or dose_candidates, key=len)
        if dose_candidate:
            rec.dose = dose_candidate

        if not rec.country:
            rec.country = _extract_country(rec.name)

        if not rec.dose:
            rec.dose = _extract_dose(blob)

        # Quantity/price/sum should come from top compact block, not from metadata text.
        if _looks_like_meta_blob(rec.qty_need) or "СТРАНА ПРОИСХОЖДЕНИЯ" in rec.qty_need.upper():
            rec.qty_need = ""

        if rec.price_per_unit and not _looks_like_price(rec.price_per_unit):
            rec.price_per_unit = ""

        if rec.sum_rub and not _looks_like_sum(rec.sum_rub):
            rec.sum_rub = ""

        compact = _extract_compact_values(blob)
        if not rec.qty_need and compact.get("qty_need"):
            rec.qty_need = compact["qty_need"]
        if not rec.price_per_unit and compact.get("price_per_unit"):
            rec.price_per_unit = compact["price_per_unit"]
        if not rec.sum_rub and compact.get("sum_rub"):
            rec.sum_rub = compact["sum_rub"]

        if not rec.qty_need:
            rec.qty_need = _extract_qty_from_blob(blob)

        if not rec.price_per_unit:
            rec.price_per_unit = _extract_price(blob)

        if not rec.sum_rub:
            rec.sum_rub = _extract_sum(blob)

        rec.country = _short_country(rec.country)

        # Keep name complete when source row ended up in another column.
        if (not rec.name or _looks_like_okpd2_code(rec.name)):
            recovered_name = _extract_name_from_blob(blob)
            if recovered_name:
                rec.name = recovered_name

        # Fallback: compose a readable name from stable columns instead of copying category.
        if not rec.name and rec.trade_name:
            chunks = [rec.trade_name, rec.release_form, rec.dose]
            rec.name = _clean(", ".join([c for c in chunks if c]))

        if _looks_like_okpd2_code(rec.name):
            rec.name = ""

        if not rec.name and rec.trade_name:
            chunks = [rec.trade_name, rec.release_form, rec.dose]
            rec.name = _clean(", ".join([c for c in chunks if c]))

        # If category contains an item-like title, move it to name and keep parsed category.
        if rec.category_ls and (re.match(r"^\d+\.\s", rec.category_ls) or ":" in rec.category_ls):
            if not rec.name or len(rec.name) < len(rec.category_ls):
                rec.name = rec.category_ls
            # Category should stay a class, not a full item title.
            if rec.okpd2:
                rec.category_ls = ""

        if rec.category_ls and rec.name and rec.category_ls == rec.name:
            rec.category_ls = ""

        return rec

    def _finalize_record(self, rec: ParseRecord) -> ParseRecord:
        row_blob = " | ".join(_clean(getattr(rec, f, "")) for f in FIELD_ORDER if _clean(getattr(rec, f, "")))

        if not rec.name or _looks_like_okpd2_code(rec.name):
            rec.name = _extract_name_from_blob(row_blob)
        if (not rec.name or _looks_like_okpd2_code(rec.name)) and rec.trade_name:
            rec.name = _clean(", ".join([x for x in [rec.trade_name, rec.release_form, rec.dose] if _clean(x)])
            )

        dose_candidates = [_extract_dose(rec.dose), _extract_dose(rec.name), _extract_dose(row_blob)]
        dose_candidates = [d for d in dose_candidates if d]
        dose_candidate = ""
        if dose_candidates:
            complex_candidates = [d for d in dose_candidates if "+" in d]
            dose_candidate = max(complex_candidates or dose_candidates, key=len)
        if dose_candidate:
            rec.dose = dose_candidate

        if rec.price_per_unit and not _looks_like_price(rec.price_per_unit):
            rec.price_per_unit = ""
        if rec.sum_rub and not _looks_like_sum(rec.sum_rub):
            rec.sum_rub = ""

        compact = _extract_compact_values(row_blob)
        if not rec.qty_need and compact.get("qty_need"):
            rec.qty_need = compact["qty_need"]
        if not rec.price_per_unit and compact.get("price_per_unit"):
            rec.price_per_unit = compact["price_per_unit"]
        if not rec.sum_rub and compact.get("sum_rub"):
            rec.sum_rub = compact["sum_rub"]

        if rec.consumer_package_completeness and (
            rec.consumer_package_completeness.strip().startswith("~")
            or "СТРАНА ПРОИСХОЖДЕНИЯ" in rec.consumer_package_completeness.upper()
            or "ПРЕПАРАТ" in rec.consumer_package_completeness.upper()
        ):
            rec.consumer_package_completeness = "~"

        return rec

    def _merge_split_records(self, records: list[ParseRecord]) -> list[ParseRecord]:
        if not records:
            return records

        merged: list[ParseRecord] = []
        last_core: Optional[ParseRecord] = None

        for rec in records:
            if last_core and self._is_addon_row(rec):
                self._merge_into(last_core, rec)
                continue

            key = self._record_key(rec)
            if key:
                existing = next((r for r in merged if self._record_key(r) == key), None)
                if existing:
                    self._merge_into(existing, rec)
                    last_core = existing
                    continue

            merged.append(rec)
            if self._is_core_row(rec):
                last_core = rec

        return merged

    def _merge_into(self, base: ParseRecord, extra: ParseRecord) -> None:
        # Keep the most informative name while preventing OKPD2-only values.
        if extra.name and (not base.name or len(extra.name) > len(base.name) or _looks_like_okpd2_code(base.name)):
            if not _looks_like_okpd2_code(extra.name):
                base.name = extra.name

        for field in FIELD_ORDER:
            if field == "name":
                continue
            if not getattr(base, field) and getattr(extra, field):
                setattr(base, field, getattr(extra, field))

        # Price/sum can be mixed up in sparse rows. Keep stricter values if available in addon row.
        if extra.price_per_unit and _looks_like_price(extra.price_per_unit):
            base.price_per_unit = extra.price_per_unit
        if extra.sum_rub and _looks_like_sum(extra.sum_rub):
            base.sum_rub = _extract_sum(extra.sum_rub)

    def _record_key(self, rec: ParseRecord) -> str:
        key_id = _clean(rec.ru or rec.trade_name or rec.name)
        if not key_id:
            return ""
        return "|".join(
            [
                (_extract_okpd2(rec.okpd2) or _extract_okpd2(rec.name)).upper(),
                _short_country(rec.country).upper(),
                key_id.upper(),
            ]
        )

    def _is_core_row(self, rec: ParseRecord) -> bool:
        has_identity = bool(_clean(rec.trade_name) or _clean(rec.ru) or (_clean(rec.name) and not _looks_like_okpd2_code(rec.name)))
        has_top_cols = bool(_clean(rec.category_ls) or _clean(rec.okpd2) or _clean(rec.country))
        return has_identity or has_top_cols

    def _is_addon_row(self, rec: ParseRecord) -> bool:
        meta_fields = [
            rec.holder_name,
            rec.manufacturer_name,
            rec.manufacturer_country,
            rec.primary_package_type,
            rec.qty_forms_primary,
            rec.qty_primary_packages,
            rec.qty_consumer_units,
            rec.consumer_package_completeness,
        ]
        meta_count = sum(1 for v in meta_fields if _clean(v))
        weak_identity = not _clean(rec.trade_name) and not _looks_like_ru_code(rec.ru)
        return meta_count >= 2 and weak_identity

    def _split_compact_top_block(self, rec: ParseRecord, source_text: Optional[str] = None) -> None:
        src = source_text if source_text is not None else rec.country
        parts = [_clean(x) for x in str(src).split("|") if _clean(x)]
        if not parts:
            return

        if not rec.country:
            rec.country = _short_country(parts[0])
        for part in parts[1:]:
            up = part.upper()
            if "ТОВАР" == up:
                continue
            if "НДС" in up:
                if not rec.sum_rub:
                    rec.sum_rub = _extract_sum(part)
                continue
            if _extract_okpd2(part):
                if not rec.okpd2:
                    rec.okpd2 = _extract_okpd2(part)
                if not rec.category_ls:
                    rec.category_ls = _clean(re.sub(r"\(\d{2}\.\d{2}\.\d{2}\.\d{3}\)", "", part))
                continue
            if not rec.qty_need and _looks_like_qty_text(part):
                rec.qty_need = part
                continue
            if not rec.price_per_unit and _looks_like_price(part):
                rec.price_per_unit = _extract_price(part)
                continue
            if not rec.sum_rub and _looks_like_sum(part):
                rec.sum_rub = _extract_sum(part)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def _extract_okpd2(text: str) -> str:
    m = re.search(r"(\d{2}\.\d{2}\.\d{2}\.\d{3})", text or "")
    return m.group(1) if m else ""


def _looks_like_okpd2_code(text: str) -> bool:
    return bool(re.fullmatch(r"\d{2}\.\d{2}\.\d{2}\.\d{3}", _clean(text)))


def _extract_dose(text: str) -> str:
    src = text or ""
    unit = r"(?:МГ|МЛ|МКГ|ЕД|МЕ|Г)"
    # Complex doses: 5 мг+10 мг, 0.400 мг+0.270 мг+6 мг+3.2 мг/мл
    complex_pat = re.compile(
        rf"((?:\d+[\.,]?\d*\s*{unit}\s*\+\s*)+\d+[\.,]?\d*\s*{unit}(?:\s*/\s*(?:МЛ|Г|КГ|Л|МКГ|МГ|ЕД|МЕ))?)",
        flags=re.IGNORECASE,
    )
    complex_matches = [
        _clean(m.group(1))
        for m in complex_pat.finditer(src)
        if m and _clean(m.group(1))
    ]
    if complex_matches:
        return max(complex_matches, key=len)

    patterns = [
        r"(\d+[\.,]?\d*\s*(?:МГ|МЛ|МКГ|ЕД|МЕ|Г)\s*/\s*(?:МЛ|Г|КГ|Л|МКГ|МГ|ЕД|МЕ))",
        r"(\d+[\.,]?\d*\s*(?:МГ|МЛ|МКГ|ЕД|МЕ|Г))\b",
    ]
    for p in patterns:
        m = re.search(p, src, flags=re.IGNORECASE)
        if m:
            return _clean(m.group(1))
    return ""


def _extract_country(text: str) -> str:
    m = re.search(r"Страна происхождения\s*:\s*(.+)$", text or "", flags=re.IGNORECASE)
    return _clean(m.group(1)) if m else ""


def _short_country(text: str) -> str:
    src = _clean(text)
    if not src:
        return ""
    m = re.search(r"([A-Za-zА-Яа-яЁё\-\s]+\(\d{3}\))", src)
    return _clean(m.group(1)) if m else src


def _looks_like_price(text: str) -> bool:
    src = _clean(text)
    if not src or _looks_like_okpd2_code(src):
        return False
    if src.count(".") > 1:
        return False
    return bool(re.fullmatch(r"\d{1,6}[\.,]\d{2,7}", src))


def _looks_like_sum(text: str) -> bool:
    src = _clean(text)
    if "НДС" not in src.upper():
        return False
    return bool(re.search(r"\d{1,3}(?:\s\d{3})+,\d{2}|\d{4,},\d{2}", src))


def _extract_price(text: str) -> str:
    src = _clean(text)
    for m in re.finditer(r"\b\d{1,6}[\.,]\d{2,7}\b", src):
        val = _clean(m.group(0))
        if _looks_like_okpd2_code(val):
            continue
        after = src[m.end() : m.end() + 12].upper()
        before = src[max(0, m.start() - 2) : m.start()].upper()
        # Skip dosage fragments like "0.400 мг+" or "3.2 мг/мл".
        if re.match(r"\s*(МГ|МЛ|МКГ|ЕД|МЕ|Г|КГ)\b", after):
            continue
        if "/" in after[:4] or "+" in before:
            continue
        # Ignore fragments from OKPD2-like chains such as 21.20.10.141
        if re.search(r"\d+\.\d+\.\d+\.\d+", src):
            if f".{val}" in src or f"{val}." in src:
                continue
        return val
    return ""


def _extract_sum(text: str) -> str:
    src = _clean(text)
    if "НДС" not in src.upper():
        return ""
    m = re.search(r"(\d{1,3}(?:\s\d{3})+,\d{2}|\d{4,},\d{2})", src)
    return _clean(m.group(1)) if m else ""


def _looks_like_qty_text(text: str) -> bool:
    src = _clean(text)
    if not src:
        return False
    if re.search(r"\b(ШТУКА\s*\(ШТ\)|ГРАММ\s*\(Г\)|МИЛЛИГРАММ\s*\(МГ\)|КУБИЧЕСКИЙ\s+САНТИМЕТР[^|]*\(СМ\[?3\*?\][^)]*\)|МИЛЛИЛИТР\s*\(МЛ\)|ШТ\.?|СМ\[?3\*?\])\b", src, flags=re.IGNORECASE):
        return True
    return bool(re.search(r"\d[\d\s.,]*\s*(СМ3|МЛ|Л|Г|КГ|ШТ|ЕД|МЕ)", src, flags=re.IGNORECASE))


def _looks_like_ru_code(text: str) -> bool:
    src = _clean(text)
    if not src:
        return False
    return bool(
        re.search(r"ЛП[-№A-ZА-Я0-9()\-/]+", src, flags=re.IGNORECASE)
        or re.search(r"\b[РP]?\s*№?\s*N?\d{5,}/\d+\b", src, flags=re.IGNORECASE)
    )


def _extract_compact_values(text: str) -> dict[str, str]:
    src = _clean(text)
    out = {"qty_need": "", "price_per_unit": "", "sum_rub": ""}
    if not src:
        return out

    has_vat = "НДС" in src.upper()

    parts = [_clean(x) for x in src.split("|") if _clean(x)]
    for part in parts:
        up = part.upper()
        if not out["sum_rub"] and "НДС" in up:
            out["sum_rub"] = _extract_sum(part)
            continue
        if not out["qty_need"] and _looks_like_qty_text(part):
            if len(part) > 100 and re.search(r"\d+\.\s+", part):
                continue
            out["qty_need"] = part
            continue
        if not out["price_per_unit"] and _looks_like_price(part):
            out["price_per_unit"] = _extract_price(part)
            continue
        if has_vat and not out["sum_rub"] and _looks_like_sum(part):
            out["sum_rub"] = _extract_sum(part)

    if not out["qty_need"]:
        out["qty_need"] = _extract_qty_from_blob(src)
    if out["qty_need"] and len(out["qty_need"]) > 120:
        # Some pages leak full item description into qty cell; keep only unit text.
        trimmed_qty = _extract_qty_from_blob(out["qty_need"])
        out["qty_need"] = trimmed_qty if trimmed_qty and len(trimmed_qty) < len(out["qty_need"]) else ""

    # Global fallback for rows where compact values are merged without "|" delimiters.
    if has_vat and not out["sum_rub"]:
        sum_match = re.search(r"\b(\d{1,3}(?:\s\d{3})+,\d{2}|\d{4,},\d{2})\b", src)
        if sum_match:
            out["sum_rub"] = _clean(sum_match.group(1))

    if not out["price_per_unit"]:
        for m in re.finditer(r"\b\d{1,6}[\.,]\d{2,7}\b", src):
            val = _clean(m.group(0))
            if _looks_like_okpd2_code(val):
                continue
            after = src[m.end() : m.end() + 12].upper()
            if re.match(r"\s*(МГ|МЛ|МКГ|ЕД|МЕ|Г|КГ)\b", after):
                continue
            if "/" in after[:4]:
                continue
            if out["sum_rub"] and val == out["sum_rub"]:
                continue
            if re.search(r"\d+\.\d+\.\d+\.\d+", src) and (f".{val}" in src or f"{val}." in src):
                continue
            out["price_per_unit"] = val
            break

    # Last resort: infer from decimal sequence when source block is compact without separators.
    if not out["price_per_unit"] or (has_vat and not out["sum_rub"]):
        nums: list[str] = []
        for m in re.finditer(r"\b\d{1,6}[\.,]\d{2,7}\b", src):
            val = _clean(m.group(0))
            if _looks_like_okpd2_code(val):
                continue
            after = src[m.end() : m.end() + 12].upper()
            if re.match(r"\s*(МГ|МЛ|МКГ|ЕД|МЕ|Г|КГ)\b", after):
                continue
            if "/" in after[:4]:
                continue
            nums.append(val)
        if nums:
            if not out["price_per_unit"]:
                out["price_per_unit"] = nums[0]
            if has_vat and not out["sum_rub"] and len(nums) > 1:
                out["sum_rub"] = nums[-1]

    if not out["price_per_unit"]:
        out["price_per_unit"] = _extract_price(src)
    if has_vat and not out["sum_rub"]:
        out["sum_rub"] = _extract_sum(src)
    return out


def _extract_name_from_blob(text: str) -> str:
    src = _clean(text)
    if not src:
        return ""

    m = re.search(r"(\d+\.\s*[^|]+)", src, flags=re.IGNORECASE)
    if not m:
        return ""

    value = _clean(m.group(1))
    stop_markers = [
        "ЕДИНИЦА ИЗМЕРЕНИЯ ТОВАРА",
        "СТРАНА ПРОИСХОЖДЕНИЯ",
        "МНН И ФОРМА ВЫПУСКА",
        "ТОРГОВОЕ НАИМЕНОВАНИЕ",
    ]
    up = value.upper()
    for marker in stop_markers:
        idx = up.find(marker)
        if idx > 0:
            value = _clean(value[:idx])
            up = value.upper()
    return value


def _extract_qty_from_blob(text: str) -> str:
    src = _clean(text)
    if not src:
        return ""

    labeled = re.search(r"ЕДИНИЦА\s+ИЗМЕРЕНИЯ(?:\s+ТОВАРА)?\s*:\s*([^|]+)", src, flags=re.IGNORECASE)
    if labeled:
        value = _clean(labeled.group(1))
        value = re.split(
            r"СТРАНА\s+ПРОИСХОЖДЕНИЯ|ПРЕПАРАТЫ|ТОВАР\b|НАИМЕНОВАНИЕ\s+ДЕРЖАТЕЛЯ|НАИМЕНОВАНИЕ\s+ПРОИЗВОДИТЕЛЯ",
            value,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        return _clean(value)

    if "|" in src:
        for part in [_clean(x) for x in src.split("|") if _clean(x)]:
            if _looks_like_qty_text(part):
                return part

    unit_only = re.search(
        r"(ШТУКА\s*\(ШТ\)|КУБИЧЕСКИЙ\s+САНТИМЕТР[^|]*\(СМ\[?3\*?\][^)]*\)|ГРАММ\s*\(Г\)|МИЛЛИГРАММ\s*\(МГ\)|МИЛЛИЛИТР\s*\(МЛ\))",
        src,
        flags=re.IGNORECASE,
    )
    if unit_only:
        return _clean(unit_only.group(1))

    m = re.search(r"(\d[\d\s.,]*\s*(?:СМ3|МЛ|Л|Г|КГ|ШТ|ЕД|МЕ)[^|]*)", src, flags=re.IGNORECASE)
    return _clean(m.group(1)) if m else ""


def _looks_like_meta_blob(text: str) -> bool:
    src = _clean(text).upper()
    keys = [
        "НАИМЕНОВАНИЕ ДЕРЖАТЕЛЯ ИЛИ ВЛАДЕЛЬЦА РУ",
        "НАИМЕНОВАНИЕ ПРОИЗВОДИТЕЛЯ",
        "ВИД ПЕРВИЧНОЙ УПАКОВКИ",
        "КОМПЛЕКТНОСТЬ ПОТРЕБИТЕЛЬСКОЙ УПАКОВКИ",
    ]
    return any(k in src for k in keys)


def _extract_meta_fields(text: str) -> dict[str, str]:
    src = _clean(text).replace("|", " ")
    labels = {
        "release_form": "Лекарственная форма",
        "dose": "Дозировка",
        "holder_name": "Наименование держателя или владельца РУ",
        "manufacturer_name": "Наименование производителя",
        "manufacturer_country": "Страна производителя",
        "primary_package_type": "Вид первичной упаковки",
        "qty_forms_primary": "Количество лекарственных форм в первичной упаковке",
        "qty_primary_packages": "Количество первичных упаковок в потребительской упаковке",
        "qty_consumer_units": "Количество потребительских единиц в потребительской упаковке",
        "consumer_package_completeness": "Комплектность потребительской упаковки",
    }
    all_markers = sorted((re.escape(v) for v in labels.values()), key=len, reverse=True)
    any_marker = "|".join(all_markers)

    out: dict[str, str] = {}
    for field, label in labels.items():
        pattern = re.compile(
            rf"{re.escape(label)}\s*:?\s*(.+?)(?=(?:{any_marker})\s*:?|$)",
            flags=re.IGNORECASE,
        )
        m = pattern.search(src)
        if m:
            out[field] = _clean(m.group(1))
    return out


def _read_urls(single_url: Optional[str], url_file: Optional[Path]) -> list[str]:
    urls: list[str] = []
    if single_url:
        urls.append(single_url.strip())
    if url_file and url_file.exists():
        for line in url_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    if not urls:
        raise ValueError("Передайте --url или --url-file")
    return urls


def export_csv(rows: list[dict[str, str]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELD_ORDER)
        writer.writeheader()
        writer.writerows(rows)


def export_xlsx(rows: list[dict[str, str]], out_path: Path) -> bool:
    try:
        import pandas as pd
    except Exception:
        return False

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=FIELD_ORDER)
    df = df.rename(columns=EXPORT_HEADERS_RU)
    df.to_excel(out_path, index=False)
    return True


def _log_line(log_fn, text: str, *, is_error: bool = False) -> None:
    if log_fn:
        log_fn(text, is_error=is_error)
    else:
        stream = sys.stderr if is_error else sys.stdout
        print(text, file=stream)


async def run(args: argparse.Namespace, log_fn=None) -> int:
    parser = EISParser(timeout_ms=args.timeout_ms, expand_rounds=args.expand_rounds)
    archive_dir = Path(args.archive_dir)
    urls = _read_urls(args.url, Path(args.url_file) if args.url_file else None)

    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=not args.headed)
        context: BrowserContext = await browser.new_context(locale="ru-RU")
        if args.trace:
            await context.tracing.start(screenshots=True, snapshots=True, sources=True)

        all_rows: list[dict[str, str]] = []
        for idx, url in enumerate(urls, start=1):
            page = await context.new_page()
            try:
                _log_line(log_fn, f"[{idx}/{len(urls)}] Parse: {url}")
                rows = await parser.parse_url(page, url, archive_dir=archive_dir, save_trace=args.trace)
                all_rows.extend(rows)
                _log_line(log_fn, f"  -> rows: {len(rows)}")
            except Exception as exc:
                fail_dir = archive_dir / "failures"
                fail_dir.mkdir(parents=True, exist_ok=True)
                safe_name = re.sub(r"[^\w\-]+", "_", url)[:120]
                await page.screenshot(path=str(fail_dir / f"{safe_name}.png"), full_page=True)
                (fail_dir / f"{safe_name}.txt").write_text(str(exc), encoding="utf-8")
                _log_line(log_fn, f"  -> error: {exc}", is_error=True)
            finally:
                await page.close()

        if args.trace:
            trace_name = archive_dir / f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            await context.tracing.stop(path=str(trace_name))
            _log_line(log_fn, f"Trace: {trace_name}")

        await context.close()
        await browser.close()

    if not all_rows:
        _log_line(log_fn, "Нет данных для экспорта", is_error=True)
        return 2

    csv_out = Path(args.out_csv)
    export_csv(all_rows, csv_out)
    _log_line(log_fn, f"CSV saved: {csv_out}")

    if args.out_xlsx:
        ok = export_xlsx(all_rows, Path(args.out_xlsx))
        if ok:
            _log_line(log_fn, f"XLSX saved: {args.out_xlsx}")
        else:
            _log_line(log_fn, "XLSX skipped: установите pandas и openpyxl", is_error=True)

    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="EIS parser: Объекты закупки")
    p.add_argument("--gui", action="store_true", help="Запуск в графическом интерфейсе")
    p.add_argument("--url", help="Single EIS URL")
    p.add_argument("--url-file", help="Path to file with one URL per line")
    p.add_argument("--archive-dir", default="archive", help="Debug archive directory")
    p.add_argument("--out-csv", default="export/result.csv", help="Output CSV path")
    p.add_argument("--out-xlsx", default="export/result.xlsx", help="Output XLSX path")
    p.add_argument("--headed", action="store_true", help="Run browser in headed mode")
    p.add_argument("--trace", action="store_true", help="Save Playwright trace.zip")
    p.add_argument("--timeout-ms", type=int, default=60000, help="Navigation timeout")
    p.add_argument("--expand-rounds", type=int, default=4, help="Expand passes for nested rows")
    return p


class EISParserGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("EIS Parser - Единый интерфейс")
        self.geometry("1380x800")
        self.minsize(1120, 640)

        self.url_var = tk.StringVar(
            value=(
                "https://zakupki.gov.ru/epz/contract/contractCard/payment-info-and-target-of-order.html"
                "?reestrNumber=2312813818126000251&contractInfoId=108730614"
            )
        )
        self.search_var = tk.StringVar(value="")
        self.archive_var = tk.StringVar(value="archive")
        self.csv_var = tk.StringVar(value="export/result.csv")
        self.xlsx_var = tk.StringVar(value="export/result.xlsx")
        self.trace_var = tk.BooleanVar(value=True)
        self.headed_var = tk.BooleanVar(value=False)

        self.all_rows: list[dict[str, str]] = []
        self.filtered_rows: list[dict[str, str]] = []
        self._worker_thread: Optional[threading.Thread] = None

        self._build_ui()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=10)
        root.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(
            root,
            text="Запуск парсинга ЕИС в одном окне",
            font=("Segoe UI", 13, "bold"),
        )
        title.pack(anchor="w", pady=(0, 8))

        controls = ttk.LabelFrame(root, text="Параметры", padding=8)
        controls.pack(fill=tk.X)

        self._row_input(controls, "Ссылка ЕИС", self.url_var, add_paste_button=True)
        self._row_input(controls, "Слово для фильтра (опц.)", self.search_var, on_change=self._apply_filter)
        self._row_input(controls, "Папка архива", self.archive_var)
        self._row_input(controls, "CSV файл", self.csv_var)
        self._row_input(controls, "XLSX файл", self.xlsx_var)

        toggles = ttk.Frame(controls)
        toggles.pack(fill=tk.X, pady=(4, 0))
        ttk.Checkbutton(toggles, text="Сохранять trace", variable=self.trace_var).pack(side=tk.LEFT)
        ttk.Checkbutton(
            toggles,
            text="Показывать окно браузера (headed)",
            variable=self.headed_var,
        ).pack(side=tk.LEFT, padx=(14, 0))

        actions = ttk.Frame(root)
        actions.pack(fill=tk.X, pady=(8, 8))
        self.run_btn = ttk.Button(actions, text="Запустить парсинг", command=self._start_parse)
        self.run_btn.pack(side=tk.LEFT)
        ttk.Button(actions, text="Открыть CSV", command=self._open_csv_file).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="Выгрузить Excel", command=self._export_excel_file).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="Очистить таблицу", command=self._clear_rows).pack(side=tk.LEFT, padx=(8, 0))

        self.status_var = tk.StringVar(value="Готово")
        ttk.Label(root, textvariable=self.status_var, foreground="#1f4e79").pack(anchor="w", pady=(0, 6))

        content = ttk.Panedwindow(root, orient=tk.VERTICAL)
        content.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(content)
        bottom = ttk.Frame(content)
        content.add(top, weight=4)
        content.add(bottom, weight=2)

        columns = tuple(FIELD_ORDER)
        self.tree = ttk.Treeview(top, columns=columns, show="headings", height=18)
        for field in FIELD_ORDER:
            self.tree.heading(field, text=EXPORT_HEADERS_RU[field])
            self.tree.column(field, width=150 if field != "name" else 270, anchor="w")

        sy = ttk.Scrollbar(top, orient=tk.VERTICAL, command=self.tree.yview)
        sx = ttk.Scrollbar(top, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sy.pack(side=tk.RIGHT, fill=tk.Y)
        sx.pack(side=tk.BOTTOM, fill=tk.X)

        ttk.Label(bottom, text="Лог выполнения").pack(anchor="w")
        self.log_text = tk.Text(bottom, height=9, wrap="word")
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _row_input(self, parent, label, variable, on_change=None, add_paste_button: bool = False) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text=label, width=22).pack(side=tk.LEFT)
        ent = ttk.Entry(row, textvariable=variable)
        ent.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._add_context_menu(ent)
        ent.bind("<FocusIn>", lambda _e: ent.selection_range(0, tk.END))
        if add_paste_button:
            ttk.Button(
                row,
                text="Вставить",
                command=lambda: self._paste_from_clipboard(variable),
            ).pack(side=tk.LEFT, padx=(6, 0))
        if on_change:
            ent.bind("<KeyRelease>", lambda _e: on_change())

    def _add_context_menu(self, widget: ttk.Entry) -> None:
        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(label="Копировать", command=lambda: widget.event_generate("<<Copy>>"))
        menu.add_command(label="Вырезать", command=lambda: widget.event_generate("<<Cut>>"))
        menu.add_command(label="Вставить", command=lambda: widget.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Выделить все", command=lambda: widget.selection_range(0, tk.END))

        def show_menu(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        widget.bind("<Button-3>", show_menu)
        widget.bind("<Control-Button-1>", show_menu)

    def _paste_from_clipboard(self, variable: tk.StringVar) -> None:
        try:
            text = self.clipboard_get().strip()
        except tk.TclError:
            messagebox.showwarning("Внимание", "Буфер обмена пуст или недоступен")
            return
        variable.set(text)

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)
        self.update_idletasks()

    def _append_log(self, text: str, is_error: bool = False) -> None:
        prefix = "[ERR] " if is_error else ""
        self.log_text.insert("end", f"{prefix}{text}\n")
        self.log_text.see("end")

    def _thread_log(self, text: str, is_error: bool = False) -> None:
        self.after(0, lambda: self._append_log(text, is_error=is_error))

    def _start_parse(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            messagebox.showinfo("Информация", "Парсинг уже выполняется")
            return

        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Внимание", "Укажите ссылку ЕИС")
            return

        self.run_btn.config(state=tk.DISABLED)
        self._set_status("Запуск парсинга...")
        self._append_log("Запуск...")

        config = {
            "url": url,
            "archive_dir": self.archive_var.get().strip() or "archive",
            "out_csv": self.csv_var.get().strip() or "export/result.csv",
            "out_xlsx": self.xlsx_var.get().strip() or "",
            "headed": self.headed_var.get(),
            "trace": self.trace_var.get(),
        }

        self._worker_thread = threading.Thread(target=self._worker, args=(config,), daemon=True)
        self._worker_thread.start()

    def _worker(self, config: dict) -> None:
        ns = argparse.Namespace(
            gui=False,
            url=config["url"],
            url_file=None,
            archive_dir=config["archive_dir"],
            out_csv=config["out_csv"],
            out_xlsx=config["out_xlsx"],
            headed=config["headed"],
            trace=config["trace"],
            timeout_ms=90000,
            expand_rounds=5,
        )
        try:
            rc = asyncio.run(run(ns, log_fn=self._thread_log))
        except Exception as exc:
            self.after(0, lambda: self._append_log(f"Критическая ошибка: {exc}", is_error=True))
            rc = 1

        self.after(0, lambda: self._on_worker_done(rc, Path(ns.out_csv)))

    def _on_worker_done(self, rc: int, csv_path: Path) -> None:
        self.run_btn.config(state=tk.NORMAL)
        if rc == 0 and csv_path.exists():
            self._load_rows_from_csv(csv_path)
            # Always show parse result first. Search is only optional client-side filtering.
            self.filtered_rows = list(self.all_rows)
            self._render_rows()
            self._set_status(f"Готово. Строк: {len(self.all_rows)}")
        else:
            self._set_status("Завершено с ошибкой")

    def _load_rows_from_csv(self, csv_path: Path) -> None:
        rows: list[dict[str, str]] = []
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for item in reader:
                rows.append({k: _clean(item.get(k, "")) for k in FIELD_ORDER})
        self.all_rows = rows

    def _apply_filter(self) -> None:
        query = self.search_var.get().strip().lower()
        if not query:
            self.filtered_rows = list(self.all_rows)
        else:
            self.filtered_rows = [
                r for r in self.all_rows if any(query in str(v).lower() for v in r.values())
            ]
        self._render_rows()

    def _render_rows(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        for r in self.filtered_rows:
            self.tree.insert("", "end", values=[r.get(field, "") for field in FIELD_ORDER])

    def _clear_rows(self) -> None:
        self.all_rows = []
        self.filtered_rows = []
        self._render_rows()
        self._set_status("Очищено")

    def _open_csv_file(self) -> None:
        path = Path(self.csv_var.get().strip() or "export/result.csv")
        if not path.exists():
            messagebox.showwarning("Внимание", "CSV файл еще не создан")
            return
        try:
            import os

            os.startfile(path.resolve())  # type: ignore[attr-defined]
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось открыть CSV: {exc}")

    def _export_excel_file(self) -> None:
        rows = self.filtered_rows if self.filtered_rows else self.all_rows
        if not rows:
            messagebox.showwarning("Внимание", "Нет данных для выгрузки в Excel")
            return

        out_path = Path(self.xlsx_var.get().strip() or "export/result.xlsx")
        ok = export_xlsx(rows, out_path)
        if not ok:
            messagebox.showerror(
                "Ошибка",
                "Не удалось выгрузить Excel. Установите pandas и openpyxl:\n"
                "pip install pandas openpyxl",
            )
            return

        self._append_log(f"XLSX saved: {out_path}")
        self._set_status(f"Excel выгружен: {out_path}")
        messagebox.showinfo("Готово", f"Excel файл сохранен:\n{out_path}")


def launch_gui() -> int:
    app = EISParserGUI()
    app.mainloop()
    return 0


def main() -> int:
    args = build_arg_parser().parse_args()
    if args.gui:
        return launch_gui()
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("Interrupted by user", file=sys.stderr)
        return 130


EXTRACT_SCRIPT = r"""
() => {
  const clean = (s) => (s || '').replace(/\u00A0/g, ' ').replace(/\s+/g, ' ').trim();
  const text = (node) => clean((node?.innerText || node?.textContent || ''));

  const rx = {
    okpd2: /(\d{2}\.\d{2}\.\d{2}\.\d{3})/,
    ru: /(ЛП[-№\w()\/]+|\b[РP]?\s*№?\s*N?\d{5,}\/\d+\b)/i,
    dose: /((?:\d+[\.,]?\d*\s*(?:МГ|МЛ|МКГ|ЕД|МЕ|Г)\s*\+\s*)+\d+[\.,]?\d*\s*(?:МГ|МЛ|МКГ|ЕД|МЕ|Г)(?:\s*\/\s*(?:МЛ|Г|КГ|Л|МКГ|МГ|ЕД|МЕ))?|\d+[\.,]?\d*\s*(?:МГ|МЛ|МКГ|ЕД|МЕ|Г)\s*\/\s*(?:МЛ|Г|КГ|Л|МКГ|МГ|ЕД|МЕ)|\d+[\.,]?\d*\s*(?:МГ|МЛ|МКГ|ЕД|МЕ|Г))/i,
    countryShort: /([A-Za-zА-Яа-яЁё\-\s]+\(\d{3}\))/,
    sum: /(\d{1,3}(?:\s\d{3})+,\d{2}|\d+,\d{2})/
  };

  const blank = () => ({
    name: '',
    category_ls: '',
    okpd2: '',
    country: '',
    trade_name: '',
    ru: '',
    release_form: '',
    dose: '',
    qty_need: '',
    price_per_unit: '',
    sum_rub: '',
    holder_name: '',
    manufacturer_name: '',
    manufacturer_country: '',
    primary_package_type: '',
    qty_forms_primary: '',
    qty_primary_packages: '',
    qty_consumer_units: '',
    consumer_package_completeness: '',
  });

  const looksLikePrice = (s) => /^\d{1,6}[.,]\d{2,7}$/.test(clean(s));
  const looksLikeSumRub = (s) => /^\d{1,3}(\s\d{3})+,\d{2}$/.test(clean(s)) || /^\d{4,},\d{2}$/.test(clean(s));
  const looksLikeQty = (s) => {
    const src = clean(s);
    return /\d[\d\s.,]*\s*(СМ3|МЛ|Л|Г|КГ|ШТ|ЕД|МЕ)/i.test(src)
      || /(Штука\s*\(шт\)|Кубический\s+сантиметр[^|]*\(см\[?3\*?\][^)]*\)|Миллилитр\s*\(мл\)|Грамм\s*\(г\)|Миллиграмм\s*\(мг\))/i.test(src);
  };

  const shortCountry = (s) => {
    const src = clean(s);
    const m = src.match(rx.countryShort);
    return clean(m ? m[1] : src);
  };

  const extractSum = (s) => clean((clean(s).match(rx.sum) || [])[1] || '');

  const extractPrice = (srcText) => {
    const src = clean(srcText);
    if (!src) return '';
    const candidates = src.match(/\d{1,6}[.,]\d{2,7}/g) || [];
    for (const c of candidates) {
      const val = clean(c);
      if (!val) continue;
      if (/^\d{2}\.\d{2}\.\d{2}\.\d{3}$/.test(val)) continue;
      const idx = src.indexOf(val);
      const after = idx >= 0 ? src.slice(idx + val.length, idx + val.length + 12).toUpperCase() : '';
      if (/^\s*(МГ|МЛ|МКГ|ЕД|МЕ|Г|КГ)\b/.test(after)) continue;
      if (after.slice(0, 4).includes('/')) continue;
      if (/\d+\.\d+\.\d+\.\d+/.test(src) && (src.includes(`.${val}`) || src.includes(`${val}.`))) {
        continue;
      }
      return val;
    }
    return '';
  };

  const extractQty = (srcText) => {
    const src = clean(srcText);
    if (!src) return '';
    const labeled = src.match(/ЕДИНИЦА\s+ИЗМЕРЕНИЯ(?:\s+ТОВАРА)?\s*:\s*([^|]+)/i);
    if (labeled) {
      return clean(labeled[1].split(/СТРАНА\s+ПРОИСХОЖДЕНИЯ/i)[0]);
    }
    const unitOnly = src.match(/(Штука\s*\(шт\)|Кубический\s+сантиметр[^|]*\(см\[?3\*?\][^)]*\)|Миллилитр\s*\(мл\)|Грамм\s*\(г\)|Миллиграмм\s*\(мг\))/i);
    if (unitOnly) return clean(unitOnly[1]);
    const m = src.match(/\d[\d\s.,]*\s*(СМ3|МЛ|Л|Г|КГ|ШТ|ЕД|МЕ)(?:\s*\([^)]*\))?/i);
    return m ? clean(m[0]) : '';
  };

  const extractName = (srcText) => {
    const src = clean(srcText);
    if (!src) return '';
    // Match pattern like "1. DRUG NAME" - the number followed by dot and space, then the name
    const m = src.match(/^\s*(\d+\.)\s*([А-Яа-я0-9\s\-\+\(\),]+)/);
    if (!m) return '';
    let value = clean(m[2]);
    // Remove country info if present (stop at first occurrence of 'Страна')
    const countryIdx = value.toUpperCase().indexOf('СТРАНА');
    if (countryIdx > 0) {
      value = value.slice(0, countryIdx);
    }
    return clean(value);
  };

  const metaMap = [
    ['release_form', 'Лекарственная форма'],
    ['dose', 'Дозировка'],
    ['holder_name', 'Наименование держателя или владельца РУ'],
    ['manufacturer_name', 'Наименование производителя'],
    ['manufacturer_country', 'Страна производителя'],
    ['primary_package_type', 'Вид первичной упаковки'],
    ['qty_forms_primary', 'Количество лекарственных форм в первичной упаковке'],
    ['qty_primary_packages', 'Количество первичных упаковок в потребительской упаковке'],
    ['qty_consumer_units', 'Количество потребительских единиц в потребительской упаковке'],
    ['consumer_package_completeness', 'Комплектность потребительской упаковки'],
  ];

  const extractMetaFromText = (srcText) => {
    const src = clean(srcText).replace(/\|/g, ' ');
    const points = [];
    for (const [key, label] of metaMap) {
      const token = `${label}:`;
      const idx = src.toUpperCase().indexOf(token.toUpperCase());
      if (idx >= 0) points.push({ key, label, idx, end: idx + token.length });
    }
    points.sort((a, b) => a.idx - b.idx);
    const out = {};
    for (let i = 0; i < points.length; i++) {
      const cur = points[i];
      const nextIdx = i + 1 < points.length ? points[i + 1].idx : src.length;
      out[cur.key] = clean(src.slice(cur.end, nextIdx));
    }
    return out;
  };

  const section = Array.from(document.querySelectorAll('section,div,table')).find((el) =>
    /Объекты закупки/i.test(text(el))
  ) || document.body;

  const isTopRow = (tr) => {
    // Check if row starts with a number pattern like "1." or "2."
    if (!/^\s*\d+\.\s+/.test(text(tr))) return false;
    const tds = tr.querySelectorAll('td');
    // Top rows have 7+ cells OR contain qty/price/sum columns
    if (tds.length >= 7) return true;
    // Also check if it contains quantity-like data in expected column positions
    const cellTexts = Array.from(tds).map(td => text(td));
    if (cellTexts.length >= 5) {
      // Check if any cell looks like quantity with unit
      for (const c of cellTexts) {
        if (looksLikeQty(c)) return true;
      }
    }
    return false;
  };
  const topRows = Array.from(section.querySelectorAll('tr')).filter((tr) => {
    return isTopRow(tr);
  });

  const parseTopRow = (tr) => {
    const rec = blank();
    const cols = Array.from(tr.querySelectorAll('td')).map((td) => text(td));
    const rowText = text(tr);
    rec.name = cols.map(extractName).find(Boolean) || extractName(rowText) || clean(cols[0] || '');

    // Direct column mapping for quantity, price, and sum when we have enough columns
    // Typical structure: [empty, name+country, category+okpd2, "Товар", qty, price, sum+VAT]
    // OR for rows with 9 cells: [empty, name, empty, trade, ru, form, dose, qty, meta]
    if (cols.length >= 7) {
      // Try standard 7-column layout first
      let foundQty = false;
      
      // Column 4 (index 4) typically contains quantity with unit
      const qtyCell = clean(cols[4] || '');
      if (qtyCell && looksLikeQty(qtyCell)) {
        rec.qty_need = extractQty(qtyCell) || qtyCell;
        foundQty = true;
      }
      
      // Column 5 (index 5) typically contains price per unit
      const priceCell = clean(cols[5] || '');
      if (priceCell && looksLikePrice(priceCell)) {
        rec.price_per_unit = priceCell;
      }
      
      // Column 6 (index 6) typically contains sum with VAT info
      const sumCell = clean(cols[6] || '');
      if (sumCell && /НДС/i.test(sumCell)) {
        rec.sum_rub = extractSum(sumCell);
      }
      
      // For 9-column layouts, check alternative positions
      if (!foundQty && cols.length >= 9) {
        // In some layouts, qty might be in a different position
        for (let i = 4; i < cols.length; i++) {
          const cell = clean(cols[i] || '');
          if (!rec.qty_need && looksLikeQty(cell)) {
            rec.qty_need = extractQty(cell) || cell;
          }
          if (!rec.price_per_unit && looksLikePrice(cell)) {
            rec.price_per_unit = cell;
          }
        }
      }
    }

    const tokens = [];
    cols.forEach((c) => {
      const cc = clean(c);
      if (!cc) return;
      tokens.push(cc);
      cc.split('|').map(clean).filter(Boolean).forEach((x) => tokens.push(x));
    });

    for (const token of tokens) {
      const up = token.toUpperCase();
      const countryLabel = token.match(/Страна происхождения\s*:\s*([^|]+)/i);
      if (!rec.country && countryLabel) {
        rec.country = shortCountry(countryLabel[1]);
      }
      if (!rec.country && /\(\d{3}\)/.test(token)) {
        rec.country = shortCountry(token);
      }
      if (!rec.okpd2 && rx.okpd2.test(token)) {
        rec.okpd2 = clean((token.match(rx.okpd2) || [])[1] || '');
        rec.category_ls = clean(token.replace(rx.okpd2, '').replace(/[()]/g, ''));
      }
      if (up === 'ТОВАР') continue;
      if (up.includes('НДС')) {
        if (!rec.sum_rub) rec.sum_rub = extractSum(token);
        continue;
      }
      if (!rec.qty_need && looksLikeQty(token)) {
        rec.qty_need = extractQty(token) || clean(token);
      }
      if (!rec.price_per_unit && (looksLikePrice(token) || /\d{1,6}[.,]\d{2,7}/.test(token))) {
        rec.price_per_unit = extractPrice(token);
      }
      // Sum is exported only when VAT label is explicitly present.
    }

    if (!rec.qty_need) rec.qty_need = extractQty(rowText);
    if (!rec.price_per_unit) rec.price_per_unit = extractPrice(rowText);
    if (!rec.sum_rub && /НДС/i.test(rowText)) rec.sum_rub = extractSum(rowText);

    if (!rec.category_ls) {
      const c2 = clean(cols[1] || '');
      rec.okpd2 = rec.okpd2 || clean((c2.match(rx.okpd2) || [])[1] || '');
      rec.category_ls = clean(c2.replace(rx.okpd2, '').replace(/[()]/g, ''));
    }
    return rec;
  };

  const parseNestedTable = (table) => {
    const rows = Array.from(table.querySelectorAll('tr'));
    const hMap = {};
    let headerFound = false;

    for (const tr of rows) {
      const cells = Array.from(tr.querySelectorAll('th,td'));
      if (!cells.length) continue;
      const headers = cells.map((x) => text(x).toUpperCase());
      const headerLine = headers.join(' | ');
      if (!/ТОРГОВОЕ НАИМЕНОВАНИЕ/.test(headerLine) || !/НОМЕР РУ/.test(headerLine)) continue;
      
      // Find column indices by matching header text explicitly
      for (let i = 0; i < headers.length; i++) {
        const h = headers[i];
        // Match exact header names to avoid confusion with similar labels
        if (/ТОРГОВОЕ\s+НАИМЕНОВАНИЕ/.test(h)) hMap.trade = i;
        if (/НОМЕР\s+РУ/.test(h)) hMap.ru = i;
        if (/ЛЕКАРСТВЕННАЯ\s+ФОРМА/.test(h)) hMap.form = i;
        if (/ДОЗИРОВКА/.test(h)) hMap.dose = i;
      }
      headerFound = true;
      break;
    }

    if (!headerFound) return [];

    const details = [];
    for (const tr of rows) {
      const cols = Array.from(tr.querySelectorAll('td')).map((td) => text(td));
      if (!cols.length) continue;
      const rowText = clean(text(tr));
      const rowUp = rowText.toUpperCase();
      if (rowUp.includes('ТОРГОВОЕ НАИМЕНОВАНИЕ') || rowUp.includes('НОМЕР РУ')) continue;

      const rec = blank();
      
      // Use mapped indices with fallbacks based on typical nested table structure:
      // [chevron(empty), trade_name, ru, form, dose, qty]
      const tradeRaw = hMap.trade !== undefined ? cols[hMap.trade] : (cols[1] || '');
      const ruRaw = hMap.ru !== undefined ? cols[hMap.ru] : (cols[2] || '');
      const formRaw = hMap.form !== undefined ? cols[hMap.form] : (cols[3] || '');
      const doseRaw = hMap.dose !== undefined ? cols[hMap.dose] : (cols[4] || '');

      // Skip cells that contain meta blob (МНН и форма выпуска в соответствии с ГРЛС...)
      rec.trade_name = /МНН\s*:/i.test(tradeRaw) ? '' : clean(tradeRaw);
      rec.ru = clean((clean(ruRaw).match(rx.ru) || [])[1] || ruRaw || '');
      rec.release_form = clean(formRaw);
      rec.dose = clean((clean(doseRaw).match(rx.dose) || [])[1] || doseRaw || '');

      // Extract meta fields from the row text (including from cells with long meta blobs)
      const meta = extractMetaFromText(rowText);
      Object.keys(meta).forEach((k) => {
        if (!rec[k]) rec[k] = clean(meta[k]);
      });

      if (Object.values(rec).some(Boolean)) details.push(rec);
    }
    return details;
  };

  const nestedTables = Array.from(section.querySelectorAll('table')).filter((t) => {
    const tText = text(t).toUpperCase();
    return tText.includes('ТОРГОВОЕ НАИМЕНОВАНИЕ') && tText.includes('НОМЕР РУ');
  });

  const topRecords = topRows.map(parseTopRow);
  const detailsByIndex = nestedTables.map(parseNestedTable);
  const out = [];

  for (let i = 0; i < topRecords.length; i++) {
    const top = topRecords[i];
    const details = detailsByIndex[i] || [];
    if (!details.length) {
      out.push(top);
      continue;
    }

    for (const d of details) {
      const rec = {
        ...top,
        trade_name: clean(d.trade_name || top.trade_name),
        ru: clean(d.ru || top.ru),
        release_form: clean(d.release_form || top.release_form),
        dose: clean(d.dose || top.dose),
        holder_name: clean(d.holder_name || top.holder_name),
        manufacturer_name: clean(d.manufacturer_name || top.manufacturer_name),
        manufacturer_country: clean(d.manufacturer_country || top.manufacturer_country),
        primary_package_type: clean(d.primary_package_type || top.primary_package_type),
        qty_forms_primary: clean(d.qty_forms_primary || top.qty_forms_primary),
        qty_primary_packages: clean(d.qty_primary_packages || top.qty_primary_packages),
        qty_consumer_units: clean(d.qty_consumer_units || top.qty_consumer_units),
        consumer_package_completeness: clean(d.consumer_package_completeness || top.consumer_package_completeness),
      };
      out.push(rec);
    }
  }

  const uniq = [];
  const seen = new Set();
  for (const rec of out) {
    const key = [
      rec.name,
      rec.category_ls,
      rec.okpd2,
      rec.country,
      rec.trade_name,
      rec.ru,
      rec.release_form,
      rec.dose,
      rec.qty_need,
      rec.price_per_unit,
      rec.sum_rub,
      rec.holder_name,
      rec.manufacturer_name,
      rec.manufacturer_country,
      rec.primary_package_type,
      rec.qty_forms_primary,
      rec.qty_primary_packages,
      rec.qty_consumer_units,
      rec.consumer_package_completeness,
    ].join('|');
    if (seen.has(key)) continue;
    seen.add(key);
    uniq.push(rec);
  }

  return uniq;
}
"""


if __name__ == "__main__":
    raise SystemExit(main())