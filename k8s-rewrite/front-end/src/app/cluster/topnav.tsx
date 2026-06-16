"use client";

import { useRouter } from "next/navigation";
import { Settings, User, RefreshCw } from "lucide-react";
import { useState, useCallback } from "react";
import ViewportWrapper from "./viewport-wrapper";

export default function TopNav() {
  const router = useRouter();
  const [syncing, setSyncing] = useState(false);

  const refreshCache = useCallback(async () => {
    setSyncing(true);
    try {
      await fetch("/api/cluster/refresh", { method: "POST" });
    } catch {
      // best effort
    } finally {
      setSyncing(false);
    }
  }, []);

  return (
    <header className="sticky top-0 z-10">
      <ViewportWrapper>
        <div className="h-12 flex items-center justify-end px-3 sm:px-4 lg:px-6 gap-1">
          <button
            onClick={refreshCache}
            disabled={syncing}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/30 transition-colors outline-none disabled:opacity-50"
            title="Refresh cluster data"
          >
            <RefreshCw className={`w-5 h-5 ${syncing ? "animate-spin" : ""}`} />
          </button>
          <button
            onClick={() => router.push("/settings")}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/30 transition-colors outline-none"
            title="Settings"
          >
            <Settings className="w-5 h-5" />
          </button>
          <div className="w-8 h-8 rounded-lg flex items-center justify-center text-zinc-400">
            <User className="w-5 h-5" />
          </div>
        </div>
      </ViewportWrapper>
    </header>
  );
}
