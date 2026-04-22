import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
    PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend,
    BarChart, Bar, XAxis, YAxis, CartesianGrid
} from 'recharts';
import { ArrowRight, Calculator, Info, Zap, ShieldCheck, TrendingUp } from 'lucide-react';
import { calculatePortfolioTransactionCosts, Portfolio } from '../services/portfolioService';
import {
    generatePortfolioViaApi,
    getCurrentModelStatusViaApi,
    getMandateQuestionnaireViaApi,
    ModelVariant,
    RiskAttitude,
    UserMandate,
} from '../services/backendApi';
import { MetricCard, SectorChip } from './MetricCard';
import { StockInsightDrawer } from './StockInsightDrawer';

const COLORS = ['#D4A843', '#5B9CF6', '#52C97A', '#E05C5C', '#F59E0B', '#A78BFA'];

interface Props { onPortfolioGenerated: (p: Portfolio) => void; portfolio: Portfolio | null; }

export function GenerateTab({ onPortfolioGenerated, portfolio }: Props) {
    const [amount, setAmount] = useState(500000);
    const [mandate, setMandate] = useState<UserMandate>({
        investment_horizon_weeks: '4-8',
        preferred_num_positions: 10,
        allow_small_caps: false,
        risk_attitude: 'balanced',
    });
    const [generating, setGenerating] = useState(false);
    const [activeModelVariant, setActiveModelVariant] = useState<ModelVariant>('RULES');
    const [activeModelVersion, setActiveModelVersion] = useState<string>('');
    const [activeTrainingMode, setActiveTrainingMode] = useState<string>('');
    const [artifactClassification, setArtifactClassification] = useState<'bootstrap' | 'standard' | ''>('');
    const [modelStatusReason, setModelStatusReason] = useState<string>('');
    const [generationNotice, setGenerationNotice] = useState<{ tone: 'info' | 'warning'; text: string } | null>(null);
    const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
    const [drawerOpen, setDrawerOpen] = useState(false);
    const runtimeLoaded = useRef(false);

    useEffect(() => {
        const loadModelStatus = async () => {
            try {
                const status = await getCurrentModelStatusViaApi();
                runtimeLoaded.current = true;
                if (status.available) {
                    setActiveModelVariant('LIGHTGBM_HYBRID');
                    setModelStatusReason('');
                    if (typeof status.modelVersion === 'string') setActiveModelVersion(status.modelVersion);
                    if (typeof status.trainingMode === 'string') setActiveTrainingMode(status.trainingMode);
                    if (status.artifactClassification) setArtifactClassification(status.artifactClassification);
                } else {
                    setActiveModelVariant('RULES');
                    setActiveTrainingMode('');
                    setArtifactClassification('');
                    setModelStatusReason(status.reason || 'missing_or_invalid_artifact');
                }
            } catch {
                runtimeLoaded.current = true;
                setActiveModelVariant('RULES');
                setActiveTrainingMode('');
                setArtifactClassification('');
                setModelStatusReason('api_unreachable');
            }
        };
        void loadModelStatus();

        const loadQuestionnaire = async () => {
            try {
                const questionnaire = await getMandateQuestionnaireViaApi();
                setMandate(questionnaire.defaults);
            } catch {}
        };
        void loadQuestionnaire();
    }, []);

    const updateMandate = <K extends keyof UserMandate>(key: K, value: UserMandate[K]) => {
        setMandate(current => ({ ...current, [key]: value }));
    };

    const handleGenerate = async (capitalOverride?: number, riskOverride?: RiskAttitude) => {
        if (activeModelVariant !== 'LIGHTGBM_HYBRID') {
            setGenerationNotice({
                tone: 'warning',
                text: `Ensemble runtime is not ready${modelStatusReason ? ` (${modelStatusReason})` : ''}. Portfolio generation is blocked instead of falling back to rules.`,
            });
            return;
        }

        const capitalAmount = capitalOverride ?? amount;
        const requestMandate = riskOverride ? { ...mandate, risk_attitude: riskOverride } : mandate;

        setGenerating(true);
        setGenerationNotice(null);
        try {
            if (capitalOverride !== undefined) {
                setAmount(capitalOverride);
            }
            if (riskOverride) {
                setMandate(current => ({ ...current, risk_attitude: riskOverride }));
            }

            const generated = await generatePortfolioViaApi(capitalAmount, requestMandate, activeModelVariant);
            onPortfolioGenerated(generated);
            setGenerationNotice({
                tone: 'info',
                text:
                    generated.modelSource === 'ENSEMBLE'
                        ? `Using ensemble runtime${generated.modelVersion ? ` ${generated.modelVersion}` : ''}${generated.predictionHorizonDays ? ` over ${generated.predictionHorizonDays} trading days` : ''}, with a ${generated.lookbackWindowDays ?? '--'}-day lookback and ${generated.expectedHoldingPeriodDays ?? '--'}-day holding target.`
                        : 'Portfolio generation completed without ensemble output.',
            });
        } catch (error) {
            setGenerationNotice({
                tone: 'warning',
                text: `Portfolio generation failed: ${error instanceof Error ? error.message : 'Unable to reach the local backend.'}`,
            });
        } finally {
            setGenerating(false);
        }
    };

    const chartData = useMemo(
        () => portfolio?.allocations.map(a => ({ name: a.stock.symbol, value: a.amount })) ?? [],
        [portfolio],
    );

    const sectorData = useMemo(() => {
        if (!portfolio) return [];
        const totals: Record<string, number> = {};
        portfolio.allocations.forEach(allocation => {
            totals[allocation.stock.sector] = (totals[allocation.stock.sector] || 0) + allocation.amount;
        });
        return Object.entries(totals).map(([name, value]) => ({ name, value }));
    }, [portfolio]);

    const costs = useMemo(
        () => (portfolio ? calculatePortfolioTransactionCosts(portfolio.allocations, true) : null),
        [portfolio],
    );

    const riskOpts: { id: RiskAttitude; label: string; icon: React.ReactNode; desc: string }[] = [
        { id: 'capital_preservation', label: 'Preserve', icon: <ShieldCheck className="w-5 h-5" />, desc: 'Strict downside control' },
        { id: 'balanced', label: 'Balanced', icon: <TrendingUp className="w-5 h-5" />, desc: 'Risk and upside in balance' },
        { id: 'growth', label: 'Growth', icon: <Zap className="w-5 h-5" />, desc: 'Higher upside bias' },
    ];

    const openStockDrawer = (symbol: string) => {
        setSelectedSymbol(symbol);
        setDrawerOpen(true);
    };

    return (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 animate-fade-in">
            <div className="lg:col-span-4 space-y-5">
                <div className="card p-4">
                    <h2 className="font-mono text-[10px] uppercase tracking-wider font-bold flex items-center gap-2 mb-4">
                        <Calculator className="w-4 h-4 text-blue-500" /> Investment Parameters
                    </h2>

                    <div className="space-y-5">
                        {generationNotice && (
                            <div className={generationNotice.tone === 'info' ? 'alert-info text-xs' : 'alert-warning text-xs'}>
                                {generationNotice.text}
                            </div>
                        )}

                        <div className="alert-info text-xs">
                            Active generation engine: {activeModelVariant === 'LIGHTGBM_HYBRID' ? `Ensemble runtime${activeModelVersion ? ` ${activeModelVersion}` : ''}` : 'Unavailable'}
                            {activeModelVariant !== 'LIGHTGBM_HYBRID' && modelStatusReason ? ` (${modelStatusReason})` : ''}
                        </div>

                        {activeModelVariant === 'LIGHTGBM_HYBRID' ? (
                            <div className={artifactClassification === 'bootstrap' ? 'alert-warning text-xs' : 'alert-success text-xs'}>
                                Ensemble training mode: {activeTrainingMode || 'unknown'}.
                                {artifactClassification === 'bootstrap'
                                    ? ' This is still a bootstrap artifact and should be treated as a development/demo model.'
                                    : ' This artifact passed the standard local validation flow.'}
                            </div>
                        ) : runtimeLoaded.current ? (
                            <div className="alert-warning text-xs">
                                Ensemble runtime is unavailable, so generation stays blocked instead of silently switching to rules.
                            </div>
                        ) : null}

                        <div>
                            <label className="block text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-1.5">Investment Amount (Rs)</label>
                            <input
                                type="number"
                                value={amount}
                                onChange={e => setAmount(Number(e.target.value))}
                                className="input-field px-4 py-2.5"
                                placeholder="e.g. 500000"
                            />
                            <p className="text-xs text-slate-400 mt-1">Approx. Rs {(amount / 100000).toFixed(1)}L</p>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="block text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-1.5">Horizon (weeks)</label>
                                <select
                                    value={mandate.investment_horizon_weeks}
                                    onChange={e => updateMandate('investment_horizon_weeks', e.target.value as UserMandate['investment_horizon_weeks'])}
                                    className="input-field px-4 py-2.5"
                                >
                                    {['2-4', '4-8', '8-24'].map(option => (
                                        <option key={option} value={option}>{option}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className="block text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-1.5">Target Positions</label>
                                <input
                                    type="number"
                                    value={mandate.preferred_num_positions}
                                    onChange={e => updateMandate('preferred_num_positions', Number(e.target.value))}
                                    className="input-field px-4 py-2.5"
                                />
                            </div>
                        </div>

                        <div>
                            <label className="block text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-2">Risk Attitude</label>
                            <div className="grid grid-cols-3 gap-2">
                                {riskOpts.map(risk => (
                                    <button
                                        key={risk.id}
                                        onClick={() => updateMandate('risk_attitude', risk.id)}
                                        className={`risk-btn ${mandate.risk_attitude === risk.id ? 'active-risk' : ''}`}
                                    >
                                        {risk.icon}
                                        <span>{risk.label}</span>
                                        <span className="text-[9px] font-normal normal-case tracking-normal text-slate-400">{risk.desc}</span>
                                    </button>
                                ))}
                            </div>
                        </div>

                        <label className="flex items-center justify-between rounded-sm border border-slate-700 bg-slate-800/50 px-4 py-3 text-sm text-slate-300 font-mono text-[11px] uppercase tracking-wide">
                            <span>Allow small caps</span>
                            <input
                                type="checkbox"
                                checked={mandate.allow_small_caps}
                                onChange={e => updateMandate('allow_small_caps', e.target.checked)}
                            />
                        </label>

                        <button
                            onClick={() => void handleGenerate()}
                            disabled={generating || activeModelVariant !== 'LIGHTGBM_HYBRID'}
                            className="btn btn-primary btn-lg w-full flex items-center justify-center gap-2"
                        >
                            {generating ? 'Generating...' : 'Generate AI Portfolio'} <ArrowRight className="w-4 h-4" />
                        </button>
                    </div>
                </div>

                {portfolio && (
                    <>
                        <div className="card p-4">
                            <div className="flex items-center justify-between">
                                <div className="text-[10px] text-slate-400 font-mono tracking-wider uppercase font-medium">MODEL GENERATION SUMMARY</div>
                                {portfolio.modelSource === 'ENSEMBLE'
                                    ? <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">AI Ensemble Active</span>
                                    : <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-800">Rules-Based Mode</span>}
                            </div>
                        </div>

                        {portfolio.backendNotes && portfolio.backendNotes.length > 0 && (
                            <div className="card p-4">
                                <h3 className="font-mono text-xs uppercase tracking-wider font-bold mb-3 text-slate-50">Backend Model Notes</h3>
                                <div className="space-y-2">
                                    {portfolio.backendNotes.map((note, index) => (
                                        <p key={index} className="text-xs text-slate-600 leading-relaxed">{note}</p>
                                    ))}
                                </div>
                            </div>
                        )}

                        <div className="card p-4">
                            <h3 className="font-mono text-[10px] uppercase tracking-wider font-bold flex items-center gap-2 mb-4">
                                <Info className="w-4 h-4 text-blue-500" /> Transaction Costs
                            </h3>
                            <div className="space-y-1">
                                {[
                                    ['Brokerage', `Rs ${costs!.brokerage.toFixed(2)}`],
                                    ['STT (0.1%)', `Rs ${costs!.stt.toFixed(2)}`],
                                    ['Stamp Duty', `Rs ${costs!.stampDuty.toFixed(2)}`],
                                    ['Exchange Txn', `Rs ${costs!.exchangeTxn.toFixed(2)}`],
                                    ['SEBI Fees', `Rs ${costs!.sebi.toFixed(2)}`],
                                    ['GST', `Rs ${costs!.gst.toFixed(2)}`],
                                    ['Slippage (0.1%)', `Rs ${costs!.slippage.toFixed(2)}`],
                                ].map(([label, value]) => (
                                    <div key={label} className="stat-row">
                                        <span className="stat-label text-xs">{label}</span>
                                        <span className="stat-value text-xs text-rose-500">{value}</span>
                                    </div>
                                ))}
                                <div className="stat-row" style={{ fontWeight: 700 }}>
                                    <span className="stat-label text-xs font-bold text-slate-50">Total Charges</span>
                                    <span className="text-rose-500 font-mono font-bold text-sm">Rs {costs!.total.toFixed(2)}</span>
                                </div>
                            </div>
                            <p className="text-[10px] text-slate-400 mt-3 italic">Stop-loss: 15% trailing, STCG: 20%, LTCG: 12.5%</p>
                        </div>
                    </>
                )}
            </div>

            <div className="lg:col-span-8 space-y-5">
                {!portfolio ? (
                    <div className="card flex flex-col items-center justify-center text-slate-400 p-8 border border-dashed border-slate-600" style={{ minHeight: '400px' }}>
                        <div className="w-16 h-16 rounded-full bg-slate-800 flex items-center justify-center mb-4">
                            <TrendingUp className="w-8 h-8 opacity-30 text-blue-500" />
                        </div>
                        <p className="font-mono text-[11px] uppercase tracking-wider font-semibold mb-1 text-slate-300">Set the mandate and generate</p>
                        <p className="text-[10px] font-mono tracking-wide text-slate-500">The ensemble allocator uses horizon, risk attitude, position count, and news context.</p>
                    </div>
                ) : (
                    <>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            <MetricCard
                                label="Total Invested"
                                value={`Rs ${(portfolio.totalInvested / 100000).toFixed(2)}L`}
                                sub={
                                    portfolio.cashRemaining && portfolio.cashRemaining > 0
                                        ? `Cash left: Rs ${portfolio.cashRemaining.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
                                        : 'Whole-share deployment'
                                }
                                color="slate"
                            />
                            <MetricCard label="Portfolio Beta" value={portfolio.metrics.avgBeta.toFixed(2)} sub="vs Nifty 50 = 1.00" color={portfolio.metrics.avgBeta > 1.3 ? 'red' : portfolio.metrics.avgBeta < 0.8 ? 'green' : 'blue'} trend={portfolio.metrics.avgBeta > 1.3 ? 'up' : 'down'} />
                            <MetricCard label="Sharpe Ratio" value={portfolio.metrics.sharpeRatio.toFixed(2)} sub="Risk-free rate: 7% pa" color={portfolio.metrics.sharpeRatio > 1.2 ? 'green' : 'amber'} trend="up" />
                            <MetricCard label="Exp. Annual Return" value={`${portfolio.metrics.estimatedAnnualReturn.toFixed(1)}%`} sub={`Volatility: ${portfolio.metrics.estimatedVolatility.toFixed(1)}%`} color="green" trend="up" />
                        </div>

                        {portfolio.mandate && (
                            <div className="card p-4">
                                <p className="section-title">Mandate In Effect</p>
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

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                            <div className="card p-4">
                                <p className="section-title">Stock Allocation</p>
                                <div className="h-56">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <PieChart>
                                            <Pie data={chartData} innerRadius={50} outerRadius={75} paddingAngle={4} dataKey="value">
                                                {chartData.map((_, index) => <Cell key={index} fill={COLORS[index % COLORS.length]} />)}
                                            </Pie>
                                            <Tooltip formatter={(value: number) => [`Rs ${value.toLocaleString()}`, 'Amount']} />
                                            <Legend iconSize={8} iconType="circle" />
                                        </PieChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>

                            <div className="card p-4">
                                <p className="section-title">Sector Diversification</p>
                                <div className="h-56">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart data={sectorData} layout="vertical" margin={{ left: 60 }}>
                                            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                                            <XAxis type="number" hide />
                                            <YAxis dataKey="name" type="category" fontSize={10} width={56} />
                                            <Tooltip formatter={(value: number) => [`Rs ${value.toLocaleString()}`]} />
                                            <Bar dataKey="value" fill="#D4A843" radius={[0, 6, 6, 0]} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        </div>

                        <div className="card overflow-hidden">
                            <div className="overflow-x-auto">
                                <table className="data-table">
                                    <thead>
                                        <tr className="bg-slate-800/50">
                                            <th>Stock</th><th>Sector</th><th>Wt%</th><th>News</th><th className="text-right">Shares</th><th className="text-right">Amount</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {portfolio.allocations.map((allocation, index) => (
                                            <tr
                                                key={index}
                                                role="button"
                                                tabIndex={0}
                                                onClick={() => openStockDrawer(allocation.stock.symbol)}
                                                onKeyDown={(event) => {
                                                    if (event.key === 'Enter' || event.key === ' ') {
                                                        event.preventDefault();
                                                        openStockDrawer(allocation.stock.symbol);
                                                    }
                                                }}
                                                className="cursor-pointer hover:bg-slate-800/50 even:bg-slate-800/30 border-b border-slate-700/50 last:border-0"
                                                aria-label={`Open AI stock insights for ${allocation.stock.symbol}`}
                                            >
                                                <td>
                                                    <div className="font-semibold font-mono text-sm text-slate-50">
                                                        {allocation.stock.symbol}
                                                    </div>
                                                    <div className="text-[10px] font-mono tracking-wide text-slate-400">{allocation.stock.name}</div>
                                                    {allocation.drivers && allocation.drivers.length > 0 && (
                                                        <div className="text-[10px] text-slate-500 mt-1">
                                                            ML drivers: {allocation.drivers.slice(0, 2).join(', ')}
                                                        </div>
                                                    )}
                                                </td>
                                                <td><SectorChip sector={allocation.stock.sector} /></td>
                                                <td>
                                                    <div className="flex items-center gap-2">
                                                        <div className="progress-bar-track w-12">
                                                            <div className="progress-bar-fill" style={{ width: `${allocation.weight}%`, background: '#D4A843' }} />
                                                        </div>
                                                        <span className="font-mono text-xs">{allocation.weight}%</span>
                                                    </div>
                                                </td>
                                                <td>
                                                    <div className="text-xs text-slate-600">
                                                        <div className="font-medium">S {allocation.news_sentiment?.toFixed(2) ?? '0.00'} · I {allocation.news_impact?.toFixed(1) ?? '0.0'}</div>
                                                        <div className="text-[10px] text-slate-400 max-w-52">{allocation.news_explanation ?? 'No mapped news.'}</div>
                                                    </div>
                                                </td>
                                                <td className="font-mono text-right">{allocation.shares}</td>
                                                <td className="text-right font-semibold font-mono">Rs {allocation.amount.toLocaleString()}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </>
                )}
            </div>
            <StockInsightDrawer
                symbol={selectedSymbol}
                open={drawerOpen}
                onClose={() => setDrawerOpen(false)}
            />
        </div>
    );
}
