/**
 * FeedbackWidget — thumbs-up/down rating widget for AI resolution quality.
 *
 * Renders inline next to any complaint resolution card.
 * Submits to POST /api/learning/feedback.
 *
 * @param {string}   complaintId    — complaint ID to rate
 * @param {string}   category       — which aspect: resolution|classification|priority|response
 * @param {Function} onSubmitted    — optional callback after successful submission
 */
import React, { useState } from "react";
import { ThumbsUp, ThumbsDown, MessageSquare, Send, CheckCircle } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

export default function FeedbackWidget({
  complaintId,
  category = "resolution",
  onSubmitted,
}) {
  const [rating,     setRating]     = useState(null);   // "thumbs_up" | "thumbs_down"
  const [correction, setCorrection] = useState("");
  const [showInput,  setShowInput]  = useState(false);
  const [submitted,  setSubmitted]  = useState(false);
  const [loading,    setLoading]    = useState(false);

  const submit = async (chosenRating) => {
    const finalRating = chosenRating || rating;
    if (!finalRating) return;

    setLoading(true);
    try {
      await api.post("/learning/feedback", {
        complaint_id: complaintId,
        rating:       finalRating,
        category,
        correction:   correction.trim() || null,
      });
      setSubmitted(true);
      toast.success("Feedback recorded — thank you!");
      onSubmitted?.({ rating: finalRating, correction });
    } catch (err) {
      toast.error("Could not save feedback. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <div className="inline-flex items-center gap-1.5 text-xs text-emerald-600 font-medium">
        <CheckCircle className="w-3.5 h-3.5" />
        Feedback recorded
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Rating buttons */}
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-slate-400 mr-1">Helpful?</span>

        <button
          id={`feedback-thumbsup-${complaintId}`}
          onClick={() => { setRating("thumbs_up"); submit("thumbs_up"); }}
          disabled={loading}
          className={`p-1.5 rounded-lg border transition-all ${
            rating === "thumbs_up"
              ? "bg-emerald-50 border-emerald-300 text-emerald-600"
              : "border-slate-200 text-slate-400 hover:border-emerald-300 hover:text-emerald-600 hover:bg-emerald-50"
          }`}
        >
          <ThumbsUp className="w-3.5 h-3.5" />
        </button>

        <button
          id={`feedback-thumbsdown-${complaintId}`}
          onClick={() => { setRating("thumbs_down"); setShowInput(true); }}
          disabled={loading}
          className={`p-1.5 rounded-lg border transition-all ${
            rating === "thumbs_down"
              ? "bg-rose-50 border-rose-300 text-rose-600"
              : "border-slate-200 text-slate-400 hover:border-rose-300 hover:text-rose-600 hover:bg-rose-50"
          }`}
        >
          <ThumbsDown className="w-3.5 h-3.5" />
        </button>

        {rating === "thumbs_down" && !showInput && (
          <button
            onClick={() => setShowInput(true)}
            className="text-xs text-slate-400 hover:text-slate-600 flex items-center gap-1"
          >
            <MessageSquare className="w-3 h-3" /> Add correction
          </button>
        )}
      </div>

      {/* Correction textarea */}
      {showInput && rating === "thumbs_down" && (
        <div className="flex gap-2 items-end">
          <textarea
            id={`feedback-correction-${complaintId}`}
            className="flex-1 text-xs border border-slate-200 rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-rose-300 text-slate-700 placeholder-slate-300"
            rows={2}
            placeholder="What was wrong? (optional)"
            value={correction}
            onChange={(e) => setCorrection(e.target.value)}
          />
          <button
            onClick={() => submit("thumbs_down")}
            disabled={loading}
            className="p-2 rounded-lg bg-rose-500 hover:bg-rose-600 text-white transition-colors flex-shrink-0"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
