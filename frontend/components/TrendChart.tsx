"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { formatINR } from "@/lib/api";

interface TrendPoint {
  month: string;
  invoiced: number | string;
  collected: number | string;
  overdue: number | string;
  collection_rate_pct: number;
}

interface TrendChartProps {
  data: TrendPoint[];
}

export default function TrendChart({ data }: TrendChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="h-64 flex flex-col items-center justify-center text-slate-400 text-xs space-y-1">
        <span>No monthly collection trend data available</span>
      </div>
    );
  }

  const chartData = data.map((d) => ({
    month: d.month,
    invoiced: parseFloat(String(d.invoiced)),
    collected: parseFloat(String(d.collected)),
    rate: d.collection_rate_pct,
  }));

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const inv = payload.find((p: any) => p.dataKey === "invoiced")?.value || 0;
      const col = payload.find((p: any) => p.dataKey === "collected")?.value || 0;
      const rate = inv > 0 ? ((col / inv) * 100).toFixed(1) : "0.0";
      return (
        <div className="bg-[#0B1330] text-white p-3 rounded-xl shadow-dropdown text-xs space-y-1.5 border border-slate-700/80 min-w-[200px]">
          <p className="font-semibold text-slate-300 pb-1 border-b border-slate-800 text-[11px] font-mono">
            {label}
          </p>
          <div className="space-y-1 pt-0.5">
            <div className="flex justify-between items-baseline">
              <span className="text-slate-400 text-[11px] flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-[#3B5CDB]" />
                Invoiced:
              </span>
              <span className="font-mono font-medium text-slate-100">
                {formatINR(inv)}
              </span>
            </div>
            <div className="flex justify-between items-baseline">
              <span className="text-emerald-400 text-[11px] flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-[#10B981]" />
                Collected:
              </span>
              <span className="font-mono font-bold text-emerald-400">
                {formatINR(col)}
              </span>
            </div>
            <div className="flex justify-between items-baseline pt-1.5 border-t border-slate-800 text-[11px]">
              <span className="text-slate-400">Monthly Realization:</span>
              <span className="font-mono font-bold text-indigo-300">{rate}%</span>
            </div>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="w-full h-64">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={chartData}
          margin={{ top: 10, right: 10, left: -10, bottom: 0 }}
        >
          <defs>
            <linearGradient id="gradientInvoiced" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3B5CDB" stopOpacity={0.16} />
              <stop offset="95%" stopColor="#3B5CDB" stopOpacity={0.0} />
            </linearGradient>
            <linearGradient id="gradientCollected" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10B981" stopOpacity={0.2} />
              <stop offset="95%" stopColor="#10B981" stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
          <XAxis
            dataKey="month"
            tick={{ fill: "#64748B", fontSize: 11, fontWeight: 500 }}
            tickLine={false}
            axisLine={{ stroke: "#E2E8F0" }}
          />
          <YAxis
            tick={{ fill: "#94A3B8", fontSize: 10, fontFamily: "monospace" }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(val) => {
              if (val >= 10000000) return `₹${(val / 10000000).toFixed(1)}Cr`;
              if (val >= 100000) return `₹${(val / 100000).toFixed(0)}L`;
              return `₹${val}`;
            }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone"
            dataKey="invoiced"
            stroke="#3B5CDB"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#gradientInvoiced)"
          />
          <Area
            type="monotone"
            dataKey="collected"
            stroke="#10B981"
            strokeWidth={2.5}
            fillOpacity={1}
            fill="url(#gradientCollected)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
