#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EIS Contract Parser - Production version for CLI usage.
Parses "Объекты закупки" section from zakupki.gov.ru contract pages.

Usage:
    python eis_parser.py --url "https://..."
    python eis_parser.py --url-file urls.txt
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

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
    def __init__(self, timeout_ms: int = 90000, expand_rounds: int = 5) -> None:
        self.timeout_ms = timeout_ms
        self.expand_rounds = expand_rounds

    async def parse_url(
        self,
        page: Page,
        url: str,
        archive_dir: Optional[Path] = None,
    ) -> list[dict[str, str]]:
        await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        await page.wait_for_timeout(2000)

        await self._close_overlays(page)
        frame = await self._find_frame_with_objects(page)
        if frame is None:
            raise RuntimeError("Не найден контекст с блоком 'Объекты закупки'")

        await self._expand_objects(frame)
        await page.wait_for_timeout(1000)

        payload = await frame.evaluate(EXTRACT_SCRIPT)
        records = [self._normalize_record(item) for item in payload or []]
        rows = [r.as_row() for r in records]

        if archive_dir:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            job_dir = archive_dir / f"job_{ts}"
            parsed_dir = job_dir / "parsed"
            parsed_dir.mkdir(parents=True, exist_ok=True)
            (parsed_dir / "rows.json").write_text(
                json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
            )

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
            for i in range(min(cnt, 150)):
                item = toggles.nth(i)
                try:
                    await item.scroll_into_view_if_needed(timeout=1200)
                    await item.click(timeout=1200)
                    clicked += 1
                except Error:
                    continue

            if clicked == 0:
                break
            await frame.page.wait_for_timeout(600)

    def _normalize_record(self, raw: dict) -> ParseRecord:
        rec = ParseRecord(**{k: _clean(raw.get(k, "")) for k in FIELD_ORDER})

        # Fix OKPD2 in name field
        if _looks_like_okpd2_code(rec.name):
            rec.name = ""

        # Extract OKPD2 from category if missing
        if not rec.okpd2:
            rec.okpd2 = _extract_okpd2(rec.category_ls) or _extract_okpd2(rec.name)

        # Clean up category if it's just OKPD2 wrapper
        if rec.okpd2 and rec.category_ls and f"({rec.okpd2})" in rec.category_ls:
            rec.category_ls = _clean(re.sub(rf"\({re.escape(rec.okpd2)}\)", "", rec.category_ls))

        # Shorten country format
        if rec.country:
            rec.country = _short_country(rec.country)

        # Validate price and sum
        if rec.price_per_unit and not _looks_like_price(rec.price_per_unit):
            rec.price_per_unit = ""
        if rec.sum_rub and not _looks_like_sum(rec.sum_rub):
            rec.sum_rub = ""

        # Build name from components if missing
        if not rec.name and rec.trade_name:
            chunks = [rec.trade_name, rec.release_form, rec.dose]
            rec.name = _clean(", ".join([c for c in chunks if c]))

        return rec


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def _extract_okpd2(text: str) -> str:
    m = re.search(r"(\d{2}\.\d{2}\.\d{2}\.\d{3})", text or "")
    return m.group(1) if m else ""


def _looks_like_okpd2_code(text: str) -> bool:
    return bool(re.fullmatch(r"\d{2}\.\d{2}\.\d{2}\.\d{3}", _clean(text)))


def _looks_like_price(text: str) -> bool:
    src = _clean(text)
    if not src or _looks_like_okpd2_code(src):
        return False
    if src.count(".") > 1:
        return False
    return bool(re.fullmatch(r"\d{1,6}[.,]\d{2,7}", src))


def _looks_like_sum(text: str) -> bool:
    src = _clean(text)
    return bool(re.search(r"\d{1,3}(?:\s\d{3})+,\d{2}|\d{4,},\d{2}", src)) and "НДС" in src.upper()


def _short_country(text: str) -> str:
    src = _clean(text)
    if not src:
        return ""
    m = re.search(r"([A-Za-zА-Яа-яЁё\-\s]+\(\d{3}\))", src)
    return _clean(m.group(1)) if m else src


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


