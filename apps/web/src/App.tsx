import { Route, Routes } from "react-router-dom";
import { AgencyPage } from "./pages/AgencyPage";
import { AuditPage } from "./pages/AuditPage";
import { EventsPage } from "./pages/EventsPage";
import { FuturesPage } from "./pages/FuturesPage";
import { LiveGatePage } from "./pages/LiveGatePage";
import { MarketPage } from "./pages/MarketPage";
import { OverviewPage } from "./pages/OverviewPage";
import { PaperSwapsPage } from "./pages/PaperSwapsPage";
import { PortfolioPage } from "./pages/PortfolioPage";
import { QuantPage } from "./pages/QuantPage";
import { ReconciliationPage } from "./pages/ReconciliationPage";
import { ResearchPage } from "./pages/ResearchPage";
import { RiskLogPage } from "./pages/RiskLogPage";
import { RiskPage } from "./pages/RiskPage";
import { SchedulePage } from "./pages/SchedulePage";
import { SettingsPage } from "./pages/SettingsPage";
import { SupervisorPage } from "./pages/SupervisorPage";
import { StrategyPage } from "./pages/StrategyPage";
import { SystemPage } from "./pages/SystemPage";
import { TreasuryPage } from "./pages/TreasuryPage";
import { AppShell } from "./shell/AppShell";

export function AppRoutes() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/agency" element={<AgencyPage />} />
        <Route path="/agency/:code" element={<AgencyPage />} />
        <Route path="/supervisor" element={<SupervisorPage />} />
        <Route path="/market" element={<MarketPage />} />
        <Route path="/quant" element={<QuantPage />} />
        <Route path="/strategy" element={<StrategyPage />} />
        <Route path="/scheduler" element={<SchedulePage />} />
        <Route path="/events" element={<EventsPage />} />
        <Route path="/risk" element={<RiskPage />} />
        <Route path="/risk-log" element={<RiskLogPage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/reconciliation" element={<ReconciliationPage />} />
        <Route path="/research" element={<ResearchPage />} />
        <Route path="/audit" element={<AuditPage />} />
        <Route path="/treasury" element={<TreasuryPage />} />
        <Route path="/system" element={<SystemPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/live-gate" element={<LiveGatePage />} />
        <Route path="/paper-swaps" element={<PaperSwapsPage />} />
        <Route path="/futures" element={<FuturesPage />} />
        <Route
          path="*"
          element={
            <div>
              <h1 className="text-2xl font-semibold">Not built</h1>
              <p className="mt-2 text-sm text-muted">That page is not part of this sprint.</p>
            </div>
          }
        />
      </Routes>
    </AppShell>
  );
}
