import { useState, useEffect } from "react";
import { Home, PieChart, Lightbulb, FlaskConical, GitCompare, Activity } from "lucide-react";
import "./index.css";
import { Portfolio } from "./services/portfolioService";
import { BacktestTab } from "./components/BacktestTab";
import { CompareTab } from "./components/CompareTab";
import { AIChat } from "./components/AIChat";
import { TradeIdeasTab } from "./components/TradeIdeasTab";
import { MarketTab } from "./components/MarketTab";
import { PortfolioWorkspace } from "./components/PortfolioWorkspace";
import { OverviewTab } from "./components/OverviewTab";
import { MarketEventsTab } from "./components/MarketEventsTab";

type Tab = "OVERVIEW" | "MARKET" | "EVENTS" | "PORTFOLIO" | "IDEAS" | "BACKTEST" | "COMPARE";

const PAGE_META: Record<Tab, { title: string; subtitle: string }> = {
  OVERVIEW: { title: "Research Command Center", subtitle: "Ensemble Status · Market Regime · Neural Signals · System Metrics" },
  MARKET: { title: "Market", subtitle: "Regime · Sectors · Factor weather · News pulse" },
  EVENTS: { title: "Market Events", subtitle: "Real-time news analysis · Event impact · Trading opportunities" },
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
          <div className="logo-name">NSE Atlas</div>
          <div className="logo-tag">AI portfolio research for Indian markets</div>
        </div>
      </div>

      <nav className="sidebar-nav">
        <button className={`nav-item ${tab === "OVERVIEW" ? "active" : ""}`} onClick={() => setTab("OVERVIEW")}>
          <Activity size={14} />
          <span>Overview</span>
        </button>

        <button className={`nav-item ${tab === "MARKET" ? "active" : ""}`} onClick={() => setTab("MARKET")}>
          <Home size={14} />
          <span>Market</span>
        </button>

        <button className={`nav-item ${tab === "EVENTS" ? "active" : ""}`} onClick={() => setTab("EVENTS")}>
          <Activity size={14} />
          <span>Events</span>
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
  const [tab, setTab] = useState<Tab>("OVERVIEW");
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);

  useEffect(() => {
    const handleAction = (e: any) => {
      const action = e.detail;
      if (action.name === 'navigate_to_tab') {
        const targetTab = action.arguments.tab_name;
          if (["OVERVIEW", "MARKET", "EVENTS", "PORTFOLIO", "IDEAS", "BACKTEST", "COMPARE"].includes(targetTab)) {
          setTab(targetTab as Tab);
        }
      } else if (action.name === 'generate_portfolio') {
        setTab("PORTFOLIO");
      } else if (action.name === 'benchmark_portfolio') {
        setTab("COMPARE");
      } else if (action.name === 'analyze_portfolio') {
        window.pendingAiAction = 'analyze_portfolio';
        setTab("PORTFOLIO");
      } else if (action.name === 'run_backtest') {
        window.pendingAiAction = 'run_backtest';
        setTab("BACKTEST");
      }
    };
    window.addEventListener('AI_ACTION', handleAction);
    return () => window.removeEventListener('AI_ACTION', handleAction);
  }, []);

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
          {tab === "OVERVIEW" && <OverviewTab />}
          {tab === "MARKET" && <MarketTab />}
          {tab === "EVENTS" && <MarketEventsTab />}
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
