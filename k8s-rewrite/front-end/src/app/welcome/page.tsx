"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Terminal, Server, Database, Shield, Activity, Settings } from "lucide-react";

const navItems = [
  { href: "/secrets", label: "Secrets Engine", icon: Shield },
  { href: "/deploy", label: "Deploy Cluster", icon: Terminal },
  { href: "/", label: "Cluster", icon: Server },
];

export default function Dashboard() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Header */}
      <header className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-indigo-600 flex items-center justify-center">
                <Activity className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-zinc-100">Botrus K8s</h1>
                <p className="text-sm text-zinc-400">Kubernetes Cluster Provisioning & Management</p>
              </div>
            </div>

            <nav className="hidden md:flex items-center gap-1">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors"
                >
                  <item.icon className="w-4 h-4" />
                  {item.label}
                </Link>
              ))}
            </nav>

            <div className="flex items-center gap-3">
              <button
                onClick={() => router.push("/secrets")}
                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-colors"
              >
                Get Started
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="text-center mb-12">
          <h2 className="text-4xl md:text-5xl font-bold text-zinc-100 mb-4">
            Welcome to Botrus K8s
          </h2>
          <p className="text-xl text-zinc-400 max-w-3xl mx-auto">
            Provision and manage your Kubernetes cluster with Longhorn distributed storage.
            Configure variables, deploy the cluster, and manage workloads from a beautiful UI.
          </p>
        </div>

        {/* Quick Actions */}
        <div className="grid md:grid-cols-3 gap-6 mb-12">
          <Link href="/secrets" className="glass-card p-6 rounded-xl hover:bg-zinc-800/80 transition-colors group">
            <Shield className="w-12 h-12 text-indigo-400 mb-4 group-hover:scale-110 transition-transform" />
            <h3 className="text-lg font-semibold text-zinc-100 mb-2">Secrets Engine</h3>
            <p className="text-zinc-400 text-sm">Manage configuration variables and secrets for your cluster</p>
          </Link>

          <Link href="/deploy" className="glass-card p-6 rounded-xl hover:bg-zinc-800/80 transition-colors group">
            <Terminal className="w-12 h-12 text-emerald-400 mb-4 group-hover:scale-110 transition-transform" />
            <h3 className="text-lg font-semibold text-zinc-100 mb-2">Deploy Cluster</h3>
            <p className="text-zinc-400 text-sm">Run Ansible playbooks with real-time terminal output</p>
          </Link>

          <Link href="/" className="glass-card p-6 rounded-xl hover:bg-zinc-800/80 transition-colors group">
            <Server className="w-12 h-12 text-blue-400 mb-4 group-hover:scale-110 transition-transform" />
            <h3 className="text-lg font-semibold text-zinc-100 mb-2">Manage Cluster</h3>
            <p className="text-zinc-400 text-sm">View nodes, pods, services, and Longhorn volumes</p>
          </Link>
        </div>

        {/* Features */}
        <div className="grid md:grid-cols-2 gap-6">
          <div className="glass-card p-6 rounded-xl">
            <Shield className="w-8 h-8 text-indigo-400 mb-3" />
            <h4 className="text-lg font-semibold text-zinc-100 mb-2">Encrypted Storage</h4>
            <p className="text-zinc-400 text-sm">All sensitive data (API keys, kubeconfig) is encrypted at rest using AES-256-GCM</p>
          </div>

          <div className="glass-card p-6 rounded-xl">
            <Terminal className="w-8 h-8 text-emerald-400 mb-3" />
            <h4 className="text-lg font-semibold text-zinc-100 mb-2">Real-time Terminal</h4>
            <p className="text-zinc-400 text-sm">Watch Ansible playbooks execute with live streaming output in an xterm.js terminal</p>
          </div>

          <div className="glass-card p-6 rounded-xl">
            <Activity className="w-8 h-8 text-blue-400 mb-3" />
            <h4 className="text-lg font-semibold text-zinc-100 mb-2">Rancher-like UI</h4>
            <p className="text-zinc-400 text-sm">Manage your cluster with a beautiful, intuitive interface similar to Rancher</p>
          </div>

          <div className="glass-card p-6 rounded-xl">
            <Settings className="w-8 h-8 text-purple-400 mb-3" />
            <h4 className="text-lg font-semibold text-zinc-100 mb-2">SQLite Database</h4>
            <p className="text-zinc-400 text-sm">Zero-config SQLite database for storing cluster state and job history</p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-800 mt-12 py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-zinc-500 text-sm">
          <p>Botrus Homelab • Kubernetes Cluster Manager</p>
        </div>
      </footer>
    </div>
  );
}