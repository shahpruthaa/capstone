import { useState } from "react";
import { Home, PieChart, Lightbulb, FlaskConical, GitCompare } from "lucide-react";
import "./index.css";
import { Portfolio } from "./services/portfolioService";
import { GenerateTab } from "./components/GenerateTab";
import { AnalyzeTab } from "./components/AnalyzeTab";
import { BacktestTab } from "./components/BacktestTab";
import { CompareTab } from "./components/CompareTab";
import { AIChat } from "./components/AIChat";

type Tab = "MARKET" | "PORTFOLIO" | "IDEAS" | "BACKTEST" | "COMPARE";

const PAGE_META: Record<Tab, { title: string; subtitle: string }> = {
  MARKET: { title: "Market", subtitle: "Conditions · Heatmap · Factor weather · News" },
  PORTFOLIO: { title: "Portfolio", subtitle: "Step 1 to Step 4: Build and review picks" },
  IDEAS: { title: "Trade Ideas", subtitle: "Individual setups · 10-point checklist" },
  BACKTEST: { title: "Research Backtest", subtitle: "Step 5: Run strategy inline" },
  COMPARE: { title: "Research Compare", subtitle: "Compare vs benchmark strategies" },
};

function Sidebar({ tab, setTab }: { tab: Tab; setTab: (tab: Tab) => void }) {
  return (
    <aside className="app-sidebar">
      <div className="sidebar-logo">
        <div className="logo-mark">A</div>
        <div className="logo-text-wrap">
          <div className="logo-name">AlphaLens</div>
          <div className="logo-tag">NSE Portfolio Manager</div>
        </div>
      </div>

      <nav className="sidebar-nav">
        <button className={`nav-item ${tab === "MARKET" ? "active" : ""}`} onClick={() => setTab("MARKET")}>
          <Home size={14} />
          <span>Market</span>
        </button>

        <button className={`nav-item ${tab === "PORTFOLIO" ? "active" : ""}`} onClick={() => setTab("PORTFOLIO")}>
          <PieChart size={14} />
          <span>Portfolio</span>
        </button>

        <button className={`nav-item ${tab === "IDEAS" ? "active" : ""}`} onClick={() => setTab("IDEAS")}>
          <Lightbulb size={14} />
          <span>Trade Ideas</span>
        </button>

        <button className={`nav-item ${tab === "BACKTEST" ? "active" : ""}`} onClick={() => setTab("BACKTEST")}>
          <FlaskConical size={14} />
          <span>Backtest</span>
        </button>

        <button className={`nav-item ${tab === "COMPARE" ? "active" : ""}`} onClick={() => setTab("COMPARE")}>
          <GitCompare size={14} />
          <span>Compare</span>
        </button>
      </nav>

      <div className="sidebar-bottom">
        <div className="market-status">
          <div className="status-dot open" />
          <div className="text-mono text-xs">NSE: Open/Closed</div>
        </div>
        <div className="market-status">
          <div className="status-dot open" />
          <div className="text-mono text-xs">Ensemble: Active</div>
        </div>
        <div className="market-status">
          <div className="status-dot closed" />
          <div className="text-mono text-xs">Data: Apr 2</div>
        </div>
      </div>
    </aside>
  );
}

function MarketPanel() {
  return (
    <div className="grid-2">
      <div className="card">
        <div className="card-header"><span className="card-title">Market Conditions</span></div>
        <div className="card-body text-muted">Regime, trend, and macro pulse will appear here.</div>
      </div>
      <div className="card">
        <div className="card-header"><span className="card-title">Sector Heatmap</span></div>
        <div className="card-body text-muted">Sector breadth and relative strength map.</div>
      </div>
      <div className="card">
        <div className="card-header"><span className="card-title">Factor Weather</span></div>
        <div className="card-body text-muted">Momentum, quality, value, and low-vol factors.</div>
      </div>
      <div className="card">
        <div className="card-header"><span className="card-title">News + Accio Tip</span></div>
        <div className="card-body text-muted">Top events plus one actionable guidance tip.</div>
      </div>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState<Tab>("MARKET");
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);

  return (
    <div className="app-shell">
      <Sidebar tab={tab} setTab={setTab} />

      <div className="app-content">
        <header className="app-topbar">
          <div className="topbar-left">
            <div className="page-title">{PAGE_META[tab].title}</div>
          </div>
          <div className="topbar-right">
            <span className="badge badge-neutral">{PAGE_META[tab].subtitle}</span>
          </div>
        </header>

        <main className="app-main">
          {tab === "MARKET" && <MarketPanel />}
          {tab === "PORTFOLIO" && <GenerateTab onPortfolioGenerated={setPortfolio} portfolio={portfolio} />}
          {tab === "IDEAS" && <AnalyzeTab />}
          {tab === "BACKTEST" && <BacktestTab portfolio={portfolio} />}
          {tab === "COMPARE" && <CompareTab />}
        </main>
      </div>

      <AIChat portfolio={portfolio} />
    </div>
  );
}
