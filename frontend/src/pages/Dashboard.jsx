import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PlusCircle, FileText, CheckCircle2, AlertTriangle, Clock } from "lucide-react";

const STATUS_LABEL = {
  submitted: "Submitted", analyzing: "Analyzing", analyzed: "Analyzed",
  assigned: "Assigned", in_progress: "In Progress", resolved: "Resolved", rejected: "Rejected",
};

export default function Dashboard() {
  const { user } = useAuth();
  const [complaints, setComplaints] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get("/complaints?limit=10"),
      api.get("/analytics/overview"),
    ]).then(([c, a]) => { setComplaints(c.data); setStats(a.data.totals); })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div data-testid="dashboard-page">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-8">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 mb-2">Customer dashboard</div>
          <h1 className="font-heading text-3xl sm:text-4xl font-semibold text-slate-900">Hi {user?.full_name?.split(" ")[0]} 👋</h1>
          <p className="text-slate-600 mt-1">Submit a complaint and our 10-agent AI will analyze it in under 10 seconds.</p>
        </div>
        <Link to="/submit" data-testid="submit-cta" className="btn-primary"><PlusCircle className="w-4 h-4" /> Submit Complaint</Link>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="My Complaints" value={stats?.total ?? "—"} icon={FileText} tone="blue" testid="stat-total" />
        <StatCard label="Pending" value={stats?.pending ?? "—"} icon={Clock} tone="amber" testid="stat-pending" />
        <StatCard label="Resolved" value={stats?.resolved ?? "—"} icon={CheckCircle2} tone="green" testid="stat-resolved" />
        <StatCard label="Critical" value={stats?.critical ?? "—"} icon={AlertTriangle} tone="red" testid="stat-critical" />
      </div>

      <div className="card-soft p-6">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="font-heading text-xl font-semibold text-slate-900">Recent complaints</h2>
            <p className="text-sm text-slate-500">Latest 10 entries</p>
          </div>
          <Link to="/complaints" className="text-sm text-blue-600 font-medium" data-testid="view-all-link">View all →</Link>
        </div>
        {loading ? (
          <div className="text-sm text-slate-500">Loading…</div>
        ) : complaints.length === 0 ? (
          <div className="text-center py-12">
            <FileText className="w-10 h-10 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-600">No complaints yet. Submit your first one!</p>
            <Link to="/submit" className="btn-primary mt-4 inline-flex" data-testid="empty-submit-cta">Submit Complaint</Link>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {complaints.map((c) => (
              <Link to={`/complaints/${c.id}`} key={c.id} className="flex items-center gap-4 py-3 hover:bg-slate-50 -mx-3 px-3 rounded-[10px] transition-colors" data-testid={`complaint-row-${c.id}`}>
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-slate-800 truncate font-medium">{c.description}</div>
                  <div className="text-xs text-slate-500 mt-1 capitalize">{c.domain} · {c.analysis?.intent || "Pending analysis"}</div>
                </div>
                {c.analysis?.severity && (<span className={`badge-pill severity-${c.analysis.severity} capitalize`}>{c.analysis.severity}</span>)}
                <span className={`badge-pill status-${c.status}`}>{STATUS_LABEL[c.status] || c.status}</span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, icon: Icon, tone, testid }) {
  const tones = {
    blue: "bg-blue-50 text-blue-600",
    amber: "bg-amber-50 text-amber-600",
    green: "bg-green-50 text-green-600",
    red: "bg-red-50 text-red-600",
  };
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
