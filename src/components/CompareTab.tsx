import React, { useEffect, useState } from 'react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
    ResponsiveContainer, LineChart, Line, Cell
} from 'recharts';
import { Award, TrendingUp } from 'lucide-react';
import { BenchmarkStrategy, ComparisonResult } from '../services/benchmarkService';
import { getBenchmarkComparisonViaApi } from '../services/backendApi';

const TYPE_BADGES: Record<string, string> = { AI: 'bg-emerald-50 text-emerald-600 border border-emerald-200/50', INDEX: 'bg-blue-50 text-blue-600 border border-blue-200/50', FACTOR: 'bg-violet-50 text-violet-600 border border-violet-200/50', AMC_STYLE: 'bg-slate-100 text-slate-600 border border-slate-200/50' };
const TYPE_LABELS: Record<string, string> = { AI: 'AI', INDEX: 'Index', FACTOR: 'Factor', AMC_STYLE: 'AMC Style' };

const StrategyCard: React.FC<{ s: BenchmarkStrategy; isWinner: boolean }> = ({ s, isWinner }) => {
    return (
        <div className={`bg-white border ${isWinner ? 'border-blue-500 ring-1 ring-blue-500' : 'border-slate-200/80'} rounded-2xl shadow-[0_2px_8px_rgb(0,0,0,0.04)] p-4 transition-all`}>
            <div className="flex items-start justify-between mb-3">
                <div>
                    <div className="flex items-center gap-2">
                        <p className="font-semibold text-sm text-[#1D1D1F] font-mono">{s.name}</p>
                        {isWinner && <Award className="w-4 h-4 text-amber-500" />}
                        {s.isProxy && <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-semibold">Proxy</span>}
                    </div>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold uppercase tracking-wider mt-1 inline-block ${TYPE_BADGES[s.type]}`}>{TYPE_LABELS[s.type]}</span>
                </div>
                <div className="text-right">
                    <p className="text-xl font-bold text-emerald-600">+{s.annualReturn}%</p>
                    <p className="text-xs text-slate-600">Annual Return</p>
                </div>
            </div>
            <p className="text-xs text-[#86868B] mb-4 leading-relaxed">{s.description}</p>
            <div className="mb-4 space-y-1">
                <p className="text-[10px] text-[#86868B] font-mono uppercase tracking-wider"><span className="font-semibold text-[#1D1D1F]">Construction:</span> {s.constructionMethod}</p>
                <p className="text-[10px] text-[#86868B] font-mono uppercase tracking-wider"><span className="font-semibold text-[#1D1D1F]">Constituents:</span> {s.constituentMethod}</p>
                <p className="text-[10px] text-[#86868B] font-mono uppercase tracking-wider"><span className="font-semibold text-[#1D1D1F]">Source Window:</span> {s.sourceWindow}</p>
                <p className="text-[10px] text-[#86868B] font-mono uppercase tracking-wider">
                    <span className="font-semibold text-[#1D1D1F]">Data Source:</span> {s.sourceProvider || 'local_research'}
                    {s.sourceType === 'THIRD_PARTY' ? ' (3rd-party)' : ' (local proxy)'}
                </p>
                <p className="text-[10px] text-[#86868B] font-mono uppercase tracking-wider">
                    <span className="font-semibold text-[#1D1D1F]">Benchmark Beat Rate:</span> {(s.relativeAccuracyScorePct || 0).toFixed(1)}%
                </p>
            </div>
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
            {s.limitations.length > 0 && (
                <div className="mt-4 space-y-1">
                    {s.limitations.slice(0, 2).map((limitation) => (
                        <p key={limitation} className="text-[10px] text-[#86868B] font-mono">- {limitation}</p>
                    ))}
                </div>
            )}
        </div>
    );
};

export function CompareTab() {
    const [cmp, setCmp] = useState<ComparisonResult | null>(null);
    const [loading, setLoading] = useState(true);
    const [compareNotice, setCompareNotice] = useState<{ tone: 'info'; text: string } | null>(null);

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
                    setCompareNotice({
                        tone: 'info',
                        text: `Benchmark comparison is syncing: ${error instanceof Error ? error.message : 'The benchmark service is initializing.'}`,
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

    if (!cmp && loading) {
        return (
            <div className="space-y-8 animate-fade-in">
                <div className="bg-white border border-slate-200/80 rounded-2xl shadow-[0_2px_8px_rgb(0,0,0,0.04)] p-4 text-sm font-mono text-slate-600">
                    Loading benchmark comparison from the local backend research service...
                </div>
            </div>
        );
    }

    if (!cmp) {
        return (
            <div className="space-y-8 animate-fade-in">
                <div className="bg-white border border-slate-200/80 rounded-2xl shadow-[0_2px_8px_rgb(0,0,0,0.04)] p-4">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="w-8 h-8 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-center">
                            <TrendingUp className="w-4 h-4 text-blue-600" />
                        </div>
                        <div>
                            <h2 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em]">Industry Benchmark Comparison</h2>
                            <p className="text-[10px] text-[#86868B] font-mono mt-1">Backend benchmark service required</p>
                        </div>
                    </div>
                    {compareNotice && (
                        <p className="mt-3 text-xs text-slate-500">
                            {compareNotice.text}
                        </p>
                    )}
                </div>
            </div>
        );
    }

    const barData = cmp.strategies.map(s => ({
        name: s.name.replace(' Portfolio', '').replace(' Factor', '').slice(0, 12),
        Return: s.annualReturn,
        Drawdown: s.maxDrawdown,
        Sharpe: +(s.sharpe * 10).toFixed(1),
    }));

    const growthCurve = cmp.projectedGrowth.filter(r => r.year % 2 === 0 || r.year === 1 || r.year === 10);

    const KEY_STRATEGIES = ['NSE AI Portfolio', 'Nifty 50 Proxy', 'Nifty 500 Proxy', 'Momentum Factor'];
    const LINE_COLORS = ['#14b8a6', '#94a3b8', '#8b5cf6', '#f59e0b'];

    return (
        <div className="space-y-8 animate-fade-in">
            {/* Header */}
            <div className="bg-white border border-slate-200/80 rounded-2xl shadow-[0_2px_8px_rgb(0,0,0,0.04)] p-4">
                <div className="flex items-center gap-3 mb-2">
                    <div className="w-8 h-8 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-center">
                        <TrendingUp className="w-4 h-4 text-blue-600" />
                    </div>
                    <div>
                        <h2 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em]">Industry Benchmark Comparison</h2>
                        <p className="text-[10px] text-[#86868B] font-mono mt-1">AI Portfolio vs Standard Indian Market Strategies · Backend Research Results</p>
                    </div>
                </div>
                <p className="mt-3 text-[10px] text-[#86868B] font-mono leading-relaxed">
                    This comparison view measures realized strategy performance against industry-style proxies and shows how often each strategy matched or beat the Nifty 50 proxy on overlapping trading days.
                </p>
                {compareNotice && (
                    <p className="mt-3 text-xs text-slate-500">
                        {compareNotice.text}
                    </p>
                )}
                {cmp.notes && cmp.notes.length > 0 && (
                    <div className="mt-3 space-y-2">
                        {cmp.notes.map((note, index) => (
                            <p key={index} className="text-xs text-slate-500">- {note}</p>
                        ))}
                    </div>
                )}
            </div>

            {loading && (
                <div className="bg-white border border-slate-200/80 rounded-2xl shadow-[0_2px_8px_rgb(0,0,0,0.04)] p-4 text-[10px] font-mono text-slate-600">
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
                <div className="bg-white border border-slate-200/80 rounded-2xl shadow-[0_2px_8px_rgb(0,0,0,0.04)] p-4">
                    <p className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-3">Annual Return vs Max Drawdown</p>
                    <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={barData} margin={{ bottom: 30 }}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                <XAxis dataKey="name" fontSize={9} angle={-25} textAnchor="end" />
                                <YAxis fontSize={10} unit="%" />
                                <Tooltip formatter={(v: number, n: string) => [`${v}%`, n]} />
                                <Legend />
                                <Bar dataKey="Return" name="Annual Return %" fill="#14b8a6" radius={[4, 4, 0, 0]} />
                                <Bar dataKey="Drawdown" name="Max Drawdown %" fill="#e11d48" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                <div className="bg-white border border-slate-200/80 rounded-2xl shadow-[0_2px_8px_rgb(0,0,0,0.04)] p-4">
                    <p className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-3">Sharpe Ratio × 10 (Risk-Adjusted)</p>
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
                                        return <Cell key={i} fill={colors[i % colors.length]} />;
                                    })}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>

            {/* Projected Growth Curve */}
            <div className="bg-white border border-slate-200/80 rounded-2xl shadow-[0_2px_8px_rgb(0,0,0,0.04)] p-4">
                <p className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-3">₹5L Projected Growth over 10 Years (Net of Expenses)</p>
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
                                    strokeDasharray={name === 'Nifty 50 Proxy' ? '5 5' : undefined}
                                />
                            ))}
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Metrics comparison table */}
            <div className="bg-white border border-slate-200/80 rounded-2xl shadow-[0_2px_8px_rgb(0,0,0,0.04)] overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-slate-50/50 border-b border-slate-200">
                                <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3">Strategy</th>
                                <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3">Type</th>
                                <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3 text-right">Annual Ret%</th>
                                <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3 text-right">Volatility%</th>
                                <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3 text-right">Sharpe</th>
                                <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3 text-right">Sortino</th>
                                <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3 text-right">Max DD%</th>
                                <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3 text-right">5Y CAGR%</th>
                                <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3 text-right">Expense%</th>
                                <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3">Source</th>
                                <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3 text-right">Beat Rate%</th>
                            </tr>
                        </thead>
                        <tbody>
                            {cmp.strategies.map(s => (
                                <tr key={s.name} className={`border-b border-slate-100 text-sm hover:bg-slate-50 transition-colors ${s.name === cmp.winner ? 'bg-blue-50/50' : 'even:bg-slate-50/30'}`}>
                                    <td className="p-3">
                                        <div className="flex items-center gap-2 font-mono text-xs font-bold text-[#1D1D1F]">
                                            {s.name === cmp.winner && <Award className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />}
                                            {s.name}
                                            {s.isProxy && <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-semibold">Proxy</span>}
                                        </div>
                                    </td>
                                    <td className="p-3"><span className={`badge ${TYPE_BADGES[s.type]}`}>{TYPE_LABELS[s.type]}</span></td>
                                    <td className="p-3 text-emerald-600 font-mono font-semibold text-right">{s.annualReturn}%</td>
                                    <td className="p-3 font-mono text-right">{s.volatility}%</td>
                                    <td className={`p-3 font-mono font-semibold text-right ${s.sharpe > 1.3 ? 'text-emerald-600' : s.sharpe > 1 ? 'text-blue-600' : 'text-slate-600'}`}>{s.sharpe.toFixed(2)}</td>
                                    <td className="p-3 font-mono text-right">{s.sortino.toFixed(2)}</td>
                                    <td className="p-3 text-rose-600 font-mono text-right">{s.maxDrawdown}%</td>
                                    <td className="p-3 font-mono text-right">{s.cagr5Y}%</td>
                                    <td className="p-3 font-mono text-[#86868B] text-right">{s.expenseRatio}%</td>
                                    <td className="p-3 font-mono text-[10px]">{s.sourceType === 'THIRD_PARTY' ? '3P Ref' : 'Local'}</td>
                                    <td className="p-3 font-mono text-right">{(s.relativeAccuracyScorePct || 0).toFixed(1)}%</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            <div className="bg-white border border-slate-200/80 rounded-2xl shadow-[0_2px_8px_rgb(0,0,0,0.04)] p-4">
                <p className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-3">Benchmark Construction Notes</p>
                <div className="space-y-3">
                    {cmp.strategies.map((strategy) => (
                        <div key={`${strategy.name}-notes`} className="bg-slate-50/50 border border-slate-200/50 rounded-xl p-3">
                            <div className="flex items-center gap-2 mb-2">
                                <p className="font-mono text-xs uppercase tracking-wider font-bold text-[#1D1D1F]">{strategy.name}</p>
                                {strategy.isProxy && <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-semibold">Proxy</span>}
                            </div>
                            <p className="text-[10px] text-[#86868B] font-mono uppercase tracking-wider mb-1"><span className="font-semibold text-[#1D1D1F]">Method:</span> {strategy.constructionMethod}</p>
                            <p className="text-[10px] text-[#86868B] font-mono uppercase tracking-wider mb-1"><span className="font-semibold text-[#1D1D1F]">Constituent Policy:</span> {strategy.constituentMethod}</p>
                            <p className="text-[10px] text-[#86868B] font-mono uppercase tracking-wider mb-2"><span className="font-semibold text-[#1D1D1F]">Source Window:</span> {strategy.sourceWindow}</p>
                            {strategy.limitations.length > 0 && (
                                <div className="space-y-1">
                                    {strategy.limitations.map((limitation) => (
                                        <p key={limitation} className="text-[11px] text-[#86868B]">- {limitation}</p>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
