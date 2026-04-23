import React, { useEffect, useState } from 'react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
    ResponsiveContainer, LineChart, Line, Cell
} from 'recharts';
import { Award, TrendingUp } from 'lucide-react';
import { BenchmarkStrategy, ComparisonResult } from '../services/benchmarkService';
import { getBenchmarkComparisonViaApi } from '../services/backendApi';

const TYPE_BADGES: Record<string, string> = { AI: 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20', INDEX: 'bg-slate-500/10 text-slate-400 border border-slate-500/20', FACTOR: 'bg-violet-500/10 text-violet-400 border border-violet-500/20', AMC_STYLE: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' };
const TYPE_LABELS: Record<string, string> = { AI: 'AI', INDEX: 'Index', FACTOR: 'Factor', AMC_STYLE: 'AMC Style' };

const formatReturn = (val: number) => `${val > 0 ? '+' : ''}${val.toFixed(2)}%`;

const StrategyCard: React.FC<{ s: BenchmarkStrategy; isWinner: boolean }> = ({ s, isWinner }) => {
    return (
        <div className={`bg-[#141415] border ${isWinner ? 'border-yellow-500/50 ring-1 ring-yellow-500/20' : 'border-[#2d2d2d]'} rounded-2xl p-4 transition-all`}>
            <div className="flex items-start justify-between mb-3">
                <div>
                    <div className="flex items-center gap-2">
                        <p className="font-semibold text-sm text-[#f5f5f7] font-mono">{s.name}</p>
                        {isWinner && <Award className="w-4 h-4 text-amber-500" />}
                        {s.isProxy && <span className="text-[10px] bg-[#1d1d1f] text-[#86868b] px-2 py-0.5 rounded-full font-semibold">Proxy</span>}
                    </div>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold uppercase tracking-wider mt-1 inline-block ${TYPE_BADGES[s.type]}`}>{TYPE_LABELS[s.type]}</span>
                </div>
                <div className="text-right">
                    <p className={`text-xl font-bold font-mono ${s.annualReturn >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                        {formatReturn(s.annualReturn)}
                    </p>
                    <p className="text-xs text-[#6e6e73]">Annual Return</p>
                </div>
            </div>
            <p className="text-xs text-[#86868B] mb-4 leading-relaxed">{s.description}</p>
            <div className="mb-4 space-y-1">
                <p className="text-[10px] text-[#86868B] font-mono uppercase tracking-wider"><span className="font-semibold text-[#f5f5f7]">Construction:</span> {s.constructionMethod}</p>
                <p className="text-[10px] text-[#86868B] font-mono uppercase tracking-wider"><span className="font-semibold text-[#f5f5f7]">Constituents:</span> {s.constituentMethod}</p>
                <p className="text-[10px] text-[#86868B] font-mono uppercase tracking-wider"><span className="font-semibold text-[#f5f5f7]">Source Window:</span> {s.sourceWindow}</p>
                <p className="text-[10px] text-[#86868B] font-mono uppercase tracking-wider">
                    <span className="font-semibold text-[#f5f5f7]">Data Source:</span> {s.sourceProvider || 'local_research'}
                    {s.sourceType === 'THIRD_PARTY' ? ' (3rd-party)' : ' (local proxy)'}
                </p>
                <p className="text-[10px] text-[#86868B] font-mono uppercase tracking-wider">
                    <span className="font-semibold text-[#f5f5f7]">Benchmark Beat Rate:</span> {(s.relativeAccuracyScorePct || 0).toFixed(1)}%
                </p>
            </div>
            <div className="grid grid-cols-2 gap-4">
                {[
                    ['Volatility', `${s.volatility.toFixed(2)}%`],
                    ['Max Drawdown', `${s.maxDrawdown.toFixed(2)}%`],
                    ['Sharpe', s.sharpe.toFixed(2)],
                    ['Sortino', s.sortino.toFixed(2)],
                    ['5Y CAGR', `${s.cagr5Y.toFixed(2)}%`],
                    ['Expense', `${s.expenseRatio.toFixed(2)}%`],
                ].map(([k, v]) => (
                    <div key={k} className="flex flex-col">
                        <span className="text-[10px] font-bold text-[#86868B] uppercase tracking-tight">{k}</span>
                        <span className="text-[#f5f5f7] font-mono text-2xl">{v}</span>
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

            {s.type === 'AI' && (
                <div className="mt-4 pt-4 border-t border-[#2d2d2d]">
                    <div className="flex justify-between items-center mb-1">
                        <span className="text-[10px] uppercase font-bold text-[#86868B] tracking-widest">Active Share Posture</span>
                        <span className="text-xs font-mono font-bold text-amber-500">HIGH DIVERGENCE</span>
                    </div>
                    <p className="text-[10px] text-[#86868b] font-serif leading-relaxed">
                        This is a concentrated 10-15 asset portfolio. Outperformance vs cap-weighted indices is driven by heavy active factor tilts (Momentum/Quality), resulting in high tracking error.
                    </p>
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
                <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-4 text-sm font-mono text-[#6e6e73]">
                    Loading benchmark comparison from the local backend research service...
                </div>
            </div>
        );
    }

    if (!cmp) {
        return (
            <div className="space-y-8 animate-fade-in">
                <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-4">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="w-8 h-8 rounded-xl bg-[#0a0a0a] border border-[#2d2d2d] flex items-center justify-center">
                            <TrendingUp className="w-4 h-4 text-yellow-500" />
                        </div>
                        <div>
                            <h2 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em]">Industry Benchmark Comparison</h2>
                            <p className="text-[10px] text-[#86868B] font-mono mt-1">Backend benchmark service required</p>
                        </div>
                    </div>
                    {compareNotice && (
                        <p className="mt-3 text-xs text-[#86868b]">
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
            <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-4">
                <div className="flex items-center gap-3 mb-2">
                    <div className="w-8 h-8 rounded-xl bg-[#0a0a0a] border border-[#2d2d2d] flex items-center justify-center">
                        <TrendingUp className="w-4 h-4 text-yellow-500" />
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
                    <p className="mt-3 text-xs text-[#86868b]">
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
                <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-4 text-[10px] font-mono text-[#6e6e73]">
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
                <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-4">
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

                <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-4">
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
            <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-5">
                <p className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-4">₹5L Theoretical Unadjusted Compounding (Net of Expenses)</p>
                <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={growthCurve}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#2d2d2d" />
                            <XAxis dataKey="year" fontSize={11} stroke="#86868b" label={{ value: 'Years', position: 'insideBottom', offset: -5, fontSize: 11, fill: '#86868b' }} />
                            <YAxis fontSize={10} stroke="#86868b" tickFormatter={v => `₹${(v / 100000).toFixed(0)}L`} />
                            <Tooltip 
                                contentStyle={{ background: '#141415', border: '1px solid #2d2d2d', color: '#f5f5f7' }}
                                formatter={(v: number) => [`₹${(v / 100000).toFixed(2)}L`]} 
                                labelFormatter={l => `Year ${l}`} 
                            />
                            <Legend iconType="circle" />
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
            <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-[#0a0a0a] border-b border-[#2d2d2d]">
                                <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3">Strategy</th>
                                <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3">Type</th>
                                <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3 text-right">Annual Ret%</th>
                                <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3 text-right">Volatility%</th>
                                <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3 text-right">Sharpe</th>
                                <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3 text-right">Sortino</th>
                                <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3 text-right">Max DD%</th>
                                <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3 text-right">5Y CAGR%</th>
                                <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3 text-right">Expense%</th>
                                {cmp.strategies.some(s => s.sourceType) && <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3">Source</th>}
                                {cmp.strategies.some(s => s.relativeAccuracyScorePct) && <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3 text-right">Beat Rate%</th>}
                            </tr>
                        </thead>
                        <tbody>
                            {cmp.strategies.map(s => (
                                <tr 
                                    key={s.name} 
                                    className={`border-b border-slate-800/60 bg-[#141415] hover:bg-slate-800/40 transition-colors ${s.name === cmp.winner ? 'bg-yellow-500/10' : ''}`}
                                >
                                    <td className="p-3">
                                        <div className="flex items-center gap-2 font-mono text-xs font-bold text-[#f5f5f7]">
                                            {s.name === cmp.winner && <Award className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />}
                                            {s.name}
                                            {s.isProxy && <span className="text-[10px] bg-[#1d1d1f] text-[#86868b] px-2 py-0.5 rounded-full font-semibold">Proxy</span>}
                                        </div>
                                    </td>
                                    <td className="p-3"><span className={`badge ${TYPE_BADGES[s.type]}`}>{TYPE_LABELS[s.type]}</span></td>
                                    <td className={`p-3 font-mono font-semibold text-right ${s.annualReturn >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                                        {formatReturn(s.annualReturn)}
                                    </td>
                                    <td className="p-3 font-mono text-right text-slate-300">{s.volatility.toFixed(2)}%</td>
                                    <td className={`p-3 font-mono font-semibold text-right ${s.sharpe > 1.3 ? 'text-emerald-500' : s.sharpe > 1 ? 'text-yellow-500' : 'text-slate-400'}`}>{s.sharpe.toFixed(2)}</td>
                                    <td className="p-3 font-mono text-right text-slate-300">{s.sortino.toFixed(2)}</td>
                                    <td className="p-3 text-rose-500 font-mono text-right">{s.maxDrawdown.toFixed(2)}%</td>
                                    <td className="p-3 font-mono text-right text-slate-300">{s.cagr5Y.toFixed(2)}%</td>
                                    <td className="p-3 font-mono text-[#86868B] text-right">{s.expenseRatio.toFixed(2)}%</td>
                                    {cmp.strategies.some(s2 => s2.sourceType) && <td className="p-3 font-mono text-[10px] text-slate-400">{s.sourceType === 'THIRD_PARTY' ? '3P Ref' : 'Local'}</td>}
                                    {cmp.strategies.some(s2 => s2.relativeAccuracyScorePct) && <td className="p-3 font-mono text-right text-slate-300">{(s.relativeAccuracyScorePct || 0).toFixed(2)}%</td>}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-4">
                <p className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-3">Benchmark Construction Notes</p>
                <div className="space-y-3">
                    {cmp.strategies.map((strategy) => (
                        <div key={`${strategy.name}-notes`} className="bg-[#0a0a0a] border border-[#2d2d2d] rounded-xl p-3">
                            <div className="flex items-center gap-2 mb-2">
                                <p className="font-mono text-xs uppercase tracking-wider font-bold text-[#f5f5f7]">{strategy.name}</p>
                                {strategy.isProxy && <span className="text-[10px] bg-[#1d1d1f] text-[#86868b] px-2 py-0.5 rounded-full font-semibold">Proxy</span>}
                            </div>
                            <p className="text-[10px] text-[#86868B] font-mono uppercase tracking-wider mb-1"><span className="font-semibold text-[#f5f5f7]">Method:</span> {strategy.constructionMethod}</p>
                            <p className="text-[10px] text-[#86868B] font-mono uppercase tracking-wider mb-1"><span className="font-semibold text-[#f5f5f7]">Constituent Policy:</span> {strategy.constituentMethod}</p>
                            <p className="text-[10px] text-[#86868B] font-mono uppercase tracking-wider mb-2"><span className="font-semibold text-[#f5f5f7]">Source Window:</span> {strategy.sourceWindow}</p>
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
