import React, { useEffect, useRef, useState } from 'react';
import { MessageCircle, X, Send, Bot, User, Sparkles } from 'lucide-react';
import { Portfolio } from '../services/portfolioService';
import { postExplainChat, fetchPlatformContext, type ExplainChatHistoryItem } from '../services/backendApi';

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
        { role: 'ai', text: "Hi! I'm your NSE AI Portfolio Assistant. I can explain the current portfolio, reason about NSE stocks, and answer strategy questions from the live platform context." }
    ]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const send = async () => {
        if (!input.trim() || loading) return;

        const userMsg = input.trim();
        const placeholderIndex = messages.length + 1;
        const historyMessages = [...messages, { role: 'user' as const, text: userMsg }]
            .filter(message => message.text.trim().length > 0)
            .slice(-6);

        setInput('');
        setMessages(prev => [...prev, { role: 'user', text: userMsg }, { role: 'ai', text: '', thinking: [] }]);
        setLoading(true);

        const thinkingSteps = [
            "Refreshing portfolio and market context...",
            "Checking ensemble signals and recent drivers...",
            "Reviewing news and sector context...",
            "Drafting a portfolio-aware response..."
        ];

        try {
            const latestPlatformContext = await fetchPlatformContext();

            for (let index = 0; index < thinkingSteps.length; index++) {
                await new Promise(resolve => setTimeout(resolve, 350));
                setMessages(prev => prev.map((message, messageIndex) =>
                    messageIndex === placeholderIndex
                        ? { ...message, thinking: thinkingSteps.slice(0, index + 1) }
                        : message
                ));
            }

            const history: ExplainChatHistoryItem[] = historyMessages.map(message => ({
                role: message.role === 'ai' ? 'assistant' : 'user',
                content: message.text,
            }));

            const fullContextPayload = {
                ...latestPlatformContext,
                portfolio: portfolio ? {
                    allocations: portfolio.allocations,
                    mandate: portfolio.mandate,
                    capital_amount: portfolio.totalInvested,
                } : null,
            };

            const data = await postExplainChat(userMsg, history, fullContextPayload);
            setMessages(prev => prev.map((message, messageIndex) =>
                messageIndex === placeholderIndex
                    ? { role: 'ai', text: data.response, action: data.action }
                    : message
            ));

            if (data.action) {
                window.dispatchEvent(new CustomEvent('AI_ACTION', { detail: data.action }));
            }
        } catch (error) {
            setMessages(prev => prev.map((message, messageIndex) =>
                messageIndex === placeholderIndex
                    ? {
                        role: 'ai',
                        text: `Assistant request failed: ${error instanceof Error ? error.message : 'unknown error'}.`,
                    }
                    : message
            ));
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
                        {messages.map((message, index) => (
                            <div key={index} className={`flex gap-2 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}>
                                <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${message.role === 'ai' ? 'bg-teal-100' : 'bg-blue-100'}`}>
                                    {message.role === 'ai'
                                        ? <Bot className="w-3.5 h-3.5 text-teal-700" />
                                        : <User className="w-3.5 h-3.5 text-blue-700" />}
                                </div>
                                <div
                                    className={`px-3 py-2 rounded-2xl text-sm max-w-[80%] leading-relaxed whitespace-pre-wrap ${message.role === 'ai'
                                        ? 'bg-slate-100 text-slate-800 rounded-tl-sm'
                                        : 'bg-teal-600 text-white rounded-tr-sm'
                                        }`}
                                >
                                    {message.thinking && message.thinking.length > 0 && (
                                        <div className="thinking-blocks mb-2">
                                            {message.thinking.map((step, thinkingIndex) => (
                                                <div key={thinkingIndex} className="thinking-step">
                                                    <Sparkles className="w-3 h-3 inline mr-1" />
                                                    {step}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                    {message.text}
                                    {message.action && (
                                        <div className="mt-2 text-[10px] font-mono text-teal-700 bg-teal-50 border border-teal-200 rounded px-2 py-1 inline-flex items-center gap-1">
                                            <Sparkles className="w-3 h-3" /> Executed: {message.action.name.replace(/_/g, ' ')}
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
                            onKeyDown={e => e.key === 'Enter' && void send()}
                        />
                        <button
                            onClick={() => void send()}
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
                    onClick={() => setOpen(value => !value)}
                    className="btn-primary w-14 h-14 rounded-full flex items-center justify-center shadow-xl"
                    title="AI Strategy Assistant"
                >
                    {open ? <X className="w-6 h-6" /> : <MessageCircle className="w-6 h-6" />}
                </button>
            </div>
        </>
    );
}
