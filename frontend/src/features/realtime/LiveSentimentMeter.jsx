import React from "react";

export default function LiveSentimentMeter({ sentiment, loading }) {
  // Map sentiment to percentage and colors
  let percentage = 50; // Neutral default
  let barColor = "bg-slate-400";
  let label = "Neutral";

  if (sentiment === "positive") {
    percentage = 100;
    barColor = "bg-emerald-500";
    label = "Positive";
  } else if (sentiment === "negative") {
    percentage = 0;
    barColor = "bg-red-500";
    label = "Negative";
  }

  return (
    <div className="w-full space-y-1">
      <div className="flex justify-between items-center text-xs text-slate-500">
        <span>Sentiment</span>
        <span className="font-medium text-slate-700 capitalize">{label}</span>
      </div>
      <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden relative">
        <div 
          className={`h-full transition-all duration-500 ease-out ${barColor} ${loading ? 'opacity-50' : ''}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
