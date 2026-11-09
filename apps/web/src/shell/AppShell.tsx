import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { AUTH_NOTICE, LIVE_NOTICE } from "../content";

const LINKS = [
  { to: "/", label: "Overview", end: true },
  { to: "/agency", label: "Agency", end: false },
  { to: "/supervisor", label: "Supervisor", end: false },
  { to: "/market", label: "Market", end: false },
  { to: "/quant", label: "Quant", end: false },
  { to: "/strategy", label: "Strategy", end: false },
  { to: "/scheduler", label: "Scheduler", end: false },
  { to: "/events", label: "Events", end: false },
  { to: "/risk", label: "Risk", end: false },
  { to: "/portfolio", label: "Portfolio", end: false },
  { to: "/reconciliation", label: "Reconciliation", end: false },
  { to: "/research", label: "Research", end: false },
  { to: "/audit", label: "Audit", end: false },
  { to: "/treasury", label: "Treasury", end: false },
  { to: "/system", label: "System", end: false },
  { to: "/settings", label: "Settings", end: false },
  { to: "/live-gate", label: "Live gate", end: false },
  { to: "/paper-swaps", label: "Paper swaps", end: false },
] as const;

type AppShellProps = {
  children: ReactNode;
};

function useIsMobile(): boolean {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(max-width: 767px)");
    const onChange = () => setMatches(media.matches);
    onChange();
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  return matches;
}

export function AppShell({ children }: AppShellProps) {
  const isMobile = useIsMobile();
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const menuRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        menuRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => {
    if (open && isMobile) {
      closeRef.current?.focus();
    }
  }, [open, isMobile]);

  const drawerHidden = isMobile && !open;

  return (
    <div className="min-h-screen bg-obsidian text-ink">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <div className="md:grid md:grid-cols-[auto_1fr]">
        {open ? (
          <button
            type="button"
            className="fixed inset-0 z-20 bg-black/60 md:hidden"
            aria-label="Close navigation"
            onClick={() => {
              setOpen(false);
              menuRef.current?.focus();
            }}
          />
        ) : null}
        <aside
          id="primary-nav"
          className={`fixed inset-y-0 left-0 z-30 flex w-64 flex-col border-r border-line bg-panel transition-transform md:static ${
            open ? "translate-x-0" : "-translate-x-full md:translate-x-0"
          } ${collapsed ? "md:w-20" : "md:w-64"}`}
          aria-hidden={drawerHidden ? true : undefined}
          role={isMobile && open ? "dialog" : undefined}
          aria-modal={isMobile && open ? true : undefined}
          aria-labelledby={isMobile && open ? titleId : undefined}
          inert={drawerHidden ? true : undefined}
        >
          <div className="flex items-start justify-between gap-3 border-b border-line px-4 py-4">
            <div>
              <p id={titleId} className="text-xs font-semibold tracking-wide text-jade">
                Veytrix
              </p>
              <p className={`mt-1 text-sm text-muted ${collapsed ? "md:sr-only" : ""}`}>
                Intelligence beyond the market
              </p>
            </div>
            <button
              ref={closeRef}
              type="button"
              className="rounded-md border border-line px-2 py-1 text-sm md:hidden"
              onClick={() => {
                setOpen(false);
                menuRef.current?.focus();
              }}
            >
              Close
            </button>
          </div>
          <nav aria-label="Primary" className="flex flex-1 flex-col gap-1 p-3">
            {LINKS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                aria-label={item.label}
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  `rounded-md px-3 py-2 text-sm ${
                    isActive ? "bg-panel-2 text-jade" : "text-ink hover:bg-panel-2"
                  }`
                }
              >
                <span aria-hidden="true" className={collapsed ? "hidden md:inline" : "hidden"}>
                  {item.label.slice(0, 1)}
                </span>
                <span className={collapsed ? "md:sr-only" : undefined}>{item.label}</span>
              </NavLink>
            ))}
            <button
              type="button"
              className="mt-auto hidden rounded-md border border-line px-3 py-2 text-sm md:inline-flex"
              aria-pressed={collapsed}
              onClick={() => setCollapsed((value) => !value)}
            >
              {collapsed ? "Expand sidebar" : "Collapse sidebar"}
            </button>
          </nav>
        </aside>
        <div className="min-w-0">
          <header className="flex items-center gap-3 border-b border-line px-4 py-3 md:px-6">
            <button
              ref={menuRef}
              type="button"
              className="rounded-md border border-line px-3 py-2 text-sm md:hidden"
              aria-expanded={open}
              aria-controls="primary-nav"
              onClick={() => setOpen(true)}
            >
              Open navigation
            </button>
            <p className="text-sm text-muted">Private research desk · live quotes</p>
          </header>
          <div
            className="border-b border-line bg-panel-2 px-4 py-3 text-sm text-warn md:px-6"
            role="status"
          >
            {LIVE_NOTICE}
          </div>
          <main id="main" tabIndex={-1} className="mx-auto max-w-6xl px-4 py-6 outline-none md:px-6">
            {children}
          </main>
          <footer className="space-y-2 border-t border-line px-4 py-4 text-sm text-muted md:px-6">
            <p>{AUTH_NOTICE}</p>
            <p>
              Charts use{" "}
              <a
                className="text-jade-2 underline"
                href="https://github.com/tradingview/lightweight-charts/blob/master/LICENSE"
              >
                TradingView Lightweight Charts
              </a>{" "}
              {`5.2.1 (Apache-2.0). This is not TradingView's proprietary Charting Library.`}
            </p>
          </footer>
        </div>
      </div>
    </div>
  );
}
