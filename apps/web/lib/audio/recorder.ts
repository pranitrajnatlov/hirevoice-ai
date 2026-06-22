/** Thin MediaRecorder wrapper for push-to-talk answer capture. */

export class AnswerRecorder {
  private mediaRecorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  stream: MediaStream | null = null;

  async init(): Promise<MediaStream> {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
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
    this.mediaRecorder.start(onPartial ? timesliceMs : undefined);
  }

  stop(): Promise<Blob> {
    return new Promise((resolve) => {
      if (!this.mediaRecorder) return resolve(new Blob());
      this.mediaRecorder.onstop = () => resolve(new Blob(this.chunks, { type: "audio/webm" }));
      this.mediaRecorder.stop();
    });
  }

  dispose() {
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
  }
}
