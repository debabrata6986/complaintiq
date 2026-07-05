import React, { useEffect, useState } from "react";
import { useWebSocket } from "./useWebSocket";
import RealtimeStatusBar from "./RealtimeStatusBar";
import LiveSentimentMeter from "./LiveSentimentMeter";
import SmartSuggestions from "./SmartSuggestions";
import { Bot } from "lucide-react";

export default function AssistantPanel({ complaintText, sessionId, userId = "anonymous" }) {
  const { send, lastMessage, status } = useWebSocket(sessionId);
  const [hintsData, setHintsData] = useState({
    hints: [],
    sentiment: "neutral",
    category_suggestion: "",
    similar_complaint_count: 0
  });
  const [loading, setLoading] = useState(false);

  // Handle incoming WS messages
  useEffect(() => {
    if (lastMessage && lastMessage.type === "HINT") {
      setHintsData(lastMessage.payload);
      setLoading(false);
    }
  }, [lastMessage]);

  // Debounced sending of typing events
  useEffect(() => {
    if (status !== "connected") return;

    const timer = setTimeout(() => {
      // Only send if length >= 15 chars (enforced here or backend, doing here avoids empty calls)
      if (complaintText && complaintText.length >= 15) {
        setLoading(true);
        send("TYPING", { text: complaintText });
      } else {
        // Reset if text deleted
        setHintsData({
          hints: [],
          sentiment: "neutral",
          category_suggestion: "",
          similar_complaint_count: 0
        });
      }
    }, 800);

    return () => clearTimeout(timer);
  }, [complaintText, status, send]);

  return (
    <div className="fixed right-0 top-0 h-full w-80 bg-slate-50 border-l border-slate-200 shadow-xl p-6 overflow-y-auto flex flex-col transition-transform">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2 text-slate-800 font-semibold">
          <Bot className="w-5 h-5 text-indigo-500" />
          AI Assistant
        </div>
        <RealtimeStatusBar status={status} />
      </div>

      <div className="space-y-8 flex-1">
        <LiveSentimentMeter sentiment={hintsData.sentiment} loading={loading} />
        
        <div className="pt-4 border-t border-slate-200">
          <SmartSuggestions 
            hints={hintsData.hints} 
            categoryGuess={hintsData.category_suggestion} 
            similarCount={hintsData.similar_complaint_count} 
          />
        </div>
      </div>
    </div>
  );
}
