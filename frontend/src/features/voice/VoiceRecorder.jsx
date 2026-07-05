/**
 * VoiceRecorder — manages microphone recording via MediaRecorder API.
 *
 * States: idle → recording → recorded → uploading → done
 *
 * @param {Object}   props
 * @param {Function} props.onTranscriptionComplete — called with {text, language, confidence, ...}
 * @param {Function} props.onError                — called with error message string
 */
import React, { useState, useRef, useEffect } from "react";
import { Mic, StopCircle, RefreshCw, Loader2, Send } from "lucide-react";
import { api } from "@/lib/api";
import AudioWaveform from "./AudioWaveform";

const STATES = { IDLE: "idle", RECORDING: "recording", RECORDED: "recorded", UPLOADING: "uploading", DONE: "done" };

function formatTime(seconds) {
  const m = Math.floor(seconds / 60).toString().padStart(2, "0");
  const s = (seconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

export default function VoiceRecorder({ onTranscriptionComplete, onError }) {
  const [status, setStatus]   = useState(STATES.IDLE);
  const [seconds, setSeconds] = useState(0);
  const [audioBlob, setAudioBlob] = useState(null);
  const [audioUrl,  setAudioUrl]  = useState(null);
  const [stream,    setStream]    = useState(null);

  const mediaRecorderRef = useRef(null);
  const chunksRef        = useRef([]);
  const timerRef         = useRef(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clearInterval(timerRef.current);
      if (stream) stream.getTracks().forEach((t) => t.stop());
    };
  }, [stream]);

  const startRecording = async () => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setStream(mediaStream);

      // Pick the best supported MIME type
      const mimeType = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/ogg;codecs=opus",
        "audio/ogg",
      ].find((m) => MediaRecorder.isTypeSupported(m)) || "";

      const recorderOptions = mimeType ? { mimeType } : {};
      const recorder = new MediaRecorder(mediaStream, recorderOptions);
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        const actualType = recorder.mimeType || mimeType || "audio/webm";
        const blob = new Blob(chunksRef.current, { type: actualType });
        setAudioBlob(blob);
        setAudioUrl(URL.createObjectURL(blob));
        setStatus(STATES.RECORDED);
        mediaStream.getTracks().forEach((t) => t.stop());
        setStream(null);
      };

      recorder.start(100);
      setStatus(STATES.RECORDING);
      setSeconds(0);
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch (err) {
      onError?.(`Microphone access denied: ${err.message}`);
    }
  };

  const stopRecording = () => {
    clearInterval(timerRef.current);
    if (mediaRecorderRef.current?.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
  };

  const reset = () => {
    setStatus(STATES.IDLE);
    setAudioBlob(null);
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioUrl(null);
    setSeconds(0);
  };

  const upload = async () => {
    if (!audioBlob) return;
    setStatus(STATES.UPLOADING);
    try {
      const formData = new FormData();
      // Use a filename that matches the MIME type so the validator can use extension fallback
      const ext = (audioBlob.type || "audio/webm").split("/")[1]?.split(";")[0] || "webm";
      formData.append("file", audioBlob, `recording.${ext}`);

      // The api instance defaults to Content-Type: application/json.
      // We must delete that header so axios auto-sets multipart/form-data with the correct boundary.
      const { data } = await api.post("/voice/transcribe", formData, {
        headers: { "Content-Type": undefined },
        transformRequest: (data, headers) => {
          // Remove Content-Type so the browser/axios sets it with the correct multipart boundary
          delete headers["Content-Type"];
          delete headers["content-type"];
          return data;
        },
      });


      setStatus(STATES.DONE);
      onTranscriptionComplete?.(data);
    } catch (err) {
      setStatus(STATES.RECORDED);
      // Extract the most useful error message available
      const detail = err?.response?.data?.detail;
      const status  = err?.response?.status;
      const fallback = err?.message || "Transcription failed. Please try again.";
      const msg = detail
        ? `Error ${status}: ${typeof detail === "string" ? detail : JSON.stringify(detail)}`
        : fallback;
      console.error("[VoiceRecorder] Transcribe error:", status, err?.response?.data, err);
      onError?.(msg);
    }
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Mic className={`w-5 h-5 ${status === STATES.RECORDING ? "text-rose-500 animate-pulse" : "text-slate-400"}`} />
            <span className="font-semibold text-slate-700">Voice Recording</span>
          </div>
          {status === STATES.RECORDING && (
            <span className="flex items-center gap-1.5 text-sm font-mono font-bold text-rose-600">
              <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
              {formatTime(seconds)}
            </span>
          )}
          {status === STATES.RECORDED && (
            <span className="text-xs text-slate-400">Duration: {formatTime(seconds)}</span>
          )}
        </div>
      </div>

      {/* Waveform / Preview */}
      <div className="px-5 py-4 bg-slate-900/5">
        {status === STATES.RECORDING ? (
          <AudioWaveform mediaStream={stream} isRecording={true} />
        ) : (
          <div className="h-16 rounded-lg bg-slate-100 flex items-center justify-center">
            {status === STATES.IDLE && (
              <span className="text-xs text-slate-400">Press record to start</span>
            )}
            {status === STATES.RECORDED && audioUrl && (
              <audio src={audioUrl} controls className="w-full h-10" />
            )}
            {(status === STATES.UPLOADING || status === STATES.DONE) && (
              <span className="text-xs text-slate-400">Processing audio…</span>
            )}
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="px-5 py-4 flex items-center gap-3">
        {status === STATES.IDLE && (
          <button
            id="voice-record-btn"
            onClick={startRecording}
            className="flex items-center gap-2 bg-rose-500 hover:bg-rose-600 text-white font-semibold px-5 py-2.5 rounded-full transition-colors shadow-sm"
          >
            <Mic className="w-4 h-4" /> Start Recording
          </button>
        )}

        {status === STATES.RECORDING && (
          <button
            id="voice-stop-btn"
            onClick={stopRecording}
            className="flex items-center gap-2 bg-slate-800 hover:bg-slate-900 text-white font-semibold px-5 py-2.5 rounded-full transition-colors shadow-sm"
          >
            <StopCircle className="w-4 h-4" /> Stop
          </button>
        )}

        {status === STATES.RECORDED && (
          <>
            <button
              id="voice-transcribe-btn"
              onClick={upload}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-5 py-2.5 rounded-full transition-colors shadow-sm"
            >
              <Send className="w-4 h-4" /> Transcribe
            </button>
            <button
              id="voice-reset-btn"
              onClick={reset}
              className="flex items-center gap-2 text-slate-500 hover:text-slate-700 px-3 py-2.5 rounded-full border border-slate-200 hover:border-slate-300 transition-colors"
            >
              <RefreshCw className="w-4 h-4" /> Re-record
            </button>
          </>
        )}

        {status === STATES.UPLOADING && (
          <button disabled className="flex items-center gap-2 bg-indigo-400 text-white font-semibold px-5 py-2.5 rounded-full cursor-not-allowed">
            <Loader2 className="w-4 h-4 animate-spin" /> Transcribing…
          </button>
        )}

        {status === STATES.DONE && (
          <button
            onClick={reset}
            className="flex items-center gap-2 text-slate-500 hover:text-slate-700 px-3 py-2.5 rounded-full border border-slate-200 transition-colors"
          >
            <RefreshCw className="w-4 h-4" /> Record again
          </button>
        )}
      </div>
    </div>
  );
}
