import { useMemo, useState } from "react";

type Row = {
  name: string;
  mnn: string;
  tradeName: string;
  ru: string;
  dose: string;
  sum: string;
};

const demoRows: Row[] = [
  {
    name: "2. ЦИПРОФЛОКСАЦИН: РАСТВОР ДЛЯ ИНФУЗИЙ, 2 мг/мл",
    mnn: "ЦИПРОФЛОКСАЦИН",
    tradeName: "ЦИПРОКАЗ",
    ru: "ЛП-003895",
    dose: "2 МГ/МЛ",
    sum: "16 898,25",
  },
  {
    name: "3. АЗИТРОМИЦИН: ПОРОШОК ДЛЯ ПРИГОТОВЛЕНИЯ",
    mnn: "АЗИТРОМИЦИН",
    tradeName: "АЗИФАРМ",
    ru: "ЛП-002344",
    dose: "500 МГ",
    sum: "9 450,00",
  },
  {
    name: "4. ПАРАЦЕТАМОЛ: ТАБЛЕТКИ, 500 мг",
    mnn: "ПАРАЦЕТАМОЛ",
    tradeName: "ПАРАЦЕТАМОЛ-ФАРМ",
    ru: "ЛП-001234",
    dose: "500 МГ",
    sum: "5 200,00",
  },
];

type TabType = "main" | "settings";

