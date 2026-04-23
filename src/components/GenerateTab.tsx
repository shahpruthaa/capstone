import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
    PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend,
    BarChart, Bar, XAxis, YAxis, CartesianGrid
} from 'recharts';
import { ArrowRight, Calculator, Info, Zap, ShieldCheck, TrendingUp, AlertTriangle } from 'lucide-react';
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

const COLORS = ['#eab308', '#14b8a6', '#8b5cf6', '#e11d48', '#3b82f6', '#f59e0b'];

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
                <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-6 relative overflow-hidden mb-5">
                    <div className="absolute top-0 left-0 w-1 h-full bg-yellow-500"></div>
                    <h2 className="text-[10px] font-bold text-yellow-500 uppercase tracking-[0.15em] flex items-center gap-2 mb-4">
                        <Zap className="w-4 h-4" /> Build or analyze with the same decision engine
                    </h2>
                    <div className="space-y-4 text-xs text-[#86868b] leading-relaxed">
                        <p><span className="font-bold text-[#f5f5f7]">Step 1:</span> Define the mandate based on your horizon and risk tolerance.</p>
                        <p><span className="font-bold text-[#f5f5f7]">Step 2:</span> Review the recommended portfolio generated by the ensemble alpha models.</p>
                        <p><span className="font-bold text-[#f5f5f7]">Step 3:</span> Compare it against your real holdings using the same institutional research stack.</p>
                    </div>
                </div>

                <div className="bg-rose-500/10 border border-rose-500/30 rounded-2xl p-6 relative overflow-hidden mb-5">
                    <div className="absolute top-0 left-0 w-1 h-full bg-rose-500"></div>
                    <h3 className="text-[10px] font-bold text-rose-500 uppercase tracking-[0.15em] flex items-center gap-2 mb-3">
                        <AlertTriangle className="w-4 h-4" /> Bear Market Warning
                    </h3>
                    <p className="text-xs text-rose-400/90 leading-relaxed italic">
                        "Current bear regime signals negative expected returns. Consider waiting for confirmation of trend reversal before deploying full capital."
                    </p>
                </div>

                <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-4">
                    <h2 className="font-mono text-[10px] uppercase tracking-[0.08em] font-bold flex items-center gap-2 mb-4 text-[#86868B]">
                        <Calculator className="w-4 h-4 text-yellow-500" /> Investment Parameters
                    </h2>

                    <div className="space-y-5">
                        {generationNotice && (
                            <div className={generationNotice.tone === 'info' 
                                ? 'bg-blue-500/10 border border-blue-500/30 text-blue-400 text-xs p-3 rounded-xl font-mono leading-relaxed' 
                                : 'bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs p-3 rounded-xl font-mono leading-relaxed'}>
                                {generationNotice.text}
                            </div>
                        )}

                        <div className="bg-blue-500/10 border border-blue-500/30 text-blue-400 text-xs p-3 rounded-xl font-mono leading-relaxed">
                            Active generation engine: {activeModelVariant === 'LIGHTGBM_HYBRID' ? `Ensemble runtime${activeModelVersion ? ` ${activeModelVersion}` : ''}` : 'Unavailable'}
                            {activeModelVariant !== 'LIGHTGBM_HYBRID' && modelStatusReason ? ` (${modelStatusReason})` : ''}
                        </div>

                        {activeModelVariant === 'LIGHTGBM_HYBRID' ? (
                            <div className={artifactClassification === 'bootstrap' 
                                ? 'bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs p-3 rounded-xl font-mono leading-relaxed' 
                                : 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs p-3 rounded-xl font-mono leading-relaxed'}>
                                Ensemble training mode: {activeTrainingMode || 'unknown'}.
                                {artifactClassification === 'bootstrap'
                                    ? ' This is still a bootstrap artifact and should be treated as a development/demo model.'
                                    : ' This artifact passed the standard local validation flow.'}
                            </div>
                        ) : runtimeLoaded.current ? (
                            <div className="bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs p-3 rounded-xl font-mono leading-relaxed">
                                Ensemble runtime is unavailable, so generation stays blocked instead of silently switching to rules.
                            </div>
                        ) : null}

                        <div>
                            <label className="block text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-1.5">Investment Amount (Rs)</label>
                            <input
                                type="number"
                                value={amount}
                                onChange={e => setAmount(Number(e.target.value))}
                                className="w-full bg-[#0a0a0a] border border-[#2d2d2d] rounded-xl text-[#f5f5f7] px-4 py-2.5 focus:bg-[#1d1d1f] focus:outline-none focus:ring-4 focus:ring-yellow-600/10 focus:border-yellow-600 transition-all font-mono text-sm"
                                placeholder="e.g. 500000"
                            />
                            <p className="text-xs text-[#6e6e73] mt-1">Approx. Rs {(amount / 100000).toFixed(1)}L</p>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="block text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-1.5">Horizon (weeks)</label>
                                <select
                                    value={mandate.investment_horizon_weeks}
                                    onChange={e => updateMandate('investment_horizon_weeks', e.target.value as UserMandate['investment_horizon_weeks'])}
                                    className="w-full bg-[#0a0a0a] border border-[#2d2d2d] rounded-xl text-[#f5f5f7] px-4 py-2.5 focus:bg-[#1d1d1f] focus:outline-none focus:ring-4 focus:ring-yellow-600/10 focus:border-yellow-600 transition-all font-mono text-sm"
                                >
                                    {['2-4', '4-8', '8-24'].map(option => (
                                        <option key={option} value={option}>{option}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className="block text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-1.5">Target Positions</label>
                                <input
                                    type="number"
                                    value={mandate.preferred_num_positions}
                                    onChange={e => updateMandate('preferred_num_positions', Number(e.target.value))}
                                    className="w-full bg-[#0a0a0a] border border-[#2d2d2d] rounded-xl text-[#f5f5f7] px-4 py-2.5 focus:bg-[#1d1d1f] focus:outline-none focus:ring-4 focus:ring-yellow-600/10 focus:border-yellow-600 transition-all font-mono text-sm"
                                />
                            </div>
                        </div>

                        <div>
                            <label className="block text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-2">Risk Attitude</label>
                            <div className="grid grid-cols-3 gap-2">
                                {riskOpts.map(risk => (
                                    <button
                                        key={risk.id}
                                        onClick={() => updateMandate('risk_attitude', risk.id)}
                                        className={`flex flex-col items-center justify-center p-3 rounded-xl border transition-all ${mandate.risk_attitude === risk.id ? 'bg-yellow-500/10 border-yellow-500/40 text-yellow-500' : 'bg-[#0a0a0a] border-[#2d2d2d] text-[#6e6e73] hover:bg-[#1d1d1f]'}`}
                                    >
                                        {risk.icon}
                                        <span>{risk.label}</span>
                                        <span className="text-[9px] font-normal normal-case tracking-normal text-[#86868b]">{risk.desc}</span>
                                    </button>
                                ))}
                            </div>
                        </div>

                        <label className="flex items-center justify-between bg-[#0a0a0a] border border-[#2d2d2d] rounded-xl p-3 text-[#f5f5f7] font-mono text-[11px] uppercase tracking-wide">
                            <span>Allow small caps</span>
                            <input
                                type="checkbox"
                                checked={mandate.allow_small_caps}
                                onChange={e => updateMandate('allow_small_caps', e.target.checked)}
                                className="w-4 h-4 rounded text-yellow-500 focus:ring-yellow-500 bg-[#1d1d1f] border-[#2d2d2d]"
                            />
                        </label>

                        <button
                            onClick={() => void handleGenerate()}
                            disabled={generating || activeModelVariant !== 'LIGHTGBM_HYBRID'}
                            className="bg-yellow-500 text-black rounded-xl font-bold hover:bg-yellow-400 transition-all w-full py-3 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {generating ? 'Generating...' : 'Generate AI Portfolio'} <ArrowRight className="w-4 h-4" />
                        </button>
                    </div>
                </div>

                {portfolio && (
                    <>
                        <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-4">
                            <div className="flex items-center justify-between">
                                <div className="text-[10px] text-[#86868B] font-mono tracking-[0.08em] uppercase font-bold">MODEL GENERATION SUMMARY</div>
                                {portfolio.modelSource === 'ENSEMBLE'
                                    ? <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-500/10 text-yellow-500">AI Ensemble Active</span>
                                    : <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-[#1d1d1f] text-[#86868b]">Rules-Based Mode</span>}
                            </div>
                        </div>

                        {portfolio.backendNotes && portfolio.backendNotes.length > 0 && (
                        <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-4">
                                <h3 className="font-mono text-[10px] uppercase tracking-[0.08em] font-bold mb-3 text-[#86868B]">Backend Model Notes</h3>
                                <div className="space-y-2">
                                    {portfolio.backendNotes.map((note, index) => (
                                        <p key={index} className="text-xs text-[#6e6e73] leading-relaxed font-mono">{note}</p>
                                    ))}
                                </div>
                            </div>
                        )}

                        <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-4">
                            <h3 className="font-mono text-[10px] uppercase tracking-[0.08em] font-bold flex items-center gap-2 mb-4 text-[#86868B]">
                                <Info className="w-4 h-4 text-yellow-500" /> Transaction Costs
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
                                        <span className="stat-label text-xs text-[#86868B]">{label}</span>
                                        <span className="stat-value text-xs text-rose-600 font-mono">{value}</span>
                                    </div>
                                ))}
                                <div className="stat-row" style={{ fontWeight: 700 }}>
                                    <span className="stat-label text-xs font-bold text-[#f5f5f7]">Total Charges</span>
                                    <span className="text-rose-500 font-mono font-bold text-sm">Rs {costs!.total.toFixed(2)}</span>
                                </div>
                            </div>
                            <p className="text-[10px] text-[#86868B] mt-3 italic">Stop-loss: 15% trailing, STCG: 20%, LTCG: 12.5%</p>
                        </div>
                    </>
                )}
            </div>

            <div className="lg:col-span-8 space-y-5">
                {!portfolio ? (
                    <div className="bg-[#0a0a0a] flex flex-col items-center justify-center text-[#86868B] p-8 border border-dashed border-[#2d2d2d] rounded-2xl" style={{ minHeight: '400px' }}>
                        <div className="w-16 h-16 rounded-full bg-[#141415] flex items-center justify-center mb-4">
                            <TrendingUp className="w-8 h-8 opacity-30 text-yellow-500" />
                        </div>
                        <p className="font-mono text-[11px] uppercase tracking-[0.08em] font-bold mb-1 text-[#86868b]">Set the mandate and generate</p>
                        <p className="text-[10px] font-mono tracking-wide text-[#6e6e73]">The ensemble allocator uses horizon, risk attitude, position count, and news context.</p>
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
                            <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-4">
                                <p className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-3">Mandate In Effect</p>
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                                    <div className="stat-row">
                                        <span className="stat-label text-[#86868B]">Attitude</span>
                                        <span className="stat-value text-[#f5f5f7]">{portfolio.mandate.risk_attitude.replace('_', ' ')}</span>
                                    </div>
                                    <div className="stat-row">
                                        <span className="stat-label text-[#86868B]">Horizon</span>
                                        <span className="stat-value text-[#f5f5f7]">{portfolio.mandate.investment_horizon_weeks} weeks</span>
                                    </div>
                                    <div className="stat-row">
                                        <span className="stat-label text-[#86868B]">Positions</span>
                                        <span className="stat-value text-[#f5f5f7]">{portfolio.mandate.preferred_num_positions}</span>
                                    </div>
                                    <div className="stat-row">
                                        <span className="stat-label text-[#86868B]">Small Caps</span>
                                        <span className="stat-value text-[#f5f5f7]">{portfolio.mandate.allow_small_caps ? 'Allowed' : 'Excluded'}</span>
                                    </div>
                                </div>
                            </div>
                        )}

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                             <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-4">
                                <p className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-3">Stock Allocation</p>
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

                            <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-4">
                                <p className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-3">Sector Diversification</p>
                                <div className="h-56">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart data={sectorData} layout="vertical" margin={{ left: 60 }}>
                                            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#2d2d2d" />
                                            <XAxis type="number" hide />
                                            <YAxis dataKey="name" type="category" fontSize={10} width={56} stroke="#86868b" />
                                            <Tooltip formatter={(value: number) => [`Rs ${value.toLocaleString()}`]} />
                                            <Bar dataKey="value" fill="#eab308" radius={[0, 6, 6, 0]} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        </div>

                        <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl overflow-hidden">
                            <div className="overflow-x-auto">
                                <table className="w-full text-left border-collapse">
                                    <thead>
                                        <tr className="bg-[#0a0a0a] border-b border-[#2d2d2d]">
                                            <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3">Stock</th>
                                            <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3">Sector</th>
                                            <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3 text-right">Wt%</th>
                                            <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3">News</th>
                                            <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3 text-right">Shares</th>
                                            <th className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] p-3 text-right">Amount</th>
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
                                                className="cursor-pointer border-b border-[#2d2d2d] even:bg-[#0a0a0a]/30 text-sm hover:bg-[#1d1d1f] transition-colors"
                                                aria-label={`Open AI stock insights for ${allocation.stock.symbol}`}
                                            >
                                                <td className="p-3">
                                                    <div className="font-semibold font-mono text-sm text-[#f5f5f7]">
                                                        {allocation.stock.symbol}
                                                    </div>
                                                    <div className="text-[10px] font-mono tracking-wide text-[#86868b]">{allocation.stock.name}</div>
                                                    {allocation.drivers && allocation.drivers.length > 0 && (
                                                        <div className="text-[10px] text-[#86868B] mt-1">
                                                            ML drivers: {allocation.drivers.slice(0, 2).join(', ')}
                                                        </div>
                                                    )}
                                                </td>
                                                <td className="p-3"><SectorChip sector={allocation.stock.sector} /></td>
                                                <td className="p-3 text-right">
                                                    <div className="flex items-center justify-end gap-2">
                                                        <div className="progress-bar-track w-12 hidden md:block bg-[#2d2d2d]">
                                                            <div className="progress-bar-fill" style={{ width: `${allocation.weight}%`, background: '#eab308' }} />
                                                        </div>
                                                        <span className="font-mono text-xs text-[#f5f5f7]">{(allocation.weight).toFixed(2)}%</span>
                                                    </div>
                                                </td>
                                                <td className="p-3">
                                                    <div className="text-xs text-[#86868b]">
                                                        <div className="font-mono">S {allocation.news_sentiment?.toFixed(2) ?? '0.00'} · I {allocation.news_impact?.toFixed(1) ?? '0.0'}</div>
                                                        <div className="text-[10px] text-[#86868B] max-w-52 truncate">{allocation.news_explanation ?? 'No mapped news.'}</div>
                                                    </div>
                                                </td>
                                                <td className="p-3 font-mono text-right text-[#f5f5f7]">{allocation.shares}</td>
                                                <td className="p-3 text-right font-semibold font-mono text-[#f5f5f7]">Rs {allocation.amount.toLocaleString()}</td>
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
