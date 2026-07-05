import React, { useState } from "react";
import AssistantPanel from "./AssistantPanel";

export default function RealtimeTestPage() {
  const [text, setText] = useState("");
  const sessionId = "test-session-123";

  return (
    <div className="flex h-full min-h-screen">
      {/* Main content */}
      <div className="flex-1 py-12 px-6 mr-80">
        <h1 className="text-3xl font-bold text-slate-900 mb-2">Real-Time Assistant Test</h1>
        <p className="text-slate-500 mb-8">
          Type a complaint below. Once you pass 15 characters, the AI Assistant
          on the right will start generating live hints and sentiment analysis
          via WebSocket.
        </p>

        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-700">
            Complaint Description
          </label>
          <textarea
            className="w-full h-64 rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-800 placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none shadow-sm"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Start typing your complaint here..."
          />
          <p className="text-xs text-slate-400 text-right">
            {text.length} characters
          </p>
        </div>
      </div>

      {/* AI Assistant panel — fixed to right side */}
      <div className="fixed top-0 right-0 h-full w-80 border-l border-slate-200 bg-white z-10">
        <AssistantPanel complaintText={text} sessionId={sessionId} />
      </div>
    </div>
  );
}