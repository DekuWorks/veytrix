import { Route, Routes } from "react-router-dom";
import { AgencyPage } from "./pages/AgencyPage";
import { AuditPage } from "./pages/AuditPage";
import { EventsPage } from "./pages/EventsPage";
import { MarketPage } from "./pages/MarketPage";
import { OverviewPage } from "./pages/OverviewPage";
import { PaperSwapsPage } from "./pages/PaperSwapsPage";
import { PortfolioPage } from "./pages/PortfolioPage";
import { QuantPage } from "./pages/QuantPage";
import { ResearchPage } from "./pages/ResearchPage";
import { RiskPage } from "./pages/RiskPage";
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
        <Route path="/market" element={<MarketPage />} />
        <Route path="/quant" element={<QuantPage />} />
        <Route path="/strategy" element={<StrategyPage />} />
        <Route path="/events" element={<EventsPage />} />
        <Route path="/risk" element={<RiskPage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/research" element={<ResearchPage />} />
        <Route path="/audit" element={<AuditPage />} />
        <Route path="/treasury" element={<TreasuryPage />} />
        <Route path="/system" element={<SystemPage />} />
        <Route path="/paper-swaps" element={<PaperSwapsPage />} />
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
