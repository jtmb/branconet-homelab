"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import {
  Activity,
  ArrowRight,
  Box,
  Cpu,
  Database,
  GitBranch,
  Github,
  Globe,
  HardDrive,
  Key,
  LayoutDashboard,
  Loader2,
  Play,
  Server,
  Shield,
  Terminal,
  Users,
} from "lucide-react";

export default function WelcomePage() {
  const router = useRouter();
  const [checking, setChecking] = useState(true);
  const [pendingRequests, setPendingRequests] = useState(0);

  useEffect(() => {
    setChecking(false);
  }, []);

  async function handleGetStarted() {
    setPendingRequests((count) => count + 1);
    try {
      const res = await fetch("/api/auth/session");
      if (!res.ok) throw new Error("Session unavailable");
      const session = await res.json();
      if (
        !session || typeof session !== "object" || Array.isArray(session) ||
        typeof session.authenticated !== "boolean" || typeof session.hasUsers !== "boolean"
      ) throw new Error("Invalid session response");

      if (session.authenticated === true) {
        router.push("/");
      } else if (session.hasUsers === false) {
        router.push("/auth/register");
      } else {
        router.push("/auth/login");
      }
    } catch {
      router.push("/auth/login");
    } finally {
      setPendingRequests((count) => count - 1);
    }
  }

  if (checking) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <p className="sr-only" role="status">{pendingRequests > 0 ? "Checking session…" : ""}</p>
      {/* ===== 1. Header ===== */}
      <header className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-indigo-600 flex items-center justify-center">
                <Activity className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-zinc-100">Botrus K8s</h1>
                <p className="text-sm text-zinc-400">Kubernetes Cluster Manager</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <a
                href="https://github.com/jtmb/branconet-homelab"
                target="_blank"
                rel="noopener noreferrer"
                className="hidden sm:inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-zinc-700 text-zinc-300 hover:text-zinc-100 hover:border-zinc-600 transition-colors text-sm font-medium"
              >
                <Github className="w-4 h-4" />
                GitHub
              </a>
              <button
                onClick={handleGetStarted}
                aria-busy={pendingRequests > 0}
                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-colors"
              >
                Get Started
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* ===== 2. Hero ===== */}
      <section className="relative overflow-hidden">
        {/* Dot grid background */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: "radial-gradient(circle, rgb(148, 163, 184) 1px, transparent 1px)",
            backgroundSize: "24px 24px",
          }}
        />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 lg:py-28">
          <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
            {/* Left — text */}
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-sm font-medium mb-6">
                <Server className="w-3.5 h-3.5" />
                Homelab Dashboard
              </div>
              <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold text-zinc-100 leading-tight mb-6">
                Kubernetes Cluster
                <br />
                <span className="text-indigo-400">Management</span> Made Simple
              </h2>
              <p className="text-lg text-zinc-400 max-w-lg mb-8 leading-relaxed">
                Inspect cluster resources, manage native Kubernetes Secrets, and view
                FluxCD status from one dashboard. Built for bare-metal homelabs.
              </p>
              <div className="flex flex-wrap gap-4">
                <button
                  onClick={handleGetStarted}
                  aria-busy={pendingRequests > 0}
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-colors"
                >
                  Get Started
                  <ArrowRight className="w-4 h-4" />
                </button>
                <a
                  href="https://github.com/jtmb/branconet-homelab"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-lg border border-zinc-700 hover:border-zinc-500 text-zinc-300 hover:text-zinc-100 transition-colors font-medium"
                >
                  <Github className="w-4 h-4" />
                  View on GitHub
                </a>
              </div>
            </div>

            {/* Right — screenshot */}
            <div className="hidden lg:block">
              <Screenshot src="/images/screenshots/deploy.webp" alt="Example optional Ansible runner view; container provisioning is disabled" priority />
            </div>
          </div>
        </div>
      </section>

      {/* ===== 3. What is Botrus? ===== */}
      <section className="py-20 border-t border-zinc-800/50">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-zinc-900 border border-zinc-800 text-zinc-400 text-sm font-medium mb-6">
            About the Project
          </div>
          <h2 className="text-3xl md:text-4xl font-bold text-zinc-100 mb-6">
            What is Botrus?
          </h2>
          <p className="text-lg text-zinc-400 leading-relaxed mb-8">
            Botrus is a Kubernetes cluster management platform designed for
            bare-metal homelab environments. Its dashboard uses externally supplied
            Kubernetes access, native Secrets, and FluxCD resource views. Cluster
            provisioning runs separately in an independent operator environment.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <span className="px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm font-medium">
              Native Secrets
            </span>
            <span className="px-3 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-sm font-medium">
              Operator Managed
            </span>
            <span className="px-3 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-sm font-medium">
              Built for Homelabs
            </span>
          </div>
        </div>
      </section>

      {/* ===== 4. Features — alternating rows ===== */}
      <section className="pb-20">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16 lg:space-y-24">
          {/* Gradient accent */}
          <div className="text-center mb-6">
            <div className="w-20 h-1 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full mx-auto mb-6" />
            <h2 className="text-3xl md:text-4xl font-bold text-zinc-100">
              Key Features
            </h2>
          </div>

          {/* Feature A — Independent Provisioning */}
          <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
            <div className="order-1 lg:order-1">
              <div className="w-14 h-14 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mb-5">
                <Play className="w-7 h-7 text-emerald-400" />
              </div>
              <h3 className="text-2xl font-bold text-zinc-100 mb-4">
                Independent Cluster Provisioning
              </h3>
              <p className="text-zinc-400 leading-relaxed mb-4">
                Provision and recover your cluster from an independent operator
                environment. Provisioning is disabled in the packaged dashboard; the
                optional local runner requires separately supplied Ansible and playbooks.
              </p>
              <ul className="space-y-2 text-sm text-zinc-400">
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400 mt-0.5">&#x2713;</span>
                  Keep bootstrap credentials available outside the target cluster
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400 mt-0.5">&#x2713;</span>
                  Optional local runs report playbook progress
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400 mt-0.5">&#x2713;</span>
                  Dashboard inventory records do not provision or join machines
                </li>
              </ul>
            </div>
            <div className="order-2 lg:order-2 flex justify-center">
              <Screenshot src="/images/screenshots/deploy.webp" alt="Example optional local provisioning view" />
            </div>
          </div>

          {/* Feature B — GitOps with FluxCD */}
          <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
            <div className="order-2 lg:order-1 flex justify-center">
              <Screenshot src="/images/screenshots/flux.webp" alt="FluxCD GitOps dashboard showing repository status" />
            </div>
            <div className="order-1 lg:order-2">
              <div className="w-14 h-14 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center mb-5">
                <GitBranch className="w-7 h-7 text-cyan-400" />
              </div>
              <h3 className="text-2xl font-bold text-zinc-100 mb-4">
                GitOps with FluxCD
              </h3>
              <p className="text-zinc-400 leading-relaxed mb-4">
                Inspect configured GitRepositories, Kustomizations, and HelmReleases.
                FluxCD reconciles resources owned by its configured sources when
                reconciliation is enabled. Credentials remain in native Kubernetes Secrets.
              </p>
              <ul className="space-y-2 text-sm text-zinc-400">
                <li className="flex items-start gap-2">
                  <span className="text-cyan-400 mt-0.5">&#x2713;</span>
                  View configured sources and Kustomization relationships
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-cyan-400 mt-0.5">&#x2713;</span>
                  Inspect readiness and suspended reconciliation status
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-cyan-400 mt-0.5">&#x2713;</span>
                  View hierarchy tree with live readiness status per resource
                </li>
              </ul>
            </div>
          </div>

          {/* Feature C — Cluster Dashboard */}
          <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
            <div className="order-1 lg:order-1">
              <div className="w-14 h-14 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mb-5">
                <LayoutDashboard className="w-7 h-7 text-indigo-400" />
              </div>
              <h3 className="text-2xl font-bold text-zinc-100 mb-4">
                Cluster Management Dashboard
              </h3>
              <p className="text-zinc-400 leading-relaxed mb-4">
                View nodes, pods, deployments, services, ingresses, and storage using
                externally supplied Kubernetes access. Cached snapshots show freshness
                and availability; actions depend on current permissions and runtime settings.
              </p>
              <ul className="space-y-2 text-sm text-zinc-400">
                <li className="flex items-start gap-2">
                  <span className="text-indigo-400 mt-0.5">&#x2713;</span>
                  Hierarchical tree view of configured FluxCD resources
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-indigo-400 mt-0.5">&#x2713;</span>
                  Pod logs and optional pod shell for authorized operators
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-indigo-400 mt-0.5">&#x2713;</span>
                  Longhorn distributed storage visibility with PVC/PV tracking
                </li>
              </ul>
            </div>
            <div className="order-2 lg:order-2 flex justify-center">
              <Screenshot src="/images/screenshots/dashboard.webp" alt="Cluster management dashboard overview" />
            </div>
          </div>

          {/* Feature D — Secrets Engine */}
          <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
            <div className="order-2 lg:order-1 flex justify-center">
              <Screenshot src="/images/screenshots/secrets.webp" alt="Native Kubernetes Secrets interface" />
            </div>
            <div className="order-1 lg:order-2">
              <div className="w-14 h-14 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center mb-5">
                <Key className="w-7 h-7 text-purple-400" />
              </div>
              <h3 className="text-2xl font-bold text-zinc-100 mb-4">
                Native Kubernetes Secrets
              </h3>
              <p className="text-zinc-400 leading-relaxed mb-4">
                Credentials are managed through a TLS-verified Kubernetes API client;
                nonsecret configuration stays in SQLite. Protect Secret storage with
                cluster-level encryption and access controls configured by your operator.
              </p>
              <ul className="space-y-2 text-sm text-zinc-400">
                <li className="flex items-start gap-2">
                  <span className="text-purple-400 mt-0.5">&#x2713;</span>
                  Explicit alias, namespace, Secret, and key mappings
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-purple-400 mt-0.5">&#x2713;</span>
                  Bearer-authenticated lookup for a separately supplied Ansible plugin
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-purple-400 mt-0.5">&#x2713;</span>
                  Explicit Ansible sync writes lookup references and inventory, not Secret values
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* ===== 5. Capabilities Bar ===== */}
      <section className="py-16 border-t border-zinc-800/50">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-8 md:p-10">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
              {[
                { icon: Key, value: "Native", label: "Kubernetes Secrets", color: "text-amber-400" },
                { icon: Users, value: "Scoped", label: "Access Controls", color: "text-indigo-400" },
                { icon: Box, value: "FluxCD", label: "Resource Status", color: "text-emerald-400" },
                { icon: Cpu, value: "External", label: "Cluster Provisioning", color: "text-cyan-400" },
              ].map((stat) => (
                <div key={stat.label} className="text-center">
                  <stat.icon className={`w-8 h-8 ${stat.color} mx-auto mb-3`} />
                  <div className="text-3xl font-bold text-zinc-100 mb-1">{stat.value}</div>
                  <div className="text-sm text-zinc-500">{stat.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ===== 6. Tech Stack ===== */}
      <section className="py-20 border-t border-zinc-800/50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <div className="w-20 h-1 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full mx-auto mb-6" />
          <h2 className="text-3xl md:text-4xl font-bold text-zinc-100 mb-12">
            Built With
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { icon: Globe, label: "Kubernetes", color: "text-blue-400" },
              { icon: GitBranch, label: "FluxCD", color: "text-cyan-400" },
              { icon: Play, label: "Ansible", color: "text-red-400" },
              { icon: HardDrive, label: "Longhorn", color: "text-emerald-400" },
              { icon: Globe, label: "Next.js 15", color: "text-zinc-300" },
              { icon: Terminal, label: "xterm.js", color: "text-emerald-400" },
              { icon: Database, label: "Prisma", color: "text-indigo-400" },
              { icon: LayoutDashboard, label: "Tailwind CSS", color: "text-cyan-400" },
            ].map((tech) => (
              <div
                key={tech.label}
                className="group flex flex-col items-center gap-3 p-5 rounded-xl bg-zinc-900/40 border border-zinc-800/50 hover:border-zinc-700 hover:bg-zinc-900/60 transition-all"
              >
                <tech.icon className={`w-8 h-8 ${tech.color}`} />
                <span className="text-sm font-medium text-zinc-400 group-hover:text-zinc-300 transition-colors">
                  {tech.label}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ===== 7. Bottom CTA ===== */}
      <section className="py-20 border-t border-zinc-800/50">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl md:text-4xl font-bold text-zinc-100 mb-4">
            Ready to get started?
          </h2>
          <p className="text-lg text-zinc-400 mb-8">
            Connect to your cluster, inspect resources, and manage your homelab configuration.
          </p>
          <div className="flex flex-wrap justify-center gap-4 mb-6">
            <button
              onClick={handleGetStarted}
              aria-busy={pendingRequests > 0}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-colors"
            >
              Get Started
              <ArrowRight className="w-4 h-4" />
            </button>
            <a
              href="https://github.com/jtmb/branconet-homelab"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg border border-zinc-700 hover:border-zinc-500 text-zinc-300 hover:text-zinc-100 transition-colors font-medium"
            >
              <Github className="w-4 h-4" />
              View on GitHub
            </a>
          </div>
          <p className="text-sm text-zinc-600">
            Built for bare-metal homelabs.
          </p>
        </div>
      </section>

      {/* ===== 8. Footer ===== */}
      <footer className="border-t border-zinc-800 py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-3 gap-8">
            {/* Col 1 — Project */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
                  <Activity className="w-5 h-5 text-white" />
                </div>
                <span className="font-bold text-zinc-100">Botrus K8s</span>
              </div>
              <p className="text-sm text-zinc-500 leading-relaxed">
                Kubernetes cluster management for bare-metal homelabs.
                Inspect resources, manage native Secrets, and view FluxCD status.
              </p>
            </div>

            {/* Col 2 — Links */}
            <div>
              <h4 className="text-sm font-semibold text-zinc-300 mb-3 uppercase tracking-wider">
                Links
              </h4>
              <ul className="space-y-2">
                <li>
                  <a
                    href="https://github.com/jtmb/branconet-homelab"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors inline-flex items-center gap-1.5"
                  >
                    <Github className="w-3.5 h-3.5" />
                    GitHub
                  </a>
                </li>
                <li>
                  <a
                    href="https://github.com/jtmb/branconet-homelab"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors inline-flex items-center gap-1.5"
                  >
                    <Shield className="w-3.5 h-3.5" />
                    Project Information
                  </a>
                </li>
              </ul>
            </div>

            {/* Col 3 — Community */}
            <div>
              <h4 className="text-sm font-semibold text-zinc-300 mb-3 uppercase tracking-wider">
                Community
              </h4>
              <p className="text-sm text-zinc-500 leading-relaxed">
                Built for the homelab community. Contributions, issues, and feature requests
                are welcome on GitHub.
              </p>
            </div>
          </div>

          <div className="mt-10 pt-6 border-t border-zinc-800/50 text-center text-xs text-zinc-600">
            &copy; {new Date().getFullYear()} Botrus Homelab.
          </div>
        </div>
      </footer>
    </div>
  );
}

/* ── Screenshot sub-component ── */
function Screenshot({ src, alt, priority }: { src: string; alt: string; priority?: boolean }) {
  return (
    <div className="w-full max-w-md rounded-xl border border-zinc-800 bg-zinc-900/80 overflow-hidden shadow-lg">
      <Image
        src={src}
        alt={alt}
        width={1280}
        height={720}
        className="w-full h-auto rounded-xl"
        priority={priority}
      />
    </div>
  );
}
