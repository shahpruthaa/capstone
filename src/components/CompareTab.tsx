import React, { useEffect, useState } from 'react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
    ResponsiveContainer, LineChart, Line
} from 'recharts';
import { Award, TrendingUp, ShieldCheck, Zap } from 'lucide-react';
import { getComparisonResult, BenchmarkStrategy, ComparisonResult } from '../services/benchmarkService';
import { getBenchmarkComparisonViaApi } from '../services/backendApi';

const TYPE_COLORS: Record<string, string> = { AI: '#14b8a6', INDEX: '#3b82f6', QUANT: '#8b5cf6', PASSIVE: '#f59e0b' };
const TYPE_BADGES: Record<string, string> = { AI: 'badge-green', INDEX: 'badge-blue', QUANT: 'badge-purple', PASSIVE: 'badge-amber' };

function StrategyCard({ s, isWinner }: { s: BenchmarkStrategy; isWinner: boolean }) {
    return (
        <div className={`card p-5 transition-all ${isWinner ? 'ring-2 ring-teal-400 ring-offset-2' : ''}`}>
            <div className="flex items-start justify-between mb-3">
                <div>
                    <div className="flex items-center gap-2">
                        <p className="font-bold text-sm text-slate-900">{s.name}</p>
                        {isWinner && <Award className="w-4 h-4 text-amber-500" />}
                    </div>
                    <span className={`badge ${TYPE_BADGES[s.type]} mt-1`}>{s.type}</span>
                </div>
                <div className="text-right">
                    <p className="text-xl font-bold text-emerald-600">+{s.annualReturn}%</p>
                    <p className="text-xs text-slate-400">Annual Return</p>
                </div>
            </div>
            <p className="text-xs text-slate-500 mb-4 leading-relaxed">{s.description}</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                {[
                    ['Volatility', `${s.volatility}%`],
                    ['Max Drawdown', `${s.maxDrawdown}%`],
                    ['Sharpe', s.sharpe.toFixed(2)],
                    ['Sortino', s.sortino.toFixed(2)],
                    ['5Y CAGR', `${s.cagr5Y}%`],
                    ['Expense', `${s.expenseRatio}%`],
                ].map(([k, v]) => (
                    <div key={k} className="stat-row">
                        <span className="stat-label text-xs">{k}</span>
                        <span className="stat-value text-xs font-mono">{v}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}

export function CompareTab() {
    const [cmp, setCmp] = useState<ComparisonResult>(() => getComparisonResult(500000));
    const [loading, setLoading] = useState(true);
    const [compareNotice, setCompareNotice] = useState<{ tone: 'info' | 'warning'; text: string } | null>(null);

    useEffect(() => {
        let active = true;
        setLoading(true);
        setCompareNotice(null);
        getBenchmarkComparisonViaApi()
            .then(result => {
                if (active) {
                    setCmp(result);
                    setCompareNotice({ tone: 'info', text: 'Benchmark metrics are being served from the backend research layer.' });
                }
            })
            .catch((error) => {
                if (active) {
                    setCmp(getComparisonResult(500000));
                    setCompareNotice({
                        tone: 'warning',
                        text: `API fallback engaged: ${error instanceof Error ? error.message : 'Backend benchmark service is unavailable.'} Showing the local benchmark comparison instead.`,
                    });
                }
            })
            .finally(() => {
                if (active) setLoading(false);
            });
        return () => {
            active = false;
        };
    }, []);

    const barData = cmp.strategies.map(s => ({
        name: s.name.replace(' Portfolio', '').replace(' Factor', '').slice(0, 12),
        Return: s.annualReturn,
        Drawdown: s.maxDrawdown,
        Sharpe: +(s.sharpe * 10).toFixed(1),
    }));

    const growthCurve = cmp.projectedGrowth.filter(r => r.year % 2 === 0 || r.year === 1 || r.year === 10);

    const KEY_STRATEGIES = ['NSE AI Portfolio', 'Nifty 50 Index', 'Markowitz MVO', 'Momentum Factor'];
    const LINE_COLORS = ['#14b8a6', '#94a3b8', '#8b5cf6', '#f59e0b'];

    return (
        <div className="space-y-8 animate-fade-in">
            {/* Header */}
            <div className="card p-6" style={{ background: 'linear-gradient(135deg,#f0fdf9,#eff6ff)' }}>
                <div className="flex items-center gap-3 mb-2">
                    <div className="w-10 h-10 rounded-xl bg-teal-100 flex items-center justify-center">
                        <TrendingUp className="w-5 h-5 text-teal-700" />
                    </div>
                    <div>
                        <h2 className="font-bold text-lg text-slate-900">Industry Benchmark Comparison</h2>
                        <p className="text-sm text-slate-500">AI Portfolio vs Standard Indian Market Strategies · Simulated Results</p>
                    </div>
                </div>
                <div className="alert-info mt-3 text-xs">
                    <strong>Disclaimer:</strong> Results are simulated using factor-model estimates, not live historical data. Actual returns will vary. Past performance does not guarantee future results. Consult a SEBI-registered advisor.
                </div>
                {compareNotice && (
                    <div className={`${compareNotice.tone === 'info' ? 'alert-info' : 'alert-warning'} mt-3 text-xs`}>
                        {compareNotice.text}
                    </div>
                )}
            </div>

            {loading && (
                <div className="card p-5 text-sm text-slate-500">
                    Loading benchmark comparison from the backend research service...
                </div>
            )}

            {/* Strategy cards grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {cmp.strategies.map(s => (
                    <StrategyCard key={s.name} s={s} isWinner={s.name === cmp.winner} />
                ))}
            </div>

            {/* Bar comparison charts */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="card p-5">
                    <p className="section-title">Annual Return vs Max Drawdown</p>
                    <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={barData} margin={{ bottom: 30 }}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                <XAxis dataKey="name" fontSize={9} angle={-25} textAnchor="end" />
                                <YAxis fontSize={10} unit="%" />
                                <Tooltip formatter={(v: number, n: string) => [`${v}%`, n]} />
                                <Legend />
                                <Bar dataKey="Return" name="Annual Return %" fill="#14b8a6" radius={[4, 4, 0, 0]} />
                                <Bar dataKey="Drawdown" name="Max Drawdown %" fill="#f43f5e" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                <div className="card p-5">
                    <p className="section-title">Sharpe Ratio × 10 (Risk-Adjusted)</p>
                    <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={barData} margin={{ bottom: 30 }}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                <XAxis dataKey="name" fontSize={9} angle={-25} textAnchor="end" />
                                <YAxis fontSize={10} />
                                <Tooltip />
                                <Bar dataKey="Sharpe" name="Sharpe ×10" radius={[4, 4, 0, 0]}>
                                    {barData.map((_, i) => {
                                        const colors = ['#14b8a6', '#94a3b8', '#3b82f6', '#f59e0b', '#8b5cf6', '#f43f5e', '#10b981'];
                                        return <rect key={i} fill={colors[i % colors.length]} />;
                                    })}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>

            {/* Projected Growth Curve */}
            <div className="card p-5">
                <p className="section-title">₹5L Projected Growth over 10 Years (Net of Expenses)</p>
                <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={growthCurve}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                            <XAxis dataKey="year" fontSize={11} label={{ value: 'Years', position: 'insideBottom', offset: -5, fontSize: 11 }} />
                            <YAxis fontSize={10} tickFormatter={v => `₹${(v / 100000).toFixed(0)}L`} />
                            <Tooltip formatter={(v: number) => [`₹${(v / 100000).toFixed(2)}L`]} labelFormatter={l => `Year ${l}`} />
                            <Legend />
                            {KEY_STRATEGIES.map((name, i) => (
                                <Line
                                    key={name}
                                    type="monotone"
                                    dataKey={name}
                                    stroke={LINE_COLORS[i]}
                                    strokeWidth={name === 'NSE AI Portfolio' ? 3 : 1.5}
                                    dot={false}
                                    strokeDasharray={name === 'Nifty 50 Index' ? '5 5' : undefined}
                                />
                            ))}
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Metrics comparison table */}
            <div className="card overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Strategy</th><th>Type</th><th>Annual Ret%</th><th>Volatility%</th>
                                <th>Sharpe</th><th>Sortino</th><th>Max DD%</th><th>5Y CAGR%</th><th>Expense%</th>
                            </tr>
                        </thead>
                        <tbody>
                            {cmp.strategies.map(s => (
                                <tr key={s.name} className={s.name === cmp.winner ? 'bg-teal-50' : ''}>
                                    <td>
                                        <div className="flex items-center gap-2 font-semibold">
                                            {s.name === cmp.winner && <Award className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />}
                                            {s.name}
                                        </div>
                                    </td>
                                    <td><span className={`badge ${TYPE_BADGES[s.type]}`}>{s.type}</span></td>
                                    <td className="text-emerald-600 font-mono font-semibold">{s.annualReturn}%</td>
                                    <td className="font-mono">{s.volatility}%</td>
                                    <td className={`font-mono font-semibold ${s.sharpe > 1.3 ? 'text-emerald-600' : s.sharpe > 1 ? 'text-blue-600' : 'text-slate-500'}`}>{s.sharpe.toFixed(2)}</td>
                                    <td className="font-mono">{s.sortino.toFixed(2)}</td>
                                    <td className="text-rose-500 font-mono">{s.maxDrawdown}%</td>
                                    <td className="font-mono">{s.cagr5Y}%</td>
                                    <td className="font-mono text-slate-400">{s.expenseRatio}%</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
