"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/dashboard/Sidebar";

export default function RecruiterLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  useEffect(() => {
    if (!localStorage.getItem("hv_token")) router.replace("/login");
  }, [router]);
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 px-5 py-6 md:px-8">{children}</main>
    </div>
  );
}
