/**
 * VoiceComplaintFlow — full 3-step voice complaint submission page.
 *
 * Step 1: Record audio
 * Step 2: Review & edit transcription
 * Step 3: Submit complaint
 */
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Mic, FileText, CheckCircle, Send, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import VoiceRecorder from "./VoiceRecorder";
import TranscriptionResult from "./TranscriptionResult";

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
  { id: 1, label: "Record",    icon: Mic },
  { id: 2, label: "Review",   icon: FileText },
  { id: 3, label: "Submit",   icon: CheckCircle },
];

export default function VoiceComplaintFlow() {
  const navigate = useNavigate();
  const [step, setStep]               = useState(1);
  const [transcription, setTranscription] = useState(null);
  const [editedText, setEditedText]   = useState("");
  const [domain, setDomain]           = useState("ecommerce");
  const [submitting, setSubmitting]   = useState(false);

  const onTranscriptionComplete = (data) => {
    setTranscription(data);
    setEditedText(data.transcribed_text || "");
    setStep(2);
  };

  const onError = (msg) => {
    toast.error(msg);
  };

  const submit = async () => {
    if (!editedText.trim() || editedText.trim().length < 10) {
      toast.error("Complaint text must be at least 10 characters.");
      return;
    }
    setSubmitting(true);
    try {
      const { data } = await api.post("/complaints", {
        domain,
        description: editedText,
      });
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
      {/* Page header */}
      <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 mb-2">
        Voice complaint
      </div>
      <h1 className="font-heading text-3xl font-semibold text-slate-900 flex items-center gap-3">
        <Mic className="w-7 h-7 text-rose-500" />
        Submit by voice
      </h1>
      <p className="text-slate-600 mt-2">
        Speak your complaint and let AI transcribe it for you. Review and edit before submitting.
      </p>

      {/* Step indicator */}
      <div className="flex items-center gap-2 mt-8 mb-6">
        {STEPS.map((s, idx) => {
          const Icon = s.icon;
          const active   = s.id === step;
          const done     = s.id < step;
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

      {/* Step 1 — Record */}
      {step === 1 && (
        <div className="space-y-4">
          <VoiceRecorder onTranscriptionComplete={onTranscriptionComplete} onError={onError} />
          <p className="text-xs text-slate-400 text-center">
            Maximum recording: 25 MB. Supports wav, mp3, webm, ogg.
          </p>
        </div>
      )}

      {/* Step 2 — Review */}
      {step === 2 && transcription && (
        <div className="space-y-5">
          <TranscriptionResult
            text={editedText}
            language={transcription.detected_language}
            confidence={transcription.confidence}
            onTextChange={setEditedText}
          />

          {/* Domain selector */}
          <div className="card-soft p-5 space-y-3">
            <label className="label-field">Industry / Domain</label>
            <select
              className="input-field"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
            >
              {DOMAINS.map((d) => <option key={d.v} value={d.v}>{d.l}</option>)}
            </select>
          </div>

          <div className="flex gap-3">
            <button
              id="voice-submit-complaint-btn"
              onClick={submit}
              disabled={submitting}
              className="btn-primary flex items-center gap-2"
            >
              {submitting
                ? <><Loader2 className="w-4 h-4 animate-spin" /> Submitting…</>
                : <><Send className="w-4 h-4" /> Submit complaint</>
              }
            </button>
            <button
              onClick={() => setStep(1)}
              className="px-4 py-2 border border-slate-200 rounded-lg text-sm text-slate-500 hover:border-slate-300 transition-colors"
            >
              ← Re-record
            </button>
          </div>
        </div>
      )}

      {/* Step 3 — Done */}
      {step === 3 && (
        <div className="card-soft p-8 text-center space-y-4">
          <CheckCircle className="w-14 h-14 text-emerald-500 mx-auto" />
          <h2 className="text-xl font-semibold text-slate-800">Complaint submitted!</h2>
          <p className="text-slate-500">Our AI agents are analyzing your complaint. Redirecting…</p>
        </div>
      )}
    </div>
  );
}
