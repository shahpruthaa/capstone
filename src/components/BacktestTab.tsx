import React, { useState, useMemo } from 'react';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
    ResponsiveContainer, ReferenceLine
} from 'recharts';
import { Play, Settings, TrendingUp, TrendingDown, Minus, AlertTriangle, IndianRupee } from 'lucide-react';
import { Portfolio } from '../services/portfolioService';
import { runBacktest, BacktestConfig, BacktestResult } from '../services/backtestEngine';
import { runBacktestViaApi } from '../services/backendApi';
import { MetricCard } from './MetricCard';

interface Props { portfolio: Portfolio | null; }

const DEFAULT_CONFIG: BacktestConfig = {
    startDate: '2022-01-01',
    endDate: '2025-01-01',
    stopLossPct: 0.15,
    takeProfitPct: 0.40,
    rebalanceFreq: 'Quarterly',
    slippagePct: 0.001,
};

function fmt(n: number, dec = 2) { return n.toFixed(dec); }
function fmtRs(n: number) { return `₹${Math.abs(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`; }

export function BacktestTab({ portfolio }: Props) {
    const [config, setConfig] = useState<BacktestConfig>(DEFAULT_CONFIG);
    const [result, setResult] = useState<BacktestResult | null>(null);
    const [running, setRunning] = useState(false);
    const [runNotice, setRunNotice] = useState<{ tone: 'info' | 'warning'; text: string } | null>(null);

    const handleRun = async () => {
        if (!portfolio) return;
        setRunning(true);
        setRunNotice(null);
        try {
            setResult(await runBacktestViaApi(portfolio, config));
            setRunNotice({ tone: 'info', text: 'Using the backend historical replay with persisted market data and tax-cost logic.' });
        } catch (error) {
            setResult(runBacktest(portfolio, config));
            setRunNotice({
                tone: 'warning',
                text: `API fallback engaged: ${error instanceof Error ? error.message : 'Backend backtest is unavailable.'} Showing the local simulation instead.`,
            });
        } finally {
            setRunning(false);
        }
    };

    const totalReturnColor = result ? (result.totalReturn >= 0 ? 'green' : 'red') : 'slate';
    const cagrColor = result ? (result.cagr >= 0 ? 'green' : 'red') : 'slate';

    return (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 animate-fade-in">
            {/* Config sidebar */}
            <div className="lg:col-span-3 space-y-5">
                <div className="card p-5">
                    <h2 className="font-bold text-sm flex items-center gap-2 mb-5">
                        <Settings className="w-4 h-4 text-teal-600" /> Simulation Config
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
                        <div>
                            <label className="block text-xs font-semibold text-slate-500 mb-1">Start Date</label>
                            <input type="date" value={config.startDate} onChange={e => setConfig(c => ({ ...c, startDate: e.target.value }))} className="input-field px-3 py-2 text-sm" />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-500 mb-1">End Date</label>
                            <input type="date" value={config.endDate} onChange={e => setConfig(c => ({ ...c, endDate: e.target.value }))} className="input-field px-3 py-2 text-sm" />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-500 mb-1">
                                Stop Loss: {(config.stopLossPct * 100).toFixed(0)}%
                            </label>
                            <input type="range" min={5} max={30} step={1} value={config.stopLossPct * 100} onChange={e => setConfig(c => ({ ...c, stopLossPct: +e.target.value / 100 }))} className="w-full" />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-500 mb-1">
                                Take Profit: {(config.takeProfitPct * 100).toFixed(0)}%
                            </label>
                            <input type="range" min={10} max={80} step={5} value={config.takeProfitPct * 100} onChange={e => setConfig(c => ({ ...c, takeProfitPct: +e.target.value / 100 }))} className="w-full" />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-500 mb-1">Rebalancing</label>
                            <select
                                value={config.rebalanceFreq}
                                onChange={e => setConfig(c => ({ ...c, rebalanceFreq: e.target.value as BacktestConfig['rebalanceFreq'] }))}
                                className="input-field px-3 py-2 text-sm"
                            >
                                {(['Monthly', 'Quarterly', 'Annually', 'None'] as const).map(f => (
                                    <option key={f} value={f}>{f}</option>
                                ))}
                            </select>
                        </div>

                        <button onClick={handleRun} disabled={!portfolio || running} className="btn-primary w-full py-2.5 text-sm flex items-center justify-center gap-2">
                            {running ? (
                                <><span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full spin" /> Running...</>
                            ) : (
                                <><Play className="w-4 h-4" /> Run Backtest</>
                            )}
                        </button>
                    </div>
                </div>

                {/* Indian Tax Summary */}
                {result && (
                    <div className="card p-5">
                        <h3 className="font-bold text-sm flex items-center gap-2 mb-4">
                            <IndianRupee className="w-4 h-4 text-amber-600" /> Tax Liability
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
                        <p className="text-[10px] text-slate-400 mt-2 italic">LTCG exempt up to ₹1.25L pa. Budget 2024 rates.</p>

                        <div className="mt-4 pt-3 border-t border-slate-100">
                            <p className="text-xs font-semibold text-slate-500 mb-2">Transaction Costs</p>
                            {[
                                ['Brokerage', fmtRs(result.costBreakdown.totalBrokerage)],
                                ['STT', fmtRs(result.costBreakdown.totalSTT)],
                                ['Exchange Txn', fmtRs(result.costBreakdown.totalExchangeTxn)],
                                ['SEBI Fees', fmtRs(result.costBreakdown.totalSebiFees)],
                                ['Stamp Duty', fmtRs(result.costBreakdown.totalStampDuty)],
                                ['GST', fmtRs(result.costBreakdown.totalGST)],
                                ['Slippage', fmtRs(result.costBreakdown.totalSlippage)],
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
                    <div className="card flex flex-col items-center justify-center text-slate-400 p-16 border-2 border-dashed" style={{ minHeight: '480px' }}>
                        <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mb-4">
                            <TrendingUp className="w-8 h-8 opacity-30" />
                        </div>
                        <p className="text-base font-semibold mb-1">{portfolio ? 'Configure & run backtest' : 'Generate a portfolio first'}</p>
                        <p className="text-sm">Historical replay with Indian market frictions, taxes, and benchmark comparison.</p>
                    </div>
                ) : (
                    <>
                        {result.notes && result.notes.length > 0 && (
                            <div className="card p-5">
                                <p className="section-title">Backend Simulation Notes</p>
                                <div className="space-y-2">
                                    {result.notes.map((note, index) => (
                                        <p key={index} className="text-xs text-slate-600 leading-relaxed">{note}</p>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Key metrics */}
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
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
                                sub="Compounded Annual Growth"
                                color={cagrColor}
                                trend={result.cagr >= 0 ? 'up' : 'down'}
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
                                sub="Peak-to-trough decline"
                                color={result.maxDrawdown < 12 ? 'green' : result.maxDrawdown < 20 ? 'amber' : 'red'}
                                trend="down"
                            />
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            <MetricCard label="Sortino Ratio" value={fmt(result.sortino)} sub="Downside risk adj." color={result.sortino > 1 ? 'green' : 'amber'} />
                            <MetricCard label="Calmar Ratio" value={fmt(result.calmar)} sub="CAGR / Max Drawdown" color={result.calmar > 1 ? 'green' : 'amber'} />
                            <MetricCard label="Win Rate" value={`${fmt(result.winRate, 1)}%`} sub="Positive return days" color={result.winRate > 52 ? 'green' : 'red'} />
                            <MetricCard label="Total Trades" value={result.totalTrades} sub="Stop-loss + Take-profit + Rebalancing" />
                        </div>

                        {/* Equity Curve */}
                        <div className="card p-5">
                            <p className="section-title">Equity Curve vs Nifty 50 Benchmark</p>
                            <div className="h-72">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={result.equityCurve} margin={{ right: 20 }}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                        <XAxis dataKey="date" fontSize={10} tickFormatter={d => d.slice(2, 7)} />
                                        <YAxis fontSize={10} tickFormatter={v => `₹${(v / 1000).toFixed(0)}K`} />
                                        <Tooltip
                                            formatter={(v: number, name: string) => [fmtRs(v), name]}
                                            labelFormatter={l => `Date: ${l}`}
                                        />
                                        <Legend />
                                        <ReferenceLine y={result.initialInvestment} stroke="#94a3b8" strokeDasharray="4 4" label={{ value: 'Invested', fill: '#94a3b8', fontSize: 10 }} />
                                        <Line type="monotone" dataKey="value" name="AI Portfolio" stroke="#14b8a6" strokeWidth={2.5} dot={false} />
                                        <Line type="monotone" dataKey="benchmark" name="Nifty Benchmark" stroke="#94a3b8" strokeWidth={1.5} dot={false} strokeDasharray="5 5" />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
