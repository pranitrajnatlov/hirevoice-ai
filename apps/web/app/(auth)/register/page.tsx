"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import Cookies from "js-cookie";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [orgName, setOrgName] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErr("");
    try {
      const body: Record<string, string> = { email, password };
      if (fullName.trim()) body.full_name = fullName.trim();
      if (orgName.trim()) body.org_name = orgName.trim();
      const { access_token } = await api.register(body);
      Cookies.set("hv_token", access_token, { expires: 7, path: "/" });
      router.push("/dashboard");
    } catch (error) {
      const message = error instanceof Error ? error.message : "";
      setErr(message.startsWith("409:") ? "Email already registered" : "Could not create account");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-screen place-items-center px-4">
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="glass-card w-full max-w-sm p-8">
        <h1 className="text-2xl font-bold text-gradient">HireVoice</h1>
        <p className="mt-1 mb-6 text-sm text-ink-muted">Create your recruiter workspace.</p>
        <form onSubmit={submit} className="flex flex-col gap-3">
          <input
            type="text" placeholder="Full name" value={fullName} onChange={(e) => setFullName(e.target.value)}
            className="h-11 rounded-xl glass px-4 text-sm text-ink outline-none focus:border-accent"
          />
          <input
            type="text" placeholder="Organization" value={orgName} onChange={(e) => setOrgName(e.target.value)}
            className="h-11 rounded-xl glass px-4 text-sm text-ink outline-none focus:border-accent"
          />
          <input
            type="email" placeholder="you@company.com" value={email} onChange={(e) => setEmail(e.target.value)} required
            className="h-11 rounded-xl glass px-4 text-sm text-ink outline-none focus:border-accent"
          />
          <input
            type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required
            className="h-11 rounded-xl glass px-4 text-sm text-ink outline-none focus:border-accent"
          />
          {err && <p className="text-sm text-danger">{err}</p>}
          <Button type="submit" size="lg" disabled={loading} className="mt-1">
            {loading ? "Creating account…" : "Create account"}
          </Button>
        </form>
        <p className="mt-4 text-center text-sm text-ink-muted">
          Already have an account?{" "}
          <Link href="/login" className="text-accent hover:underline">
            Sign in
          </Link>
        </p>
      </motion.div>
    </div>
  );
}