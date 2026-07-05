import React from "react";
import { Lightbulb, Info } from "lucide-react";

export default function SmartSuggestions({ hints = [], categoryGuess, similarCount }) {
  if (!hints.length && !categoryGuess) {
    return (
      <div className="text-sm text-slate-400 text-center py-6">
        Keep typing for AI suggestions...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {categoryGuess && (
        <div className="flex items-center gap-2 bg-indigo-50 border border-indigo-100 rounded-lg p-3">
          <Info className="w-4 h-4 text-indigo-500" />
          <div className="text-sm">
            <span className="text-slate-600">This looks like a </span>
            <span className="font-semibold text-indigo-700">{categoryGuess}</span>
            <span className="text-slate-600"> complaint.</span>
          </div>
        </div>
      )}

      {similarCount > 0 && (
        <div className="text-xs text-slate-500 font-medium">
          Found {similarCount} similar previous complaints.
        </div>
      )}

      {hints.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">
            <Lightbulb className="w-3.5 h-3.5 text-amber-500" />
            Suggested Details
          </div>
          <ul className="space-y-2">
            {hints.map((hint, idx) => (
              <li key={idx} className="bg-white border border-slate-200 rounded-lg p-3 text-sm text-slate-700 shadow-sm leading-relaxed">
                {hint}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
