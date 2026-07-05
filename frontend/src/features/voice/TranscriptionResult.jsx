/**
 * TranscriptionResult — editable display of transcribed audio text with language badge.
 *
 * @param {Object}   props
 * @param {string}   props.text           — transcribed text
 * @param {Object}   props.language       — detected language object {code, name, confidence}
 * @param {number}   props.confidence     — language confidence 0.0–1.0
 * @param {Function} props.onTextChange   — called when user edits the text
 */
import React, { useState } from "react";
import { Edit3, CheckCircle } from "lucide-react";
import LanguageBadge from "@/features/multilingual/LanguageBadge";

export default function TranscriptionResult({ text, language, confidence, onTextChange }) {
  const [editing, setEditing] = useState(false);
  const [localText, setLocalText] = useState(text || "");

  // Sync with parent when transcription arrives
  React.useEffect(() => {
    setLocalText(text || "");
  }, [text]);

  const handleChange = (e) => {
    setLocalText(e.target.value);
    onTextChange?.(e.target.value);
  };

  return (
    <div className="rounded-xl border border-slate-200 overflow-hidden bg-white shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-slate-50 border-b border-slate-200">
        <div className="flex items-center gap-2">
          <CheckCircle className="w-4 h-4 text-emerald-500" />
          <span className="text-sm font-semibold text-slate-700">Transcription</span>
          {language?.code && (
            <LanguageBadge
              code={language.code}
              name={language.name}
              confidence={confidence || language.confidence}
            />
          )}
        </div>
        <button
          type="button"
          onClick={() => setEditing((e) => !e)}
          className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border transition-colors ${
            editing
              ? "bg-indigo-50 text-indigo-700 border-indigo-200"
              : "bg-white text-slate-500 border-slate-200 hover:border-indigo-200 hover:text-indigo-600"
          }`}
        >
          <Edit3 className="w-3 h-3" />
          {editing ? "Done editing" : "Edit"}
        </button>
      </div>

      {/* Body */}
      <div className="p-4">
        {editing ? (
          <textarea
            id="transcription-edit-textarea"
            className="w-full text-sm text-slate-800 leading-relaxed bg-slate-50 rounded-lg border border-indigo-200 p-3 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
            rows={6}
            value={localText}
            onChange={handleChange}
            placeholder="Edit transcription…"
            autoFocus
          />
        ) : (
          <p className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap min-h-[4rem]">
            {localText || <span className="text-slate-400 italic">No transcription yet</span>}
          </p>
        )}
      </div>

      {editing && (
        <div className="px-4 pb-3 text-xs text-slate-400">
          {localText.length} characters — edits will be used when submitting
        </div>
      )}
    </div>
  );
}
