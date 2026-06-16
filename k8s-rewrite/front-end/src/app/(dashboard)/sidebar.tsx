"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  Server, HardDrive, GitBranch, Terminal,
  PanelLeftClose, PanelLeft, LayoutDashboard, Key,
  Container, FolderTree, Rocket, Network, Globe, UsersRound,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: LayoutDashboard, color: "text-indigo-400" },
  { href: "/nodes", label: "Nodes", icon: Server, color: "text-blue-400" },
  { href: "/pods", label: "Pods", icon: Container, color: "text-cyan-400" },
  { href: "/name-spaces", label: "Namespaces", icon: FolderTree, color: "text-violet-400" },
  { href: "/deployments", label: "Deployments", icon: Rocket, color: "text-amber-400" },
  { href: "/services", label: "Services", icon: Network, color: "text-rose-400" },
  { href: "/ingresses", label: "Ingresses", icon: Globe, color: "text-sky-400" },
  { href: "/storage", label: "Storage", icon: HardDrive, color: "text-purple-400" },
  { href: "/flux", label: "Flux", icon: GitBranch, color: "text-emerald-400" },
  { href: "/deploy", label: "Provisioning", icon: Terminal, color: "text-emerald-400" },
  { href: "/secrets", label: "Secrets", icon: Key, color: "text-cyan-400" },
  { href: "/users", label: "Users", icon: UsersRound, color: "text-emerald-400" },
];

export default function ClusterSidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`sticky top-0 h-screen flex flex-col bg-zinc-900/50 sidebar-border backdrop-blur-sm transition-all duration-300 ${
        collapsed ? "w-14" : "w-56"
      }`}
    >
      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center justify-center h-12 border-b section-border text-zinc-500 hover:text-zinc-300 transition-colors flex-shrink-0 outline-none"
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? (
          <PanelLeft className="w-4 h-4" />
        ) : (
          <PanelLeftClose className="w-4 h-4" />
        )}
      </button>

      {/* Nav items */}
      <nav className="flex-1 py-3 space-y-1 px-2 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/" && pathname.startsWith(item.href + "/"));

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors outline-none ${
                isActive
                  ? "bg-zinc-800/50 text-zinc-100"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/30"
              }`}
            >
              <item.icon
                className={`w-5 h-5 flex-shrink-0 ${isActive ? item.color : ""}`}
              />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Bottom branding */}
      {!collapsed && (
        <div className="px-3 py-3 border-t section-border flex-shrink-0">
          <p className="text-[10px] text-zinc-600 tracking-wide uppercase">
            Botrus Homelab
          </p>
        </div>
      )}
    </aside>
  );
}
