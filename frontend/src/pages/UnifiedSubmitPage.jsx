import React, { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Send, Loader2, Mic, Paperclip, Globe, FileText, CheckCircle, Sparkles, Edit3 } from "lucide-react";

import AssistantPanel from "@/features/realtime/AssistantPanel";
import LanguageBadge from "@/features/multilingual/LanguageBadge";
import LanguageSelector from "@/features/multilingual/LanguageSelector";
import TranslationPreview from "@/features/multilingual/TranslationPreview";
import VoiceRecorder from "@/features/voice/VoiceRecorder";
import TranscriptionResult from "@/features/voice/TranscriptionResult";
import FileUploadZone from "@/features/multimodal/FileUploadZone";
import AnalysisResult from "@/features/multimodal/AnalysisResult";

const DOMAINS = [
  { v: "ecommerce", l: "E-commerce" }, { v: "banking", l: "Banking" },
  { v: "telecom", l: "Telecom" }, { v: "insurance", l: "Insurance" },
  { v: "healthcare", l: "Healthcare" }, { v: "government", l: "Government" },
  { v: "utilities", l: "Utilities" },
];
const CATEGORIES = ["Refund", "Replacement", "Delivery Delay", "Payment Failure", "Billing Issue", "Warranty", "Fraud", "Account Issue", "Cancellation", "General Complaint"];

export default function UnifiedSubmitPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("text"); 
  const [description, setDescription] = useState("");
  const [sessionId] = useState(() => "sess-" + Math.random().toString(36).substring(2, 10));
  const [submitting, setSubmitting] = useState(false);

  const doSubmit = async (finalDescription, extraPayload = {}) => {
    if (!finalDescription || finalDescription.trim().length < 10) {
      toast.error("Description must be at least 10 characters");
      return;
    }
    setSubmitting(true);
    try {
      const payload = { description: finalDescription, ...extraPayload };
      if (!payload.domain) payload.domain = "ecommerce"; // default
      const { data } = await api.post("/complaints", payload);
      toast.success("Complaint submitted — AI is analyzing");
      navigate(`/complaints/${data.id}`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Submission failed");
    } finally {
      setSubmitting(false);
    }
  };

  // Reset description when switching tabs to avoid confusion
  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setDescription("");
  };

  return (
    <div className="max-w-3xl pb-24 relative">
      <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 mb-2">New complaint</div>
      <h1 className="font-heading text-3xl font-semibold text-slate-900 mb-6">Submit a complaint</h1>

      <div className="flex items-center gap-2 mb-8 border-b border-slate-200 overflow-x-auto">
        <TabButton active={activeTab === "text"} onClick={() => handleTabChange("text")} icon={Edit3} label="Text" />
        <TabButton active={activeTab === "multilingual"} onClick={() => handleTabChange("multilingual")} icon={Globe} label="Multilingual" />
        <TabButton active={activeTab === "voice"} onClick={() => handleTabChange("voice")} icon={Mic} label="Voice" />
        <TabButton active={activeTab === "upload"} onClick={() => handleTabChange("upload")} icon={Paperclip} label="Upload" />
      </div>

      {activeTab === "text" && <TextTab description={description} setDescription={setDescription} doSubmit={doSubmit} submitting={submitting} />}
      {activeTab === "multilingual" && <MultilingualTab description={description} setDescription={setDescription} doSubmit={doSubmit} submitting={submitting} />}
      {activeTab === "voice" && <VoiceTab description={description} setDescription={setDescription} doSubmit={doSubmit} submitting={submitting} />}
      {activeTab === "upload" && <UploadTab description={description} setDescription={setDescription} doSubmit={doSubmit} submitting={submitting} />}

      <AssistantPanel complaintText={description} sessionId={sessionId} userId="anonymous" />
    </div>
  );
}

