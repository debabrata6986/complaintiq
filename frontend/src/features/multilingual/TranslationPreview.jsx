/**
 * TranslationPreview — two-panel side-by-side view of original vs. translated text.
 *
 * @param {Object} props
 * @param {string} props.originalText    — the raw input text
 * @param {string} props.translatedText  — the English translation
 * @param {string} props.sourceLang      — source language name (display)
 * @param {string} props.targetLang      — target language name (display, usually "English")
 */
import React from "react";
import { Languages } from "lucide-react";

export default function TranslationPreview({ originalText, translatedText, sourceLang, targetLang }) {
  if (!originalText && !translatedText) return null;

  return (
    <div className="rounded-xl border border-indigo-100 bg-gradient-to-br from-indigo-50/60 to-purple-50/40 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2.5 bg-white/70 border-b border-indigo-100">
        <Languages className="w-4 h-4 text-indigo-500" />
        <span className="text-xs font-semibold text-indigo-700 uppercase tracking-wider">
          Translation Preview
        </span>
        <span className="text-xs text-slate-400 ml-auto">
          {sourceLang || "Detected"} → {targetLang || "English"}
        </span>
      </div>

      {/* Two-panel body */}
      <div className="grid md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-indigo-100">
        {/* Original */}
        <div className="p-4">
          <div className="text-[10px] font-bold uppercase tracking-widest text-indigo-400 mb-2">
            {sourceLang || "Original"}
          </div>
          <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
            {originalText}
          </p>
        </div>

        {/* Translation */}
        <div className="p-4">
          <div className="text-[10px] font-bold uppercase tracking-widest text-emerald-500 mb-2">
            {targetLang || "English"} (translated)
          </div>
          <p className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap font-medium">
            {translatedText || <span className="text-slate-400 italic">Translating…</span>}
          </p>
        </div>
      </div>
    </div>
  );
}