async def run(args: argparse.Namespace) -> int:
    parser = EISParser(timeout_ms=args.timeout_ms, expand_rounds=args.expand_rounds)
    archive_dir = Path(args.archive_dir) if args.archive_dir else None
    urls = _read_urls(args.url, Path(args.url_file) if args.url_file else None)

    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=not args.headed)
        context: BrowserContext = await browser.new_context(locale="ru-RU")

        all_rows: list[dict[str, str]] = []
        for idx, url in enumerate(urls, start=1):
            page = await context.new_page()
            try:
                print(f"[{idx}/{len(urls)}] Parse: {url}")
                rows = await parser.parse_url(page, url, archive_dir=archive_dir)
                all_rows.extend(rows)
                print(f"  -> rows: {len(rows)}")
            except Exception as exc:
                print(f"  -> error: {exc}", file=sys.stderr)
                if archive_dir:
                    fail_dir = archive_dir / "failures"
                    fail_dir.mkdir(parents=True, exist_ok=True)
                    safe_name = re.sub(r"[^\w\-]+", "_", url)[:120]
                    await page.screenshot(path=str(fail_dir / f"{safe_name}.png"), full_page=True)
                    (fail_dir / f"{safe_name}.txt").write_text(str(exc), encoding="utf-8")
            finally:
                await page.close()

        await context.close()
        await browser.close()

    if not all_rows:
        print("Нет данных для экспорта", file=sys.stderr)
        return 2

    csv_out = Path(args.out_csv)
    export_csv(all_rows, csv_out)
    print(f"CSV saved: {csv_out}")

    if args.out_xlsx:
        ok = export_xlsx(all_rows, Path(args.out_xlsx))
        if ok:
            print(f"XLSX saved: {args.out_xlsx}")
        else:
            print("XLSX skipped: установите pandas и openpyxl", file=sys.stderr)

    return 0


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


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="EIS parser: Объекты закупки")
    p.add_argument("--url", help="Single EIS URL")
    p.add_argument("--url-file", help="Path to file with one URL per line")
    p.add_argument("--archive-dir", help="Debug archive directory (optional)")
    p.add_argument("--out-csv", default="export/result.csv", help="Output CSV path")
    p.add_argument("--out-xlsx", help="Output XLSX path (optional)")
    p.add_argument("--headed", action="store_true", help="Run browser in headed mode")
    p.add_argument("--timeout-ms", type=int, default=90000, help="Navigation timeout")
    p.add_argument("--expand-rounds", type=int, default=5, help="Expand passes for nested rows")
    return p


