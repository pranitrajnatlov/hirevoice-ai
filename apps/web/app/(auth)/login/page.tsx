"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErr("");
    try {
      const { access_token } = await api.login({ email, password });
      localStorage.setItem("hv_token", access_token);
      router.push("/dashboard");
    } catch {
      setErr("Invalid credentials");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-screen place-items-center px-4">
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="glass-card w-full max-w-sm p-8">
        <h1 className="text-2xl font-bold text-gradient">HireVoice</h1>
        <p className="mt-1 mb-6 text-sm text-ink-muted">Sign in to your recruiter workspace.</p>
        <form onSubmit={submit} className="flex flex-col gap-3">
          <input
            type="email" placeholder="you@company.com" value={email} onChange={(e) => setEmail(e.target.value)}
            className="h-11 rounded-xl glass px-4 text-sm text-ink outline-none focus:border-accent"
          />
          <input
            type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)}
            className="h-11 rounded-xl glass px-4 text-sm text-ink outline-none focus:border-accent"
          />
          {err && <p className="text-sm text-danger">{err}</p>}
          <Button type="submit" size="lg" disabled={loading} className="mt-1">
            {loading ? "Signing in…" : "Sign in"}
          </Button>
        </form>
        <div className="mt-4 flex gap-2">
          <Button variant="secondary" size="sm" className="flex-1">Google</Button>
          <Button variant="secondary" size="sm" className="flex-1">Microsoft</Button>
        </div>
      </motion.div>
    </div>
  );
}
