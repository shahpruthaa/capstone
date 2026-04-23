import { useState } from "react";
import { Home, PieChart, Lightbulb, FlaskConical, GitCompare, Activity } from "lucide-react";

const isMarketOpen = () => true; // Toggle for demo
import "./index.css";
import { Portfolio } from "./services/portfolioService";
import { BacktestTab } from "./components/BacktestTab";
import { CompareTab } from "./components/CompareTab";
import { TradeIdeasTab } from "./components/TradeIdeasTab";
import { MarketTab } from "./components/MarketTab";
import { PortfolioWorkspace } from "./components/PortfolioWorkspace";
import { OverviewTab } from "./components/OverviewTab";

type Tab = "OVERVIEW" | "MARKET" | "PORTFOLIO" | "IDEAS" | "BACKTEST" | "COMPARE";

const PAGE_META: Record<Tab, { title: string; subtitle: string }> = {
  OVERVIEW: { title: "Research Command Center", subtitle: "Ensemble Status | Market Regime | Neural Signals | System Metrics" },
  MARKET: { title: "Market", subtitle: "Regime | Sectors | Factor weather | News pulse" },
  PORTFOLIO: { title: "Portfolio", subtitle: "Mandate questionnaire | Recommended basket | Holdings review" },
  IDEAS: { title: "Trade Ideas", subtitle: "Why now checklist | Entries | Stops | News context" },
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
        <div className="market-status bg-[#141415] border border-[#2d2d2d] rounded-xl">
          <div className={`status-dot ${isMarketOpen() ? 'open' : 'closed'}`} />
          <div className="font-mono uppercase tracking-wider text-[10px] text-[#6e6e73]">NSE: {isMarketOpen() ? 'OPEN' : 'CLOSED'}</div>
        </div>
        <div className="market-status bg-[#141415] border border-[#2d2d2d] rounded-xl">
          <div className="status-dot open" />
          <div className="font-mono uppercase tracking-wider text-[10px] text-[#6e6e73]">Ensemble: Active</div>
        </div>
        <div className="market-status bg-[#141415] border border-[#2d2d2d] rounded-xl">
          <div className="status-dot closed" />
          <div className="font-mono uppercase tracking-wider text-[10px] text-[#6e6e73]">Data: {new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</div>
        </div>
      </div>
    </aside>
  );
}

export default function App() {
  const [tab, setTab] = useState<Tab>("OVERVIEW");
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
            <span className="text-[#86868b] font-bold text-[10px] tracking-widest uppercase">{PAGE_META[tab].subtitle}</span>
            {portfolio && <span className="text-[10px] bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 px-2 py-0.5 rounded-full font-semibold">{portfolio.allocations.length} live picks</span>}
          </div>
        </header>

        <main className="app-main">
          {tab === "OVERVIEW" && <OverviewTab />}
          {tab === "MARKET" && <MarketTab />}
          {tab === "PORTFOLIO" && <PortfolioWorkspace onPortfolioGenerated={setPortfolio} portfolio={portfolio} />}
          {tab === "IDEAS" && <TradeIdeasTab portfolio={portfolio} />}
          {tab === "BACKTEST" && <BacktestTab portfolio={portfolio} />}
          {tab === "COMPARE" && <CompareTab />}
        </main>
      </div>
    </div>
  );
}
