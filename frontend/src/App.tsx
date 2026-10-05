import { useRef, useState, type KeyboardEvent } from 'react';
import { CompanyPage } from './pages/CompanyPage';
import { HeatmapPage } from './pages/HeatmapPage';
import { ScreenerPage } from './pages/ScreenerPage';

type Tab = 'screener' | 'heatmap' | 'company';
const TABS: { id: Tab; label: string }[] = [
  { id: 'screener', label: 'SCREENER' },
  { id: 'heatmap', label: 'HEATMAP' },
  { id: 'company', label: 'COMPANY' },
];

export default function App() {
  const [tab, setTab] = useState<Tab>('screener');
  // Pages mount on first visit and then stay mounted (hidden), so switching
  // tabs keeps filters and doesn't re-spend API credits.
  const [visited, setVisited] = useState<Set<Tab>>(new Set(['screener']));
  const [symbol, setSymbol] = useState<string | null>(null);
  const tabRefs = useRef<Record<Tab, HTMLButtonElement | null>>({ screener: null, heatmap: null, company: null });

  const select = (t: Tab, focus = false) => {
    setTab(t);
    setVisited((v) => (v.has(t) ? v : new Set(v).add(t)));
    if (focus) tabRefs.current[t]?.focus();
  };

  const openCompany = (s: string) => {
    setSymbol(s);
    select('company');
    window.scrollTo({ top: 0 });
  };

  // WAI-ARIA tabs pattern: arrows / Home / End move between tabs.
  const onTabKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const i = TABS.findIndex((t) => t.id === tab);
    let next: number | null = null;
    if (e.key === 'ArrowRight') next = (i + 1) % TABS.length;
    else if (e.key === 'ArrowLeft') next = (i - 1 + TABS.length) % TABS.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = TABS.length - 1;
    if (next != null) {
      e.preventDefault();
      select(TABS[next].id, true);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="brand">
          MARKET.EXE
          <small>STOCK HEALTH AND PROFITABILITY SIMULATOR</small>
        </h1>
        <span className="mono dim" style={{ fontSize: 11 }}>
          For informational purposes only · Not a recommendation to buy or sell securities
        </span>
      </header>

      <div className="tabbar" role="tablist" aria-label="Views" onKeyDown={onTabKey}>
        {TABS.map((t) => (
          <button
            key={t.id}
            ref={(el) => {
              tabRefs.current[t.id] = el;
            }}
            type="button"
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls={`panel-${t.id}`}
            tabIndex={tab === t.id ? 0 : -1}
            className="tab"
            onClick={() => select(t.id)}
          >
            {t.label}
            {t.id === 'company' && symbol ? ` · ${symbol}` : ''}
          </button>
        ))}
      </div>

      <main>
        {TABS.map((t) => (
          <div
            key={t.id}
            role="tabpanel"
            id={`panel-${t.id}`}
            aria-labelledby={`tab-${t.id}`}
            hidden={tab !== t.id}
            tabIndex={0}
          >
            {visited.has(t.id) && t.id === 'screener' && <ScreenerPage onOpen={openCompany} />}
            {visited.has(t.id) && t.id === 'heatmap' && <HeatmapPage />}
            {visited.has(t.id) && t.id === 'company' && <CompanyPage symbol={symbol} onSymbol={openCompany} />}
          </div>
        ))}
      </main>
    </div>
  );
}
