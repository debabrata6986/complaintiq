import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PlusCircle, Search } from "lucide-react";

const STATUS_LABEL = {
  submitted: "Submitted", analyzing: "Analyzing", analyzed: "Analyzed",
  assigned: "Assigned", in_progress: "In Progress", resolved: "Resolved", rejected: "Rejected",
};

export default function ComplaintsList() {
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    api.get(`/complaints?${params.toString()}`).then(({ data }) => setItems(data)).finally(() => setLoading(false));
  }, [status]);

  const filtered = items.filter((c) => c.description.toLowerCase().includes(q.toLowerCase()) || (c.analysis?.intent || "").toLowerCase().includes(q.toLowerCase()));

  return (
    <div data-testid="complaints-list-page">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-6">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 mb-2">Complaints</div>
          <h1 className="font-heading text-3xl font-semibold text-slate-900">{user?.role === "customer" ? "My complaints" : "All complaints"}</h1>
        </div>
        {user?.role === "customer" && (
          <Link to="/submit" className="btn-primary" data-testid="list-submit-cta"><PlusCircle className="w-4 h-4" /> New complaint</Link>
        )}
      </div>

      <div className="card-soft p-4 mb-5 flex flex-col md:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input data-testid="search-input" className="input-field pl-9" value={q} onChange={(e)=>setQ(e.target.value)} placeholder="Search by text or intent…" />
        </div>
        <select data-testid="status-filter" className="input-field md:w-56" value={status} onChange={(e)=>setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {Object.keys(STATUS_LABEL).map((s)=> <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
        </select>
      </div>

      <div className="card-soft p-0 overflow-hidden">
        {loading ? <div className="p-6 text-slate-500 text-sm">Loading…</div> : filtered.length === 0 ? (
          <div className="p-10 text-center text-slate-500">No complaints found.</div>
        ) : (
          <div className="divide-y divide-slate-100">
            {filtered.map((c) => (
              <Link to={`/complaints/${c.id}`} key={c.id} className="flex items-start gap-4 p-4 hover:bg-slate-50 transition-colors" data-testid={`list-row-${c.id}`}>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="text-xs font-semibold text-slate-500">#{c.id.slice(0,8)}</span>
                    <span className="text-xs text-slate-400">·</span>
                    <span className="text-xs text-slate-500 capitalize">{c.domain}</span>
                    {c.analysis?.intent && <><span className="text-xs text-slate-400">·</span><span className="badge-pill bg-blue-50 text-blue-700">{c.analysis.intent}</span></>}
                  </div>
                  <p className="text-sm text-slate-800 line-clamp-2">{c.description}</p>
                  <div className="text-xs text-slate-400 mt-1">{new Date(c.created_at).toLocaleString()}</div>
                </div>
                <div className="flex flex-col items-end gap-2 shrink-0">
                  {c.analysis?.severity && <span className={`badge-pill severity-${c.analysis.severity} capitalize`}>{c.analysis.severity}</span>}
                  <span className={`badge-pill status-${c.status}`}>{STATUS_LABEL[c.status] || c.status}</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
