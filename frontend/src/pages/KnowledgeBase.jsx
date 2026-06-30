import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Search, BookOpen } from "lucide-react";

export default function KnowledgeBase() {
  const [q, setQ] = useState("");
  const [domain, setDomain] = useState("");
  const [docs, setDocs] = useState([]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const params = domain ? `?domain=${domain}` : "";
    api.get(`/knowledge${params}`).then(({ data }) => setDocs(data));
  }, [domain]);

  const search = async (e) => {
    e?.preventDefault();
    if (!q.trim()) { setResults(null); return; }
    setLoading(true);
    try {
      const { data } = await api.get(`/knowledge/search?q=${encodeURIComponent(q)}${domain?`&domain=${domain}`:""}`);
      setResults(data.results);
    } finally { setLoading(false); }
  };

  const display = results ?? docs;

  return (
    <div data-testid="kb-page">
      <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 mb-2">Knowledge base</div>
      <h1 className="font-heading text-3xl font-semibold text-slate-900">Policies, FAQs & SOPs</h1>
      <p className="text-slate-600 mt-2">Semantic search across the entire RAG corpus.</p>

      <form onSubmit={search} className="card-soft p-4 mt-6 flex flex-col md:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input data-testid="kb-search" className="input-field pl-9" value={q} onChange={(e)=>setQ(e.target.value)} placeholder="e.g. refund timeline for damaged items" />
        </div>
        <select data-testid="kb-domain" className="input-field md:w-52" value={domain} onChange={(e)=>setDomain(e.target.value)}>
          <option value="">All domains</option>
          {["ecommerce","banking","telecom","insurance","healthcare","government","utilities","general"].map((d)=> <option key={d} value={d}>{d}</option>)}
        </select>
        <button type="submit" className="btn-primary" data-testid="kb-search-btn">{loading ? "Searching…" : "Search"}</button>
      </form>

      <div className="grid md:grid-cols-2 gap-4 mt-6">
        {display.map((d, i) => (
          <div key={d.id || i} className="card-soft p-5" data-testid={`kb-doc-${d.id}`}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-[8px] bg-blue-50 text-blue-600 flex items-center justify-center"><BookOpen className="w-4 h-4" /></div>
                <div>
                  <div className="text-sm font-medium text-slate-800">{d.title}</div>
                  <div className="text-xs text-slate-500 capitalize">{d.doc_type} · {d.domain}</div>
                </div>
              </div>
              {d.score !== undefined && (<span className="badge-pill bg-blue-50 text-blue-700">{(d.score*100).toFixed(0)}% match</span>)}
            </div>
            <p className="text-sm text-slate-600 leading-relaxed line-clamp-4 mt-2">{d.content}</p>
          </div>
        ))}
        {display.length === 0 && (<div className="text-slate-500 col-span-2 text-center py-10">No documents.</div>)}
      </div>
    </div>
  );
}