export default function App() {
  const [searchWord, setSearchWord] = useState("ципрофлоксацин");
  const [archiveDir, setArchiveDir] = useState("archive");
  const [outCsv, setOutCsv] = useState("export/result.csv");
  const [outXlsx, setOutXlsx] = useState("export/result.xlsx");
  const [traceEnabled, setTraceEnabled] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>("main");
  const [mnnFilter, setMnnFilter] = useState("");
  const [timeoutMs, setTimeoutMs] = useState("90000");
  const [expandRounds, setExpandRounds] = useState("5");
  const [pageLoadDelay, setPageLoadDelay] = useState("1200");
  const [expandDelay, setExpandDelay] = useState("800");
  const [headed, setHeaded] = useState(false);

  const filteredRows = useMemo(() => {
    const query = searchWord.trim().toLowerCase();
    const mnnQuery = mnnFilter.trim().toUpperCase();
    let result = demoRows;
    if (query) {
      result = result.filter((row) =>
        Object.values(row).some((value) => value.toLowerCase().includes(query)),
      );
    }
    if (mnnQuery) {
      result = result.filter((row) => row.mnn.toUpperCase().includes(mnnQuery));
    }
    return result;
  }, [searchWord, mnnFilter]);

  const openExcel = () => {
    const excelPath = outXlsx.trim();
    if (excelPath) {
      window.open(excelPath, "_blank");
    }
  };

  return (
    <div className="flex h-screen flex-col bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/80 px-6 py-4 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div>
            <p className="text-xs tracking-[0.22em] text-cyan-300">UNIFIED PARSER</p>
            <h1 className="text-xl font-semibold md:text-2xl">Парсер ЕИС</h1>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab("main")}
              className={`rounded-md px-4 py-2 text-sm font-medium transition ${
                activeTab === "main" ? "bg-cyan-500 text-white" : "text-slate-300 hover:bg-slate-800"
              }`}
            >
              Основная
            </button>
            <button
              onClick={() => setActiveTab("settings")}
              className={`rounded-md px-4 py-2 text-sm font-medium transition ${
                activeTab === "settings" ? "bg-cyan-500 text-white" : "text-slate-300 hover:bg-slate-800"
              }`}
            >
              Настройки
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-7xl flex-1 gap-4 overflow-hidden p-4">
        <aside className="flex w-80 min-w-[280px] flex-shrink-0 flex-col gap-4 overflow-y-auto rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          {activeTab === "main" ? (
            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-cyan-300" htmlFor="search-word">
                  Поисковый запрос (МНН)
                </label>
                <input
                  id="search-word"
                  value={searchWord}
                  onChange={(event) => setSearchWord(event.target.value)}
                  className="w-full rounded border border-slate-700 bg-yellow-50 px-3 py-2 text-sm outline-none ring-cyan-300 transition focus:ring"
                  placeholder="азитромицин"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="mb-1 block text-xs font-medium text-cyan-300" htmlFor="date-from">Дата с</label>
                  <input id="date-from" type="date" className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-2 text-sm outline-none ring-cyan-300 transition focus:ring" />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-cyan-300" htmlFor="date-to">Дата по</label>
                  <input id="date-to" type="date" className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-2 text-sm outline-none ring-cyan-300 transition focus:ring" />
                </div>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-cyan-300" htmlFor="max-contracts">Макс. контрактов</label>
                <input id="max-contracts" type="number" defaultValue="20" className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none ring-cyan-300 transition focus:ring" />
              </div>
              <div className="space-y-2 pt-2">
                <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-300">
                  <input type="checkbox" className="accent-cyan-300 h-4 w-4" /> Только Москва и МО
                </label>
                <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-300">
                  <input type="checkbox" className="accent-cyan-300 h-4 w-4" /> Только Росунимед
                </label>
              </div>
              <div className="pt-4">
                <label className="mb-1 block text-xs font-medium text-cyan-300" htmlFor="mnn-filter-sidebar">
                  Фильтр по МНН
                </label>
                <input
                  id="mnn-filter-sidebar"
                  value={mnnFilter}
                  onChange={(event) => setMnnFilter(event.target.value)}
                  className="w-full rounded border border-slate-700 bg-yellow-50 px-3 py-2 text-sm outline-none ring-cyan-300 transition focus:ring"
                  placeholder="введите МНН"
                />
              </div>
              <div className="pt-2">
                <button type="button" className="w-full rounded-md bg-slate-700 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-600">
                  Фильтровать
                </button>
              </div>
              <div className="pt-4">
                <button type="button" className="w-full rounded-md bg-lime-300 px-4 py-2.5 text-sm font-medium text-slate-900 transition hover:bg-lime-400">
                  Запустить парсинг
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-cyan-300" htmlFor="timeout">Таймаут загрузки (мс)</label>
                <input id="timeout" value={timeoutMs} onChange={(e) => setTimeoutMs(e.target.value)} type="number" className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none ring-cyan-300 transition focus:ring" />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-cyan-300" htmlFor="rounds">Раунды раскрытия</label>
                <input id="rounds" value={expandRounds} onChange={(e) => setExpandRounds(e.target.value)} type="number" className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none ring-cyan-300 transition focus:ring" />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-cyan-300" htmlFor="page-delay">Задержка после загрузки (мс)</label>
                <input id="page-delay" value={pageLoadDelay} onChange={(e) => setPageLoadDelay(e.target.value)} type="number" className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none ring-cyan-300 transition focus:ring" />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-cyan-300" htmlFor="expand-delay">Задержка раскрытия (мс)</label>
                <input id="expand-delay" value={expandDelay} onChange={(e) => setExpandDelay(e.target.value)} type="number" className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none ring-cyan-300 transition focus:ring" />
              </div>
              <div className="pt-2">
                <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-300">
                  <input type="checkbox" checked={headed} onChange={(e) => setHeaded(e.target.checked)} className="accent-cyan-300 h-4 w-4" /> Браузер с окном (не headless)
                </label>
              </div>
              <div className="pt-4 border-t border-slate-800">
                <label className="mb-2 block text-xs font-medium text-cyan-300" htmlFor="archive-dir">Папка архива</label>
                <input id="archive-dir" value={archiveDir} onChange={(event) => setArchiveDir(event.target.value)} className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none ring-cyan-300 transition focus:ring" />
              </div>
              <div>
                <label className="mb-2 block text-xs font-medium text-cyan-300" htmlFor="csv">CSV файл</label>
                <input id="csv" value={outCsv} onChange={(event) => setOutCsv(event.target.value)} className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none ring-cyan-300 transition focus:ring" />
              </div>
              <div>
                <label className="mb-2 block text-xs font-medium text-cyan-300" htmlFor="xlsx">XLSX файл</label>
                <input id="xlsx" value={outXlsx} onChange={(event) => setOutXlsx(event.target.value)} className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none ring-cyan-300 transition focus:ring" />
              </div>
              <div className="pt-2">
                <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-300">
                  <input type="checkbox" checked={traceEnabled} onChange={(event) => setTraceEnabled(event.target.checked)} className="accent-cyan-300 h-4 w-4" /> Сохранять trace
                </label>
              </div>
            </div>
          )}
        </aside>

        <section className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-lg border border-slate-800 bg-slate-900/60">
          <div className="border-b border-slate-800 px-4 py-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-medium text-cyan-300">Результаты парсинга</h2>
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-2">
                  <label className="text-xs text-slate-400" htmlFor="mnn-filter">Фильтр МНН:</label>
                  <input id="mnn-filter" value={mnnFilter} onChange={(event) => setMnnFilter(event.target.value)} className="w-32 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs outline-none ring-cyan-300 transition focus:ring" placeholder="введите МНН" />
                </div>
                <span className="rounded bg-slate-800 px-2 py-1 text-xs text-slate-400">Найдено: {filteredRows.length} из {demoRows.length}</span>
              </div>
            </div>
            <div className="mt-3">
              <button type="button" onClick={openExcel} className="w-40 rounded-md border border-green-500 px-3 py-2 text-sm font-medium text-green-400 transition hover:bg-green-500/10">
                Выгрузить в excel
              </button>
            </div>
          </div>
          <div className="min-h-[50vh] flex-1 overflow-auto">
            <table className="w-full border-collapse text-sm">
              <thead className="sticky top-0 z-10 bg-slate-900/95 backdrop-blur">
                <tr className="text-left text-slate-400">
                  <th className="border-b border-slate-700 px-3 py-3 font-medium min-w-[300px]">Наименование</th>
                  <th className="border-b border-slate-700 px-3 py-3 font-medium min-w-[140px]">МНН</th>
                  <th className="border-b border-slate-700 px-3 py-3 font-medium min-w-[140px]">ТН</th>
                  <th className="border-b border-slate-700 px-3 py-3 font-medium min-w-[120px]">РУ</th>
                  <th className="border-b border-slate-700 px-3 py-3 font-medium min-w-[180px]">Форма выпуска</th>
                  <th className="border-b border-slate-700 px-3 py-3 font-medium min-w-[100px] text-right">Сумма, руб</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((row, idx) => (
                  <tr key={row.ru + idx} className="border-b border-slate-800/50 transition hover:bg-slate-800/30">
                    <td className="px-3 py-2.5 max-w-[300px] truncate text-slate-200">{row.name}</td>
                    <td className="px-3 py-2.5 text-slate-300">{row.mnn}</td>
                    <td className="px-3 py-2.5 text-slate-300">{row.tradeName}</td>
                    <td className="px-3 py-2.5 font-mono text-xs text-cyan-200">{row.ru}</td>
                    <td className="px-3 py-2.5 max-w-[180px] truncate text-slate-300">{row.dose}</td>
                    <td className="px-3 py-2.5 text-right font-medium text-green-400">{row.sum}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="border-t border-slate-800 bg-slate-900/80 px-4 py-2 text-xs text-slate-400">
            <div className="flex items-center justify-between">
              <span>Готов к работе</span>
              <span className="text-slate-500">unifind_parser</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
