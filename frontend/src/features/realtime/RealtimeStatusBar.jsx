import React from "react";
import { Activity } from "lucide-react";

export default function RealtimeStatusBar({ status }) {
  let bgColor = "bg-slate-200";
  let dotColor = "bg-slate-400";
  let text = "Offline";

  if (status === "connected") {
    bgColor = "bg-emerald-50";
    dotColor = "bg-emerald-500 animate-pulse";
    text = "Connected";
  } else if (status === "connecting") {
    bgColor = "bg-amber-50";
    dotColor = "bg-amber-500 animate-pulse";
    text = "Reconnecting...";
  } else if (status === "error") {
    bgColor = "bg-red-50";
    dotColor = "bg-red-500";
    text = "Connection Error";
  }

  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border border-white/50 ${bgColor}`}>
      <Activity className="w-3.5 h-3.5 text-slate-500" />
      <span className={`w-2 h-2 rounded-full ${dotColor}`} />
      <span className="text-slate-700">{text}</span>
    </div>
  );
}
