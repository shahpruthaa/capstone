import React, { useEffect, useMemo, useState } from 'react';
import {
    PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend,
    BarChart, Bar, XAxis, YAxis, CartesianGrid
} from 'recharts';
import { ArrowRight, Calculator, Info, RefreshCw, Zap, ShieldCheck, TrendingUp } from 'lucide-react';
import { calculateTransactionCosts, Portfolio } from '../services/portfolioService';
import {
    generatePortfolioViaApi,
    getCurrentModelStatusViaApi,
    getMandateQuestionnaireViaApi,
    ModelVariant,
    postExplainPortfolio,
    RiskAttitude,
    UserMandate,
} from '../services/backendApi';
import { MetricCard, SectorChip } from './MetricCard';

const COLORS = ['#14b8a6', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316', '#10b981', '#6366f1', '#84cc16', '#f43f5e', '#0ea5e9', '#a855f7'];

interface Props { onPortfolioGenerated: (p: Portfolio) => void; portfolio: Portfolio | null; }
function AIInsightPanel({ portfolio }: { portfolio: Portfolio }) {
    const [insight, setInsight] = useState('');
    const [loading, setLoading] = useState(false);
    const generate = async () => {
        setLoading(true);
        try {
            const data = await postExplainPortfolio(portfolio);
            setInsight(data.explanation || 'No explanation returned.');
        } catch {
            setInsight('AI analysis temporarily unavailable.');
        } finally {
            setLoading(false);
        }
    };
    return (
        <div className="card p-5" style={{ background: 'linear-gradient(135deg, rgba(14, 116, 144, 0.24), rgba(21, 94, 117, 0.1))', borderColor: 'rgba(103, 232, 249, 0.2)' }}>
            <div className="flex items-center gap-2 mb-2">
                <Zap className="w-4 h-4 text-teal-600" />
                <h3 className="font-bold text-sm text-slate-50">AI Portfolio Analysis</h3>
                <span className="text-xs text-cyan-200 bg-cyan-500/10 px-2 py-0.5 rounded-full">Powered by Groq LLM</span>
            </div>
            {insight ? (
                <p className="text-sm text-slate-200 leading-relaxed mb-3 whitespace-pre-wrap">{insight}</p>
            ) : (
                <p className="text-sm text-slate-300 mb-3">Get an AI-powered analysis of your portfolio using ensemble signals, sector trends, and market context.</p>
            )}
            <button onClick={generate} disabled={loading} className="btn-primary px-4 py-2 text-xs flex items-center gap-2">
                {loading ? <RefreshCw className="w-3 h-3 spin" /> : <Zap className="w-3 h-3" />}
                {loading ? 'Analysing with AI...' : insight ? 'Regenerate AI Analysis' : 'Generate AI Analysis'}
            </button>
        </div>
    );
}

export function GenerateTab({ onPortfolioGenerated, portfolio }: Props) {
    const [amount, setAmount] = useState(500000);
    const [mandate, setMandate] = useState<UserMandate>({
        investment_horizon_weeks: '4-8',
        max_portfolio_drawdown_pct: 12,
        max_position_size_pct: 12.5,
        preferred_num_positions: 10,
        sector_inclusions: [],
        sector_exclusions: [],
        allow_small_caps: false,
        risk_attitude: 'balanced',
    });
    const [sectorIncludeInput, setSectorIncludeInput] = useState('');
    const [sectorExcludeInput, setSectorExcludeInput] = useState('');
    const [sectorCodes, setSectorCodes] = useState<string[]>([]);
    const [generating, setGenerating] = useState(false);
    const [activeModelVariant, setActiveModelVariant] = useState<ModelVariant>('RULES');
    const [activeModelVersion, setActiveModelVersion] = useState<string>('');
    const [activeTrainingMode, setActiveTrainingMode] = useState<string>('');
    const [artifactClassification, setArtifactClassification] = useState<'bootstrap' | 'standard' | ''>('');
    const [modelStatusReason, setModelStatusReason] = useState<string>('');
    const [generationNotice, setGenerationNotice] = useState<{ tone: 'info' | 'warning'; text: string } | null>(null);

    useEffect(() => {
        const loadModelStatus = async () => {
            try {
                const status = await getCurrentModelStatusViaApi();
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
                setSectorCodes(questionnaire.sector_codes);
                setSectorIncludeInput(questionnaire.defaults.sector_inclusions.join(', '));
                setSectorExcludeInput(questionnaire.defaults.sector_exclusions.join(', '));
            } catch {
                setSectorCodes([]);
            }
        };
        void loadQuestionnaire();
    }, []);

    const updateMandate = <K extends keyof UserMandate>(key: K, value: UserMandate[K]) => {
        setMandate(current => ({ ...current, [key]: value }));
    };

    const handleGenerate = async () => {
        setGenerating(true);
        setGenerationNotice(null);
        try {
            const payload: UserMandate = {
                ...mandate,
                sector_inclusions: sectorIncludeInput.split(',').map(item => item.trim()).filter(Boolean),
                sector_exclusions: sectorExcludeInput.split(',').map(item => item.trim()).filter(Boolean),
            };
            const p = await generatePortfolioViaApi(amount, payload, activeModelVariant);
            onPortfolioGenerated(p);
            setGenerationNotice({
                tone: 'info',
                text:
                    p.modelSource === 'LIGHTGBM'
                        ? `Using local LightGBM hybrid expected returns${p.modelVersion ? ` (v${p.modelVersion})` : ''}${p.predictionHorizonDays ? ` over ${p.predictionHorizonDays} trading days` : ''}, with a ${p.lookbackWindowDays ?? '--'}-day lookback and ${p.expectedHoldingPeriodDays ?? '--'}-day holding target.`
                        : 'Using the local rule-based portfolio allocator because no active LightGBM artifact is available.',
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

    useEffect(() => {
        const handleAction = async (e: any) => {
            const action = e.detail;
            if (action.name === 'generate_portfolio') {
                const capital = action.arguments.capital || amount;
                const riskEnum = action.arguments.risk;
                const rMap: any = { CONSERVATIVE: 'capital_preservation', MODERATE: 'balanced', AGGRESSIVE: 'growth' };
                const newRisk = rMap[riskEnum] || mandate.risk_attitude;
                
                setAmount(capital);
                setMandate(m => ({ ...m, risk_attitude: newRisk }));
                
                setGenerating(true);
                setGenerationNotice(null);
                try {
                    const payload: UserMandate = {
                        ...mandate,
                        risk_attitude: newRisk,
                        sector_inclusions: sectorIncludeInput.split(',').map(item => item.trim()).filter(Boolean),
                        sector_exclusions: sectorExcludeInput.split(',').map(item => item.trim()).filter(Boolean),
                    };
                    const p = await generatePortfolioViaApi(capital, payload, activeModelVariant);
                    onPortfolioGenerated(p);
                    setGenerationNotice({ tone: 'info', text: 'Portfolio generated successfully by AI Copilot.' });
                } catch (error) {
                    setGenerationNotice({ tone: 'warning', text: `Failed: ${error instanceof Error ? error.message : 'Unknown error'}` });
                } finally {
                    setGenerating(false);
                }
            }
        };
        window.addEventListener('AI_ACTION', handleAction);
        return () => window.removeEventListener('AI_ACTION', handleAction);
    }, [mandate, sectorIncludeInput, sectorExcludeInput, activeModelVariant, amount, onPortfolioGenerated]);

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

    const riskOpts: { id: RiskAttitude; label: string; icon: React.ReactNode; desc: string }[] = [
        { id: 'capital_preservation', label: 'Preserve', icon: <ShieldCheck className="w-5 h-5" />, desc: 'Strict downside control' },
        { id: 'balanced', label: 'Balanced', icon: <TrendingUp className="w-5 h-5" />, desc: 'Risk and upside in balance' },
        { id: 'growth', label: 'Growth', icon: <Zap className="w-5 h-5" />, desc: 'Higher upside within caps' },
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
                        <div className="alert-info text-xs">
                            Active local engine: {activeModelVariant === 'LIGHTGBM_HYBRID' ? `LightGBM hybrid${activeModelVersion ? ` v${activeModelVersion}` : ''}` : 'Rules only'}
                            {activeModelVariant === 'RULES' && modelStatusReason ? ` (${modelStatusReason})` : ''}
                        </div>
                        {activeModelVariant === 'LIGHTGBM_HYBRID' && (
                            <div className={artifactClassification === 'bootstrap' ? 'alert-warning text-xs' : 'alert-success text-xs'}>
                                Training mode: {activeTrainingMode || 'unknown'}.
                                {artifactClassification === 'bootstrap'
                                    ? ' This is still a bootstrap artifact and should be treated as a development/demo model.'
                                    : ' This artifact passed the standard local validation flow.'}
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

                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="block text-xs font-600 text-slate-500 mb-1.5">Horizon (weeks)</label>
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
                                <label className="block text-xs font-600 text-slate-500 mb-1.5">Target Positions</label>
                                <input
                                    type="number"
                                    value={mandate.preferred_num_positions}
                                    onChange={e => updateMandate('preferred_num_positions', Number(e.target.value))}
                                    className="input-field px-4 py-2.5"
                                />
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="block text-xs font-600 text-slate-500 mb-1.5">Max Drawdown %</label>
                                <input
                                    type="number"
                                    min={1}
                                    max={100}
                                    value={mandate.max_portfolio_drawdown_pct}
                                    onChange={e => updateMandate('max_portfolio_drawdown_pct', Number(e.target.value))}
                                    className="input-field px-4 py-2.5"
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-600 text-slate-500 mb-1.5">Max Position %</label>
                                <input
                                    type="number"
                                    min={1}
                                    max={100}
                                    value={mandate.max_position_size_pct}
                                    onChange={e => updateMandate('max_position_size_pct', Number(e.target.value))}
                                    className="input-field px-4 py-2.5"
                                />
                            </div>
                        </div>

                        <div>
                            <label className="block text-xs font-600 text-slate-500 mb-2">Risk Attitude</label>
                            <div className="grid grid-cols-3 gap-2">
                                {riskOpts.map(r => (
                                    <button
                                        key={r.id}
                                        onClick={() => updateMandate('risk_attitude', r.id)}
                                        className={`risk-btn ${mandate.risk_attitude === r.id ? 'active-risk' : ''}`}
                                    >
                                        {r.icon}
                                        <span>{r.label}</span>
                                        <span className="text-[9px] font-normal normal-case tracking-normal text-slate-400">{r.desc}</span>
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div>
                            <label className="block text-xs font-600 text-slate-500 mb-1.5">Sector Inclusions</label>
                            <input
                                value={sectorIncludeInput}
                                onChange={e => setSectorIncludeInput(e.target.value)}
                                className="input-field px-4 py-2.5"
                                placeholder="e.g. Banking, IT, Pharma"
                            />
                        </div>

                        <div>
                            <label className="block text-xs font-600 text-slate-500 mb-1.5">Sector Exclusions</label>
                            <input
                                value={sectorExcludeInput}
                                onChange={e => setSectorExcludeInput(e.target.value)}
                                className="input-field px-4 py-2.5"
                                placeholder="e.g. Energy, Real Estate"
                            />
                            {sectorCodes.length > 0 && (
                                <p className="text-[10px] text-slate-400 mt-1">
                                    Available sectors: {sectorCodes.join(', ')}
                                </p>
                            )}
                        </div>

                        <label className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
                            <span>Allow small caps</span>
                            <input
                                type="checkbox"
                                checked={mandate.allow_small_caps}
                                onChange={e => updateMandate('allow_small_caps', e.target.checked)}
                            />
                        </label>

                        <button onClick={handleGenerate} disabled={generating} className="btn-primary w-full py-3 text-sm flex items-center justify-center gap-2">
                            {generating ? 'Generating...' : 'Generate AI Portfolio'} <ArrowRight className="w-4 h-4" />
                        </button>
                    </div>
                </div>

                {portfolio && (
                    <>
                        {(portfolio.modelVariant || portfolio.modelSource) && (
                            <div className="card p-5">
                                <h3 className="font-bold text-sm mb-3 text-slate-900">Model Runtime</h3>
                                <div className="grid grid-cols-2 gap-3 text-xs">
                                    <div className="stat-row">
                                        <span className="stat-label">Variant</span>
                                        <span className="stat-value">{portfolio.modelVariant || 'RULES'}</span>
                                    </div>
                                    <div className="stat-row">
                                        <span className="stat-label">Source</span>
                                        <span className="stat-value">{portfolio.modelSource || 'RULES'}</span>
                                    </div>
                                    <div className="stat-row">
                                        <span className="stat-label">Version</span>
                                        <span className="stat-value">{portfolio.modelVersion || 'rules'}</span>
                                    </div>
                                    <div className="stat-row">
                                        <span className="stat-label">Horizon</span>
                                        <span className="stat-value">{portfolio.predictionHorizonDays || 21}D</span>
                                    </div>
                                    <div className="stat-row">
                                        <span className="stat-label">Lookback</span>
                                        <span className="stat-value">{portfolio.lookbackWindowDays || '--'}D</span>
                                    </div>
                                    <div className="stat-row">
                                        <span className="stat-label">Holding</span>
                                        <span className="stat-value">{portfolio.expectedHoldingPeriodDays || '--'}D</span>
                                    </div>
                                    <div className="stat-row">
                                        <span className="stat-label">Training</span>
                                        <span className="stat-value">{activeTrainingMode || 'rules'}</span>
                                    </div>
                                    <div className="stat-row">
                                        <span className="stat-label">Artifact</span>
                                        <span className="stat-value">{artifactClassification || 'n/a'}</span>
                                    </div>
                                </div>
                            </div>
                        )}

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
                                    ['Exchange Txn', `Rs ${costs!.exchangeTxn.toFixed(2)}`],
                                    ['SEBI Fees', `Rs ${costs!.sebi.toFixed(2)}`],
                                    ['GST', `Rs ${costs!.gst.toFixed(2)}`],
                                    ['Slippage (0.1%)', `Rs ${costs!.slippage.toFixed(2)}`],
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
                        <p className="text-base font-semibold mb-1">Set the mandate questionnaire and generate</p>
                        <p className="text-sm">The allocator will respect horizon, drawdown, sector, and news constraints.</p>
                    </div>
                ) : (
                    <>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            <MetricCard label="Total Invested" value={`Rs ${(portfolio.totalInvested / 100000).toFixed(2)}L`} sub="After rounding to whole shares" color="slate" />
                            <MetricCard label="Portfolio Beta" value={portfolio.metrics.avgBeta.toFixed(2)} sub="vs Nifty 50 = 1.00" color={portfolio.metrics.avgBeta > 1.3 ? 'red' : portfolio.metrics.avgBeta < 0.8 ? 'green' : 'blue'} trend={portfolio.metrics.avgBeta > 1.3 ? 'up' : 'down'} />
                            <MetricCard label="Sharpe Ratio" value={portfolio.metrics.sharpeRatio.toFixed(2)} sub="Risk-free rate: 7% pa" color={portfolio.metrics.sharpeRatio > 1.2 ? 'green' : 'amber'} trend="up" />
                            <MetricCard label="Exp. Annual Return" value={`${portfolio.metrics.estimatedAnnualReturn.toFixed(1)}%`} sub={`Volatility: ${portfolio.metrics.estimatedVolatility.toFixed(1)}%`} color="green" trend="up" />
                        </div>

                        {portfolio.mandate && (
                            <div className="card p-5">
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
                                        <span className="stat-label">Drawdown</span>
                                        <span className="stat-value">{portfolio.mandate.max_portfolio_drawdown_pct}%</span>
                                    </div>
                                    <div className="stat-row">
                                        <span className="stat-label">Max Position</span>
                                        <span className="stat-value">{portfolio.mandate.max_position_size_pct}%</span>
                                    </div>
                                </div>
                            </div>
                        )}

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
                                            <th>Stock</th><th>Sector</th><th>Wt%</th><th>News</th><th>Shares</th><th className="text-right">Amount</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {portfolio.allocations.map((a, i) => (
                                            <tr key={i}>
                                                <td>
                                                    <div className="font-semibold text-slate-900">{a.stock.symbol}</div>
                                                    <div className="text-xs text-slate-400">{a.stock.name}</div>
                                                    {a.drivers && a.drivers.length > 0 && (
                                                        <div className="text-[10px] text-slate-500 mt-1">
                                                            ML drivers: {a.drivers.slice(0, 2).join(', ')}
                                                        </div>
                                                    )}
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
                                                <td>
                                                    <div className="text-xs text-slate-600">
                                                        <div className="font-medium">S {a.news_sentiment?.toFixed(2) ?? '0.00'} · I {a.news_impact?.toFixed(1) ?? '0.0'}</div>
                                                        <div className="text-[10px] text-slate-400 max-w-52">{a.news_explanation ?? 'No mapped news.'}</div>
                                                    </div>
                                                </td>
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
