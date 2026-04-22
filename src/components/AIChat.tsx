import React, { useEffect, useRef, useState } from 'react';
import { MessageCircle, X, Send, Bot, User, Sparkles } from 'lucide-react';
import { Portfolio } from '../services/portfolioService';
import { postExplainChat, fetchPlatformContext, type ExplainChatHistoryItem } from '../services/backendApi';
import { answerChatQuestion } from '../services/localAdvisor';

interface Message {
    role: 'user' | 'ai';
    text: string;
    action?: { name: string; arguments: any };
    thinking?: string[];
}

interface AIChatProps {
    portfolio: Portfolio | null;
}

export function AIChat({ portfolio }: AIChatProps) {
    const [open, setOpen] = useState(false);
    const [messages, setMessages] = useState<Message[]>([
        { role: 'ai', text: "Hi! I'm your NSE AI Portfolio Assistant. I know your current portfolio, market regime, and top trade ideas. Ask me anything." }
    ]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [platformContext, setPlatformContext] = useState<Record<string, unknown>>({});
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        fetchPlatformContext().then(ctx => setPlatformContext(ctx));
    }, []);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const send = async () => {
        if (!input.trim() || loading) return;

        const userMsg = input.trim();
        setInput('');
        setMessages(prev => [...prev, { role: 'user', text: userMsg }]);
        setLoading(true);

        // Simulate thinking steps
        const thinkingSteps = [
            "Retrieving historical volatility data...",
            "Running LightGBM inference on market factors...",
            "Analyzing news sentiment from financial feeds...",
            "Cross-referencing with institutional flows...",
            "Generating ensemble prediction..."
        ];

        setMessages(prev => [...prev, { role: 'ai', text: '', thinking: thinkingSteps }]);

        for (let i = 0; i < thinkingSteps.length; i++) {
            await new Promise(resolve => setTimeout(resolve, 800));
            setMessages(prev => prev.map((msg, idx) =>
                idx === prev.length - 1 && msg.role === 'ai'
                    ? { ...msg, thinking: thinkingSteps.slice(0, i + 1) }
                    : msg
            ));
        }

        try {
            const history: ExplainChatHistoryItem[] = messages.slice(-6).map(m => ({
                role: m.role === 'ai' ? 'assistant' : 'user',
                content: m.text,
            }));

            const portfolioContextText = portfolio
                ? `Portfolio: ${portfolio.mandate?.risk_attitude ?? portfolio.riskProfile}, horizon ${portfolio.mandate?.investment_horizon_weeks ?? 'n/a'} weeks, ₹${portfolio.totalInvested.toLocaleString('en-IN')}, ${portfolio.allocations.length} stocks (${portfolio.allocations.slice(0, 5).map(a => `${a.stock.symbol} (${a.weight.toFixed(1)}%)`).join(', ')})`
                : 'No portfolio generated yet.';

            const enrichedMessage = `${userMsg}\n\n[Context: ${portfolioContextText}]`;

            // Merge the frontend portfolio object into the platform context payload
            const fullContextPayload = {
                ...platformContext,
                portfolio: portfolio ? {
                    allocations: portfolio.allocations,
                    mandate: portfolio.mandate,
                    capital_amount: portfolio.totalInvested
                } : null
            };

            const data = await postExplainChat(enrichedMessage, history, fullContextPayload);
            const fallbackRequired = /AI unavailable|temporarily unavailable/i.test(data.response);
            const localAction = fallbackRequired ? inferLocalAiAction(userMsg) : data.action;
            const localResponse = fallbackRequired ? answerChatQuestion(userMsg, portfolio) : data.response;
            setMessages(prev => [...prev, { role: 'ai', text: localResponse, action: localAction }]);
            if (localAction) {
                window.dispatchEvent(new CustomEvent('AI_ACTION', { detail: localAction }));
            }
        } catch {
            const localAction = inferLocalAiAction(userMsg);
            setMessages(prev => [...prev, {
                role: 'ai',
                text: answerChatQuestion(userMsg, portfolio),
                action: localAction,
            }]);
            if (localAction) {
                window.dispatchEvent(new CustomEvent('AI_ACTION', { detail: localAction }));
            }
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
                                <p className="text-sm font-bold text-white">NSE AI Assistant</p>
                                <p className="text-xs text-teal-100 flex items-center gap-1">
                                    <Sparkles className="w-3 h-3" /> Powered by Groq LLM
                                </p>
                            </div>
                        </div>
                        <button onClick={() => setOpen(false)} className="text-white/70 hover:text-white transition-colors">
                            <X className="w-5 h-5" />
                        </button>
                    </div>

                    <div className="flex-1 overflow-y-auto p-4 space-y-3" style={{ maxHeight: '340px' }}>
                        {messages.map((msg, i) => (
                            <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                                <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${msg.role === 'ai' ? 'bg-teal-100' : 'bg-blue-100'}`}>
                                    {msg.role === 'ai'
                                        ? <Bot className="w-3.5 h-3.5 text-teal-700" />
                                        : <User className="w-3.5 h-3.5 text-blue-700" />}
                                </div>
                                <div
                                    className={`px-3 py-2 rounded-2xl text-sm max-w-[80%] leading-relaxed whitespace-pre-wrap ${msg.role === 'ai'
                                        ? 'bg-slate-100 text-slate-800 rounded-tl-sm'
                                        : 'bg-teal-600 text-white rounded-tr-sm'
                                        }`}
                                >
                                    {msg.thinking && msg.thinking.length > 0 && (
                                        <div className="thinking-blocks mb-2">
                                            {msg.thinking.map((step, idx) => (
                                                <div key={idx} className="thinking-step">
                                                    <Sparkles className="w-3 h-3 inline mr-1" />
                                                    {step}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                    {msg.text}
                                    {msg.action && (
                                        <div className="mt-2 text-[10px] font-mono text-teal-700 bg-teal-50 border border-teal-200 rounded px-2 py-1 inline-flex items-center gap-1">
                                            <Sparkles className="w-3 h-3" /> Executed: {msg.action.name.replace(/_/g, ' ')}
                                        </div>
                                    )}
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
                            placeholder="Ask about stocks, taxes, strategy..."
                            value={input}
                            onChange={e => setInput(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && send()}
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
                    onClick={() => setOpen(o => !o)}
                    className="btn-primary w-14 h-14 rounded-full flex items-center justify-center shadow-xl"
                    title="AI Strategy Assistant"
                >
                    {open ? <X className="w-6 h-6" /> : <MessageCircle className="w-6 h-6" />}
                </button>
            </div>
        </>
    );
}

function inferLocalAiAction(message: string): { name: string; arguments: any } | undefined {
    const normalized = message.toLowerCase();

    if (normalized.includes('compare') || normalized.includes('benchmark')) {
        return { name: 'benchmark_portfolio', arguments: {} };
    }
    if (normalized.includes('trade idea') || normalized.includes('ideas')) {
        return { name: 'navigate_to_tab', arguments: { tab_name: 'IDEAS' } };
    }
    if (normalized.includes('backtest')) {
        return { name: 'run_backtest', arguments: {} };
    }
    if (normalized.includes('analyze') && normalized.includes('portfolio')) {
        return { name: 'analyze_portfolio', arguments: {} };
    }
    if (normalized.includes('market event')) {
        return { name: 'navigate_to_tab', arguments: { tab_name: 'EVENTS' } };
    }
    if (normalized.includes('market') || normalized.includes('news')) {
        return { name: 'navigate_to_tab', arguments: { tab_name: 'MARKET' } };
    }
    if (normalized.includes('generate') || normalized.includes('build') || normalized.includes('create portfolio')) {
        return { name: 'generate_portfolio', arguments: { capital: 500000, risk: 'MODERATE' } };
    }

    return undefined;
}
