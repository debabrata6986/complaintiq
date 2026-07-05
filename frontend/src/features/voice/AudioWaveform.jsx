/**
 * AudioWaveform — canvas-based real-time frequency visualiser.
 *
 * Uses Web Audio API AnalyserNode to render live frequency bars while recording.
 *
 * @param {Object}       props
 * @param {MediaStream}  props.mediaStream  — active microphone stream
 * @param {boolean}      props.isRecording  — drives animation lifecycle
 */
import React, { useEffect, useRef } from "react";

export default function AudioWaveform({ mediaStream, isRecording }) {
  const canvasRef = useRef(null);
  const rafRef    = useRef(null);
  const ctxRef    = useRef(null);  // AudioContext
  const analyserRef = useRef(null);

  useEffect(() => {
    if (!isRecording || !mediaStream) {
      // Stop animation and tear down audio context
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      if (ctxRef.current && ctxRef.current.state !== "closed") {
        ctxRef.current.close();
        ctxRef.current = null;
      }
      // Blank the canvas
      const canvas = canvasRef.current;
      if (canvas) {
        const ctx = canvas.getContext("2d");
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
      return;
    }

    // Set up AudioContext
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    ctxRef.current = audioCtx;

    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 64;
    analyserRef.current = analyser;

    const source = audioCtx.createMediaStreamSource(mediaStream);
    source.connect(analyser);

    const bufferLength = analyser.frequencyBinCount; // fftSize / 2 = 32
    const dataArray    = new Uint8Array(bufferLength);

    const canvas = canvasRef.current;
    const ctx    = canvas.getContext("2d");

    const draw = () => {
      rafRef.current = requestAnimationFrame(draw);
      analyser.getByteFrequencyData(dataArray);

      const { width, height } = canvas;
      ctx.clearRect(0, 0, width, height);

      const barWidth = (width / bufferLength) * 0.8;
      const gap      = (width / bufferLength) * 0.2;
      let x = 0;

      for (let i = 0; i < bufferLength; i++) {
        const barHeight = (dataArray[i] / 255) * height;
        const hue       = 200 + (i / bufferLength) * 60; // blue→violet
        ctx.fillStyle   = `hsla(${hue}, 80%, 55%, 0.85)`;
        ctx.beginPath();
        ctx.roundRect(x, height - barHeight, barWidth, barHeight, 3);
        ctx.fill();
        x += barWidth + gap;
      }
    };

    draw();

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      audioCtx.close();
    };
  }, [isRecording, mediaStream]);

  return (
    <canvas
      ref={canvasRef}
      width={320}
      height={64}
      className="w-full rounded-lg bg-slate-900/60"
      style={{ maxHeight: 64 }}
    />
  );
}
