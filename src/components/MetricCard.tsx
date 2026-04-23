import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface MetricCardProps {
    label: string;
    value: string | number;
    sub?: string | React.ReactNode;
    color?: 'green' | 'red' | 'blue' | 'amber' | 'purple' | 'slate';
    trend?: 'up' | 'down' | 'flat';
    icon?: React.ReactNode;
}

export function MetricCard({ label, value, sub, color = 'slate', trend, icon }: MetricCardProps) {
    const colorMap = {
        green: 'text-emerald-500',
        red: 'text-rose-500',
        blue: 'text-blue-500',
        amber: 'text-yellow-500',
        purple: 'text-violet-400',
        slate: 'text-[#f5f5f7]',
    };

    const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus;
    const trendColor = trend === 'up' ? 'text-emerald-500' : trend === 'down' ? 'text-rose-500' : 'text-[#6e6e73]';

    return (
        <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-4 animate-fade-in">
            <div className="flex items-start justify-between mb-2">
                <p className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em]" style={{ marginBottom: 0 }}>{label}</p>
                <div className="flex items-center gap-1">
                    {trend && <TrendIcon className={`w-4 h-4 ${trendColor}`} />}
                    {icon && <span className="text-[#6e6e73]">{icon}</span>}
                </div>
            </div>
            <p className={`text-xl font-bold font-mono ${colorMap[color]}`}>{value}</p>
            {sub && <p className="text-xs text-[#6e6e73] mt-1">{sub}</p>}
        </div>
    );
}

export function SectorChip({ sector }: { sector: string }) {
    const colorMap: Record<string, string> = {
        'IT': 'background:rgba(59,130,246,0.1);color:#60a5fa',
        'Banking': 'background:rgba(234,179,8,0.1);color:#facc15',
        'Finance': 'background:rgba(234,179,8,0.1);color:#facc15',
        'FMCG': 'background:rgba(16,185,129,0.1);color:#34d399',
        'Energy': 'background:rgba(239,68,68,0.1);color:#f87171',
        'Pharma': 'background:rgba(139,92,246,0.1);color:#a78bfa',
        'Auto': 'background:rgba(249,115,22,0.1);color:#fb923c',
        'Metals': 'background:rgba(148,163,184,0.1);color:#cbd5e1',
        'Consumer Durables': 'background:rgba(236,72,153,0.1);color:#f472b6',
        'Infra': 'background:rgba(16,185,129,0.1);color:#34d399',
        'Telecom': 'background:rgba(14,165,233,0.1);color:#38bdf8',
        'Cement': 'background:rgba(115,115,115,0.1);color:#d4d4d4',
        'Insurance': 'background:rgba(139,92,246,0.1);color:#a78bfa',
        'Real Estate': 'background:rgba(249,115,22,0.1);color:#fb923c',
        'Chemicals': 'background:rgba(34,197,94,0.1);color:#4ade80',
        'Tech/Internet': 'background:rgba(59,130,246,0.1);color:#60a5fa',
        'Gold': 'background:rgba(234,179,8,0.1);color:#eab308',
        'Liquid': 'background:rgba(16,185,129,0.1);color:#10b981',
        'Index': 'background:rgba(148,163,184,0.1);color:#94a3b8',
        'Silver': 'background:rgba(148,163,184,0.1);color:#cbd5e1',
        'Logistics': 'background:rgba(225,29,72,0.1);color:#fb7185',
        'Tourism': 'background:rgba(168,85,247,0.1);color:#c084fc',
        'Miscellaneous': 'background:rgba(115,115,115,0.1);color:#a3a3a3',
    };
    const style = colorMap[sector] || 'background:rgba(148,163,184,0.1);color:#94a3b8';
    const [bg, fg] = style.split(';');
    return (
        <span
            className="px-2 py-0.5 rounded text-[9px] font-mono font-bold uppercase tracking-wider border border-white/5"
            style={{ backgroundColor: bg.split(':')[1], color: fg.split(':')[1] }}
        >
            {sector}
        </span>
    );
}
