import React, { useMemo, useState } from 'react';
import {
    PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend,
    BarChart, Bar, XAxis, YAxis, CartesianGrid
} from 'recharts';
import { ArrowRight, Calculator, Info, RefreshCw, Zap, ShieldCheck, TrendingUp } from 'lucide-react';
import { generatePortfolio, calculateTransactionCosts, RiskProfile, Portfolio } from '../services/portfolioService';
import { generatePortfolioViaApi } from '../services/backendApi';
import { generatePortfolioInsight } from '../services/localAdvisor';
import { MetricCard, SectorChip } from './MetricCard';

const COLORS = ['#14b8a6', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316', '#10b981', '#6366f1', '#84cc16', '#f43f5e', '#0ea5e9', '#a855f7'];

interface Props { onPortfolioGenerated: (p: Portfolio) => void; portfolio: Portfolio | null; }

function AIInsightPanel({ portfolio }: { portfolio: Portfolio }) {
    const [insight, setInsight] = useState('');
    const [loading, setLoading] = useState(false);

    const generate = async () => {
        setLoading(true);
        try {
            await new Promise(resolve => setTimeout(resolve, 250));
            setInsight(generatePortfolioInsight(portfolio));
        } catch {
            setInsight('Local insight engine could not generate analysis.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="card p-5" style={{ background: 'linear-gradient(135deg,#f0fdf9,#e0f2fe)', borderColor: '#99f6de' }}>
            <div className="flex items-center gap-2 mb-2">
                <Zap className="w-4 h-4 text-teal-600" />
                <h3 className="font-bold text-sm text-teal-800">Local Quant Insights</h3>
            </div>
            {insight ? (
                <p className="text-sm text-slate-700 leading-relaxed italic mb-3">"{insight}"</p>
            ) : (
                <p className="text-sm text-slate-500 mb-3">Generate a local rules-based analysis of your portfolio.</p>
            )}
            <button onClick={generate} disabled={loading} className="btn-primary px-4 py-2 text-xs flex items-center gap-2">
                {loading ? <RefreshCw className="w-3 h-3 spin" /> : <RefreshCw className="w-3 h-3" />}
                {insight ? 'Regenerate' : 'Generate Analysis'}
            </button>
        </div>
    );
}

export function GenerateTab({ onPortfolioGenerated, portfolio }: Props) {
    const [amount, setAmount] = useState(500000);
    const [risk, setRisk] = useState<RiskProfile>('LOW_RISK');
    const [generating, setGenerating] = useState(false);
    const [generationNotice, setGenerationNotice] = useState<{ tone: 'info' | 'warning'; text: string } | null>(null);

    const handleGenerate = async () => {
        setGenerating(true);
        setGenerationNotice(null);
        try {
            const p = await generatePortfolioViaApi(amount, risk);
            onPortfolioGenerated(p);
            setGenerationNotice({ tone: 'info', text: 'Using the database-backed portfolio generator with historical NSE data.' });
        } catch (error) {
            onPortfolioGenerated(generatePortfolio(amount, risk));
            setGenerationNotice({
                tone: 'warning',
                text: `API fallback engaged: ${error instanceof Error ? error.message : 'Unable to reach the backend.'} Showing the local heuristic portfolio instead.`,
            });
        } finally {
            setGenerating(false);
        }
    };

    const chartData = useMemo(() =>
        portfolio?.allocations.map(a => ({ name: a.stock.symbol, value: a.amount })) ?? [], [portfolio]);

    const sectorData = useMemo(() => {
        if (!portfolio) return [];
        const s: Record<string, number> = {};
        portfolio.allocations.forEach(a => { s[a.stock.sector] = (s[a.stock.sector] || 0) + a.amount; });
        return Object.entries(s).map(([name, value]) => ({ name, value }));
    }, [portfolio]);

    const costs = useMemo(() =>
        portfolio ? calculateTransactionCosts(portfolio.totalInvested, true) : null, [portfolio]);

    const riskOpts = [
        { id: 'NO_RISK', label: 'Ultra-Safe', icon: <ShieldCheck className="w-5 h-5" />, desc: 'Capital Preservation' },
        { id: 'LOW_RISK', label: 'Balanced', icon: <TrendingUp className="w-5 h-5" />, desc: 'Growth + Stability' },
        { id: 'HIGH_RISK', label: 'Aggressive', icon: <Zap className="w-5 h-5" />, desc: 'Maximum Growth' },
    ] as const;

    return (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 animate-fade-in">
            <div className="lg:col-span-4 space-y-5">
                <div className="card p-6">
                    <h2 className="font-bold text-base flex items-center gap-2 mb-5">
                        <Calculator className="w-4 h-4 text-teal-600" /> Investment Parameters
                    </h2>

                    <div className="space-y-5">
                        {generationNotice && (
                            <div className={generationNotice.tone === 'info' ? 'alert-info text-xs' : 'alert-warning text-xs'}>
                                {generationNotice.text}
                            </div>
                        )}
                        <div>
                            <label className="block text-xs font-600 text-slate-500 mb-1.5">Investment Amount (Rs)</label>
                            <input
                                type="number"
                                value={amount}
                                onChange={e => setAmount(Number(e.target.value))}
                                className="input-field px-4 py-2.5"
                                placeholder="e.g. 500000"
                            />
                            <p className="text-xs text-slate-400 mt-1">
                                Approx. Rs {(amount / 100000).toFixed(1)}L
                            </p>
                        </div>

                        <div>
                            <label className="block text-xs font-600 text-slate-500 mb-2">Risk Preference</label>
                            <div className="grid grid-cols-3 gap-2">
                                {riskOpts.map(r => (
                                    <button
                                        key={r.id}
                                        onClick={() => setRisk(r.id)}
                                        className={`risk-btn ${risk === r.id ? 'active-risk' : ''}`}
                                    >
                                        {r.icon}
                                        <span>{r.label}</span>
                                        <span className="text-[9px] font-normal normal-case tracking-normal text-slate-400">{r.desc}</span>
                                    </button>
                                ))}
                            </div>
                        </div>

                        <button onClick={handleGenerate} disabled={generating} className="btn-primary w-full py-3 text-sm flex items-center justify-center gap-2">
                            {generating ? 'Generating...' : 'Generate AI Portfolio'} <ArrowRight className="w-4 h-4" />
                        </button>
                    </div>
                </div>

                {portfolio && (
                    <>
                        {portfolio.backendNotes && portfolio.backendNotes.length > 0 && (
                            <div className="card p-5">
                                <h3 className="font-bold text-sm mb-3 text-slate-900">Backend Model Notes</h3>
                                <div className="space-y-2">
                                    {portfolio.backendNotes.map((note, index) => (
                                        <p key={index} className="text-xs text-slate-600 leading-relaxed">
                                            {note}
                                        </p>
                                    ))}
                                </div>
                            </div>
                        )}

                        <AIInsightPanel portfolio={portfolio} />

                        <div className="card p-5">
                            <h3 className="font-bold text-sm flex items-center gap-2 mb-4">
                                <Info className="w-4 h-4 text-blue-500" /> Transaction Costs
                            </h3>
                            <div className="space-y-1">
                                {[
                                    ['Brokerage', `Rs ${costs!.brokerage.toFixed(2)}`],
                                    ['STT (0.1%)', `Rs ${costs!.stt.toFixed(2)}`],
                                    ['Stamp Duty', `Rs ${costs!.stampDuty.toFixed(2)}`],
                                    ['GST on Brokerage', `Rs ${costs!.gst.toFixed(2)}`],
                                    ['Slippage (0.1%)', `Rs ${(portfolio.totalInvested * 0.001).toFixed(2)}`],
                                ].map(([k, v]) => (
                                    <div key={k} className="stat-row">
                                        <span className="stat-label text-xs">{k}</span>
                                        <span className="stat-value text-xs text-rose-500">{v}</span>
                                    </div>
                                ))}
                                <div className="stat-row" style={{ fontWeight: 700 }}>
                                    <span className="stat-label text-xs font-bold">Total Charges</span>
                                    <span className="text-rose-600 font-bold text-xs">Rs {costs!.total.toFixed(2)}</span>
                                </div>
                            </div>
                            <p className="text-[10px] text-slate-400 mt-3 italic">Stop-loss: 15% trailing, STCG: 20%, LTCG: 12.5%</p>
                        </div>
                    </>
                )}
            </div>

            <div className="lg:col-span-8 space-y-5">
                {!portfolio ? (
                    <div className="card flex flex-col items-center justify-center text-slate-400 p-16 border-2 border-dashed" style={{ minHeight: '400px' }}>
                        <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mb-4">
                            <TrendingUp className="w-8 h-8 opacity-30" />
                        </div>
                        <p className="text-base font-semibold mb-1">Enter amount and select risk mode</p>
                        <p className="text-sm">The generator will diversify across sectors to reduce correlation risk.</p>
                    </div>
                ) : (
                    <>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            <MetricCard label="Total Invested" value={`Rs ${(portfolio.totalInvested / 100000).toFixed(2)}L`} sub="After rounding to whole shares" color="slate" />
                            <MetricCard label="Portfolio Beta" value={portfolio.metrics.avgBeta.toFixed(2)} sub="vs Nifty 50 = 1.00" color={portfolio.metrics.avgBeta > 1.3 ? 'red' : portfolio.metrics.avgBeta < 0.8 ? 'green' : 'blue'} trend={portfolio.metrics.avgBeta > 1.3 ? 'up' : 'down'} />
                            <MetricCard label="Sharpe Ratio" value={portfolio.metrics.sharpeRatio.toFixed(2)} sub="Risk-free rate: 7% pa" color={portfolio.metrics.sharpeRatio > 1.2 ? 'green' : 'amber'} trend="up" />
                            <MetricCard label="Exp. Annual Return" value={`${portfolio.metrics.estimatedAnnualReturn.toFixed(1)}%`} sub={`Volatility: ${portfolio.metrics.estimatedVolatility.toFixed(1)}%`} color="green" trend="up" />
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                            <div className="card p-5">
                                <p className="section-title">Stock Allocation</p>
                                <div className="h-56">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <PieChart>
                                            <Pie data={chartData} innerRadius={50} outerRadius={75} paddingAngle={4} dataKey="value">
                                                {chartData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                                            </Pie>
                                            <Tooltip formatter={(v: number) => [`Rs ${v.toLocaleString()}`, 'Amount']} />
                                            <Legend iconSize={8} iconType="circle" />
                                        </PieChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>

                            <div className="card p-5">
                                <p className="section-title">Sector Diversification</p>
                                <div className="h-56">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart data={sectorData} layout="vertical" margin={{ left: 60 }}>
                                            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                                            <XAxis type="number" hide />
                                            <YAxis dataKey="name" type="category" fontSize={10} width={56} />
                                            <Tooltip formatter={(v: number) => [`Rs ${v.toLocaleString()}`]} />
                                            <Bar dataKey="value" fill="#14b8a6" radius={[0, 6, 6, 0]} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        </div>

                        <div className="card overflow-hidden">
                            <div className="overflow-x-auto">
                                <table className="data-table">
                                    <thead>
                                        <tr>
                                            <th>Stock</th><th>Sector</th><th>Wt%</th><th>Beta</th><th>Shares</th><th className="text-right">Amount</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {portfolio.allocations.map((a, i) => (
                                            <tr key={i}>
                                                <td>
                                                    <div className="font-semibold text-slate-900">{a.stock.symbol}</div>
                                                    <div className="text-xs text-slate-400">{a.stock.name}</div>
                                                </td>
                                                <td><SectorChip sector={a.stock.sector} /></td>
                                                <td>
                                                    <div className="flex items-center gap-2">
                                                        <div className="progress-bar-track w-12">
                                                            <div className="progress-bar-fill" style={{ width: `${a.weight}%`, background: '#14b8a6' }} />
                                                        </div>
                                                        <span className="font-mono text-xs">{a.weight}%</span>
                                                    </div>
                                                </td>
                                                <td><span className={`badge ${a.stock.beta > 1.3 ? 'badge-red' : a.stock.beta < 0.8 ? 'badge-green' : 'badge-blue'}`}>{a.stock.beta}</span></td>
                                                <td className="font-mono text-sm">{a.shares}</td>
                                                <td className="text-right font-semibold font-mono">Rs {a.amount.toLocaleString()}</td>
                                            </tr>
                                        ))}
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
