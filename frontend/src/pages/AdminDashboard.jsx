import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { FileText, Clock, CheckCircle2, AlertTriangle } from "lucide-react";

const COLORS = ["#2563EB", "#3B82F6", "#22C55E", "#F59E0B", "#EF4444", "#A855F7", "#0EA5E9", "#14B8A6"];

export default function AdminDashboard() {
  const [data, setData] = useState(null);

  useEffect(() => { api.get("/analytics/overview").then(({ data }) => setData(data)); }, []);
  if (!data) return <div className="text-slate-500">Loading analytics…</div>;

  return (
    <div data-testid="admin-page">
      <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 mb-2">Analytics</div>
      <h1 className="font-heading text-3xl font-semibold text-slate-900">Operations overview</h1>
      <p className="text-slate-600 mt-2">Real-time analytics across all complaints.</p>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-8">
        <Stat label="Total" value={data.totals.total} icon={FileText} tone="blue" testid="stat-total" />
        <Stat label="Pending" value={data.totals.pending} icon={Clock} tone="amber" testid="stat-pending" />
        <Stat label="Resolved" value={data.totals.resolved} icon={CheckCircle2} tone="green" testid="stat-resolved" />
        <Stat label="Critical" value={data.totals.critical} icon={AlertTriangle} tone="red" testid="stat-critical" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mt-6">
        <ChartCard title="Complaint Trend (last 14 days)" testid="chart-trend">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={data.complaint_trend}>
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#64748B" }} tickFormatter={(d)=>d.slice(5)} />
              <YAxis tick={{ fontSize: 11, fill: "#64748B" }} allowDecimals={false} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #E2E8F0" }} />
              <Line type="monotone" dataKey="count" stroke="#2563EB" strokeWidth={2.5} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Monthly Complaints (last 6 months)" testid="chart-monthly">
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={data.monthly_trend}>
              <defs><linearGradient id="grad1" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#3B82F6" stopOpacity={0.4}/><stop offset="100%" stopColor="#3B82F6" stopOpacity={0}/></linearGradient></defs>
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#64748B" }} />
              <YAxis tick={{ fontSize: 11, fill: "#64748B" }} allowDecimals={false} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #E2E8F0" }} />
              <Area type="monotone" dataKey="count" stroke="#3B82F6" fill="url(#grad1)" strokeWidth={2.5} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Department Distribution" testid="chart-dept">
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={data.department_distribution} dataKey="count" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={2}>
                {data.department_distribution.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #E2E8F0" }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Priority Distribution" testid="chart-priority">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={data.priority_distribution}>
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#64748B" }} />
              <YAxis tick={{ fontSize: 11, fill: "#64748B" }} allowDecimals={false} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #E2E8F0" }} />
              <Bar dataKey="count" radius={[8, 8, 0, 0]}>
                {data.priority_distribution.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Avg Resolution Time by Priority (hours)" testid="chart-resolution" full>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={data.resolution_time_by_priority}>
              <XAxis dataKey="priority" tick={{ fontSize: 11, fill: "#64748B" }} />
              <YAxis tick={{ fontSize: 11, fill: "#64748B" }} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #E2E8F0" }} />
              <Bar dataKey="avg_hours" radius={[8, 8, 0, 0]} fill="#22C55E" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div className="card-soft p-5 mt-6" data-testid="top-categories">
        <h3 className="font-heading text-lg font-semibold text-slate-900 mb-3">Top complaint categories</h3>
        <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-3">
          {data.top_categories.map((c, i) => (
            <div key={c.name} className="flex items-center justify-between border border-slate-100 rounded-[10px] p-3">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                <span className="text-sm text-slate-700">{c.name}</span>
              </div>
              <span className="text-sm font-semibold text-slate-900">{c.count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, icon: Icon, tone, testid }) {
  const tones = { blue: "bg-blue-50 text-blue-600", amber: "bg-amber-50 text-amber-600", green: "bg-green-50 text-green-600", red: "bg-red-50 text-red-600" };
  return (
    <div className="card-soft p-5" data-testid={testid}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">{label}</span>
        <div className={`w-9 h-9 rounded-[10px] flex items-center justify-center ${tones[tone]}`}><Icon className="w-4 h-4" /></div>
      </div>
      <div className="font-heading text-3xl font-semibold text-slate-900 mt-3">{value}</div>
    </div>
  );
}

function ChartCard({ title, children, testid, full }) {
  return (
    <div className={`card-soft p-5 ${full ? "lg:col-span-2" : ""}`} data-testid={testid}>
      <h3 className="font-heading text-sm font-semibold text-slate-800 uppercase tracking-wider mb-3">{title}</h3>
      {children}
    </div>
  );
}
