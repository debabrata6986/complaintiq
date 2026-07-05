import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CheckCircle, Loader2, Activity, Play, AlertTriangle, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

const AGENT_PIPELINE = [
  "Complaint Understanding",
  "Intent Classification",
  "Entity Recognition",
  "Sentiment & Emotion",
  "Severity Prediction",
  "Duplicate Detection",
  "Knowledge Retrieval (RAG)",
  "Resolution Recommendation",
  "Root Cause Analysis",
  "Risk Scoring",
  "Escalation Decision",
  "Explainability",
  "Response Generation"
];

export default function SelfHealingDashboard() {
  const [activeTab, setActiveTab] = useState("metrics");

  const [metrics, setMetrics] = useState(null);
  const [executions, setExecutions] = useState([]);
  const [escalations, setEscalations] = useState([]);
  const [audit, setAudit] = useState([]);
  const [scenarios, setScenarios] = useState([]);
  const [simulatorResults, setSimulatorResults] = useState({});
  const [runningScenario, setRunningScenario] = useState(null);

  const fetchMetrics = async () => {
    try {
      const { data } = await api.get("/self-healing/metrics");
      setMetrics(data);
    } catch (err) {
      toast.error("Failed to load metrics");
    }
  };

  const fetchExecutions = async () => {
    try {
      const { data } = await api.get("/self-healing/executions");
      setExecutions(data.executions || []);
    } catch (err) {
      toast.error("Failed to load executions");
    }
  };

  const fetchEscalations = async () => {
    try {
      const { data } = await api.get("/self-healing/escalations");
      setEscalations(data.escalations || []);
    } catch (err) {
      toast.error("Failed to load escalations");
    }
  };

  const fetchAudit = async () => {
    try {
      const { data } = await api.get("/self-healing/audit");
      setAudit(data.audit_trail || []);
    } catch (err) {
      toast.error("Failed to load audit trail");
    }
  };

  const fetchScenarios = async () => {
    try {
      const { data } = await api.get("/self-healing/simulator/scenarios");
      setScenarios(data.scenarios || []);
    } catch (err) {
      toast.error("Failed to load simulator scenarios");
    }
  };

  useEffect(() => {
    if (activeTab === "metrics") fetchMetrics();
    if (activeTab === "executions") fetchExecutions();
    if (activeTab === "escalations") fetchEscalations();
    if (activeTab === "audit") fetchAudit();
    if (activeTab === "simulator") fetchScenarios();
  }, [activeTab]);

  const runScenario = async (scenarioId) => {
    setRunningScenario(scenarioId);
    try {
      const { data } = await api.post("/self-healing/simulator/run", {
        scenario: scenarioId,
        domain: "ecommerce",
        customer_name: "Simulator User"
      });
      setSimulatorResults(prev => ({
        ...prev,
        [scenarioId]: {
          success: true,
          complaint_id: data.complaint_id,
          scenario_label: data.scenario_label,
          message: data.message,
          status_url: data.status_url
        }
      }));
      toast.success("Pipeline started — check Executions tab in 15 seconds");
    } catch (err) {
      toast.error("Scenario execution failed");
    } finally {
      setRunningScenario(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-2">
          <Activity className="w-8 h-8 text-blue-600" />
          Self-Healing Engine
        </h1>
        <p className="text-slate-500 mt-1">Monitor autonomous agent executions, escalations, and system health.</p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="bg-slate-100/50 p-1 rounded-xl mb-6 flex overflow-x-auto">
          <TabsTrigger value="metrics" className="flex-1 rounded-lg">Metrics</TabsTrigger>
          <TabsTrigger value="executions" className="flex-1 rounded-lg">Executions</TabsTrigger>
          <TabsTrigger value="escalations" className="flex-1 rounded-lg">Escalations</TabsTrigger>
          <TabsTrigger value="audit" className="flex-1 rounded-lg">Audit Trail</TabsTrigger>
          <TabsTrigger value="simulator" className="flex-1 rounded-lg">Simulator</TabsTrigger>
        </TabsList>

        {/* METRICS TAB */}
        <TabsContent value="metrics" className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <Card>
              <CardContent className="p-6">
                <div className="text-sm font-medium text-slate-500">Total Executions</div>
                <div className="text-2xl font-bold text-slate-900 mt-2">{metrics?.total_executions || 0}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6">
                <div className="text-sm font-medium text-slate-500">Success Rate</div>
                <div className="text-2xl font-bold text-emerald-600 mt-2">{metrics?.success_rate_percent || 0}%</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6">
                <div className="text-sm font-medium text-slate-500">Avg Resolution Time</div>
                <div className="text-2xl font-bold text-slate-900 mt-2">{metrics?.average_resolution_time || "0ms"}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6">
                <div className="text-sm font-medium text-slate-500">Escalation Rate</div>
                <div className="text-2xl font-bold text-amber-600 mt-2">{metrics?.escalation_rate_percent || 0}%</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6">
                <div className="text-sm font-medium text-slate-500">Actions Executed</div>
                <div className="text-2xl font-bold text-blue-600 mt-2">{metrics?.actions_executed || 0}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6">
                <div className="text-sm font-medium text-slate-500">Rollbacks Triggered</div>
                <div className="text-2xl font-bold text-red-600 mt-2">{metrics?.rollbacks_triggered || 0}</div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-500" />
                Active 13-Agent Pipeline
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {AGENT_PIPELINE.map((agent, idx) => (
                  <div key={idx} className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg border border-slate-100">
                    <div className="w-6 h-6 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center text-xs font-bold">
                      {idx + 1}
                    </div>
                    <span className="text-sm font-medium text-slate-700 flex-1">{agent}</span>
                    <CheckCircle className="w-4 h-4 text-emerald-500" />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* EXECUTIONS TAB */}
        <TabsContent value="executions">
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-200">
                    <tr>
                      <th className="px-6 py-4">Complaint ID</th>
                      <th className="px-6 py-4">Status</th>
                      <th className="px-6 py-4">Actions Taken</th>
                      <th className="px-6 py-4">Started At</th>
                      <th className="px-6 py-4">Duration</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {executions.map((ex) => (
                      <tr key={ex.id} className="hover:bg-slate-50/50">
                        <td className="px-6 py-4 font-medium text-blue-600">
                          <Link to={`/complaints/${ex.complaint_id}`} className="hover:underline">
                            {ex.complaint_id}
                          </Link>
                        </td>
                        <td className="px-6 py-4">
                          <Badge variant="outline" className={
                            ex.status === "success" ? "border-emerald-200 text-emerald-700 bg-emerald-50" :
                            ex.status === "failed" ? "border-red-200 text-red-700 bg-red-50" :
                            "border-amber-200 text-amber-700 bg-amber-50"
                          }>
                            {ex.status}
                          </Badge>
                        </td>
                        <td className="px-6 py-4 text-slate-600">{ex.actions_taken}</td>
                        <td className="px-6 py-4 text-slate-500">{new Date(ex.started_at).toLocaleString()}</td>
                        <td className="px-6 py-4 text-slate-500">{ex.duration_ms}ms</td>
                      </tr>
                    ))}
                    {executions.length === 0 && (
                      <tr>
                        <td colSpan="5" className="px-6 py-8 text-center text-slate-400">
                          No executions yet — run a simulator scenario to populate this tab
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ESCALATIONS TAB */}
        <TabsContent value="escalations">
          {escalations.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 bg-emerald-50/50 rounded-2xl border border-emerald-100">
              <CheckCircle className="w-12 h-12 text-emerald-500 mb-4" />
              <h3 className="text-lg font-semibold text-emerald-900">No active escalations</h3>
              <p className="text-emerald-600 mt-1">All complaints are being handled autonomously.</p>
            </div>
          ) : (
            <Card>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm text-left">
                    <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-200">
                      <tr>
                        <th className="px-6 py-4">Complaint ID</th>
                        <th className="px-6 py-4">Level</th>
                        <th className="px-6 py-4">Reason</th>
                        <th className="px-6 py-4">Timestamp</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {escalations.map((esc) => (
                        <tr key={esc.id} className="hover:bg-slate-50/50">
                          <td className="px-6 py-4 font-medium text-slate-900">{esc.complaint_id}</td>
                          <td className="px-6 py-4">
                            <Badge className={
                              esc.level === "L1" ? "bg-slate-100 text-slate-700 hover:bg-slate-200" :
                              esc.level === "L2" ? "bg-blue-100 text-blue-700 hover:bg-blue-200" :
                              esc.level === "L3" ? "bg-purple-100 text-purple-700 hover:bg-purple-200" :
                              esc.level === "Executive" ? "bg-amber-100 text-amber-700 hover:bg-amber-200" :
                              "bg-red-100 text-red-700 hover:bg-red-200"
                            }>
                              {esc.level}
                            </Badge>
                          </td>
                          <td className="px-6 py-4 text-slate-600">{esc.reason}</td>
                          <td className="px-6 py-4 text-slate-500">{new Date(esc.timestamp).toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* AUDIT TRAIL TAB */}
        <TabsContent value="audit">
          <div className="space-y-4 relative before:absolute before:inset-0 before:ml-5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-slate-200 before:to-transparent">
            {audit.map((entry, idx) => (
              <div key={idx} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
                <div className={`flex items-center justify-center w-10 h-10 rounded-full border-4 border-white shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2 shadow-sm ${
                  entry.status === "success" ? "bg-emerald-500" :
                  entry.status === "failed" ? "bg-red-500" :
                  "bg-slate-400"
                }`}>
                  {entry.status === "success" ? <CheckCircle className="w-4 h-4 text-white" /> :
                   entry.status === "failed" ? <AlertTriangle className="w-4 h-4 text-white" /> :
                   <Activity className="w-4 h-4 text-white" />}
                </div>
                <div className="w-[calc(100%-4rem)] md:w-[calc(50%-2.5rem)] bg-white p-4 rounded-xl border border-slate-100 shadow-sm">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-bold text-slate-800">{entry.action_type}</span>
                    <span className="text-xs font-medium text-slate-400">{new Date(entry.timestamp).toLocaleTimeString()}</span>
                  </div>
                  <div className="text-sm text-slate-600 mb-2">{entry.note}</div>
                  <div className="text-xs font-medium text-blue-600">Complaint: {entry.complaint_id}</div>
                </div>
              </div>
            ))}
            {audit.length === 0 && (
              <div className="text-center py-10 text-slate-500 relative z-10">
                No audit logs yet — run a simulator scenario first
              </div>
            )}
          </div>
        </TabsContent>

        {/* SIMULATOR TAB */}
        <TabsContent value="simulator" className="space-y-4">
          <div className="p-4 bg-blue-50 border border-blue-100 rounded-xl text-sm text-blue-700 mb-2">
            💡 Run a scenario to create a real complaint and watch the full 13-agent pipeline + self-healing engine execute automatically. Check the <strong>Executions</strong> tab after 15 seconds to see the result.
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {scenarios.map(scenario => (
              <Card key={scenario.name}>
                <CardHeader>
                  <CardTitle className="text-lg">{scenario.name}</CardTitle>
                  <div className="text-sm text-slate-500">{scenario.description_preview}</div>
                </CardHeader>
                <CardContent>
                  <Button
                    onClick={() => runScenario(scenario.name)}
                    disabled={runningScenario === scenario.name}
                    className="w-full gap-2"
                  >
                    {runningScenario === scenario.name ? (
                      <><Loader2 className="w-4 h-4 animate-spin" /> Running Pipeline...</>
                    ) : (
                      <><Play className="w-4 h-4" /> Run Scenario</>
                    )}
                  </Button>

                  {simulatorResults[scenario.name] && (
                    <div className="mt-4 p-4 rounded-lg border bg-emerald-50 border-emerald-200">
                      <div className="flex items-center gap-2 mb-2">
                        <CheckCircle className="w-5 h-5 text-emerald-600" />
                        <span className="font-semibold text-emerald-900">
                          Pipeline Started — {simulatorResults[scenario.name].scenario_label}
                        </span>
                      </div>
                      <p className="text-sm text-emerald-700 mb-3">
                        {simulatorResults[scenario.name].message}
                      </p>
                      <Link
                        to={`/complaints/${simulatorResults[scenario.name].complaint_id}`}
                        className="text-sm text-indigo-600 underline block mb-2"
                      >
                        View complaint →
                      </Link>
                      <p className="text-xs text-slate-400">
                        Check the Executions tab in 15 seconds to see the full result.
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
            {scenarios.length === 0 && (
              <div className="col-span-2 text-center py-10 text-slate-400">
                Loading scenarios...
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