function TabButton({ active, onClick, icon: Icon, label }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-5 py-3 text-sm font-medium rounded-t-lg transition-colors border-b-2 ${
        active ? "border-indigo-600 text-indigo-700 bg-indigo-50/50" : "border-transparent text-slate-500 hover:text-slate-800 hover:bg-slate-50"
      }`}
    >
      <Icon className="w-4 h-4" />
      {label}
    </button>
  );
}

// ── Text Tab ──────────────────────────────────────────────────────────────
function TextTab({ description, setDescription, doSubmit, submitting }) {
  const [form, setForm] = useState({ domain: "ecommerce", category: "", customer_phone: "" });
  const ch = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
      <p className="text-slate-600 mb-6">Provide as much detail as possible — order IDs, dates, amounts. The AI will extract entities automatically.</p>
      <div className="card-soft p-6 space-y-5">
        <div className="grid md:grid-cols-2 gap-5">
          <div>
            <label className="label-field">Industry / Domain</label>
            <select className="input-field" value={form.domain} onChange={ch("domain")}>
              {DOMAINS.map((d) => <option key={d.v} value={d.v}>{d.l}</option>)}
            </select>
          </div>
          <div>
            <label className="label-field">Category (optional)</label>
            <select className="input-field" value={form.category} onChange={ch("category")}>
              <option value="">Let AI decide</option>
              {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        </div>
        <div>
          <label className="label-field">Phone (optional)</label>
          <input className="input-field" value={form.customer_phone} onChange={ch("customer_phone")} placeholder="+91 98765 43210" />
        </div>
        <div>
          <label className="label-field">Complaint description</label>
          <textarea
            rows={9}
            className="input-field font-body"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe your issue. Include order numbers, dates, amounts, what happened, and what you expect."
          />
          <div className="text-xs text-slate-400 mt-1">{description.length}/10000 characters</div>
        </div>
        <button onClick={() => doSubmit(description, form)} disabled={submitting} className="btn-primary">
          {submitting ? <><Loader2 className="w-4 h-4 animate-spin" /> Submitting</> : <><Send className="w-4 h-4" /> Submit complaint</>}
        </button>
      </div>
    </div>
  );
}

// ── Multilingual Tab ──────────────────────────────────────────────────────
function MultilingualTab({ description, setDescription, doSubmit, submitting }) {
  const [form, setForm] = useState({ domain: "ecommerce", category: "", customer_phone: "" });
  const [preferredLang, setPreferredLang] = useState("en");
  const [detectedLang, setDetectedLang] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [detecting, setDetecting] = useState(false);
  const debounceTimer = useRef(null);

  const ch = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const runDetection = useCallback(async (text) => {
    if (!text || text.trim().length < 10) {
      setDetectedLang(null); setAnalysisResult(null); return;
    }
    setDetecting(true);
    try {
      const { data } = await api.post("/multilingual/detect", { text });
      setDetectedLang(data);
      if (data.code && data.code !== "en" && !data.fallback) {
        const { data: analysis } = await api.post("/multilingual/analyze", { text, preferred_lang: preferredLang });
        setAnalysisResult(analysis);
      } else {
        setAnalysisResult(null);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setDetecting(false);
    }
  }, [preferredLang]);

  useEffect(() => {
    clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => runDetection(description), 800);
    return () => clearTimeout(debounceTimer.current);
  }, [description, runDetection]);

  const showTranslation = analysisResult?.translation_applied && analysisResult?.english_text && analysisResult?.english_text !== description;

  const handleSubmit = () => {
    const finalDesc = showTranslation ? analysisResult.english_text : description;
    doSubmit(finalDesc, form);
  };

  return (
    <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
      <p className="text-slate-600 mb-6">Write your complaint in Hindi, Bengali, Tamil, or any of 11 supported languages — we'll automatically detect and translate it.</p>
      <div className="space-y-5">
        <div className="card-soft p-6 space-y-5">
          <div className="grid md:grid-cols-2 gap-5">
            <div>
              <label className="label-field">Industry / Domain</label>
              <select className="input-field" value={form.domain} onChange={ch("domain")}>
                {DOMAINS.map((d) => <option key={d.v} value={d.v}>{d.l}</option>)}
              </select>
            </div>
            <LanguageSelector value={preferredLang} onChange={setPreferredLang} label="Preferred response language" />
          </div>
        </div>
        <div className="card-soft p-6 space-y-3">
          <div className="flex items-center justify-between">
            <label className="label-field mb-0">Complaint description</label>
            <div className="flex items-center gap-2">
              {detecting && <span className="flex items-center gap-1 text-xs text-indigo-500"><Loader2 className="w-3 h-3 animate-spin" /> Detecting…</span>}
              {detectedLang && !detecting && <LanguageBadge code={detectedLang.code} name={detectedLang.name} confidence={detectedLang.confidence} />}
            </div>
          </div>
          <textarea
            rows={8}
            className="input-field font-body"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Write your complaint in any language…&#10;हिंदी में लिखें, বাংলায় লিখুন, தமிழில் எழுதுங்கள்"
          />
        </div>
        {showTranslation && (
          <div className="space-y-2">
            <div className="flex items-center gap-1.5 text-xs text-indigo-600 font-medium">
              <Sparkles className="w-3.5 h-3.5" /> Auto-translated for our AI:
            </div>
            <TranslationPreview originalText={analysisResult.original_text} translatedText={analysisResult.english_text} sourceLang={analysisResult.detected_language?.name} targetLang="English" />
          </div>
        )}
        <button onClick={handleSubmit} disabled={submitting} className="btn-primary">
          {submitting ? <><Loader2 className="w-4 h-4 animate-spin" /> Submitting…</> : <><Send className="w-4 h-4" /> Submit complaint</>}
        </button>
      </div>
    </div>
  );
}

// ── Voice Tab ─────────────────────────────────────────────────────────────
function VoiceTab({ description, setDescription, doSubmit, submitting }) {
  const [step, setStep] = useState(1);
  const [transcription, setTranscription] = useState(null);
  const [domain, setDomain] = useState("ecommerce");

  const onComplete = (data) => {
    setTranscription(data);
    setDescription(data.transcribed_text || "");
    setStep(2);
  };

  return (
    <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
      <p className="text-slate-600 mb-6">Speak your complaint and let AI transcribe it for you. Review and edit before submitting.</p>
      
      {step === 1 && (
        <div className="space-y-4">
          <VoiceRecorder onTranscriptionComplete={onComplete} onError={(msg) => toast.error(msg)} />
          <p className="text-xs text-slate-400 text-center">Maximum recording: 25 MB. Supports wav, mp3, webm, ogg.</p>
        </div>
      )}

      {step === 2 && transcription && (
        <div className="space-y-5">
          <TranscriptionResult
            text={description}
            language={transcription.detected_language}
            confidence={transcription.confidence}
            onTextChange={setDescription}
          />
          <div className="card-soft p-5 space-y-3">
            <label className="label-field">Industry / Domain</label>
            <select className="input-field" value={domain} onChange={(e) => setDomain(e.target.value)}>
              {DOMAINS.map((d) => <option key={d.v} value={d.v}>{d.l}</option>)}
            </select>
          </div>
          <div className="flex gap-3">
            <button onClick={() => doSubmit(description, { domain })} disabled={submitting} className="btn-primary flex items-center gap-2">
              {submitting ? <><Loader2 className="w-4 h-4 animate-spin" /> Submitting…</> : <><Send className="w-4 h-4" /> Submit complaint</>}
            </button>
            <button onClick={() => setStep(1)} className="px-4 py-2 border border-slate-200 rounded-lg text-sm text-slate-500 hover:border-slate-300">
              ← Re-record
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Upload Tab ────────────────────────────────────────────────────────────
function UploadTab({ description, setDescription, doSubmit, submitting }) {
  const [step, setStep] = useState(1);
  const [file, setFile] = useState(null);
  const [context, setContext] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [domain, setDomain] = useState("ecommerce");

  const analyzeFile = async () => {
    if (!file) { toast.error("Please select a file first."); return; }
    setAnalyzing(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      if (context.trim()) formData.append("context", context.trim());
      const { data } = await api.post("/multimodal/analyze", formData, {
        headers: { "Content-Type": undefined },
        transformRequest: (data, headers) => {
          delete headers["Content-Type"]; return data;
        },
      });
      setAnalysisResult(data);
      if (data.extracted_text) setDescription(data.extracted_text.slice(0, 2000));
      setStep(2);
    } catch (err) {
      toast.error(err?.message || "Analysis failed.");
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
      <p className="text-slate-600 mb-6">Upload a photo, invoice PDF, or screenshot. Our AI extracts the text and pre-fills your complaint.</p>
      
      {step === 1 && (
        <div className="space-y-5">
          <FileUploadZone onFileSelected={setFile} disabled={analyzing} />
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">Brief context <span className="text-slate-400 font-normal">(optional)</span></label>
            <input
              type="text"
              className="w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm"
              placeholder="e.g. This is my damaged product photo"
              value={context} onChange={(e) => setContext(e.target.value)}
            />
          </div>
          <button onClick={analyzeFile} disabled={!file || analyzing} className="btn-primary">
            {analyzing ? <><Loader2 className="w-4 h-4 animate-spin" /> Analyzing…</> : <><FileText className="w-4 h-4" /> Analyze File</>}
          </button>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-5">
          <AnalysisResult result={analysisResult} onUseText={(t) => { setDescription(t.slice(0, 2000)); toast.success("Text applied"); }} />
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">Complaint Description</label>
            <textarea
              className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm resize-none"
              rows={6} value={description} onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">Industry / Domain</label>
            <select className="w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm" value={domain} onChange={(e) => setDomain(e.target.value)}>
              {DOMAINS.map((d) => <option key={d.v} value={d.v}>{d.l}</option>)}
            </select>
          </div>
          <div className="flex gap-3">
            <button onClick={() => doSubmit(description, { domain })} disabled={submitting} className="btn-primary">
              {submitting ? <><Loader2 className="w-4 h-4 animate-spin" /> Submitting…</> : <><Send className="w-4 h-4" /> Submit complaint</>}
            </button>
            <button onClick={() => { setStep(1); setAnalysisResult(null); setFile(null); setDescription(""); }} className="px-4 py-3 border border-slate-200 rounded-full text-sm text-slate-500">
              ← Upload different file
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
