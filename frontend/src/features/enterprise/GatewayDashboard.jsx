/**
 * GatewayDashboard — Phase 3 Enterprise Integration Gateway admin page.
 *
 * Shows all registered gateways, their health status, and lets admins
 * fire test actions (refund, create_ticket, create_contact) in mock mode.
 */
import React, { useEffect, useState, useCallback } from "react";
import {
  Zap, RefreshCw, CheckCircle, AlertTriangle, XCircle,
  Play, RotateCcw, ChevronDown, ChevronUp, Loader2,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

// ── Preset test actions per gateway ──────────────────────────────────────────
const PRESET_ACTIONS = {
  payment: [
    { label: "Refund ₹500", action_type: "refund", context: { charge_id: "ch_test_001", amount_cents: 50000, reason: "requested_by_customer" } },
    { label: "Capture", action_type: "capture", context: { charge_id: "ch_test_002" } },
  ],
  crm: [
    { label: "Create Contact", action_type: "create_contact", context: { name: "Test User", email: "test@complaintiq.com", phone: "9999999999" } },
    { label: "Update Ticket", action_type: "update_ticket", context: { ticket_id: "TICK-001", status: "resolved" } },
  ],
  ticketing: [
    { label: "Create Ticket", action_type: "create_ticket", context: { subject: "Test complaint escalation", priority: "high", description: "Auto-generated test ticket from ComplaintIQ v4.0" } },
    { label: "Escalate", action_type: "escalate", context: { ticket_id: "ZD-001", priority: "urgent" } },
  ],
};

// ── Status badge component ─────────────────────────────────────────────────
function StatusBadge({ status }) {
  if (status === "ok") return (
    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
      <CheckCircle className="w-3 h-3" /> Online
    </span>
  );
  if (status === "degraded") return (
    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
      <AlertTriangle className="w-3 h-3" /> Degraded
    </span>
  );
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-50 text-red-700 border border-red-200">
      <XCircle className="w-3 h-3" /> Unavailable
    </span>
  );
}

