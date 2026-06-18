/** Thin MediaRecorder wrapper for push-to-talk answer capture. */

export class AnswerRecorder {
  private mediaRecorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  stream: MediaStream | null = null;

  async init(): Promise<MediaStream> {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    return this.stream;
  }

  start() {
    if (!this.stream) throw new Error("Recorder not initialized");
    this.chunks = [];
    this.mediaRecorder = new MediaRecorder(this.stream, { mimeType: "audio/webm" });
    this.mediaRecorder.ondataavailable = (e) => e.data.size > 0 && this.chunks.push(e.data);
    this.mediaRecorder.start();
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
