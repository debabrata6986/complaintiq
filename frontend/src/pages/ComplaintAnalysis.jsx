import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { ArrowLeft, Brain, Tag, Users, Smile, AlertTriangle, Layers, Copy, BookOpen, Sparkles, Eye, MessageSquare, Clock, RefreshCw, CheckCircle2, Send, Star, ShieldAlert, GitBranch, RotateCcw } from "lucide-react";

const AGENT_STEPS = [
  "Complaint Understanding", "Intent Classification", "Entity Recognition",
  "Sentiment & Emotion", "Severity Prediction", "Duplicate Detection",
  "Knowledge Retrieval (RAG)", "Resolution Recommendation", "Escalation Decision",
  "Explainability", "Response Generation",
];

const STATUS_LABEL = {
  submitted: "Submitted", analyzing: "Analyzing", analyzed: "Analyzed",
  assigned: "Assigned", in_progress: "In Progress", resolved: "Resolved", rejected: "Rejected",
};
const TIMELINE_FLOW = ["submitted", "analyzed", "assigned", "in_progress", "resolved"];

export default function ComplaintAnalysis() {
  const { id } = useParams();
  const { user } = useAuth();
  const [complaint, setComplaint] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draftResponse, setDraftResponse] = useState("");
  const [newMessage, setNewMessage] = useState("");
  const [messageVisibility, setMessageVisibility] = useState("public");
  const [overrideNote, setOverrideNote] = useState("");
  const [genLoading, setGenLoading] = useState(false);
  const pollRef = useRef(null);
  const isStaff = user?.role !== "customer";
  const isManager = user?.role === "admin" || user?.role === "manager";

  const load = async () => {
    try {
      const [c, m] = await Promise.all([api.get(`/complaints/${id}`), api.get(`/complaints/${id}/messages`)]);
      setComplaint(c.data); setMessages(m.data);
      if (c.data?.analysis?.customer_response && !draftResponse) setDraftResponse(c.data.analysis.customer_response);
      return c.data;
    } catch { toast.error("Failed to load complaint"); return null; }
  };

  useEffect(() => { load(); }, [id]);

  useEffect(() => {
    if (!complaint || complaint.status !== "analyzing") return;
    pollRef.current = setInterval(async () => {
      const d = await load();
      if (d && d.status !== "analyzing") { clearInterval(pollRef.current); toast.success("AI analysis complete"); }
    }, 2500);
    return () => clearInterval(pollRef.current);
  }, [complaint?.status]);

  const setStatus = async (s) => { try { const { data } = await api.patch(`/complaints/${id}/status`, { status: s }); setComplaint(data); toast.success(`Status: ${s}`); } catch { toast.error("Failed"); } };
  const reanalyze = async () => { try { await api.post(`/complaints/${id}/analyze`); await load(); toast.success("Re-analyzed"); } catch { toast.error("Failed"); } };
  const sendResponse = async () => {
    if (!draftResponse.trim()) return toast.error("Response cannot be empty");
    try { await api.post(`/complaints/${id}/send-response`, { body: draftResponse }); await load(); toast.success("Official response sent to customer"); } catch { toast.error("Send failed"); }
  };
  const postMessage = async () => {
    if (!newMessage.trim()) return;
    try {
      await api.post(`/complaints/${id}/messages`, { body: newMessage, visibility: messageVisibility });
      setNewMessage(""); await load(); toast.success("Message posted");
    } catch { toast.error("Failed to post"); }
  };
  const override = async (action) => {
    try {
      const { data } = await api.post(`/complaints/${id}/override`, { final_action: action });
      if (data.regenerated_response) setDraftResponse(data.regenerated_response);
      await load();
      toast.success(`Decision saved · response regenerated`);
    } catch { toast.error("Failed to save decision"); }
  };
  const saveOverrideNote = async () => {
    try {
      await api.patch(`/complaints/${id}/override-note`, { reason: overrideNote || null });
      await load();
      toast.success(overrideNote ? "Note saved" : "Note cleared");
    } catch { toast.error("Failed to save note"); }
  };
  const regenerateResponse = async () => {
    setGenLoading(true);
    try {
      const { data } = await api.post(`/complaints/${id}/generate-response`);
      setDraftResponse(data.customer_response);
      toast.success("Customer response regenerated");
    } catch { toast.error("Failed to generate response"); }
    finally { setGenLoading(false); }
  };
  const reopen = async () => { try { await api.post(`/complaints/${id}/reopen`); await load(); toast.success("Reopened"); } catch { toast.error("Failed"); } };
  const escalate = async () => { try { await api.post(`/complaints/${id}/escalate`); await load(); toast.success("Escalated to manager"); } catch { toast.error("Failed"); } };

  if (!complaint) return <div className="text-slate-500">Loading…</div>;
  const a = complaint.analysis;

  return (
    <div data-testid="analysis-page">
      <Link to="/complaints" className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-800 mb-4" data-testid="back-link">
        <ArrowLeft className="w-4 h-4" /> Back to complaints
      </Link>

      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-6">
        <div className="flex-1">
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Complaint #{complaint.id.slice(0, 8)}</div>
          <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-slate-900 mt-1">{a?.summary || complaint.description.slice(0, 120) + "…"}</h1>
          <div className="flex flex-wrap gap-2 mt-3">
            <span className="badge-pill bg-slate-100 text-slate-700 capitalize">{complaint.domain}</span>
            <span className={`badge-pill status-${complaint.status}`}>{STATUS_LABEL[complaint.status]}</span>
            {a?.severity && <span className={`badge-pill severity-${a.severity} capitalize`}>{a.severity} severity</span>}
            {a?.routing === "manager_review" && <span className="badge-pill bg-amber-50 text-amber-700">Manager review</span>}
            {a?.routing === "support_direct" && <span className="badge-pill bg-green-50 text-green-700">Auto-routed to support</span>}
            {complaint.reopen_count > 0 && <span className="badge-pill bg-purple-50 text-purple-700">Reopened ×{complaint.reopen_count}</span>}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {isStaff && <button onClick={reanalyze} className="btn-secondary" data-testid="reanalyze-btn"><RefreshCw className="w-4 h-4"/> Re-analyze</button>}
          {isStaff && complaint.status !== "resolved" && <button onClick={() => setStatus("in_progress")} className="btn-secondary" data-testid="mark-progress">Mark In Progress</button>}
          {isStaff && complaint.status !== "resolved" && (isManager || !a?.escalation_required) && <button onClick={() => setStatus("resolved")} className="btn-primary" data-testid="mark-resolved"><CheckCircle2 className="w-4 h-4"/> Resolve</button>}
          {isStaff && a?.escalation_required && !isManager && <button onClick={escalate} className="btn-primary bg-amber-600 hover:bg-amber-700" data-testid="escalate-btn"><ShieldAlert className="w-4 h-4"/> Escalate</button>}
          {!isStaff && complaint.status === "resolved" && <button onClick={reopen} className="btn-secondary" data-testid="reopen-btn"><RotateCcw className="w-4 h-4"/> Reopen</button>}
        </div>
      </div>

      {complaint.status === "analyzing" ? (
        <AnalyzingProgress trace={a?.agent_trace} />
      ) : (
        <>
          {/* Escalation banner */}
          {a?.escalation_required && (
            <div className="card-soft p-4 mb-5 border-l-4 border-amber-500 bg-amber-50/40" data-testid="escalation-banner">
              <div className="flex items-start gap-3">
                <ShieldAlert className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <div className="font-medium text-amber-900">Manager review required</div>
                  <div className="text-sm text-amber-800 mt-1">{a.escalation_reason}</div>
                </div>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <Card icon={Brain} title="Intent" testid="card-intent">
              <div className="font-heading text-2xl font-semibold text-slate-900">{a?.intent}</div>
              <div className="text-xs text-slate-500 mt-1">Confidence: {(((a?.intent_confidence)||0)*100).toFixed(0)}%</div>
            </Card>
            <Card icon={Smile} title="Sentiment & Emotion" testid="card-sentiment">
              <div className="flex items-center gap-2">
                <span className={`badge-pill ${a?.sentiment === "Negative" ? "bg-red-50 text-red-700" : "bg-slate-100 text-slate-700"}`}>{a?.sentiment}</span>
                <span className="badge-pill bg-amber-50 text-amber-700">{a?.emotion}</span>
              </div>
            </Card>
            <Card icon={AlertTriangle} title="Severity & Priority" testid="card-severity">
              <span className={`badge-pill severity-${a?.severity} capitalize`}>{a?.severity}</span>
              <p className="text-xs text-slate-600 mt-2">{a?.severity_reason}</p>
            </Card>
            <Card icon={Users} title="Routing" testid="card-routing">
              <div className="text-sm text-slate-500">Department</div>
              <div className="font-heading text-lg font-semibold text-slate-900">{a?.department}</div>
            </Card>
            <Card icon={Copy} title="Duplicate Detection" testid="card-duplicate">
              <div className="font-heading text-2xl font-semibold text-slate-900">{((a?.duplicate_score||0)*100).toFixed(0)}%</div>
              <div className="text-xs text-slate-500 mt-1">{a?.similar_complaints?.length || 0} similar found</div>
            </Card>
            <Card icon={Sparkles} title="AI Confidence" testid="card-confidence">
              <div className="font-heading text-2xl font-semibold text-slate-900">{(((a?.explanation?.confidence ?? a?.recommendation_confidence) || 0) * 100).toFixed(0)}%</div>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mt-5">
            <div className="lg:col-span-2 space-y-5">

              {/* Decision Matrix (staff only) */}
              {isStaff && a?.decision_options?.length > 0 && (
                <Card icon={GitBranch} title="Decision Matrix" testid="card-matrix">
                  <p className="text-sm text-slate-500 mb-3">Click any option to make it the final decision. Saved instantly — no confirmation needed.</p>
                  <div className="grid sm:grid-cols-3 gap-3">
                    {a.decision_options.map((o, i) => (
                      <div key={i} className={`border rounded-[12px] p-4 ${i === 0 ? "border-blue-500 bg-blue-50/30" : "border-slate-200"}`} data-testid={`option-${i}`}>
                        <div className="text-xs font-semibold uppercase tracking-wider text-blue-600 mb-1">Option {i+1}{i===0 && " · AI"}</div>
                        <div className="font-medium text-slate-900">{o.action}</div>
                        <p className="text-xs text-slate-600 mt-1.5 leading-snug">{o.rationale}</p>
                        <div className="flex items-center justify-between mt-3">
                          <span className="text-xs text-slate-500">{(o.confidence*100).toFixed(0)}% conf · {o.business_risk} risk</span>
                          {isManager && i > 0 && (
                            <button onClick={() => override(o.action)} className="text-xs text-blue-600 font-medium" data-testid={`override-${i}`}>Choose</button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                  {a?.manager_override && (
                    <div className="mt-4 bg-slate-50 rounded-[10px] p-4 border border-slate-100" data-testid="override-audit">
                      <div className="flex items-center justify-between flex-wrap gap-2">
                        <div className="text-xs">
                          <b className="text-slate-700">Manager override:</b> <span className="text-slate-600">{a.manager_override.original_action} → <b>{a.manager_override.final_action}</b></span>
                          <span className="text-slate-400"> · {a.manager_override.manager_name}</span>
                        </div>
                        {a.manager_override.reason && (<span className="badge-pill bg-blue-50 text-blue-700">{a.manager_override.reason}</span>)}
                      </div>
                      {isManager && (
                        <div className="mt-3 flex items-center gap-2">
                          <input
                            className="input-field flex-1"
                            placeholder="Optional note (e.g. VIP customer · Damaged stock unavailable) — can stay empty"
                            value={overrideNote}
                            onChange={(e) => setOverrideNote(e.target.value)}
                            data-testid="override-note-input"
                          />
                          <button onClick={saveOverrideNote} className="btn-secondary" data-testid="override-note-save">Save note</button>
                        </div>
                      )}
                    </div>
                  )}
                </Card>
              )}

              {/* AI Recommendation - customer always sees, staff sees details */}
              {!isStaff ? null : (
                <Card icon={Sparkles} title="AI Recommendation" testid="card-recommendation">
                  <div className="text-xs font-semibold uppercase tracking-wider text-blue-600 mb-2">{a?.recommendation_action}</div>
                  <p className="text-slate-700 leading-relaxed">{a?.recommendation}</p>
                </Card>
              )}

              {/* Explainable AI - staff only */}
              {isStaff && (
                <Card icon={Eye} title="Explainable AI" testid="card-explanation">
                  <p className="text-slate-700">{a?.explanation?.reasoning}</p>
                  {a?.explanation?.evidence?.length > 0 && (
                    <ul className="mt-3 space-y-1.5 list-disc list-inside text-sm text-slate-600">
                      {a.explanation.evidence.map((e, i) => <li key={i}>{e}</li>)}
                    </ul>
                  )}
                  {a?.explanation?.policy_basis?.length > 0 && (
                    <div className="mt-4">
                      <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Policy basis</div>
                      <div className="flex flex-wrap gap-2">
                        {a.explanation.policy_basis.map((p, i) => <span key={i} className="badge-pill bg-blue-50 text-blue-700">{p}</span>)}
                      </div>
                    </div>
                  )}
                </Card>
              )}

              {/* Draft & Send response - staff only */}
              {isStaff && (
                <Card icon={MessageSquare} title="Draft Customer Response" testid="card-draft-response">
                  <textarea className="input-field font-body" rows={6} value={draftResponse} onChange={(e)=>setDraftResponse(e.target.value)} data-testid="draft-response-textarea" />
                  <div className="flex flex-wrap items-center gap-3 mt-3">
                    <button onClick={regenerateResponse} disabled={genLoading} className="btn-secondary" data-testid="generate-response-btn">
                      <RefreshCw className={`w-4 h-4 ${genLoading ? "animate-spin" : ""}`} /> Generate Customer Response
                    </button>
                    <button onClick={sendResponse} className="btn-primary" data-testid="send-response-btn"><Send className="w-4 h-4"/> Send to customer</button>
                    <span className="text-xs text-slate-500">Human-in-the-loop · never auto-sent</span>
                  </div>
                </Card>
              )}

              {/* Conversation */}
              <Card icon={MessageSquare} title="Conversation" testid="card-conversation">
                {messages.length === 0 ? (
                  <p className="text-sm text-slate-500">No messages yet.</p>
                ) : (
                  <div className="space-y-3 max-h-96 overflow-auto pr-2">
                    {messages.map((m) => (
                      <div key={m.id} className={`p-3 rounded-[10px] ${m.visibility === "internal" ? "bg-amber-50/60 border border-amber-200" : m.author_role === "customer" ? "bg-slate-50" : "bg-blue-50/40"}`} data-testid={`msg-${m.id}`}>
                        <div className="flex items-center justify-between text-xs mb-1">
                          <div className="font-medium text-slate-700">{m.author_name} <span className="text-slate-400">· {m.author_role}</span> {m.visibility === "internal" && <span className="badge-pill bg-amber-100 text-amber-800 ml-1">internal</span>} {m.is_official_response && <span className="badge-pill bg-green-100 text-green-800 ml-1">official</span>}</div>
                          <div className="text-slate-400">{new Date(m.created_at).toLocaleString()}</div>
                        </div>
                        <div className="text-sm text-slate-800 whitespace-pre-wrap">{m.body}</div>
                      </div>
                    ))}
                  </div>
                )}
                <div className="mt-4 space-y-2">
                  <textarea className="input-field" rows={3} value={newMessage} onChange={(e)=>setNewMessage(e.target.value)} placeholder={isStaff ? "Reply to customer or add internal note…" : "Reply…"} data-testid="msg-input" />
                  <div className="flex items-center justify-between">
                    {isStaff && (
                      <select className="input-field w-44" value={messageVisibility} onChange={(e)=>setMessageVisibility(e.target.value)} data-testid="msg-visibility">
                        <option value="public">Reply to customer</option>
                        <option value="internal">Internal note</option>
                      </select>
                    )}
                    <button onClick={postMessage} className="btn-primary ml-auto" data-testid="msg-send"><Send className="w-4 h-4"/> Post</button>
                  </div>
                </div>
              </Card>

              <Card icon={Tag} title="Extracted Entities" testid="card-entities">
                {a?.entities?.length ? (
                  <div className="flex flex-wrap gap-2">
                    {a.entities.map((e, i) => (<span key={i} className="badge-pill bg-slate-100 text-slate-700"><b className="mr-1 text-slate-500">{e.type}:</b>{e.value}</span>))}
                  </div>
                ) : <p className="text-sm text-slate-500">No entities extracted.</p>}
              </Card>

              <Card icon={Layers} title="Original Complaint" testid="card-original">
                <p className="text-slate-700 whitespace-pre-wrap leading-relaxed">{complaint.description}</p>
              </Card>

              {/* Customer feedback */}
              {!isStaff && complaint.status === "resolved" && !complaint.feedback && (
                <FeedbackCard id={id} onDone={load} />
              )}
              {complaint.feedback && (
                <Card icon={Star} title="Customer Feedback" testid="card-feedback">
                  <div className="flex items-center gap-2 text-amber-500">{Array.from({length: complaint.feedback.rating}).map((_, i) => <Star key={i} className="w-5 h-5 fill-current" />)}</div>
                  {complaint.feedback.comment && <p className="text-slate-700 mt-2">{complaint.feedback.comment}</p>}
                </Card>
              )}
            </div>

            <div className="space-y-5">
              <Card icon={Clock} title="Timeline" testid="card-timeline">
                <ol className="space-y-3">
                  {TIMELINE_FLOW.map((s) => {
                    const reached = TIMELINE_FLOW.indexOf(complaint.status) >= TIMELINE_FLOW.indexOf(s);
                    return (
                      <li key={s} className="flex items-start gap-3">
                        <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] ${reached ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-400"}`}>{reached ? "✓" : ""}</div>
                        <div className={`text-sm ${reached ? "text-slate-900 font-medium" : "text-slate-500"}`}>{STATUS_LABEL[s]}</div>
                      </li>
                    );
                  })}
                </ol>
                {isStaff && complaint.history?.length > 0 && (
                  <div className="mt-5 border-t border-slate-100 pt-3 space-y-2 max-h-60 overflow-auto">
                    {complaint.history.slice().reverse().map((h, i) => (
                      <div key={i} className="text-xs text-slate-500"><b className="text-slate-700">{h.status}</b> — {h.note}</div>
                    ))}
                  </div>
                )}
              </Card>

              {isStaff && (
                <Card icon={BookOpen} title="Retrieved Policies (RAG)" testid="card-policies">
                  {a?.retrieved_policies?.length ? a.retrieved_policies.map((p) => (
                    <div key={p.id} className="border-b border-slate-100 last:border-0 pb-3 last:pb-0 mb-3 last:mb-0">
                      <div className="text-sm font-medium text-slate-800">{p.title}</div>
                      <div className="text-xs text-slate-500 mt-0.5">{p.doc_type} · score {p.score.toFixed(2)}</div>
                      <p className="text-xs text-slate-600 mt-1.5">{p.excerpt}</p>
                    </div>
                  )) : <p className="text-sm text-slate-500">No policies retrieved.</p>}
                </Card>
              )}

              {isStaff && (
                <Card icon={Copy} title="Similar Complaints" testid="card-similar">
                  {a?.similar_complaints?.length ? a.similar_complaints.map((s) => (
                    <Link to={`/complaints/${s.id}`} key={s.id} className="block border-b border-slate-100 last:border-0 pb-3 last:pb-0 mb-3 last:mb-0">
                      <div className="flex items-center gap-2"><span className="badge-pill bg-blue-50 text-blue-700">{(s.similarity*100).toFixed(0)}% match</span><span className="text-xs text-slate-500">{s.intent}</span></div>
                      <p className="text-xs text-slate-600 mt-1.5">{s.snippet}…</p>
                    </Link>
                  )) : <p className="text-sm text-slate-500">No similar complaints.</p>}
                </Card>
              )}

              {isStaff && a?.agent_trace?.length > 0 && (
                <Card icon={Brain} title="Agent Trace" testid="card-trace">
                  <div className="space-y-1.5">
                    {a.agent_trace.map((t, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs py-1 border-b border-slate-50 last:border-0">
                        <span className={`w-1.5 h-1.5 rounded-full ${t.status === "success" ? "bg-green-500" : "bg-red-500"}`} />
                        <span className="font-medium text-slate-700">{t.agent}</span>
                        <span className="ml-auto text-slate-400">{t.duration_ms}ms</span>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Card({ icon: Icon, title, children, testid }) {
  return (
    <div className="card-soft p-5" data-testid={testid}>
      <div className="flex items-center gap-2 mb-3">
        <div className="w-7 h-7 rounded-[8px] bg-blue-50 text-blue-600 flex items-center justify-center"><Icon className="w-4 h-4" /></div>
        <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider">{title}</h3>
      </div>
      {children}
    </div>
  );
}

function AnalyzingProgress({ trace = [] }) {
  const doneCount = trace.filter(t => t.status === "success").length;
  return (
    <div className="card-soft p-8" data-testid="analyzing-progress">
      <div className="text-center mb-6">
        <div className="inline-flex items-center gap-2 bg-blue-50 text-blue-700 text-xs font-medium px-3 py-1.5 rounded-full mb-3">
          <span className="w-2 h-2 rounded-full bg-blue-600 animate-pulse" /> AI processing
        </div>
        <h2 className="font-heading text-2xl font-semibold text-slate-900">Analyzing complaint…</h2>
        <p className="text-slate-600 text-sm mt-1">11 specialized agents working sequentially.</p>
      </div>
      <ol className="max-w-md mx-auto space-y-3">
        {AGENT_STEPS.map((s, i) => {
          const isDone = doneCount > i;
          const isRunning = doneCount === i;
          return (
            <li key={s} className="flex items-center gap-3">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-semibold ${isDone ? "bg-blue-600 text-white" : isRunning ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-400"}`}>{isDone ? "✓" : i + 1}</div>
              <span className={`text-sm ${isDone ? "text-slate-900 font-medium" : "text-slate-500"}`}>{s}</span>
              {isRunning && <span className="ml-auto text-xs text-blue-600 animate-pulse">running…</span>}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function FeedbackCard({ id, onDone }) {
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const submit = async () => {
    if (!rating) return toast.error("Please pick a rating");
    try { await api.post(`/complaints/${id}/feedback`, { rating, comment }); toast.success("Thanks for the feedback!"); onDone(); } catch { toast.error("Failed"); }
  };
  return (
    <div className="card-soft p-5" data-testid="card-feedback-form">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-7 h-7 rounded-[8px] bg-amber-50 text-amber-600 flex items-center justify-center"><Star className="w-4 h-4" /></div>
        <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider">How did we do?</h3>
      </div>
      <div className="flex items-center gap-1 mb-3">
        {[1,2,3,4,5].map((n) => (
          <button key={n} onClick={() => setRating(n)} className={`p-1 ${n <= rating ? "text-amber-500" : "text-slate-300"}`} data-testid={`rating-${n}`}>
            <Star className={`w-7 h-7 ${n <= rating ? "fill-current" : ""}`} />
          </button>
        ))}
      </div>
      <textarea className="input-field" rows={3} placeholder="Optional comment" value={comment} onChange={(e)=>setComment(e.target.value)} data-testid="feedback-comment" />
      <button onClick={submit} className="btn-primary mt-3" data-testid="feedback-submit">Submit feedback</button>
    </div>
  );
}
