/**
 * LearningDashboard — admin page for continual learning engine.
 *
 * Shows: global feedback stats, latest learning run signals,
 * top correction keywords, and a manual trigger button.
 */
import React, { useEffect, useState, useCallback } from "react";
import {
  Brain, ThumbsUp, ThumbsDown, RefreshCw, Zap,
  AlertTriangle, TrendingUp, MessageSquare, Loader2, Play,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

// ── Stat card ──────────────────────────────────────────────────────────────
function StatCard({ label, value, sub, icon: Icon, color = "indigo" }) {
  const colors = {
    indigo: "bg-indigo-50 text-indigo-600 border-indigo-100",
    emerald:"bg-emerald-50 text-emerald-600 border-emerald-100",
    rose:   "bg-rose-50 text-rose-600 border-rose-100",
    amber:  "bg-amber-50 text-amber-600 border-amber-100",
  };
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm flex items-start gap-4">
      <div className={`w-11 h-11 rounded-xl border flex items-center justify-center flex-shrink-0 ${colors[color]}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-2xl font-bold text-slate-800">{value}</p>
        <p className="text-sm font-medium text-slate-600">{label}</p>
        {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

// ── Signal card ─────────────────────────────────────────────────────────────
function SignalCard({ signal }) {
  if (signal.type === "low_satisfaction") {
    return (
      <div className="flex items-start gap-3 p-4 rounded-xl border border-amber-200 bg-amber-50">
        <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-amber-800 capitalize">{signal.category} — Low Satisfaction</p>
          <p className="text-xs text-amber-700 mt-0.5">{signal.message}</p>
          <p className="text-xs font-mono text-amber-600 mt-1">
            negative rate: {(signal.negative_rate * 100).toFixed(0)}%
          </p>
        </div>
      </div>
    );
  }
  if (signal.type === "correction_keywords") {
    return (
      <div className="flex items-start gap-3 p-4 rounded-xl border border-blue-200 bg-blue-50">
        <MessageSquare className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-sm font-semibold text-blue-800">Top Correction Keywords</p>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {signal.keywords.map(({ keyword, count }) => (
              <span key={keyword} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 text-xs font-medium">
                {keyword} <span className="opacity-60">×{count}</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    );
  }
  return null;
}

// ── Category bar ────────────────────────────────────────────────────────────
function CategoryBar({ category, thumbs_up, thumbs_down, satisfaction_pct }) {
  const total = thumbs_up + thumbs_down;
  const pct   = total > 0 ? thumbs_up / total : 0;
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-slate-700 capitalize">{category}</span>
        <span className={`text-xs font-semibold ${satisfaction_pct >= 70 ? "text-emerald-600" : "text-rose-600"}`}>
          {satisfaction_pct}%
        </span>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${satisfaction_pct >= 70 ? "bg-emerald-400" : "bg-rose-400"}`}
          style={{ width: `${pct * 100}%` }}
        />
      </div>
      <p className="text-xs text-slate-400">{thumbs_up} up · {thumbs_down} down · {total} total</p>
    </div>
  );
}

// ── Main page ───────────────────────────────────────────────────────────────
export default function LearningDashboard() {
  const [stats,      setStats]      = useState(null);
  const [latestRun,  setLatestRun]  = useState(null);
  const [loading,    setLoading]    = useState(true);
  const [triggering, setTriggering] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [statsRes, runRes] = await Promise.all([
        api.get("/learning/stats"),
        api.get("/learning/runs/latest"),
      ]);
      setStats(statsRes.data);
      setLatestRun(runRes.data?.processed !== undefined ? runRes.data : null);
    } catch (err) {
      toast.error("Could not load learning data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const triggerCycle = async () => {
    setTriggering(true);
    try {
      const { data } = await api.post("/learning/trigger-cycle");
      toast.success(`Learning cycle complete — processed ${data.processed} feedback items`);
      setLatestRun(data);
      await fetchData();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Cycle failed");
    } finally {
      setTriggering(false);
    }
  };

  return (
    <div className="max-w-4xl">
      {/* Header */}
      <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 mb-2">
        AI · Phase 4
      </div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-heading text-3xl font-semibold text-slate-900 flex items-center gap-3">
            <Brain className="w-7 h-7 text-violet-500" />
            Continual Learning
          </h1>
          <p className="text-slate-500 mt-1.5">
            Monitor user feedback signals and trigger learning cycles to improve AI agents.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-200 text-sm font-medium text-slate-600 hover:border-violet-300 hover:text-violet-700 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <button
            id="learning-trigger-btn"
            onClick={triggerCycle}
            disabled={triggering}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold shadow-sm transition-colors"
          >
            {triggering ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            {triggering ? "Running…" : "Trigger Cycle"}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="w-8 h-8 animate-spin text-violet-400" />
        </div>
      ) : (
        <div className="space-y-6">
          {/* Global stats */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard label="Total Feedback"   value={stats.total}            icon={TrendingUp}  color="indigo" />
              <StatCard label="Thumbs Up"         value={stats.thumbs_up}        icon={ThumbsUp}    color="emerald" />
              <StatCard label="Thumbs Down"       value={stats.thumbs_down}      icon={ThumbsDown}  color="rose" />
              <StatCard label="Satisfaction"      value={`${stats.satisfaction_pct}%`}  icon={Zap} color="amber"
                sub={`${stats.unprocessed} pending`} />
            </div>
          )}

          {/* Latest run */}
          {latestRun ? (
            <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Brain className="w-5 h-5 text-violet-500" />
                  <span className="font-semibold text-slate-700">Latest Learning Run</span>
                </div>
                <span className="text-xs text-slate-400">
                  {latestRun.run_at ? new Date(latestRun.run_at).toLocaleString() : "Just now"}
                  {" · "}{latestRun.processed} items processed
                </span>
              </div>

              <div className="p-6 space-y-6">
                {/* Signals */}
                {latestRun.signals?.length > 0 ? (
                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold text-slate-600 uppercase tracking-wider">Signals Detected</h3>
                    {latestRun.signals.map((s, i) => <SignalCard key={i} signal={s} />)}
                  </div>
                ) : (
                  <p className="text-sm text-slate-400 italic">No signals detected — satisfaction is healthy across all categories.</p>
                )}

                {/* Category breakdown */}
                {latestRun.categories?.length > 0 && (
                  <div className="space-y-4">
                    <h3 className="text-sm font-semibold text-slate-600 uppercase tracking-wider">Category Breakdown</h3>
                    {latestRun.categories.map((c) => (
                      <CategoryBar key={c.category} {...c} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-10 text-center space-y-3">
              <Brain className="w-12 h-12 text-slate-300 mx-auto" />
              <p className="text-slate-500 font-medium">No learning runs yet</p>
              <p className="text-sm text-slate-400">Submit feedback on complaints, then click <strong>Trigger Cycle</strong>.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
