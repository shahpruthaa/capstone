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
                        {portfolio?.mandate && (
                            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600">
                                Backtest source: replaying the exact generated mandate rather than a generic risk profile.
                                <div className="mt-2 text-[11px] text-slate-500">
                                    {portfolio.mandate.risk_attitude.replace('_', ' ')} · {portfolio.mandate.investment_horizon_weeks} weeks · {portfolio.mandate.preferred_num_positions} positions · {portfolio.mandate.allow_small_caps ? 'small caps allowed' : 'small caps excluded'}
                                </div>
                            </div>
                        )}
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

                        <div>
                            <label className="block text-xs font-semibold text-slate-500 mb-1">
                                Expected-Return Engine
                            </label>
                            <select
                                value={selectedModelVariant}
                                onChange={e => setSelectedModelVariant(e.target.value as ModelVariant)}
                                className="input-field px-3 py-2 text-sm"
                            >
                                <option value="RULES">Rules only</option>
                                <option value="LIGHTGBM_HYBRID">Ensemble runtime</option>
                            </select>
                            {activeModelVariant === 'LIGHTGBM_HYBRID' && selectedModelVariant === 'LIGHTGBM_HYBRID' && (
                                <p className="text-[10px] text-slate-400 mt-1 italic">Uses full or degraded ensemble runtime depending on artifact readiness; falls back to rules if the core artifact is missing.</p>
                            )}
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

                        <div className="card p-5">
                            <p className="section-title">Model Runtime</p>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                                <div className="stat-row">
                                    <span className="stat-label">Variant</span>
                                    <span className="stat-value">{result.modelVariant || selectedModelVariant}</span>
                                </div>
                                <div className="stat-row">
                                    <span className="stat-label">Source</span>
                                    <span className="stat-value">{result.modelSource || 'RULES'}</span>
                                </div>
                                <div className="stat-row">
                                    <span className="stat-label">Mode</span>
                                    <span className="stat-value">{result.activeMode || 'rules_only'}</span>
                                </div>
                                <div className="stat-row">
                                    <span className="stat-label">Version</span>
                                    <span className="stat-value">{result.modelVersion || 'rules'}</span>
                                </div>
                                <div className="stat-row">
                                    <span className="stat-label">Horizon</span>
                                    <span className="stat-value">{result.predictionHorizonDays || 21}D</span>
                                </div>
                                <div className="stat-row">
                                    <span className="stat-label">Artifact</span>
                                    <span className="stat-value">{result.artifactClassification || 'missing'}</span>
                                </div>
                            </div>
                        </div>

                        {portfolio?.mandate && (
                            <div className="card p-5">
                                <p className="section-title">Mandate Replay</p>
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                                    <div className="stat-row">
                                        <span className="stat-label">Attitude</span>
                                        <span className="stat-value">{portfolio.mandate.risk_attitude.replace('_', ' ')}</span>
                                    </div>
                                    <div className="stat-row">
                                        <span className="stat-label">Horizon</span>
                                        <span className="stat-value">{portfolio.mandate.investment_horizon_weeks} weeks</span>
                                    </div>
                                    <div className="stat-row">
                                        <span className="stat-label">Positions</span>
                                        <span className="stat-value">{portfolio.mandate.preferred_num_positions}</span>
                                    </div>
                                    <div className="stat-row">
                                        <span className="stat-label">Small Caps</span>
                                        <span className="stat-value">{portfolio.mandate.allow_small_caps ? 'Allowed' : 'Excluded'}</span>
                                    </div>
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