// ── Mode badge ─────────────────────────────────────────────────────────────
function ModeBadge({ mode }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-semibold ${
      mode === "live"
        ? "bg-rose-100 text-rose-700"
        : "bg-slate-100 text-slate-600"
    }`}>
      {mode === "live" ? "● LIVE" : "◎ MOCK"}
    </span>
  );
}

// ── Single gateway card ────────────────────────────────────────────────────
function GatewayCard({ name, mode, health, onExecute }) {
  const [expanded, setExpanded] = useState(false);
  const [running, setRunning]   = useState(null); // action_type currently running
  const [lastResult, setLastResult] = useState(null);
  const presets = PRESET_ACTIONS[name] || [];
  const status  = health?.status || "unavailable";

  const run = async (preset) => {
    setRunning(preset.action_type);
    setLastResult(null);
    const result = await onExecute(name, preset.action_type, preset.context);
    setLastResult(result);
    setRunning(null);
    setExpanded(true);
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      {/* Card header */}
      <div className="flex items-center justify-between px-6 py-4 bg-gradient-to-r from-slate-50 to-white border-b border-slate-100">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center">
            <Zap className="w-5 h-5 text-indigo-500" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-800 capitalize">{name} Gateway</h3>
            <p className="text-xs text-slate-400">
              {name === "payment" ? "Stripe" : name === "crm" ? "Freshdesk" : "Zendesk"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ModeBadge mode={mode} />
          <StatusBadge status={status} />
        </div>
      </div>

      {/* Actions */}
      <div className="px-6 py-4">
        <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-3">Test Actions</p>
        <div className="flex flex-wrap gap-2">
          {presets.map((p) => (
            <button
              key={p.action_type}
              id={`gateway-${name}-${p.action_type}-btn`}
              onClick={() => run(p)}
              disabled={!!running}
              className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full border border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {running === p.action_type
                ? <Loader2 className="w-3 h-3 animate-spin" />
                : <Play className="w-3 h-3" />
              }
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Result panel */}
      {lastResult && (
        <div className="px-6 pb-4">
          <button
            className="flex items-center gap-1.5 text-xs text-slate-500 mb-2 hover:text-slate-700"
            onClick={() => setExpanded((e) => !e)}
          >
            {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {lastResult.success ? "✅ Success — view response" : "❌ Failed — view error"}
          </button>
          {expanded && (
            <pre className="text-xs bg-slate-900 text-emerald-300 rounded-lg p-4 overflow-x-auto max-h-40">
              {JSON.stringify(lastResult, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────
export default function GatewayDashboard() {
  const [gateways, setGateways] = useState([]);
  const [health,   setHealth]   = useState({});
  const [loading,  setLoading]  = useState(true);
  const [checking, setChecking] = useState(false);

  const fetchGateways = useCallback(async () => {
    try {
      const { data } = await api.get("/enterprise/gateways");
      setGateways(data.gateways || []);
    } catch (err) {
      toast.error("Could not load gateway list");
    }
  }, []);

  const fetchHealth = useCallback(async (silent = false) => {
    if (!silent) setChecking(true);
    try {
      const { data } = await api.get("/enterprise/health");
      setHealth(data.gateways || {});
      if (!silent) toast.success(`All gateways checked — overall: ${data.overall}`);
    } catch (err) {
      if (!silent) toast.error("Health check failed");
    } finally {
      if (!silent) setChecking(false);
    }
  }, []);

  useEffect(() => {
    Promise.all([fetchGateways(), fetchHealth(true)]).finally(() => setLoading(false));
  }, [fetchGateways, fetchHealth]);

  const handleExecute = async (gateway, action_type, context) => {
    try {
      const { data } = await api.post("/enterprise/execute", { gateway, action_type, context });
      toast.success(`${gateway}/${action_type} succeeded`);
      return data;
    } catch (err) {
      const msg = err?.response?.data?.detail || "Action failed";
      toast.error(msg);
      return { success: false, error: msg };
    }
  };

  return (
    <div className="max-w-4xl">
      {/* Header */}
      <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 mb-2">
        Enterprise · Phase 3
      </div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-heading text-3xl font-semibold text-slate-900 flex items-center gap-3">
            <Zap className="w-7 h-7 text-indigo-500" />
            Integration Gateway
          </h1>
          <p className="text-slate-500 mt-1.5">
            Manage enterprise system connections — Payment, CRM, and Ticketing gateways.
          </p>
        </div>
        <button
          id="gateway-health-check-btn"
          onClick={() => fetchHealth(false)}
          disabled={checking}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-200 text-sm font-medium text-slate-600 hover:border-indigo-300 hover:text-indigo-700 transition-colors"
        >
          {checking
            ? <Loader2 className="w-4 h-4 animate-spin" />
            : <RefreshCw className="w-4 h-4" />
          }
          Health Check
        </button>
      </div>

      {/* Overall status bar */}
      {Object.keys(health).length > 0 && (
        <div className="mb-6 flex items-center gap-3 px-4 py-3 rounded-xl bg-emerald-50 border border-emerald-200">
          <CheckCircle className="w-5 h-5 text-emerald-600 flex-shrink-0" />
          <span className="text-sm font-medium text-emerald-800">
            All gateways reachable — running in <strong>mock mode</strong> (no real API calls). Set <code className="bg-emerald-100 px-1 rounded">GATEWAY_MODE=live</code> to enable live integrations.
          </span>
        </div>
      )}

      {/* Gateway cards */}
      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
        </div>
      ) : (
        <div className="space-y-4">
          {gateways.map((gw) => (
            <GatewayCard
              key={gw.name}
              name={gw.name}
              mode={gw.mode}
              health={health[gw.name]}
              onExecute={handleExecute}
            />
          ))}
        </div>
      )}
    </div>
  );
}
