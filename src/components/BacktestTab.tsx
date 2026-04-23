import React, { useEffect, useMemo, useState } from 'react';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
    ResponsiveContainer, ReferenceLine
} from 'recharts';
import { Play, Settings, TrendingUp, AlertTriangle, IndianRupee } from 'lucide-react';
import { Portfolio } from '../services/portfolioService';
import { BacktestConfig, BacktestResult } from '../services/backtestEngine';
import { getCurrentModelStatusViaApi, getMarketDataSummaryViaApi, ModelVariant, runBacktestViaApi } from '../services/backendApi';
import { MetricCard } from './MetricCard';

interface Props { portfolio: Portfolio | null; }

const DEFAULT_CONFIG: BacktestConfig = {
    startDate: '2025-01-01',
    endDate: '2025-12-31',
    stopLossPct: 0.15,
    takeProfitPct: 0.40,
    rebalanceFreq: 'Quarterly',
    slippagePct: 0.001,
};

function fmt(n: number, dec = 2) { return n.toFixed(dec); }
function fmtRs(n: number) { return `₹${Math.abs(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`; }

function shiftDate(dateStr: string, days: number): string {
    const value = new Date(dateStr);
    value.setDate(value.getDate() + days);
    return value.toISOString().slice(0, 10);
}

function deriveBacktestWindow(minTradeDate: string, maxTradeDate: string): Pick<BacktestConfig, 'startDate' | 'endDate'> {
    const proposedStart = shiftDate(maxTradeDate, -330);
    return {
        startDate: proposedStart < minTradeDate ? minTradeDate : proposedStart,
        endDate: maxTradeDate,
    };
}

