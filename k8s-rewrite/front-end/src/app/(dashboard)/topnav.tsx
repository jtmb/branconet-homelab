"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Settings, User, RefreshCw, LogOut, Terminal } from "lucide-react";
import { useState, useEffect } from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import ViewportWrapper from "./viewport-wrapper";
import { openShell, closeAllShells, getShells, subscribe } from "@/lib/shell-manager";
import { clearQueries, requestJson, refetchCluster, useSession } from "@/lib/use-query";

export default function TopNav() {
  const router = useRouter();
  const session = useSession();
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");
  const [terminalActive, setTerminalActive] = useState(false);
  useEffect(() => { const update = () => setTerminalActive(getShells().length > 0); update(); return subscribe(update); }, []);
  useEffect(() => {
    const ended = () => { closeAllShells(); router.replace("/auth/login"); };
    window.addEventListener("bortus-session-ended", ended);
    return () => window.removeEventListener("bortus-session-ended", ended);
  }, [router]);
  useEffect(() => { if (!session.loading && !session.canWrite) closeAllShells(); }, [session.loading, session.canWrite]);
  const refresh = async () => {
    setSyncing(true); setError("");
    try {
      if (session.canWrite) await requestJson("/api/cluster/refresh", { method: "POST" });
      refetchCluster(); session.refetch();
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Refresh failed"); }
    finally { setSyncing(false); }
  };
  const logout = async () => {
    try { await requestJson("/api/auth/logout", { method: "POST" }); closeAllShells(); clearQueries(); router.replace("/auth/login"); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "Sign out failed"); }
  };
  const buttonClass = "flex h-9 w-9 items-center justify-center rounded-lg text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100";
  return <header className="sticky top-0 z-20 border-b border-zinc-800 bg-zinc-950/90 backdrop-blur-sm">
    <ViewportWrapper><div className="flex h-12 items-center justify-end gap-1 px-3">
      {(error || session.error) && <span role="status" className="mr-auto truncate text-xs text-amber-300">{error || "Session unavailable; write controls paused."}</span>}
      <button onClick={refresh} disabled={syncing} aria-label="Refresh cluster data" className={buttonClass}><RefreshCw className={`h-5 w-5 ${syncing ? "animate-spin" : ""}`} /></button>
      {session.canWrite && (session.data?.capabilities?.operatorShell || terminalActive) && <button
        onClick={() => { if (terminalActive) closeAllShells(); else openShell("kubectl"); }} aria-label={terminalActive ? "Close terminals" : "Open operator terminal"}
        className={buttonClass}><Terminal className="h-5 w-5" /></button>}
      <Link href="/settings" prefetch={false} aria-label="Settings" className={buttonClass}><Settings className="h-5 w-5" /></Link>
      <DropdownMenu.Root><DropdownMenu.Trigger asChild><button aria-label="Account menu" className={buttonClass}><User className="h-5 w-5" /></button></DropdownMenu.Trigger>
        <DropdownMenu.Portal><DropdownMenu.Content align="end" sideOffset={6} className="z-50 min-w-[180px] rounded-lg border border-zinc-700 bg-zinc-900 p-2 shadow-xl">
          <p className="border-b border-zinc-800 px-3 py-2 text-sm">{session.data?.username ?? "Session loading…"}</p>
          <DropdownMenu.Item onSelect={() => { void logout(); }} className="flex cursor-pointer items-center gap-2 rounded px-3 py-2 text-sm outline-none focus:bg-zinc-800"><LogOut className="h-4 w-4" />Sign out</DropdownMenu.Item>
        </DropdownMenu.Content></DropdownMenu.Portal>
      </DropdownMenu.Root>
    </div></ViewportWrapper>
  </header>;
}
