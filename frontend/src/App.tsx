import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { AuthForm } from './components/AuthForm';
import { useAuth } from './hooks/useAuth';
import { CompanyPage } from './pages/CompanyPage';
import { HeatmapPage } from './pages/HeatmapPage';
import { HistoryPage } from './pages/HistoryPage';
import { PinnedPage } from './pages/PinnedPage';
import { ReportCardPage } from './pages/ReportCardPage';
import { ScreenerPage } from './pages/ScreenerPage';

type Tab = 'screener' | 'heatmap' | 'company' | 'report' | 'pinned' | 'history';
const BASE_TABS: { id: Tab; label: string }[] = [
  { id: 'screener', label: 'SCREENER' },
  { id: 'heatmap', label: 'HEATMAP' },
  { id: 'company', label: 'COMPANY' },
];
// Only shown to logged-in users.
const USER_TABS: { id: Tab; label: string }[] = [
  { id: 'pinned', label: '★ PINNED' },
  { id: 'history', label: 'HISTORY' },
];
// Always last, pushed to the right end of the tab row (see .tab-right).
const REPORT_TAB: { id: Tab; label: string } = { id: 'report', label: 'REPORT CARD' };
const USER_ONLY = new Set<Tab>(USER_TABS.map((t) => t.id));

export default function App() {
  const [tab, setTab] = useState<Tab>('screener');
  // Pages mount on first visit and then stay mounted (hidden), so switching
  // tabs keeps filters and doesn't re-spend API credits.
  const [visited, setVisited] = useState<Set<Tab>>(new Set(['screener']));
  const [symbol, setSymbol] = useState<string | null>(null);
  const [showAuth, setShowAuth] = useState(false);
  const [historyKey, setHistoryKey] = useState(0);
  const [pinnedKey, setPinnedKey] = useState(0);
  const { user } = useAuth();
  const TABS = user ? [...BASE_TABS, ...USER_TABS, REPORT_TAB] : [...BASE_TABS, REPORT_TAB];
  const tabRefs = useRef<Record<Tab, HTMLButtonElement | null>>({
    screener: null,
    heatmap: null,
    company: null,
    report: null,
    pinned: null,
    history: null,
  });

  // On logout, leave (and unmount) the user-only tabs.
  useEffect(() => {
    if (user) return;
    setTab((t) => (USER_ONLY.has(t) ? 'screener' : t));
    setVisited((v) => {
      if (![...v].some((t) => USER_ONLY.has(t))) return v;
      return new Set([...v].filter((t) => !USER_ONLY.has(t)));
    });
  }, [user]);

  const select = (t: Tab, focus = false) => {
    setTab(t);
    setVisited((v) => (v.has(t) ? v : new Set(v).add(t)));
    if (t === 'history') setHistoryKey((k) => k + 1); // always show fresh entries
    if (t === 'pinned') setPinnedKey((k) => k + 1);
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
        <UserMenu onLogin={() => setShowAuth(true)} />
      </header>

      {showAuth && !user && (
        <div className="auth-wrap">
          <AuthForm onDone={() => setShowAuth(false)} />
          <button type="button" className="btn btn-ghost" onClick={() => setShowAuth(false)}>
            Back
          </button>
        </div>
      )}

      <div hidden={showAuth && !user}>
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
            className={t.id === 'report' ? 'tab tab-right' : 'tab'}
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
            {visited.has(t.id) && t.id === 'report' && <ReportCardPage />}
            {visited.has(t.id) && t.id === 'pinned' && user && (
              <PinnedPage onOpen={openCompany} refreshKey={pinnedKey} />
            )}
            {visited.has(t.id) && t.id === 'history' && user && (
              <HistoryPage onOpen={openCompany} refreshKey={historyKey} />
            )}
          </div>
        ))}
      </main>
      </div>
    </div>
  );
}

/** Header area: "LOGIN" when signed out, username + logout when signed in. */
function UserMenu({ onLogin }: { onLogin: () => void }) {
  const { user, checking, logout } = useAuth();
  if (checking) return <span className="mono dim user-menu">…</span>;
  if (!user) {
    return (
      <button type="button" className="btn user-menu" onClick={onLogin}>
        Login / Register
      </button>
    );
  }
  return (
    <span className="mono user-menu">
      <span aria-label={`Logged in as ${user.username}`}>&gt; {user.username}</span>
      <button type="button" className="btn btn-ghost" onClick={logout}>
        Logout
      </button>
    </span>
  );
}
