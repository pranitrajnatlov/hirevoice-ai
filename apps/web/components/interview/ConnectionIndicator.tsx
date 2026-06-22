"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

/**
 * Connection quality indicator. Derives status from the browser's online state and the
 * live WebSocket connection. (Real latency metering can replace this later — the prop
 * surface stays the same.)
 */
export function ConnectionIndicator({ wsConnected }: { wsConnected: boolean }) {
  const [online, setOnline] = useState(true);

  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  const status = !online ? "offline" : wsConnected ? "good" : "fair";
  const meta = {
    good: { label: "Connected", color: "bg-success", bars: 3 },
    fair: { label: "Connecting", color: "bg-warn", bars: 2 },
    offline: { label: "Offline", color: "bg-danger", bars: 1 },
  }[status];

  return (
    <div className="flex items-center gap-2" title={`Connection: ${meta.label}`}>
      <div className="flex items-end gap-0.5" aria-hidden>
        {[1, 2, 3].map((b) => (
          <span
            key={b}
            className={cn(
              "w-1 rounded-sm transition-colors",
              b <= meta.bars ? meta.color : "bg-white/15",
            )}
            style={{ height: `${b * 4 + 2}px` }}
          />
        ))}
      </div>
      <span className="text-xs text-ink-muted">{meta.label}</span>
    </div>
  );
}
