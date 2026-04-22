import { useEffect, useState } from "react";
import { Home, PieChart, Lightbulb, FlaskConical, GitCompare, Activity } from "lucide-react";
import "./index.css";
import { Portfolio } from "./services/portfolioService";
import { BacktestTab } from "./components/BacktestTab";
import { CompareTab } from "./components/CompareTab";
import { TradeIdeasTab } from "./components/TradeIdeasTab";
import { MarketTab } from "./components/MarketTab";
import { PortfolioWorkspace } from "./components/PortfolioWorkspace";
import { OverviewTab } from "./components/OverviewTab";
import { CurrentModelStatus, getCurrentModelStatusViaApi, getMarketDataSummaryViaApi, MarketDataSummary } from "./services/backendApi";

type Tab = "OVERVIEW" | "MARKET" | "PORTFOLIO" | "IDEAS" | "BACKTEST" | "COMPARE";

const PAGE_META: Record<Tab, { title: string; subtitle: string }> = {
  OVERVIEW: { title: "Research Command Center", subtitle: "Market Regime | Signals | Portfolio Health | System Metrics" },
  MARKET: { title: "Market", subtitle: "Regime | Sectors | Factor weather | News pulse" },
  PORTFOLIO: { title: "Portfolio", subtitle: "Mandate questionnaire | Recommended basket | Holdings review" },
  IDEAS: { title: "Trade Ideas", subtitle: "Why now checklist | Entries | Stops | News context" },
  BACKTEST: { title: "Backtest", subtitle: "Replay the exact mandate portfolio vs Nifty" },
  COMPARE: { title: "Compare", subtitle: "Mandate portfolio vs Nifty and factor-style benchmarks" },
};

function Sidebar({
  tab,
  setTab,
  marketData,
  modelStatus,
}: {
  tab: Tab;
  setTab: (tab: Tab) => void;
  marketData: MarketDataSummary | null;
  modelStatus: CurrentModelStatus | null;
}) {
  const marketBadgeTone =
    marketData?.sessionStatus?.status === "OPEN" || marketData?.sessionStatus?.status === "PRE_OPEN" || marketData?.sessionStatus?.status === "POST_CLOSE"
      ? "open"
      : "closed";
  const researchBadgeTone = modelStatus?.available ? "open" : "closed";
  const dataBadgeTone = marketData?.maxTradeDate ? "open" : "closed";

  return (
    <aside className="app-sidebar">
      <div className="sidebar-logo">
        <div className="logo-mark">A</div>
        <div className="logo-text-wrap">
          <div className="logo-name">NSE Atlas</div>
          <div className="logo-tag">Portfolio research for Indian markets</div>
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
        <div className="market-status">
          <div className={`status-dot ${marketBadgeTone}`} />
          <div className="text-mono text-xs">NSE: {marketData?.sessionStatus?.label ?? "Loading"}</div>
        </div>
        <div className="market-status">
          <div className={`status-dot ${researchBadgeTone}`} />
          <div className="text-mono text-xs">Research: {modelStatus?.available ? "Ensemble live" : modelStatus ? "Rules fallback" : "Loading"}</div>
        </div>
        <div className="market-status">
          <div className={`status-dot ${dataBadgeTone}`} />
          <div className="text-mono text-xs">Data: {marketData?.maxTradeDate ?? "Unavailable"}</div>
        </div>
      </div>
    </aside>
  );
}

export default function App() {
  const [tab, setTab] = useState<Tab>("OVERVIEW");
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [marketData, setMarketData] = useState<MarketDataSummary | null>(null);
  const [modelStatus, setModelStatus] = useState<CurrentModelStatus | null>(null);

  useEffect(() => {
    let active = true;

    const loadSidebarContext = async () => {
      const [marketResult, modelResult] = await Promise.allSettled([
        getMarketDataSummaryViaApi(),
        getCurrentModelStatusViaApi(),
      ]);

      if (!active) return;
      if (marketResult.status === "fulfilled") setMarketData(marketResult.value);
      if (modelResult.status === "fulfilled") setModelStatus(modelResult.value);
    };

    void loadSidebarContext();
    const interval = window.setInterval(() => {
      void loadSidebarContext();
    }, 60_000);

    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  return (
    <div className="app-shell">
      <Sidebar tab={tab} setTab={setTab} marketData={marketData} modelStatus={modelStatus} />

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
          {tab === "PORTFOLIO" && <PortfolioWorkspace onPortfolioGenerated={setPortfolio} portfolio={portfolio} />}
          {tab === "IDEAS" && <TradeIdeasTab portfolio={portfolio} />}
          {tab === "BACKTEST" && <BacktestTab portfolio={portfolio} />}
          {tab === "COMPARE" && <CompareTab portfolio={portfolio} />}
        </main>
      </div>
    </div>
  );
}
