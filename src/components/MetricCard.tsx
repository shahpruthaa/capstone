import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface MetricCardProps {
    label: string;
    value: string | number;
    sub?: string;
    color?: 'green' | 'red' | 'blue' | 'amber' | 'purple' | 'slate';
    trend?: 'up' | 'down' | 'flat';
    icon?: React.ReactNode;
}

export function MetricCard({ label, value, sub, color = 'slate', trend, icon }: MetricCardProps) {
    const colorMap = {
        green: 'text-emerald-600',
        red: 'text-rose-500',
        blue: 'text-blue-600',
        amber: 'text-amber-600',
        purple: 'text-violet-600',
        slate: 'text-slate-800',
    };

    const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus;
    const trendColor = trend === 'up' ? 'text-emerald-500' : trend === 'down' ? 'text-rose-500' : 'text-slate-400';

    return (
        <div className="metric-card animate-fade-in">
            <div className="flex items-start justify-between mb-2">
                <p className="section-title" style={{ marginBottom: 0 }}>{label}</p>
                <div className="flex items-center gap-1">
                    {trend && <TrendIcon className={`w-4 h-4 ${trendColor}`} />}
                    {icon && <span className="text-slate-400">{icon}</span>}
                </div>
            </div>
            <p className={`text-2xl font-bold ${colorMap[color]}`}>{value}</p>
            {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
        </div>
    );
}

export function SectorChip({ sector }: { sector: string }) {
    const colorMap: Record<string, string> = {
        'IT': 'background:#dbeafe;color:#1d4ed8',
        'Banking': 'background:#fef3c7;color:#92400e',
        'Finance': 'background:#fef9c3;color:#713f12',
        'FMCG': 'background:#dcfce7;color:#15803d',
        'Energy': 'background:#fee2e2;color:#b91c1c',
        'Pharma': 'background:#ede9fe;color:#6d28d9',
        'Auto': 'background:#ffedd5;color:#c2410c',
        'Metals': 'background:#f1f5f9;color:#475569',
        'Consumer Durables': 'background:#fdf2f8;color:#9d174d',
        'Infra': 'background:#ecfdf5;color:#065f46',
        'Telecom': 'background:#f0f9ff;color:#075985',
        'Cement': 'background:#fafafa;color:#52525b',
        'Insurance': 'background:#f5f3ff;color:#6d28d9',
        'Real Estate': 'background:#fff7ed;color:#c2410c',
        'Chemicals': 'background:#f0fdf4;color:#166534',
        'Tech/Internet': 'background:#eff6ff;color:#1e40af',
        'Gold': 'background:#fef3c7;color:#92400e',
        'Liquid': 'background:#f0fdf4;color:#14532d',
        'Index': 'background:#f1f5f9;color:#334155',
        'Silver': 'background:#f8fafc;color:#475569',
        'Logistics': 'background:#fff1f2;color:#be123c',
        'Tourism': 'background:#fdf4ff;color:#7e22ce',
    };
    const style = colorMap[sector] || 'background:#f1f5f9;color:#475569';
    const [bg, fg] = style.split(';');
    return (
        <span
            className="sector-chip"
            style={{ backgroundColor: bg.split(':')[1], color: fg.split(':')[1] }}
        >
            {sector}
        </span>
    );
}
