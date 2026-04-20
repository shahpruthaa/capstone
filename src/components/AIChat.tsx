import React, { useEffect, useRef, useState } from 'react';
import { Bot, MessageCircle, Send, Sparkles, User, X } from 'lucide-react';

import { BacktestResult } from '../services/backtestEngine';
import { Portfolio } from '../services/portfolioService';
import {
    CopilotAction,
    CopilotChatResponse,
    TradeIdea,
    fetchTradeIdeasViaApi,
    generatePortfolioViaApi,
    getMandateQuestionnaireViaApi,
    getMarketContextViaApi,
    MarketContext,
    postExplainChat,
    runBacktestViaApi,
} from '../services/backendApi';

type AppTab = 'MARKET' | 'PORTFOLIO' | 'IDEAS' | 'BACKTEST' | 'COMPARE';

interface Message {
    role: 'user' | 'ai';
    text: string;
}

interface AIChatProps {
    activeTab: AppTab;
    portfolio: Portfolio | null;
    tradeIdeas: TradeIdea[];
    backtestResult: BacktestResult | null;
    marketContext: MarketContext | null;
    onPortfolioGenerated: (portfolio: Portfolio | null) => void;
    onTradeIdeasLoaded: (ideas: TradeIdea[]) => void;
    onBacktestCompleted: (result: BacktestResult | null) => void;
    onMarketContextLoaded: (context: MarketContext | null) => void;
    onNavigate: (tab: AppTab) => void;
}

const DEFAULT_BACKTEST_CONFIG = {
    startDate: '2025-01-01',
    endDate: '2025-12-31',
    stopLossPct: 0.15,
    takeProfitPct: 0.4,
    rebalanceFreq: 'Quarterly' as const,
    slippagePct: 0.001,
};

function buildGroundedContext(
    activeTab: AppTab,
    portfolio: Portfolio | null,
    tradeIdeas: TradeIdea[],
    backtestResult: BacktestResult | null,
    marketContext: MarketContext | null,
): Record<string, unknown> {
    return {
        active_tab: activeTab,
        portfolio: portfolio ? {
            total_invested: portfolio.totalInvested,
            mandate: portfolio.mandate ?? null,
            metrics: {
                avg_beta: portfolio.metrics.avgBeta,
                estimated_annual_return: portfolio.metrics.estimatedAnnualReturn,
                estimated_volatility: portfolio.metrics.estimatedVolatility,
                sharpe_ratio: portfolio.metrics.sharpeRatio,
                diversification_score: portfolio.metrics.correlationScore,
            },
            allocations: portfolio.allocations.map((allocation) => ({
                symbol: allocation.stock.symbol,
                sector: allocation.stock.sector,
                weight: allocation.weight,
                drivers: allocation.drivers ?? [],
                rationale: allocation.rationale ?? '',
                ml_pred_21d_return: allocation.ml_pred_21d_return ?? null,
                ml_pred_annual_return: allocation.ml_pred_annual_return ?? null,
                death_risk: allocation.death_risk ?? null,
                lstm_signal: allocation.lstm_signal ?? null,
                news_sentiment: allocation.news_sentiment ?? null,
                news_impact: allocation.news_impact ?? null,
            })),
        } : {},
        trade_ideas: tradeIdeas.slice(0, 8),
        backtest: backtestResult ? {
            total_return: backtestResult.totalReturn,
            cagr: backtestResult.cagr,
            max_drawdown: backtestResult.maxDrawdown,
            sharpe: backtestResult.sharpe,
            sortino: backtestResult.sortino,
            calmar: backtestResult.calmar,
            win_rate: backtestResult.winRate,
            total_trades: backtestResult.totalTrades,
            final_value: backtestResult.finalValue,
            initial_investment: backtestResult.initialInvestment,
            notes: backtestResult.notes ?? [],
        } : {},
        market_context: marketContext ? {
            overall_market_sentiment: marketContext.overall_market_sentiment,
            top_event_summary: marketContext.top_event_summary,
            briefing: marketContext.briefing,
            actionable_takeaways: marketContext.actionableTakeaways,
            articles: marketContext.articles.slice(0, 5),
            sector_sentiment: marketContext.sector_sentiment,
        } : {},
    };
}

function summarisePortfolio(portfolio: Portfolio): string {
    const holdings = portfolio.allocations
        .slice(0, 4)
        .map((allocation) => `${allocation.stock.symbol} (${allocation.weight.toFixed(1)}%)`)
        .join(', ');
    return `Portfolio generated: ${portfolio.allocations.length} holdings, expected return ${portfolio.metrics.estimatedAnnualReturn.toFixed(1)}%, expected volatility ${portfolio.metrics.estimatedVolatility.toFixed(1)}%, top weights ${holdings}.`;
}

function summariseTradeIdeas(ideas: TradeIdea[]): string {
    if (ideas.length === 0) {
        return 'Trade ideas refreshed, but nothing cleared the current checklist threshold.';
    }
    const leaders = ideas.slice(0, 3).map((idea) => `${idea.symbol} (${idea.checklist_score}/10)`).join(', ');
    return `Trade ideas refreshed. ${ideas.length} ideas are live; the strongest current names are ${leaders}.`;
}

