"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { formatINR } from "@/lib/api";

interface AgingBucket {
  label: string;
  days_min: number;
  days_max: number | null;
  amount: number | string;
  invoice_count: number;
  percentage: number;
}

interface AgingChartProps {
  data: AgingBucket[];
}

const BUCKET_COLORS = [
  "#10B981", // Current / Not Yet Due (Emerald)
  "#3B5CDB", // 1-30 days (brand)
  "#7C93F0", // 31-60 days
  "#F59E0B", // 61-90 Days Overdue (Amber)
  "#EF4444", // 91+ Days Critically Overdue (Rose)
];

export default function AgingChart({ data }: AgingChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="h-64 flex flex-col items-center justify-center text-slate-400 text-xs space-y-1">
        <span>No aging bucket data available</span>
      </div>
    );
  }

  const chartData = data.map((item, idx) => ({
    name: item.label,
    amount: parseFloat(String(item.amount)),
    count: item.invoice_count,
    percentage: item.percentage,
    color: BUCKET_COLORS[idx % BUCKET_COLORS.length],
  }));

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const d = payload[0].payload;
      return (
        <div className="bg-[#0B1330] text-white p-3 rounded-xl shadow-dropdown text-xs space-y-1.5 border border-slate-700/80 min-w-[180px]">
          <div className="flex items-center justify-between pb-1 border-b border-slate-800">
            <span className="font-semibold text-slate-200">{d.name}</span>
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: d.color }}
            />
          </div>
          <div className="flex justify-between items-baseline pt-0.5">
            <span className="text-slate-400 text-[11px]">Outstanding:</span>
            <span className="font-mono font-bold text-white text-[13px]">
              {formatINR(d.amount)}
            </span>
          </div>
          <div className="flex justify-between text-[11px] text-slate-400">
            <span>Invoices:</span>
            <span className="text-slate-200 font-medium">
              {d.count} ({d.percentage}%)
            </span>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="w-full h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={chartData}
          margin={{ top: 10, right: 10, left: -10, bottom: 0 }}
          barCategoryGap="25%"
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
          <XAxis
            dataKey="name"
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
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "#F8FAFC" }} />
          <Bar dataKey="amount" radius={[4, 4, 0, 0]}>
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
