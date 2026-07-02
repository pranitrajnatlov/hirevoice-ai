"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LayoutDashboard, Users, Video, BarChart3, LogOut, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import Cookies from "js-cookie";
import { api, type UserOut } from "@/lib/api";

const NAV = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/candidates", label: "Candidates", icon: Users },
  { href: "/interviews", label: "Interviews", icon: Video },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
];

export function Sidebar() {
  const path = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<UserOut | null>(null);

  useEffect(() => {
    const token = Cookies.get("hv_token");
    if (token) {
      api.me(token).then(setUser).catch(console.error);
    }
  }, []);

  const logout = () => {
    Cookies.remove("hv_token", { path: "/" });
    router.replace("/login");
  };

  return (
    <aside className="sticky top-0 hidden h-screen w-60 flex-col border-r border-border p-4 md:flex">
      <div className="mb-6 px-2 text-lg font-bold text-gradient">HireVoice</div>

      <nav className="flex flex-1 flex-col gap-1">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = path === href || path.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors",
                active ? "bg-accent-soft text-accent" : "text-ink-muted hover:bg-white/5 hover:text-ink",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}

        <Link
          href="/interviews/new"
          className="mt-3 flex items-center gap-3 rounded-xl bg-accent/10 px-3 py-2.5 text-sm text-accent transition-colors hover:bg-accent/20"
        >
          <Plus className="h-4 w-4" />
          New Interview
        </Link>
      </nav>

      <div className="mt-auto pt-4 border-t border-border">
        {user ? (
          <div className="flex items-center justify-between px-2">
            <div className="flex items-center gap-3 overflow-hidden">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/20 text-xs font-medium text-accent">
                {(user.full_name || user.email).charAt(0).toUpperCase()}
              </div>
              <div className="flex flex-col overflow-hidden">
                <span className="truncate text-sm font-medium text-ink">{user.full_name || "Recruiter"}</span>
                <span className="truncate text-[11px] text-ink-muted">{user.email}</span>
              </div>
            </div>
            <button
              onClick={logout}
              title="Sign out"
              className="rounded-lg p-2 text-ink-muted transition-colors hover:bg-white/5 hover:text-danger"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        ) : (
          <button
            onClick={logout}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-ink-muted transition-colors hover:bg-white/5 hover:text-ink"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        )}
      </div>
    </aside>
  );
}