function summariseBacktest(result: BacktestResult): string {
    return `Backtest complete: total return ${result.totalReturn.toFixed(2)}%, CAGR ${result.cagr.toFixed(2)}%, max drawdown ${result.maxDrawdown.toFixed(2)}%, Sharpe ${result.sharpe.toFixed(2)}, and ${result.totalTrades} trades.`;
}

function summariseMarket(context: MarketContext): string {
    return `Market pulse refreshed. Sentiment is ${context.overall_market_sentiment >= 0 ? 'positive' : 'negative'} at ${context.overall_market_sentiment.toFixed(2)}, and the lead narrative is: ${context.briefing}`;
}

export function AIChat({
    activeTab,
    portfolio,
    tradeIdeas,
    backtestResult,
    marketContext,
    onPortfolioGenerated,
    onTradeIdeasLoaded,
    onBacktestCompleted,
    onMarketContextLoaded,
    onNavigate,
}: AIChatProps) {
    const [open, setOpen] = useState(false);
    const [messages, setMessages] = useState<Message[]>([
        {
            role: 'ai',
            text: "Hi, I'm your AlphaLens copilot. I can answer from the live portfolio, trade ideas, backtests, and market pulse, and I can also run those workflows when you ask in plain English.",
        },
    ]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const appendAiMessage = (text: string) => {
        setMessages((prev) => [...prev, { role: 'ai', text }]);
    };

    const executeAction = async (action: CopilotAction): Promise<string> => {
        if (action.blocked_reason) {
            return action.blocked_reason;
        }

        if (action.type === 'generate_portfolio') {
            const questionnaire = await getMandateQuestionnaireViaApi();
            const params = action.params ?? {};
            const mandate = {
                ...questionnaire.defaults,
                risk_attitude: typeof params.risk_attitude === 'string' ? params.risk_attitude : questionnaire.defaults.risk_attitude,
                investment_horizon_weeks: typeof params.investment_horizon_weeks === 'string'
                    ? params.investment_horizon_weeks
                    : questionnaire.defaults.investment_horizon_weeks,
                sector_inclusions: Array.isArray(params.sector_inclusions) ? params.sector_inclusions.filter((item): item is string => typeof item === 'string') : questionnaire.defaults.sector_inclusions,
                sector_exclusions: Array.isArray(params.sector_exclusions) ? params.sector_exclusions.filter((item): item is string => typeof item === 'string') : questionnaire.defaults.sector_exclusions,
                allow_small_caps: typeof params.allow_small_caps === 'boolean' ? params.allow_small_caps : questionnaire.defaults.allow_small_caps,
            };
            const capital = typeof params.capital_amount === 'number' ? params.capital_amount : 500000;
            const nextPortfolio = await generatePortfolioViaApi(capital, mandate, 'LIGHTGBM_HYBRID');
            onPortfolioGenerated(nextPortfolio);
            onNavigate('PORTFOLIO');
            return summarisePortfolio(nextPortfolio);
        }

        if (action.type === 'load_trade_ideas') {
            const response = await fetchTradeIdeasViaApi({ regimeAware: true, minChecklistScore: 7, maxIdeas: 8 });
            const filtered = portfolio?.allocations.length
                ? response.filter((idea) => new Set(portfolio.allocations.map((allocation) => allocation.stock.symbol)).has(idea.symbol))
                : response;
            const nextIdeas = filtered.length > 0 ? filtered : response;
            onTradeIdeasLoaded(nextIdeas);
            onNavigate('IDEAS');
            return summariseTradeIdeas(nextIdeas);
        }

        if (action.type === 'run_backtest') {
            if (!portfolio) {
                return 'Generate a portfolio first so there is something concrete to backtest.';
            }
            const params = action.params ?? {};
            const nextResult = await runBacktestViaApi(
                portfolio,
                {
                    ...DEFAULT_BACKTEST_CONFIG,
                    startDate: typeof params.start_date === 'string' && params.start_date ? params.start_date : DEFAULT_BACKTEST_CONFIG.startDate,
                    endDate: typeof params.end_date === 'string' && params.end_date ? params.end_date : DEFAULT_BACKTEST_CONFIG.endDate,
                    rebalanceFreq: typeof params.rebalance_frequency === 'string'
                        ? params.rebalance_frequency as typeof DEFAULT_BACKTEST_CONFIG.rebalanceFreq
                        : DEFAULT_BACKTEST_CONFIG.rebalanceFreq,
                    stopLossPct: typeof params.stop_loss_pct === 'number' ? params.stop_loss_pct : DEFAULT_BACKTEST_CONFIG.stopLossPct,
                    takeProfitPct: typeof params.take_profit_pct === 'number' ? params.take_profit_pct : DEFAULT_BACKTEST_CONFIG.takeProfitPct,
                },
                'LIGHTGBM_HYBRID',
            );
            onBacktestCompleted(nextResult);
            onNavigate('BACKTEST');
            return summariseBacktest(nextResult);
        }

        const context = await getMarketContextViaApi();
        onMarketContextLoaded(context);
        onNavigate('MARKET');
        return summariseMarket(context);
    };

    const send = async () => {
        if (!input.trim() || loading) return;

        const userMsg = input.trim();
        setInput('');
        setMessages((prev) => [...prev, { role: 'user', text: userMsg }]);
        setLoading(true);

        try {
            const history = messages.slice(-6).map((message) => ({
                role: message.role === 'ai' ? 'assistant' : 'user',
                content: message.text,
            }));

            const groundedContext = buildGroundedContext(activeTab, portfolio, tradeIdeas, backtestResult, marketContext);
            const response: CopilotChatResponse = await postExplainChat(userMsg, history, groundedContext);
            appendAiMessage(response.response);

            if (response.action?.auto_execute && !response.action.blocked_reason) {
                appendAiMessage(`Running: ${response.action.label}...`);
                try {
                    const outcome = await executeAction(response.action);
                    appendAiMessage(outcome);
                } catch (error) {
                    appendAiMessage(error instanceof Error ? error.message : 'The requested action failed.');
                }
            } else if (response.action?.blocked_reason) {
                appendAiMessage(response.action.blocked_reason);
            }
        } catch {
            appendAiMessage('AI copilot is temporarily unavailable. Please try again in a moment.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            {open && (
                <div className="chat-window">
                    <div
                        className="flex items-center justify-between px-4 py-3 border-b border-slate-100"
                        style={{ background: 'linear-gradient(135deg, #0d9488, #0f766e)' }}
                    >
                        <div className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center">
                                <Bot className="w-4 h-4 text-white" />
                            </div>
                            <div>
                                <p className="text-sm font-bold text-white">AlphaLens Copilot</p>
                                <p className="text-xs text-teal-100 flex items-center gap-1">
                                    <Sparkles className="w-3 h-3" /> Grounded in portfolio, trade-idea, backtest, and market context
                                </p>
                            </div>
                        </div>
                        <button onClick={() => setOpen(false)} className="text-white/70 hover:text-white transition-colors">
                            <X className="w-5 h-5" />
                        </button>
                    </div>

                    <div className="px-4 py-2 border-b border-slate-100 bg-slate-50 text-[11px] text-slate-500">
                        Live context: {portfolio ? `${portfolio.allocations.length} holdings` : 'no portfolio'} · {tradeIdeas.length} ideas · {backtestResult ? 'backtest loaded' : 'no backtest'} · {marketContext ? 'market pulse loaded' : 'no market pulse'}
                    </div>

                    <div className="flex-1 overflow-y-auto p-4 space-y-3" style={{ maxHeight: '360px' }}>
                        {messages.map((message, index) => (
                            <div key={index} className={`flex gap-2 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}>
                                <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${message.role === 'ai' ? 'bg-teal-100' : 'bg-blue-100'}`}>
                                    {message.role === 'ai'
                                        ? <Bot className="w-3.5 h-3.5 text-teal-700" />
                                        : <User className="w-3.5 h-3.5 text-blue-700" />}
                                </div>
                                <div
                                    className={`px-3 py-2 rounded-2xl text-sm max-w-[82%] leading-relaxed whitespace-pre-wrap ${message.role === 'ai'
                                        ? 'bg-slate-100 text-slate-800 rounded-tl-sm'
                                        : 'bg-teal-600 text-white rounded-tr-sm'
                                        }`}
                                >
                                    {message.text}
                                </div>
                            </div>
                        ))}
                        {loading && (
                            <div className="flex gap-2">
                                <div className="w-7 h-7 rounded-full bg-teal-100 flex items-center justify-center flex-shrink-0">
                                    <Bot className="w-3.5 h-3.5 text-teal-700" />
                                </div>
                                <div className="px-3 py-2 bg-slate-100 rounded-2xl rounded-tl-sm">
                                    <div className="flex gap-1 items-center h-4">
                                        <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                        <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                        <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                    </div>
                                </div>
                            </div>
                        )}
                        <div ref={bottomRef} />
                    </div>

                    <div className="p-3 border-t border-slate-100 flex gap-2">
                        <input
                            className="input-field px-3 py-2 text-sm flex-1"
                            placeholder="Try: generate a balanced portfolio for 8 lakh, run a 2025 backtest, refresh trade ideas..."
                            value={input}
                            onChange={(event) => setInput(event.target.value)}
                            onKeyDown={(event) => event.key === 'Enter' && send()}
                        />
                        <button
                            onClick={send}
                            disabled={!input.trim() || loading}
                            className="btn-primary px-3 py-2 text-sm flex items-center gap-1"
                            style={{ borderRadius: '0.75rem' }}
                        >
                            <Send className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            )}

            <div className="chat-fab">
                <button
                    onClick={() => setOpen((value) => !value)}
                    className="btn-primary w-14 h-14 rounded-full flex items-center justify-center shadow-xl"
                    title="Open AlphaLens Copilot"
                >
                    {open ? <X className="w-6 h-6" /> : <MessageCircle className="w-6 h-6" />}
                </button>
            </div>
        </>
    );
}
