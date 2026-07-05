/**
 * AnalysisResult — displays the structured output from the multimodal pipeline.
 *
 * Shows different UI depending on file_type: pdf | image | text | unsupported
 *
 * @param {Object}   result          — pipeline result dict
 * @param {Function} onUseText       — called with extracted_text when user wants to use it
 */
import React, { useState } from "react";
import {
  FileText, Image, CheckCircle, XCircle, Tag,
  Copy, ChevronDown, ChevronUp, Sparkles,
} from "lucide-react";
import { toast } from "sonner";

function TypeBadge({ fileType }) {
  const map = {
    pdf:   { label: "PDF",   cls: "bg-rose-100 text-rose-700 border-rose-200" },
    image: { label: "Image", cls: "bg-indigo-100 text-indigo-700 border-indigo-200" },
    text:  { label: "Text",  cls: "bg-slate-100 text-slate-600 border-slate-200" },
  };
  const { label, cls } = map[fileType] || { label: fileType, cls: "bg-slate-100 text-slate-500" };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold border ${cls}`}>{label}</span>
  );
}

export default function AnalysisResult({ result, onUseText }) {
  const [expanded, setExpanded] = useState(false);

  if (!result) return null;

  const { success, file_type, filename, extracted_text, analysis, error, size_bytes } = result;

  const copyText = () => {
    if (extracted_text) {
      navigator.clipboard.writeText(extracted_text);
      toast.success("Text copied to clipboard");
    }
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <div className={`px-5 py-4 border-b flex items-center justify-between ${
        success ? "bg-emerald-50 border-emerald-100" : "bg-rose-50 border-rose-100"
      }`}>
        <div className="flex items-center gap-2">
          {success
            ? <CheckCircle className="w-5 h-5 text-emerald-500" />
            : <XCircle className="w-5 h-5 text-rose-500" />
          }
          <span className="font-semibold text-slate-700 truncate max-w-xs">{filename}</span>
          <TypeBadge fileType={file_type} />
        </div>
        <span className="text-xs text-slate-400">
          {size_bytes ? `${(size_bytes / 1024).toFixed(1)} KB` : ""}
        </span>
      </div>

      {!success ? (
        <div className="px-5 py-4 text-sm text-rose-600">{error}</div>
      ) : (
        <div className="p-5 space-y-4">

          {/* Image-specific: AI description + complaint type */}
          {file_type === "image" && analysis && (
            <div className="space-y-3">
              {analysis.complaint_type && (
                <div className="flex items-center gap-2">
                  <Tag className="w-4 h-4 text-indigo-500" />
                  <span className="text-sm font-medium text-slate-700">Detected type:</span>
                  <span className="px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 text-xs font-semibold border border-indigo-200">
                    {analysis.complaint_type}
                  </span>
                </div>
              )}
              {extracted_text && (
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-violet-500" />
                    <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">AI Description</span>
                  </div>
                  {/* Show first 2 meaningful non-heading sentences from the full analysis */}
                  <p className="text-sm text-slate-700 leading-relaxed">
                    {(() => {
                      const isHeading = (line) => {
                        if (/[.!?,;:]/.test(line)) return false; // has punctuation → real content
                        const words = line.split(" ").filter(w => w.length > 3);
                        if (!words.length) return false;
                        const capRatio = words.filter(w => w[0] && w[0] === w[0].toUpperCase()).length / words.length;
                        return capRatio >= 0.6; // mostly capitalised → heading
                      };
                      const meaningful = extracted_text
                        .split("\n")
                        .map(l => l.trim())
                        .filter(l => l.length > 20 && !isHeading(l));
                      return (meaningful.slice(0, 2).join(" ").slice(0, 300)) || extracted_text.slice(0, 300);
                    })()}
                  </p>

                </div>
              )}
            </div>
          )}


          {/* PDF-specific: page count */}
          {file_type === "pdf" && analysis && (
            <p className="text-xs text-slate-500">
              📄 {analysis.page_count} page{analysis.page_count !== 1 ? "s" : ""} extracted
              · {analysis.char_count?.toLocaleString()} characters
            </p>
          )}

          {/* Extracted text */}
          {extracted_text ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Extracted Text
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={copyText}
                    className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 transition-colors"
                  >
                    <Copy className="w-3 h-3" /> Copy
                  </button>
                  <button
                    onClick={() => setExpanded((e) => !e)}
                    className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600"
                  >
                    {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    {expanded ? "Collapse" : "Expand"}
                  </button>
                </div>
              </div>
              <div className={`relative overflow-hidden rounded-lg border border-slate-200 bg-slate-50 p-3 ${
                !expanded ? "max-h-24" : ""
              }`}>
                <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
                  {extracted_text}
                </p>
                {!expanded && extracted_text.length > 200 && (
                  <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-slate-50" />
                )}
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-400 italic">No text could be extracted from this file.</p>
          )}

          {/* Use text button */}
          {extracted_text && onUseText && (
            <button
              id="multimodal-use-text-btn"
              onClick={() => onUseText(extracted_text)}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold transition-colors"
            >
              <CheckCircle className="w-4 h-4" />
              Use this text as complaint description
            </button>
          )}
        </div>
      )}
    </div>
  );
}