def main() -> int:
    args = build_arg_parser().parse_args()
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
    dose: /((?:\d+[\\.,]?\d*\s*(?:МГ|МЛ|МКГ|ЕД|МЕ|Г)\s*\+\s*)+\d+[\\.,]?\d*\s*(?:МГ|МЛ|МКГ|ЕД|МЕ|Г)(?:\s*\/\s*(?:МЛ|Г|КГ|Л|МКГ|МГ|ЕД|МЕ))?|\d+[\\.,]?\d*\s*(?:МГ|МЛ|МКГ|ЕД|МЕ|Г)\s*\/\s*(?:МЛ|Г|КГ|Л|МКГ|МГ|ЕД|МЕ)|\d+[\\.,]?\d*\s*(?:МГ|МЛ|МКГ|ЕД|МЕ|Г))/i,
    countryShort: /([A-Za-zА-Яа-яЁё\-\s]+\(\d{3}\))/,
    sum: /(\d{1,3}(?:\s\d{3})+,\d{2}|\d+,\d{2})/
  };

  const blank = () => ({
    name: '', category_ls: '', okpd2: '', country: '', trade_name: '', ru: '',
    release_form: '', dose: '', qty_need: '', price_per_unit: '', sum_rub: '',
    holder_name: '', manufacturer_name: '', manufacturer_country: '',
    primary_package_type: '', qty_forms_primary: '', qty_primary_packages: '',
    qty_consumer_units: '', consumer_package_completeness: '',
  });

  const looksLikePrice = (s) => /^\d{1,6}[.,]\d{2,7}$/.test(clean(s));
  const looksLikeQty = (s) => /\d[\d\s.,]*\s*(СМ3|МЛ|Л|Г|КГ|ШТ|ЕД|МЕ)/i.test(clean(s));

  const shortCountry = (s) => {
    const m = clean(s).match(rx.countryShort);
    return clean(m ? m[1] : s);
  };

  const extractSum = (s) => clean((clean(s).match(rx.sum) || [])[1] || '');

  const extractPrice = (src) => {
    const candidates = src.match(/\d{1,6}[.,]\d{2,7}/g) || [];
    for (const c of candidates) {
      const val = clean(c);
      if (/^\d{2}\.\d{2}\.\d{2}\.\d{3}$/.test(val)) continue;
      const idx = src.indexOf(val);
      const after = src.slice(idx + val.length, idx + val.length + 12).toUpperCase();
      if (/^\s*(МГ|МЛ|МКГ|ЕД|МЕ|Г|КГ)\b/.test(after)) continue;
      if (after.slice(0, 4).includes('/')) continue;
      return val;
    }
    return '';
  };

  const extractQty = (src) => {
    const labeled = src.match(/ЕДИНИЦА\s+ИЗМЕРЕНИЯ(?:\s+ТОВАРА)?\s*:\s*([^|]+)/i);
    if (labeled) return clean(labeled[1].split(/СТРАНА\s+ПРОИСХОЖДЕНИЯ/i)[0]);
    const m = src.match(/\d[\d\s.,]*\s*(СМ3|МЛ|Л|Г|КГ|ШТ|ЕД|МЕ)(?:\s*\([^)]*\))?/i);
    return m ? clean(m[0]) : '';
  };

  const metaMap = [
    ['release_form', 'Лекарственная форма'], ['dose', 'Дозировка'],
    ['holder_name', 'Наименование держателя или владельца РУ'],
    ['manufacturer_name', 'Наименование производителя'],
    ['manufacturer_country', 'Страна производителя'],
    ['primary_package_type', 'Вид первичной упаковки'],
    ['qty_forms_primary', 'Количество лекарственных форм в первичной упаковке'],
    ['qty_primary_packages', 'Количество первичных упаковок в потребительской упаковке'],
    ['qty_consumer_units', 'Количество потребительских единиц в потребительской упаковке'],
    ['consumer_package_completeness', 'Комплектность потребительской упаковки'],
  ];

  const extractMetaFromText = (src) => {
    const s = clean(src).replace(/\|/g, ' ');
    const points = [];
    for (const [key, label] of metaMap) {
      const idx = s.toUpperCase().indexOf(`${label}:`.toUpperCase());
      if (idx >= 0) points.push({ key, idx, end: idx + label.length + 1 });
    }
    points.sort((a, b) => a.idx - b.idx);
    const out = {};
    for (let i = 0; i < points.length; i++) {
      const cur = points[i];
      const nextIdx = i + 1 < points.length ? points[i + 1].idx : s.length;
      out[cur.key] = clean(s.slice(cur.end, nextIdx));
    }
    return out;
  };

  const section = Array.from(document.querySelectorAll('section,div,table')).find((el) =>
    /Объекты закупки/i.test(text(el))
  ) || document.body;

  // Find ALL independent drug tables
  const allDrugTables = Array.from(section.querySelectorAll('table')).filter((t) => {
    const tText = text(t).toUpperCase();
    if (!tText.includes('ТОРГОВОЕ НАИМЕНОВАНИЕ') || !tText.includes('НОМЕР РУ')) return false;
    if (tText.includes('НАИМЕНОВАНИЕ ОБЪЕКТА ЗАКУПКИ') && tText.includes('ПОЗИЦИИ ПО КТРУ')) {
      if (t.querySelectorAll('tr').length > 10) return false;
    }
    return true;
  });

  const parseDrugTable = (table) => {
    const rows = Array.from(table.querySelectorAll('tr'));
    const rec = blank();
    const hMap = {};
    let headerFound = false;

    for (const tr of rows) {
      const cells = Array.from(tr.querySelectorAll('th,td'));
      if (!cells.length) continue;
      const headers = cells.map((x) => text(x).toUpperCase());
      const headerLine = headers.join(' | ');
      if (/ТОРГОВОЕ НАИМЕНОВАНИЕ/.test(headerLine) && /НОМЕР РУ/.test(headerLine)) {
        for (let i = 0; i < headers.length; i++) {
          const h = headers[i];
          if (/ТОРГОВОЕ\s+НАИМЕНОВАНИЕ/.test(h)) hMap.trade = i;
          if (/НОМЕР\s+РУ/.test(h)) hMap.ru = i;
          if (/ЛЕКАРСТВЕННАЯ\s+ФОРМА/.test(h)) hMap.form = i;
          if (/ДОЗИРОВКА/.test(h)) hMap.dose = i;
          if (/КОЛИЧЕСТВО.*ПОТРЕБ.*ЕДИНИЦ/.test(h)) hMap.qty = i;
        }
        headerFound = true;
        break;
      }
    }

    if (!headerFound) return null;

    for (const tr of rows) {
      const cols = Array.from(tr.querySelectorAll('td')).map((td) => text(td));
      if (!cols.length) continue;
      const rowText = text(tr);
      const rowUp = rowText.toUpperCase();
      if (rowUp.includes('ТОРГОВОЕ НАИМЕНОВАНИЕ') || rowUp.includes('НОМЕР РУ')) continue;
      if (rowUp.includes('МНН И ФОРМА ВЫПУСКА') && cols.length === 1) continue;

      const tradeRaw = hMap.trade !== undefined ? cols[hMap.trade] : (cols[1] || '');
      const ruRaw = hMap.ru !== undefined ? cols[hMap.ru] : (cols[2] || '');
      const formRaw = hMap.form !== undefined ? cols[hMap.form] : (cols[3] || '');
      const doseRaw = hMap.dose !== undefined ? cols[hMap.dose] : (cols[4] || '');
      const qtyRaw = hMap.qty !== undefined ? cols[hMap.qty] : (cols[5] || '');

      if (/МНН\s*:/i.test(tradeRaw)) continue;

      rec.trade_name = clean(tradeRaw);
      rec.ru = clean((clean(ruRaw).match(rx.ru) || [])[1] || ruRaw || '');
      rec.release_form = clean(formRaw);
      rec.dose = clean((clean(doseRaw).match(rx.dose) || [])[1] || doseRaw || '');

      if (qtyRaw && looksLikeQty(qtyRaw)) {
        rec.qty_need = extractQty(qtyRaw) || clean(qtyRaw);
      }

      const meta = extractMetaFromText(rowText);
      Object.keys(meta).forEach((k) => { if (!rec[k]) rec[k] = clean(meta[k]); });
    }

    return rec;
  };

  // Parse main summary table for top-level info
  const mainTable = Array.from(section.querySelectorAll('table')).find((t) => {
    const tText = text(t).toUpperCase();
    return tText.includes('НАИМЕНОВАНИЕ ОБЪЕКТА ЗАКУПКИ') && tText.includes('ПОЗИЦИИ ПО КТРУ');
  });

  const topLevelRecords = [];
  if (mainTable) {
    const rows = Array.from(mainTable.querySelectorAll('tr')).filter((tr) => {
      const cells = tr.querySelectorAll('td');
      if (cells.length < 5) return false;
      return /^\s*\d+\.\s+/.test(text(cells[1]));
    });

    for (const tr of rows) {
      const cols = Array.from(tr.querySelectorAll('td')).map((td) => text(td));
      const rec = blank();

      const nameMatch = (cols[1] || '').match(/\d+\.\s*([^|]+)/);
      rec.name = nameMatch ? clean(nameMatch[1]) : clean(cols[1] || '');

      const catText = cols[2] || '';
      rec.okpd2 = clean((catText.match(rx.okpd2) || [])[1] || '');
      rec.category_ls = clean(catText.replace(rx.okpd2, '').replace(/[()]/g, ''));

      const qtyText = cols[4] || '';
      if (looksLikeQty(qtyText)) rec.qty_need = extractQty(qtyText) || clean(qtyText);

      const priceText = cols[5] || '';
      if (looksLikePrice(priceText)) rec.price_per_unit = priceText;

      const sumText = cols[6] || '';
      if (/НДС/i.test(sumText)) rec.sum_rub = extractSum(sumText);

      const countryMatch = (cols[1] || '').match(/Страна происхождения\s*:\s*([^|]+)/i);
      if (countryMatch) rec.country = shortCountry(countryMatch[1]);

      topLevelRecords.push(rec);
    }
  }

  const drugRecords = allDrugTables.map(parseDrugTable).filter(Boolean);
  const out = [];

  if (topLevelRecords.length === drugRecords.length) {
    for (let i = 0; i < topLevelRecords.length; i++) {
      const top = topLevelRecords[i];
      const drug = drugRecords[i];
      out.push({ ...top, trade_name: drug.trade_name || top.trade_name, ru: drug.ru || top.ru, release_form: drug.release_form || top.release_form, dose: drug.dose || top.dose });
    }
  } else if (drugRecords.length > 0 && topLevelRecords.length === 0) {
    out.push(...drugRecords);
  } else if (drugRecords.length > topLevelRecords.length) {
    const top = topLevelRecords[0] || blank();
    for (const drug of drugRecords) {
      out.push({
        name: drug.trade_name || top.name, category_ls: top.category_ls, okpd2: top.okpd2, country: top.country,
        trade_name: drug.trade_name, ru: drug.ru, release_form: drug.release_form, dose: drug.dose,
        qty_need: drug.qty_need || top.qty_need,
        price_per_unit: drug.qty_need ? '' : top.price_per_unit,
        sum_rub: drug.qty_need ? '' : top.sum_rub,
        holder_name: drug.holder_name, manufacturer_name: drug.manufacturer_name,
        manufacturer_country: drug.manufacturer_country, primary_package_type: drug.primary_package_type,
        qty_forms_primary: drug.qty_forms_primary, qty_primary_packages: drug.qty_primary_packages,
        qty_consumer_units: drug.qty_consumer_units, consumer_package_completeness: drug.consumer_package_completeness,
      });
    }
  } else {
    out.push(...topLevelRecords);
  }

  // Deduplicate
  const uniq = [];
  const seen = new Set();
  for (const rec of out) {
    const key = Object.values(rec).join('|');
    if (seen.has(key)) continue;
    seen.add(key);
    uniq.push(rec);
  }

  return uniq;
}
"""


if __name__ == "__main__":
    sys.exit(main())
