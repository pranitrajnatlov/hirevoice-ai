"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import Cookies from "js-cookie";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [expired, setExpired] = useState(false);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("expired")) setExpired(true);
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErr("");
    try {
      const { access_token } = await api.login({ email, password });
      Cookies.set("hv_token", access_token, { expires: 7, path: "/" });
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
        <h1 className="text-2xl font-bold text-gradient">Welcome back</h1>
        <p className="mt-1 mb-6 text-sm text-ink-muted">Sign in to your account to continue.</p>

        {expired && (
          <div className="mb-4 rounded-xl bg-warning/15 border border-warning/30 px-4 py-3 text-sm text-warning">
            Your session expired — please sign in again.
          </div>
        )}
        
        <form onSubmit={submit} className="flex flex-col gap-3">
          <input
            type="email" placeholder="Email address" value={email} onChange={(e) => setEmail(e.target.value)} required
            className="h-11 rounded-xl glass px-4 text-sm text-ink outline-none focus:border-accent"
          />
          <input
            type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required
            className="h-11 rounded-xl glass px-4 text-sm text-ink outline-none focus:border-accent"
          />
          {err && <p className="text-sm text-danger">{err}</p>}
          <Button type="submit" size="lg" disabled={loading} className="mt-1">
            {loading ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <p className="mt-4 text-center text-sm text-ink-muted">
          Don&apos;t have an account?{" "}
          <Link href="/register" className="text-accent hover:underline">
            Sign up
          </Link>
        </p>
      </motion.div>
    </div>
  );
}
