"use client";

import { useRouter } from "next/navigation";
import { Settings, User, RefreshCw, LogOut } from "lucide-react";
import { useState, useCallback, useEffect } from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import ViewportWrapper from "./viewport-wrapper";

export default function TopNav() {
  const router = useRouter();
  const [syncing, setSyncing] = useState(false);
  const [username, setUsername] = useState<string | null>(null);
  const [role, setRole] = useState<"readonly" | "write" | null>(null);

  useEffect(() => {
    fetch("/api/auth/session")
      .then((r) => r.json())
      .then((data) => {
        if (data.authenticated) {
          setUsername(data.username);
          setRole(data.role || "readonly");
        }
      })
      .catch(() => {});
  }, []);

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

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/auth/login");
  }

  return (
    <header className="sticky top-0 z-10">
      <ViewportWrapper>
        <div className="h-12 flex items-center justify-end px-3 sm:px-4 lg:px-6 gap-1">
          {role === "write" && (
            <button
              onClick={refreshCache}
              disabled={syncing}
              className="w-8 h-8 rounded-lg flex items-center justify-center text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/30 transition-colors outline-none disabled:opacity-50"
              title="Refresh cluster data"
            >
              <RefreshCw className={`w-5 h-5 ${syncing ? "animate-spin" : ""}`} />
            </button>
          )}
          <button
            onClick={() => router.push("/settings")}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/30 transition-colors outline-none"
            title="Settings"
          >
            <Settings className="w-5 h-5" />
          </button>

          {/* User dropdown */}
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button
                className="w-8 h-8 rounded-lg flex items-center justify-center text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/30 transition-colors outline-none"
                title={username ?? "User"}
              >
                <User className="w-5 h-5" />
              </button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content
                side="bottom"
                align="end"
                sideOffset={6}
                className="min-w-[180px] bg-zinc-900 border border-zinc-800 rounded-xl p-1.5 shadow-xl z-50"
              >
                {username && (
                  <div className="px-3 py-2 text-sm text-zinc-300 border-b border-zinc-800 mb-1">
                    Signed in as{" "}
                    <span className="font-medium text-zinc-100">{username}</span>
                  </div>
                )}
                <DropdownMenu.Item
                  className="flex items-center gap-2 px-3 py-2 text-sm text-zinc-300 rounded-lg outline-none cursor-pointer hover:bg-zinc-800 focus:bg-zinc-800 transition-colors"
                  onClick={handleLogout}
                >
                  <LogOut className="w-4 h-4" />
                  Sign out
                </DropdownMenu.Item>
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        </div>
      </ViewportWrapper>
    </header>
  );
}
