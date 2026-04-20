import { useState } from "react";
import { Home, PieChart, Lightbulb, FlaskConical, GitCompare } from "lucide-react";
import "./index.css";
import { Portfolio } from "./services/portfolioService";
import { BacktestTab } from "./components/BacktestTab";
import { CompareTab } from "./components/CompareTab";
import { AIChat } from "./components/AIChat";
import { TradeIdeasTab } from "./components/TradeIdeasTab";
import { MarketTab } from "./components/MarketTab";
import { PortfolioWorkspace } from "./components/PortfolioWorkspace";

type Tab = "MARKET" | "PORTFOLIO" | "IDEAS" | "BACKTEST" | "COMPARE";

const PAGE_META: Record<Tab, { title: string; subtitle: string }> = {
  MARKET: { title: "Market", subtitle: "Regime · Sectors · Factor weather · News pulse" },
  PORTFOLIO: { title: "Portfolio", subtitle: "Mandate questionnaire · Recommended basket · Holdings review" },
  IDEAS: { title: "Trade Ideas", subtitle: "Why now checklist · Entries · Stops · News context" },
  BACKTEST: { title: "Backtest", subtitle: "Replay the exact AI mandate portfolio vs Nifty" },
  COMPARE: { title: "Compare", subtitle: "AI strategy vs Nifty and factor-style benchmarks" },
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
            {portfolio && <span className="badge badge-green">{portfolio.allocations.length} live picks</span>}
          </div>
        </header>

        <main className="app-main">
          {tab === "MARKET" && <MarketTab />}
          {tab === "PORTFOLIO" && <PortfolioWorkspace onPortfolioGenerated={setPortfolio} portfolio={portfolio} />}
          {tab === "IDEAS" && <TradeIdeasTab portfolio={portfolio} />}
          {tab === "BACKTEST" && <BacktestTab portfolio={portfolio} />}
          {tab === "COMPARE" && <CompareTab />}
        </main>
      </div>

      <AIChat portfolio={portfolio} />
    </div>
  );
}
