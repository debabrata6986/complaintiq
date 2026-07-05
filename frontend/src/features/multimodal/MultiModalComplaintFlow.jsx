/**
 * MultiModalComplaintFlow — full page for submitting complaints with attachments.
 *
 * Step 1: Upload a file (PDF invoice, product photo, screenshot, etc.)
 * Step 2: Review AI-extracted text / analysis
 * Step 3: Edit description and submit complaint
 */
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Paperclip, FileText, Send, Loader2, CheckCircle } from "lucide-react";
import { api } from "@/lib/api";
import FileUploadZone from "./FileUploadZone";
import AnalysisResult from "./AnalysisResult";
import AssistantPanel from "../realtime/AssistantPanel";

const DOMAINS = [
  { v: "ecommerce",  l: "E-commerce" },
  { v: "banking",    l: "Banking" },
  { v: "telecom",    l: "Telecom" },
  { v: "insurance",  l: "Insurance" },
  { v: "healthcare", l: "Healthcare" },
  { v: "government", l: "Government" },
  { v: "utilities",  l: "Utilities" },
];

const STEPS = [
  { id: 1, label: "Upload",  icon: Paperclip },
  { id: 2, label: "Review",  icon: FileText },
  { id: 3, label: "Submit",  icon: CheckCircle },
];

export default function MultiModalComplaintFlow() {
  const navigate = useNavigate();
  const [step,         setStep]         = useState(1);
  const [file,         setFile]         = useState(null);
  const [context,      setContext]       = useState("");
  const [analyzing,    setAnalyzing]     = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [description,  setDescription]  = useState("");
  const [domain,       setDomain]       = useState("ecommerce");
  const [submitting,   setSubmitting]   = useState(false);
  const [sessionId]    = useState(() => "sess-" + Math.random().toString(36).substring(2, 10));


  const analyzeFile = async () => {
    if (!file) { toast.error("Please select a file first."); return; }
    setAnalyzing(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      if (context.trim()) formData.append("context", context.trim());

      // Delete Content-Type so axios auto-sets multipart/form-data with correct boundary
      const { data } = await api.post("/multimodal/analyze", formData, {
        headers: { "Content-Type": undefined },
        transformRequest: (data, headers) => {
          delete headers["Content-Type"];
          delete headers["content-type"];
          return data;
        },
      });
      setAnalysisResult(data);
      if (data.extracted_text) setDescription(data.extracted_text.slice(0, 2000));
      setStep(2);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      // detail can be a string OR an array of FastAPI validation error objects
      const msg = Array.isArray(detail)
        ? detail.map((d) => d?.msg || JSON.stringify(d)).join("; ")
        : (typeof detail === "string" ? detail : null)
          ?? err?.message
          ?? "Analysis failed. Please try again.";
      toast.error(msg);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleUseText = (text) => {
    setDescription(text.slice(0, 2000));
    toast.success("Text applied to complaint description");
  };

  const submit = async () => {
    if (!description.trim() || description.trim().length < 10) {
      toast.error("Complaint description must be at least 10 characters.");
      return;
    }
    setSubmitting(true);
    try {
      const { data } = await api.post("/complaints", { domain, description });
      setStep(3);
      toast.success("Complaint submitted — AI is analyzing");
      setTimeout(() => navigate(`/complaints/${data.id}`), 1500);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Submission failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl">
      {/* Header */}
      <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 mb-2">
        Multi-Modal complaint
      </div>
      <h1 className="font-heading text-3xl font-semibold text-slate-900 flex items-center gap-3">
        <Paperclip className="w-7 h-7 text-indigo-500" />
        Submit with attachment
      </h1>
      <p className="text-slate-600 mt-2">
        Upload a photo, invoice PDF, or screenshot. Our AI extracts the text and pre-fills your complaint.
      </p>

      {/* Step indicator */}
      <div className="flex items-center gap-2 mt-8 mb-6">
        {STEPS.map((s, idx) => {
          const Icon  = s.icon;
          const active = s.id === step;
          const done   = s.id < step;
          return (
            <React.Fragment key={s.id}>
              <div className={`flex items-center gap-2 px-3 py-2 rounded-full text-sm font-medium transition-all ${
                active ? "bg-indigo-600 text-white shadow-sm"
                : done  ? "bg-emerald-100 text-emerald-700"
                : "bg-slate-100 text-slate-400"
              }`}>
                <Icon className="w-4 h-4" />
                {s.label}
              </div>
              {idx < STEPS.length - 1 && (
                <div className={`flex-1 h-0.5 rounded ${done ? "bg-emerald-300" : "bg-slate-200"}`} />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Step 1 — Upload */}
      {step === 1 && (
        <div className="space-y-5">
          <FileUploadZone onFileSelected={setFile} disabled={analyzing} />

          {/* Optional context */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">
              Brief context <span className="text-slate-400 font-normal">(optional)</span>
            </label>
            <input
              id="multimodal-context-input"
              type="text"
              className="w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm text-slate-800 placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-400"
              placeholder="e.g. This is my damaged product photo"
              value={context}
              onChange={(e) => setContext(e.target.value)}
            />
          </div>

          <button
            id="multimodal-analyze-btn"
            onClick={analyzeFile}
            disabled={!file || analyzing}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white font-semibold px-6 py-3 rounded-full transition-colors shadow-sm"
          >
            {analyzing
              ? <><Loader2 className="w-4 h-4 animate-spin" /> Analyzing…</>
              : <><FileText className="w-4 h-4" /> Analyze File</>
            }
          </button>
        </div>
      )}

      {/* Step 2 — Review */}
      {step === 2 && (
        <div className="space-y-5">
          <AnalysisResult result={analysisResult} onUseText={handleUseText} />

          {/* Editable description */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">
              Complaint Description
              <span className="text-slate-400 font-normal ml-2">(edit before submitting)</span>
            </label>
            <textarea
              id="multimodal-description-textarea"
              className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-800 placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
              rows={6}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe your complaint…"
            />
            <p className="text-xs text-slate-400 text-right">{description.length}/2000</p>
          </div>

          {/* Domain */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">Industry / Domain</label>
            <select
              className="w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-400"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
            >
              {DOMAINS.map((d) => <option key={d.v} value={d.v}>{d.l}</option>)}
            </select>
          </div>

          <div className="flex gap-3">
            <button
              id="multimodal-submit-btn"
              onClick={submit}
              disabled={submitting}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white font-semibold px-6 py-3 rounded-full transition-colors shadow-sm"
            >
              {submitting
                ? <><Loader2 className="w-4 h-4 animate-spin" /> Submitting…</>
                : <><Send className="w-4 h-4" /> Submit complaint</>
              }
            </button>
            <button
              onClick={() => { setStep(1); setAnalysisResult(null); setFile(null); }}
              className="px-4 py-3 border border-slate-200 rounded-full text-sm text-slate-500 hover:border-slate-300 transition-colors"
            >
              ← Upload different file
            </button>
          </div>
        </div>
      )}

      {/* Step 3 — Done */}
      {step === 3 && (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-10 text-center space-y-4">
          <CheckCircle className="w-14 h-14 text-emerald-500 mx-auto" />
          <h2 className="text-xl font-semibold text-slate-800">Complaint submitted!</h2>
          <p className="text-slate-500">Our AI agents are analyzing your complaint. Redirecting…</p>
        </div>
      )}

      {/* Real-time Assistant Drawer */}
      <AssistantPanel complaintText={description} sessionId={sessionId} userId="anonymous" />
    </div>
  );
}
