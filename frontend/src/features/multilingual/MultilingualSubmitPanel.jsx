/**
 * MultilingualSubmitPanel — full complaint submission page with live language detection.
 *
 * Flow:
 *  1. User types complaint text (any language)
 *  2. After 800ms debounce → POST /api/multilingual/detect → show LanguageBadge
 *  3. If non-English detected → show TranslationPreview via POST /api/multilingual/analyze
 *  4. User picks preferred response language via LanguageSelector
 *  5. Submit → POST /api/complaints/ with the English text
 */
import React, { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Send, Loader2, Globe, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import LanguageBadge from "./LanguageBadge";
import LanguageSelector from "./LanguageSelector";
import TranslationPreview from "./TranslationPreview";

const DOMAINS = [
  { v: "ecommerce",   l: "E-commerce" },
  { v: "banking",     l: "Banking" },
  { v: "telecom",     l: "Telecom" },
  { v: "insurance",   l: "Insurance" },
  { v: "healthcare",  l: "Healthcare" },
  { v: "government",  l: "Government" },
  { v: "utilities",   l: "Utilities" },
];

const CATEGORIES = [
  "Refund", "Replacement", "Delivery Delay", "Payment Failure",
  "Billing Issue", "Warranty", "Fraud", "Account Issue",
  "Cancellation", "General Complaint",
];

export default function MultilingualSubmitPanel() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    domain: "ecommerce",
    category: "",
    description: "",
    customer_phone: "",
  });
  const [preferredLang, setPreferredLang] = useState("en");
  const [detectedLang, setDetectedLang] = useState(null);   // { code, name, confidence }
  const [analysisResult, setAnalysisResult] = useState(null); // full pipeline result
  const [detecting, setDetecting] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const debounceTimer = useRef(null);

  const ch = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  // ── Live language detection (debounced 800ms) ───────────────────────────
  const runDetection = useCallback(async (text) => {
    if (!text || text.trim().length < 10) {
      setDetectedLang(null);
      setAnalysisResult(null);
      return;
    }
    setDetecting(true);
    try {
      const { data } = await api.post("/multilingual/detect", { text });
      setDetectedLang(data);

      // If non-English, run full pipeline for translation preview
      if (data.code && data.code !== "en" && !data.fallback) {
        const { data: analysis } = await api.post("/multilingual/analyze", {
          text,
          preferred_lang: preferredLang,
        });
        setAnalysisResult(analysis);
      } else {
        setAnalysisResult(null);
      }
    } catch (err) {
      console.error("Language detection error:", err);
    } finally {
      setDetecting(false);
    }
  }, [preferredLang]);

  useEffect(() => {
    clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => {
      runDetection(form.description);
    }, 800);
    return () => clearTimeout(debounceTimer.current);
  }, [form.description, runDetection]);

  // ── Submit ──────────────────────────────────────────────────────────────
  const submit = async (e) => {
    e.preventDefault();
    if (form.description.trim().length < 10) {
      toast.error("Description must be at least 10 characters");
      return;
    }
    setSubmitting(true);
    try {
      // Use translated English text if available, otherwise original
      const descriptionToSubmit =
        analysisResult?.translation_applied
          ? analysisResult.english_text
          : form.description;

      const payload = {
        domain: form.domain,
        category: form.category || undefined,
        description: descriptionToSubmit,
        customer_phone: form.customer_phone || undefined,
      };
      const { data } = await api.post("/complaints", payload);
      toast.success("Complaint submitted — AI is analyzing");
      navigate(`/complaints/${data.id}`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Submission failed");
    } finally {
      setSubmitting(false);
    }
  };

  const showTranslation =
    analysisResult?.translation_applied &&
    analysisResult?.english_text &&
    analysisResult?.english_text !== form.description;

  return (
    <div className="max-w-3xl">
      {/* Header */}
      <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 mb-2">
        Multilingual complaint submission
      </div>
      <h1 className="font-heading text-3xl font-semibold text-slate-900 flex items-center gap-3">
        <Globe className="w-7 h-7 text-indigo-500" />
        Submit in any language
      </h1>
      <p className="text-slate-600 mt-2">
        Write your complaint in Hindi, Bengali, Tamil, or any of 11 supported languages —
        we'll automatically detect and translate for our AI agents.
      </p>

      <form onSubmit={submit} className="mt-8 space-y-5">
        {/* Domain + Category */}
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
            <input
              className="input-field"
              value={form.customer_phone}
              onChange={ch("customer_phone")}
              placeholder="+91 98765 43210"
            />
          </div>

          {/* Preferred response language */}
          <LanguageSelector
            value={preferredLang}
            onChange={setPreferredLang}
            label="Preferred response language"
          />
        </div>

        {/* Description with live detection */}
        <div className="card-soft p-6 space-y-3">
          <div className="flex items-center justify-between">
            <label className="label-field mb-0">Complaint description</label>
            <div className="flex items-center gap-2">
              {detecting && (
                <span className="flex items-center gap-1 text-xs text-indigo-500">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Detecting…
                </span>
              )}
              {detectedLang && !detecting && (
                <LanguageBadge
                  code={detectedLang.code}
                  name={detectedLang.name}
                  confidence={detectedLang.confidence}
                />
              )}
            </div>
          </div>

          <textarea
            id="multilingual-description"
            rows={8}
            className="input-field font-body"
            value={form.description}
            onChange={ch("description")}
            placeholder={
              "Write your complaint in any language…\nहिंदी में लिखें, বাংলায় লিখুন, தமிழில் எழுதுங்கள்"
            }
            required
            minLength={10}
          />
          <div className="text-xs text-slate-400">{form.description.length}/10000 characters</div>
        </div>

        {/* Translation preview (shown when non-English detected) */}
        {showTranslation && (
          <div className="space-y-2">
            <div className="flex items-center gap-1.5 text-xs text-indigo-600 font-medium">
              <Sparkles className="w-3.5 h-3.5" />
              Auto-translated — the following English text will be submitted to our AI:
            </div>
            <TranslationPreview
              originalText={analysisResult.original_text}
              translatedText={analysisResult.english_text}
              sourceLang={analysisResult.detected_language?.name}
              targetLang="English"
            />
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={submitting}
          className="btn-primary"
          id="multilingual-submit-btn"
        >
          {submitting
            ? <><Loader2 className="w-4 h-4 animate-spin" /> Submitting…</>
            : <><Send className="w-4 h-4" /> Submit complaint</>
          }
        </button>
      </form>
    </div>
  );
}
