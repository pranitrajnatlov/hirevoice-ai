"use client";

import { useEffect, useRef } from "react";

/**
 * Live frequency-bar waveform (ElevenLabs-style). When a MediaStream is provided and
 * `active`, it visualizes real mic input via the Web Audio API; otherwise it idles.
 */
export function VoiceWaveform({
  stream,
  active,
  color = "#4CC9F0",
}: {
  stream?: MediaStream | null;
  active: boolean;
  color?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    const N = 48;

    let audioCtx: AudioContext | null = null;
    let analyser: AnalyserNode | null = null;
    let data: Uint8Array<ArrayBuffer> | null = null;

    if (stream && active) {
      audioCtx = new AudioContext();
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 128;
      audioCtx.createMediaStreamSource(stream).connect(analyser);
      data = new Uint8Array(analyser.frequencyBinCount);
    }

    let t = 0;
    const draw = () => {
      const { width, height } = canvas;
      ctx.clearRect(0, 0, width, height);
      const bw = width / N;
      for (let i = 0; i < N; i++) {
        let amp: number;
        if (analyser && data) {
          analyser.getByteFrequencyData(data);
          amp = (data[i % data.length] / 255) * 0.9 + 0.05;
        } else {
          // idle shimmer
          amp = active ? 0.2 + 0.18 * Math.abs(Math.sin(t / 8 + i / 3)) : 0.06;
        }
        const h = amp * height;
        ctx.fillStyle = color;
        ctx.globalAlpha = 0.35 + amp * 0.65;
        const x = i * bw + bw * 0.2;
        ctx.beginPath();
        ctx.roundRect(x, (height - h) / 2, bw * 0.6, h, 4);
        ctx.fill();
      }
      t++;
      rafRef.current = requestAnimationFrame(draw);
    };
    draw();

    return () => {
      cancelAnimationFrame(rafRef.current);
      audioCtx?.close();
    };
  }, [stream, active, color]);

  return <canvas ref={canvasRef} width={520} height={72} className="w-full" />;
}