export function BacktestTab({ portfolio }: Props) {
    const [config, setConfig] = useState<BacktestConfig>(DEFAULT_CONFIG);
    const [result, setResult] = useState<BacktestResult | null>(null);
    const [running, setRunning] = useState(false);
    const [runNotice, setRunNotice] = useState<{ tone: 'info' | 'warning'; text: string } | null>(null);
    const [activeModelVariant, setActiveModelVariant] = useState<ModelVariant>('RULES');
    const [selectedModelVariant, setSelectedModelVariant] = useState<ModelVariant>('RULES');

    useEffect(() => {
        const loadRuntimeContext = async () => {
            try {
                const [status, marketData] = await Promise.all([
                    getCurrentModelStatusViaApi(),
                    getMarketDataSummaryViaApi(),
                ]);
                const variant: ModelVariant = status.available ? 'LIGHTGBM_HYBRID' : 'RULES';
                setActiveModelVariant(variant);
                setSelectedModelVariant(variant);
                if (marketData.available && marketData.minTradeDate && marketData.maxTradeDate) {
                    setConfig(current => ({
                        ...current,
                        ...deriveBacktestWindow(marketData.minTradeDate!, marketData.maxTradeDate!),
                    }));
                } else if (!marketData.available) {
                    setRunNotice({
                        tone: 'warning',
                        text: 'No local market data is loaded yet. Start the API and let it bootstrap from cached bhavcopy archives, or ingest data manually.',
                    });
                }
            } catch {
                setActiveModelVariant('RULES');
                setSelectedModelVariant('RULES');
            }
        };
        void loadRuntimeContext();
    }, []);

    const handleRun = async () => {
        if (!portfolio) return;
        setRunning(true);
        setRunNotice(null);
        try {
            setResult(await runBacktestViaApi(portfolio, config, selectedModelVariant));
            setRunNotice({ tone: 'info', text: 'Using the local backend historical replay with persisted market data, Indian taxes, and versioned fee logic.' });
        } catch (error) {
            setResult(null);
            setRunNotice({
                tone: 'warning',
                text: `Backtest failed: ${error instanceof Error ? error.message : 'The local backend backtest endpoint is unavailable.'}`,
            });
        } finally {
            setRunning(false);
        }
    };

    const benchmarkStats = useMemo(() => {
        if (!result || result.equityCurve.length < 2) return { return: 0, cagr: 0, mdd: 0 };
        const curve = result.equityCurve;
        const first = curve[0].benchmark;
        const last = curve[curve.length - 1].benchmark;
        
        const days = (new Date(curve[curve.length - 1].date).getTime() - new Date(curve[0].date).getTime()) / 86400000;
        const years = days / 365;
        const cagr = (Math.pow(last / first, 1 / Math.max(years, 0.1)) - 1) * 100;
        
        let peak = curve[0].benchmark;
        let maxDD = 0;
        curve.forEach(p => {
            if (p.benchmark > peak) peak = p.benchmark;
            const dd = (peak - p.benchmark) / peak;
            if (dd > maxDD) maxDD = dd;
        });
        
        return { cagr, mdd: maxDD * 100 };
    }, [result]);

    const totalReturnColor = result ? (result.totalReturn >= 0 ? 'green' : 'red') : 'slate';
    const cagrColor = result ? (result.cagr >= 0 ? 'green' : 'red') : 'slate';

    return (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 animate-fade-in">
            {/* Config sidebar */}
            <div className="lg:col-span-3 space-y-5">
                <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-5">
                    <h2 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] flex items-center gap-2 mb-5">
                        <Settings className="w-4 h-4 text-yellow-500" /> Simulation Config
                    </h2>

                    {!portfolio && (
                        <div className="alert-warning flex items-center gap-2 mb-4 text-xs">
                            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                            Generate a portfolio first.
                        </div>
                    )}

                    {runNotice && (
                        <div className={`${runNotice.tone === 'info' ? 'alert-info' : 'alert-warning'} text-xs mb-4`}>
                            {runNotice.text}
                        </div>
                    )}

                    <div className="space-y-4">
                        {portfolio?.mandate && (
                            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600">
                                Backtest source: replaying the exact generated mandate rather than a generic risk profile.
                                <div className="mt-2 text-[11px] text-slate-500">
                                    {portfolio.mandate.risk_attitude.replace('_', ' ')} · {portfolio.mandate.investment_horizon_weeks} weeks · {portfolio.mandate.preferred_num_positions} positions · {portfolio.mandate.allow_small_caps ? 'small caps allowed' : 'small caps excluded'}
                                </div>
                            </div>
                        )}
                        <div>
                            <label className="block text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-1.5">Start Date</label>
                            <input type="date" value={config.startDate} onChange={e => setConfig(c => ({ ...c, startDate: e.target.value }))} className="w-full bg-slate-50/50 border border-slate-200 rounded-xl text-slate-900 px-4 py-2.5 focus:bg-white focus:outline-none focus:ring-4 focus:ring-blue-600/10 focus:border-blue-600 transition-all font-mono text-sm" />
                        </div>
                        <div>
                            <label className="block text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-1.5">End Date</label>
                            <input type="date" value={config.endDate} onChange={e => setConfig(c => ({ ...c, endDate: e.target.value }))} className="w-full bg-slate-50/50 border border-slate-200 rounded-xl text-slate-900 px-4 py-2.5 focus:bg-white focus:outline-none focus:ring-4 focus:ring-blue-600/10 focus:border-blue-600 transition-all font-mono text-sm" />
                        </div>
                        <div>
                            <label className="block text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-1.5">
                                Stop Loss: {(config.stopLossPct * 100).toFixed(0)}%
                            </label>
                            <input type="range" min={5} max={30} step={1} value={config.stopLossPct * 100} onChange={e => setConfig(c => ({ ...c, stopLossPct: +e.target.value / 100 }))} className="w-full accent-yellow-500" />
                        </div>
                        <div>
                            <label className="block text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-1.5">
                                Take Profit: {(config.takeProfitPct * 100).toFixed(0)}%
                            </label>
                            <input type="range" min={10} max={80} step={5} value={config.takeProfitPct * 100} onChange={e => setConfig(c => ({ ...c, takeProfitPct: +e.target.value / 100 }))} className="w-full accent-yellow-500" />
                        </div>
                        <div>
                            <label className="block text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-1.5">Rebalancing</label>
                            <select
                                value={config.rebalanceFreq}
                                onChange={e => setConfig(c => ({ ...c, rebalanceFreq: e.target.value as BacktestConfig['rebalanceFreq'] }))}
                                className="w-full bg-slate-50/50 border border-slate-200 rounded-xl text-slate-900 px-4 py-2.5 focus:bg-white focus:outline-none focus:ring-4 focus:ring-blue-600/10 focus:border-blue-600 transition-all font-mono text-sm"
                            >
                                {(['Monthly', 'Quarterly', 'Annually', 'None'] as const).map(f => (
                                    <option key={f} value={f}>{f}</option>
                                ))}
                            </select>
                        </div>

                        <div>
                            <label className="block text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-1.5">
                                Expected-Return Engine
                            </label>
                            <select
                                value={selectedModelVariant}
                                onChange={e => setSelectedModelVariant(e.target.value as ModelVariant)}
                                className="w-full bg-slate-50/50 border border-slate-200 rounded-xl text-slate-900 px-4 py-2.5 focus:bg-white focus:outline-none focus:ring-4 focus:ring-blue-600/10 focus:border-blue-600 transition-all font-mono text-sm"
                            >
                                <option value="RULES">Rules only</option>
                                <option value="LIGHTGBM_HYBRID">Ensemble runtime</option>
                            </select>
                            {activeModelVariant === 'LIGHTGBM_HYBRID' && selectedModelVariant === 'LIGHTGBM_HYBRID' && (
                                <p className="text-[10px] text-[#86868B] mt-1 italic">Uses full or degraded ensemble runtime depending on artifact readiness; falls back to rules if the core artifact is missing.</p>
                            )}
                        </div>

                        <button onClick={handleRun} disabled={!portfolio || running} className="bg-yellow-500 text-black rounded-xl font-bold hover:bg-yellow-400 transition-all w-full py-3 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed">
                            {running ? (
                                <><span className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" /> Running...</>
                            ) : (
                                <><Play className="w-4 h-4" /> Run Backtest</>
                            )}
                        </button>
                    </div>
                </div>

                {/* Indian Tax Summary */}
                {result && (
                    <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-5">
                        <h3 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] flex items-center gap-2 mb-4">
                            <IndianRupee className="w-4 h-4 text-yellow-500" /> <span className="text-[#f5f5f7] font-mono font-medium">TAX LIABILITY</span>
                        </h3>
                        <div className="space-y-1">
                            {[
                                ['STCG Gains', fmtRs(result.taxLiability.stcgGain), result.taxLiability.stcgGain < 0 ? 'text-emerald-600' : 'text-rose-500'],
                                ['STCG Tax', fmtRs(result.taxLiability.stcgTax), 'text-rose-500'],
                                ['LTCG Gains', fmtRs(result.taxLiability.ltcgGain), 'text-slate-700'],
                                ['LTCG Tax', fmtRs(result.taxLiability.ltcgTax), 'text-rose-500'],
                                ['Cess', fmtRs(result.taxLiability.cessTax), 'text-rose-500'],
                                ['Total Tax', fmtRs(result.taxLiability.totalTax), 'text-rose-600 font-bold'],
                            ].map(([label, val, cls]) => (
                                <div key={label} className="stat-row">
                                    <span className="stat-label text-xs">{label}</span>
                                    <span className={`stat-value text-xs ${cls}`}>{val}</span>
                                </div>
                            ))}
                        </div>
                        <p className="text-[10px] text-[#86868B] mt-2 italic">LTCG exempt up to ₹1.25L pa. Budget 2024 rates.</p>

                        <div className="mt-4 pt-3 border-t border-slate-100">
                            <p className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-2"><span className="text-slate-900 font-mono font-medium">TRANSACTION COSTS</span></p>
                            {[
                                ['Brokerage', fmtRs(result.costBreakdown.totalBrokerage)],
                                ['STT', fmtRs(result.costBreakdown.totalSTT)],
                                ['Exchange Txn', fmtRs(result.costBreakdown.totalExchangeTxn)],
                                ['SEBI Fees', fmtRs(result.costBreakdown.totalSebiFees)],
                                ['Stamp Duty', fmtRs(result.costBreakdown.totalStampDuty)],
                                ['GST', fmtRs(result.costBreakdown.totalGST)],
                                ['Slippage', fmtRs(result.costBreakdown.totalSlippage)],
                                ['Friction Drag', `${((result.costBreakdown.totalFrictionalDragPct ?? 0) * 100).toFixed(2)}%`],
                                ['Total Costs', fmtRs(result.costBreakdown.totalCosts)],
                            ].map(([label, val]) => (
                                <div key={label} className="stat-row">
                                    <span className="stat-label text-xs">{label}</span>
                                    <span className="stat-value text-xs text-rose-400">{val}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {/* Main results area */}
            <div className="lg:col-span-9 space-y-5">
                {!result ? (
                    <div className="bg-[#0a0a0a] flex flex-col items-center justify-center text-[#86868B] p-16 border border-dashed border-[#2d2d2d] rounded-2xl" style={{ minHeight: '480px' }}>
                        <div className="w-16 h-16 rounded-full bg-[#141415] flex items-center justify-center mb-4">
                            <TrendingUp className="w-8 h-8 opacity-30 text-yellow-500" />
                        </div>
                        <p className="font-mono text-[11px] uppercase tracking-[0.08em] font-bold mb-1 text-[#86868b]">{portfolio ? 'Configure & run backtest' : 'Generate a portfolio first'}</p>
                        <p className="text-[10px] font-mono tracking-wide text-[#6e6e73]">Historical replay with Indian market frictions, taxes, and benchmark comparison.</p>
                    </div>
                ) : (
                    <>
                        {result.notes && result.notes.length > 0 && (
                            <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-5">
                                <p className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-3">Backend Simulation Notes</p>
                                <div className="space-y-2">
                                    {result.notes.map((note, index) => (
                                        <p key={index} className="text-xs text-[#86868B] font-mono leading-relaxed">{note}</p>
                                    ))}
                                </div>
                            </div>
                        )}

                        <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-5">
                            <p className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-3"><span className="text-[#f5f5f7] font-mono font-medium">MODEL RUNTIME</span></p>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                                <div className="stat-row">
                                    <span className="stat-label text-[#86868B]">Variant</span>
                                    <span className="stat-value text-[#f5f5f7] font-mono">{result.modelVariant || selectedModelVariant}</span>
                                </div>
                                <div className="stat-row">
                                    <span className="stat-label text-[#86868B]">Source</span>
                                    <span className="stat-value text-[#f5f5f7] font-mono">{result.modelSource || 'RULES'}</span>
                                </div>
                                <div className="stat-row">
                                    <span className="stat-label text-[#86868B]">Mode</span>
                                    <span className="stat-value text-[#f5f5f7] font-mono">{result.activeMode || 'rules_only'}</span>
                                </div>
                                <div className="stat-row">
                                    <span className="stat-label text-[#86868B]">Version</span>
                                    <span className="stat-value text-[#f5f5f7] font-mono">{result.modelVersion || 'rules'}</span>
                                </div>
                                <div className="stat-row">
                                    <span className="stat-label text-[#86868B]">Horizon</span>
                                    <span className="stat-value text-[#f5f5f7] font-mono">{result.predictionHorizonDays || 21}D</span>
                                </div>
                                <div className="stat-row">
                                    <span className="stat-label text-[#86868B]">Artifact</span>
                                    <span className="stat-value text-[#f5f5f7] font-mono">{result.artifactClassification || 'missing'}</span>
                                </div>
                            </div>
                        </div>

                        {portfolio?.mandate && (
                            <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-5">
                                <p className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-3"><span className="text-[#f5f5f7] font-mono font-medium">MANDATE REPLAY</span></p>
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                                    <div className="stat-row">
                                        <span className="stat-label text-[#86868B]">Attitude</span>
                                        <span className="stat-value text-[#f5f5f7] font-mono">{portfolio.mandate.risk_attitude.replace('_', ' ')}</span>
                                    </div>
                                    <div className="stat-row">
                                        <span className="stat-label text-[#86868B]">Horizon</span>
                                        <span className="stat-value text-[#f5f5f7] font-mono">{portfolio.mandate.investment_horizon_weeks} weeks</span>
                                    </div>
                                    <div className="stat-row">
                                        <span className="stat-label text-[#86868B]">Positions</span>
                                        <span className="stat-value text-[#f5f5f7] font-mono">{portfolio.mandate.preferred_num_positions}</span>
                                    </div>
                                    <div className="stat-row">
                                        <span className="stat-label text-[#86868B]">Small Caps</span>
                                        <span className="stat-value text-[#f5f5f7] font-mono">{portfolio.mandate.allow_small_caps ? 'Allowed' : 'Excluded'}</span>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Key metrics */}
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                            <MetricCard
                                label="Total Return"
                                value={`${result.totalReturn >= 0 ? '+' : ''}${fmt(result.totalReturn)}%`}
                                sub={`${fmtRs(result.finalValue - result.initialInvestment)} ${result.totalReturn >= 0 ? 'profit' : 'loss'}`}
                                color={totalReturnColor}
                                trend={result.totalReturn >= 0 ? 'up' : 'down'}
                            />
                            <MetricCard
                                label="CAGR"
                                value={`${result.cagr >= 0 ? '+' : ''}${fmt(result.cagr)}%`}
                                sub={
                                    <div className="flex flex-col gap-0.5">
                                        <span>Compounded Annual Growth</span>
                                        <span className="text-xs text-[#86868b]">vs Nifty: {fmt(benchmarkStats.cagr)}%</span>
                                    </div>
                                }
                                color={cagrColor}
                                trend={result.cagr >= 0 ? 'up' : 'down'}
                            />
                            <MetricCard
                                label="FRICTION DRAG"
                                value={`${((result?.costBreakdown?.totalFrictionalDragPct ?? 0) * 100).toFixed(2)}%`}
                                sub="Slippage, STT, brokerage impact"
                                color="purple"
                                trend="down"
                            />
                            <MetricCard
                                label="Sharpe Ratio"
                                value={fmt(result.sharpe)}
                                sub="Risk-adjusted return"
                                color={result.sharpe > 1 ? 'green' : result.sharpe > 0.5 ? 'amber' : 'red'}
                            />
                            <MetricCard
                                label="Max Drawdown"
                                value={`-${fmt(result.maxDrawdown)}%`}
                                sub={
                                    <div className="flex flex-col gap-0.5">
                                        <span>Peak-to-trough decline</span>
                                        <span className="text-xs text-[#86868b]">vs Nifty: -{fmt(benchmarkStats.mdd)}%</span>
                                    </div>
                                }
                                color={result.maxDrawdown < 12 ? 'green' : result.maxDrawdown < 20 ? 'amber' : 'red'}
                                trend="down"
                            />
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            <MetricCard label="Sortino Ratio" value={fmt(result.sortino)} sub="Downside risk adj." color={result.sortino > 1 ? 'green' : 'amber'} />
                            <MetricCard label="Calmar Ratio" value={fmt(result.calmar)} sub="CAGR / Max Drawdown" color={result.calmar > 1 ? 'green' : 'amber'} />
                            <div title="Percentage of positive daily returns">
                                <MetricCard label="Win Rate" value={`${fmt(result.winRate, 1)}%`} sub="Positive return days" color={result.winRate > 52 ? 'green' : 'red'} />
                            </div>
                            <MetricCard label="Total Trades" value={result.totalTrades} sub="Stop-loss + Take-profit + Rebalancing" />
                        </div>

                        {/* Equity Curve */}
                        <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-5">
                            <p className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-4">Equity Curve vs Nifty 50 Benchmark</p>
                            <div className="h-80">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={result.equityCurve}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#2d2d2d" />
                                        <XAxis dataKey="date" hide />
                                        <YAxis domain={['auto', 'auto']} stroke="#86868b" fontSize={10} tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`} />
                                        <Tooltip 
                                            contentStyle={{ background: '#141415', border: '1px solid #2d2d2d', color: '#f5f5f7' }}
                                            formatter={(v: number) => [`₹${v.toLocaleString()}`, 'Equity']} 
                                        />
                                        <Line type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={2} dot={false} name="AI Portfolio" />
                                        <Line type="monotone" dataKey="benchmark" stroke="#94a3b8" strokeWidth={1.5} strokeDasharray="4 4" dot={false} name="Nifty Benchmark" />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {/* Simulated Final Holdings */}
                        <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-5">
                            <p className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-4">Simulated Final Holdings</p>
                            <div className="overflow-x-auto">
                                <table className="w-full text-left border-collapse">
                                    <thead>
                                        <tr className="border-b border-[#2d2d2d]">
                                            <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] pb-3">Asset</th>
                                            <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] pb-3 text-right">Shares</th>
                                            <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] pb-3 text-right">Weight%</th>
                                            <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] pb-3 text-right">Final Value</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-[#2d2d2d]">
                                        {portfolio.allocations.map(alloc => {
                                            const weight = (alloc.amount / portfolio.totalInvested) * 100;
                                            return (
                                                <tr key={alloc.stock.symbol} className="hover:bg-[#1d1d1f] transition-colors">
                                                    <td className="py-3 font-mono font-bold text-sm text-[#f5f5f7]">{alloc.stock.symbol}</td>
                                                    <td className="py-3 text-right font-mono text-sm text-[#86868b]">{alloc.shares}</td>
                                                    <td className="py-3 text-right font-mono text-sm text-[#86868b]">{weight.toFixed(2)}%</td>
                                                    <td className="py-3 text-right font-mono text-sm text-[#f5f5f7] font-semibold">{fmtRs(alloc.amount)}</td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
