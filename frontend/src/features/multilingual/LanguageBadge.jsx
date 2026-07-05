/**
 * LanguageBadge — shows a detected language name and confidence percentage
 * as a small pill badge.
 *
 * @param {Object}  props
 * @param {string}  props.code       — ISO 639-1 code, e.g. "hi"
 * @param {string}  props.name       — Human-readable name, e.g. "Hindi"
 * @param {number}  props.confidence — 0.0–1.0 confidence value
 */
import React from "react";
import { Badge } from "@/components/ui/badge";

const confidenceColor = (conf) => {
  if (conf >= 0.85) return "bg-emerald-100 text-emerald-800 border-emerald-200";
  if (conf >= 0.6)  return "bg-amber-100 text-amber-800 border-amber-200";
  return "bg-rose-100 text-rose-800 border-rose-200";
};

export default function LanguageBadge({ code, name, confidence }) {
  if (!code || code === "unknown") return null;

  const pct = Math.round((confidence || 0) * 100);
  const colorClass = confidenceColor(confidence || 0);

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${colorClass}`}
      title={`Detected: ${name} (${pct}% confidence)`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-70" />
      {name || code}
      {pct > 0 && <span className="opacity-60">{pct}%</span>}
    </span>
  );
}
