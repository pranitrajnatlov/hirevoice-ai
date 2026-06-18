import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function Landing() {
  return (
    <div className="grid min-h-screen place-items-center px-4 text-center">
      <div>
        <h1 className="text-5xl font-extrabold tracking-tight text-gradient">HireVoice AI</h1>
        <p className="mx-auto mt-4 max-w-lg text-ink-muted">
          AI-native voice interviews. Resume-aware questions, real-time scoring, and instant hiring
          recommendations — all in the browser.
        </p>
        <div className="mt-8 flex justify-center gap-3">
          <Link href="/login"><Button size="lg">Recruiter sign in</Button></Link>
          <Link href="/register"><Button size="lg" variant="secondary">Create account</Button></Link>
        </div>
        <p className="mt-6 text-xs text-ink-muted">
          Candidates join via their emailed link: <code className="text-secondary">/interview/&lt;token&gt;</code>
        </p>
      </div>
    </div>
  );
}
