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
      <div className="text-center mb-6">
        <h1 className="text-4xl font-bold text-gradient mb-2">Welcome back</h1>
        <p className="text-accent text-sm font-medium">Sign in to your account to continue</p>
      </div>

      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="glass-card w-full max-w-md p-8 relative overflow-hidden bg-white shadow-2xl">
        <div className="absolute top-0 left-0 w-full h-1.5 accent-gradient"></div>
        {expired && (
          <div className="mb-4 rounded-xl bg-warning/15 border border-warning/30 px-4 py-3 text-sm text-warning">
            Your session expired — please sign in again.
          </div>
        )}
        <form onSubmit={submit} className="flex flex-col gap-5">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-semibold text-ink">Email <span className="text-danger">*</span></label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-accent">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>
              </span>
              <input
                type="email" placeholder="Enter your email address" value={email} onChange={(e) => setEmail(e.target.value)}
                className="w-full h-11 rounded-xl border border-accent/20 bg-white pl-10 pr-4 text-sm text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent transition-all"
              />
            </div>
          </div>
          
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between items-center">
              <label className="text-sm font-semibold text-ink">Password <span className="text-danger">*</span></label>
              <div className="flex gap-4">
                <button type="button" className="text-sm font-semibold text-accent hover:underline flex items-center gap-1">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>
                  Resend email
                </button>
                <Link href="#" className="text-sm font-semibold text-accent hover:underline">
                  Forgot password?
                </Link>
              </div>
            </div>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-accent">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              </span>
              <input
                type="password" placeholder="Enter your password" value={password} onChange={(e) => setPassword(e.target.value)}
                className="w-full h-11 rounded-xl border border-accent/20 bg-white pl-10 pr-10 text-sm text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent transition-all"
              />
              <button type="button" className="absolute right-3 top-1/2 -translate-y-1/2 text-accent">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
              </button>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <input type="checkbox" id="remember" className="rounded border-accent/30 text-accent focus:ring-accent w-4 h-4" />
            <label htmlFor="remember" className="text-sm font-semibold text-accent">Remember me for 30 days</label>
          </div>

          {err && <p className="text-sm text-danger">{err}</p>}
          <Button type="submit" size="lg" disabled={loading} className="mt-2 w-full">
            {loading ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm font-medium text-ink-muted">
          Don&apos;t have an account?{" "}
          <Link href="/register" className="text-accent hover:underline font-semibold">
            Sign up
          </Link>
        </p>
      </motion.div>
    </div>
  );
}
