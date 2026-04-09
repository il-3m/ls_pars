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
];

export default function App() {
  const [url, setUrl] = useState(
    "https://zakupki.gov.ru/epz/contract/contractCard/payment-info-and-target-of-order.html?reestrNumber=2312813818126000251&contractInfoId=108730614",
  );
  const [searchWord, setSearchWord] = useState("ципрофлоксацин");
  const [archiveDir, setArchiveDir] = useState("archive");
  const [outCsv, setOutCsv] = useState("export/result.csv");
  const [outXlsx, setOutXlsx] = useState("export/result.xlsx");
  const [traceEnabled, setTraceEnabled] = useState(true);
  const [copyState, setCopyState] = useState<"idle" | "done">("idle");
  const [showSettings, setShowSettings] = useState(true);
  const [mnnFilter, setMnnFilter] = useState("");

  const runCommand = useMemo(() => {
    const parts = [
      "python eis_parser.py",
      `--url \"${url.trim()}\"`,
      `--archive-dir ${archiveDir.trim()}`,
      `--out-csv ${outCsv.trim()}`,
      `--out-xlsx ${outXlsx.trim()}`,
    ];

    if (traceEnabled) {
      parts.push("--trace");
    }

    return parts.join(" ");
  }, [archiveDir, outCsv, outXlsx, searchWord, traceEnabled, url]);

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
      result = result.filter((row) =>
        row.mnn.toUpperCase().includes(mnnQuery),
      );
    }

    return result;
  }, [searchWord, mnnFilter]);

  const copyCommand = async () => {
    try {
      await navigator.clipboard.writeText(runCommand);
      setCopyState("done");
      setTimeout(() => setCopyState("idle"), 1600);
    } catch {
      setCopyState("idle");
    }
  };

  const openExcel = () => {
    const excelPath = outXlsx.trim();
    if (excelPath) {
      window.open(excelPath, "_blank");
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <main className="mx-auto max-w-6xl px-6 py-10">
        <section className="relative overflow-hidden border border-slate-800 bg-slate-900/60 p-6 md:p-8">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_15%_20%,rgba(56,189,248,0.20),transparent_35%),radial-gradient(circle_at_85%_30%,rgba(125,211,252,0.14),transparent_45%)]" />
          <div className="relative space-y-4 [animation:fadeIn_.55s_ease-out]">
            <p className="text-xs tracking-[0.22em] text-cyan-300">EIS PARSER SHELL</p>
            <h1 className="text-3xl font-semibold md:text-4xl">Визуальная оболочка для URL и поискового слова</h1>
            <p className="max-w-3xl text-slate-300">
              Меняйте ссылку закупки и слово для поиска, затем копируйте готовую команду запуска
              Python-скрипта. Ниже есть предпросмотр фильтра по поисковому слову.
            </p>
          </div>
        </section>

        <section className="mt-6 grid gap-3 border border-slate-800 bg-slate-900/60 p-3 md:grid-cols-[1.45fr_1fr]">
          {showSettings && (
          <div className="space-y-1.5 [animation:slideUp_.6s_ease-out]">
            <label className="block text-[10px] text-slate-300" htmlFor="url">
              Ссылка ЕИС
            </label>
            <input
              id="url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              className="w-full border border-slate-700 bg-slate-950 px-1.5 py-1 text-[10px] outline-none ring-cyan-300 transition focus:ring"
            />

            <label className="block text-[10px] text-slate-300" htmlFor="search-word">
              Слово для поиска
            </label>
            <input
              id="search-word"
              value={searchWord}
              onChange={(event) => setSearchWord(event.target.value)}
              className="w-full border border-slate-700 bg-slate-950 px-1.5 py-1 text-[10px] outline-none ring-cyan-300 transition focus:ring"
              placeholder="азитромицин"
            />

            <div className="grid gap-1.5 md:grid-cols-3">
              <div>
                <label className="block text-[10px] text-slate-300" htmlFor="archive-dir">
                  Папка архива
                </label>
                <input
                  id="archive-dir"
                  value={archiveDir}
                  onChange={(event) => setArchiveDir(event.target.value)}
                  className="mt-0.5 w-full border border-slate-700 bg-slate-950 px-1.5 py-1 text-[10px] outline-none ring-cyan-300 transition focus:ring"
                />
              </div>
              <div>
                <label className="block text-[10px] text-slate-300" htmlFor="csv">
                  CSV файл
                </label>
                <input
                  id="csv"
                  value={outCsv}
                  onChange={(event) => setOutCsv(event.target.value)}
                  className="mt-0.5 w-full border border-slate-700 bg-slate-950 px-1.5 py-1 text-[10px] outline-none ring-cyan-300 transition focus:ring"
                />
              </div>
              <div>
                <label className="block text-[10px] text-slate-300" htmlFor="xlsx">
                  XLSX файл
                </label>
                <input
                  id="xlsx"
                  value={outXlsx}
                  onChange={(event) => setOutXlsx(event.target.value)}
                  className="mt-0.5 w-full border border-slate-700 bg-slate-950 px-1.5 py-1 text-[10px] outline-none ring-cyan-300 transition focus:ring"
                />
              </div>
            </div>

            <label className="flex items-center gap-1.5 text-[10px] text-slate-300">
              <input
                type="checkbox"
                checked={traceEnabled}
                onChange={(event) => setTraceEnabled(event.target.checked)}
                className="accent-cyan-300 h-2.5 w-2.5"
              />
              Сохранять trace
            </label>
          </div>
          )}

          <div className="space-y-1.5 border border-slate-700 bg-slate-950/70 p-2 text-[10px] [animation:pulseIn_.8s_ease-out]">
            <p className="text-slate-400">Готовая команда</p>
            <pre className="overflow-x-auto whitespace-pre-wrap break-all border border-slate-800 bg-slate-950 p-1.5 text-cyan-200">
              {runCommand}
            </pre>
            <button
              type="button"
              onClick={copyCommand}
              className="w-full border border-cyan-400 px-1.5 py-1 text-cyan-200 transition hover:bg-cyan-400/10"
            >
              {copyState === "done" ? "Скопировано" : "Скопировать команду"}
            </button>
            <p className="text-[9px] text-slate-400">
              Команда запускается в той же папке, где лежит файл <code>eis_parser.py</code>.
            </p>
            <p className="text-[9px] text-slate-400">
              Слово поиска применяется в интерфейсе как фильтр результата, не как аргумент запуска.
            </p>
          </div>
        </section>

        <section className="mt-6 border border-slate-800 bg-slate-900/60 p-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium">Результаты парсинга</h2>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setShowSettings(!showSettings)}
                className="border border-slate-600 px-1.5 py-0.5 text-[10px] text-slate-300 transition hover:bg-slate-700/50"
              >
                {showSettings ? "Скрыть настройки" : "Показать настройки"}
              </button>
              <button
                type="button"
                onClick={openExcel}
                className="border border-green-500 px-1.5 py-0.5 text-[10px] text-green-400 transition hover:bg-green-500/10"
              >
                Открыть Excel
              </button>
            </div>
          </div>
          
          <div className="mt-2 flex items-center gap-2">
            <div className="flex items-center gap-1.5">
              <label className="text-[10px] text-slate-300" htmlFor="mnn-filter">
                Фильтр по МНН:
              </label>
              <input
                id="mnn-filter"
                value={mnnFilter}
                onChange={(event) => setMnnFilter(event.target.value)}
                className="w-32 border border-slate-700 bg-slate-950 px-1.5 py-0.5 text-[10px] outline-none ring-cyan-300 transition focus:ring"
                placeholder="введите МНН"
              />
            </div>
            <p className="text-[10px] text-slate-400">
              Найдено: {filteredRows.length} из {demoRows.length}
            </p>
          </div>

          <div className="mt-2 overflow-x-auto text-[10px]">
            <table className="min-w-full border-collapse table-auto">
              <thead>
                <tr className="text-left text-slate-400 sticky top-0 bg-slate-900/60">
                  <th className="border-b border-slate-700 p-1 min-w-[280px]">Наименование</th>
                  <th className="border-b border-slate-700 p-1 min-w-[150px]">МНН</th>
                  <th className="border-b border-slate-700 p-1 min-w-[150px]">ТН</th>
                  <th className="border-b border-slate-700 p-1 min-w-[180px]">РУ</th>
                  <th className="border-b border-slate-700 p-1 min-w-[200px]">Форма выпуска</th>
                  <th className="border-b border-slate-700 p-1 min-w-[120px]">Дозировка</th>
                  <th className="border-b border-slate-700 p-1 min-w-[100px]">Сумма, руб</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((row) => (
                  <tr key={row.ru} className="[animation:fadeIn_.45s_ease-out] hover:bg-slate-800/30">
                    <td className="border-b border-slate-800 p-1 max-w-xs truncate">{row.name}</td>
                    <td className="border-b border-slate-800 p-1">{row.mnn}</td>
                    <td className="border-b border-slate-800 p-1">{row.tradeName}</td>
                    <td className="border-b border-slate-800 p-1 font-mono break-all">{row.ru}</td>
                    <td className="border-b border-slate-800 p-1 max-w-xs truncate">{row.dose}</td>
                    <td className="border-b border-slate-800 p-1 text-right">{row.sum}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(16px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes pulseIn {
          0% { opacity: 0; transform: scale(0.985); }
          100% { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </div>
  );
}
