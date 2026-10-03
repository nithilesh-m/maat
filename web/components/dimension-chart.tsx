"use client";
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const NAMES: Record<string, string> = {
  fairness: "Fairness",
  robustness_security: "Robustness & Security",
  privacy: "Privacy",
  transparency_explainability: "Transparency & Explainability",
  accountability_documentation: "Accountability & Docs",
};
const COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];

export function DimensionChart({ dimensions }: { dimensions: Record<string, number> }) {
  const data = Object.entries(dimensions).map(([k, v]) => ({ name: NAMES[k] ?? k, value: Number(v.toFixed(3)) }));
  return (
    <div className="h-72 w-full" role="img" aria-label="Adequacy by dimension">
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 36 }}>
          <XAxis type="number" domain={[0, 1]} tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} stroke="var(--border)" />
          <YAxis type="category" dataKey="name" width={190} tick={{ fill: "var(--foreground)", fontSize: 13 }} stroke="var(--border)" />
          <Tooltip cursor={{ fill: "var(--muted)", opacity: 0.4 }} contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 12 }} />
          <Bar dataKey="value" radius={[0, 8, 8, 0]} animationDuration={900} barSize={22}>
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
            <LabelList dataKey="value" position="right" style={{ fill: "var(--foreground)", fontSize: 12 }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
