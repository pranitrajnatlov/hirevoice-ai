/** MediaRecorder wrapper for answer capture with grace-period (forgiving) push-to-talk. */

export type CaptureMode = "ptt" | "continuous";

/** Tunables for the grace-period stop so candidates aren't cut off mid-sentence. */
export interface GraceOptions {
  /** Hard cap on how long we keep listening after release. */
  maxGraceMs?: number;
  /** Stop once trailing audio stays below `threshold` for this long. */
  silenceMs?: number;
  /** RMS level (0..1) below which audio counts as silence. */
  threshold?: number;
  /** Fired while we're still listening after release (UI "Finishing…"). */
  onGraceStart?: () => void;
}

export class AnswerRecorder {
  private mediaRecorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  stream: MediaStream | null = null;

  // Web-Audio analyser for the RMS silence meter (shared primitive a future
  // continuous/VAD mode would reuse to auto-start as well as auto-stop).
  private audioCtx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private buf: Uint8Array<ArrayBuffer> | null = null;

  async init(): Promise<MediaStream> {
    // Explicit echo cancellation / noise suppression / AGC — without these, the AI's own TTS
    // question audio can bleed back into the mic (especially on laptop speakers, no headset)
    // and gets transcribed as if it were the candidate's answer.
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    return this.stream;
  }

  /**
   * Start recording. When `onPartial` is provided, MediaRecorder emits a chunk every
   * `timesliceMs` and we hand back the FULL accumulated blob (webm header + all chunks
   * so far — lone chunks aren't independently decodable) for near-real-time transcription.
   */
  start(onPartial?: (accumulated: Blob) => void, timesliceMs = 1500) {
    if (!this.stream) throw new Error("Recorder not initialized");
    this.chunks = [];
    this.mediaRecorder = new MediaRecorder(this.stream, { mimeType: "audio/webm" });
    this.mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        this.chunks.push(e.data);
        if (onPartial) onPartial(new Blob(this.chunks, { type: "audio/webm" }));
      }
    };
    this.mediaRecorder.start(onPartial ? timesliceMs : 250);
    this.setupMeter();
  }

  /** Current input loudness as RMS in 0..1 (0 when no analyser). */
  private rms(): number {
    if (!this.analyser || !this.buf) return 0;
    this.analyser.getByteTimeDomainData(this.buf);
    let sum = 0;
    for (let i = 0; i < this.buf.length; i++) {
      const v = (this.buf[i] - 128) / 128;
      sum += v * v;
    }
    return Math.sqrt(sum / this.buf.length);
  }

  private setupMeter() {
    if (!this.stream) return;
    try {
      this.audioCtx = new AudioContext();
      this.analyser = this.audioCtx.createAnalyser();
      this.analyser.fftSize = 1024;
      this.audioCtx.createMediaStreamSource(this.stream).connect(this.analyser);
      this.buf = new Uint8Array(new ArrayBuffer(this.analyser.fftSize));
    } catch {
      this.analyser = null;
    }
  }

  /** Hard stop — ends recording immediately and resolves the recorded blob. */
  stop(): Promise<Blob> {
    return new Promise((resolve) => {
      this.teardownMeter();
      if (!this.mediaRecorder || this.mediaRecorder.state === "inactive") {
        return resolve(new Blob(this.chunks, { type: "audio/webm" }));
      }
      this.mediaRecorder.onstop = () => resolve(new Blob(this.chunks, { type: "audio/webm" }));
      this.mediaRecorder.stop();
    });
  }

  /**
   * Forgiving stop (grace period): keep recording after the button is released and only
   * finalize once the candidate has actually gone quiet, or `maxGraceMs` elapses. This
   * prevents clipping answers when the user lifts the button a beat early.
   */
  stopGraceful(opts: GraceOptions = {}): Promise<Blob> {
    // maxGraceMs is a hard cap on trailing speech AFTER the candidate releases the button —
    // 2s was cutting people off mid-sentence when they kept talking past release (a very
    // common push-to-talk habit). 8s gives real trailing thoughts room to finish naturally;
    // silenceMs still ends it immediately once they actually stop talking.
    const { maxGraceMs = 8000, silenceMs = 800, threshold = 0.02, onGraceStart } = opts;
    // No meter available → fall back to a short fixed grace then hard stop.
    if (!this.analyser) {
      onGraceStart?.();
      return new Promise((resolve) => setTimeout(() => resolve(this.stop()), 600));
    }
    onGraceStart?.();
    return new Promise((resolve) => {
      const start = performance.now();
      let quietSince: number | null = null;
      const tick = () => {
        const now = performance.now();
        const level = this.rms();
        if (level < threshold) {
          quietSince ??= now;
        } else {
          quietSince = null; // speech resumed — keep listening
        }
        const quietLongEnough = quietSince !== null && now - quietSince >= silenceMs;
        const graceExpired = now - start >= maxGraceMs;
        if (quietLongEnough || graceExpired) {
          resolve(this.stop());
          return;
        }
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
  }

  private teardownMeter() {
    this.audioCtx?.close().catch(() => {});
    this.audioCtx = null;
    this.analyser = null;
    this.buf = null;
  }

  dispose() {
    this.teardownMeter();
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
  }
}
