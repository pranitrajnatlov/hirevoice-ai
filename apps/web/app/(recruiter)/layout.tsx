import { Sidebar } from "@/components/dashboard/Sidebar";

export default function RecruiterLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 px-5 py-6 md:px-8">{children}</main>
    </div>
  );
}
