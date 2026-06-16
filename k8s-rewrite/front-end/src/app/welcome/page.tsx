"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
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
  Star,
  Terminal,
  Users,
} from "lucide-react";

export default function WelcomePage() {
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    setChecking(false);
  }, []);

  async function handleGetStarted() {
    try {
      const res = await fetch("/api/auth/session");
      const session = await res.json();

      if (session.authenticated) {
        router.push("/");
      } else if (!session.hasUsers) {
        router.push("/auth/register");
      } else {
        router.push("/auth/login");
      }
    } catch {
      router.push("/auth/login");
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
                <Star className="w-3.5 h-3.5" />
                Open Source
              </div>
              <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold text-zinc-100 leading-tight mb-6">
                Kubernetes Cluster
                <br />
                <span className="text-indigo-400">Management</span> Made Simple
              </h2>
              <p className="text-lg text-zinc-400 max-w-lg mb-8 leading-relaxed">
                Provision, configure, and manage your bare-metal Kubernetes cluster from a
                single dashboard. Built for homelabs — powerful enough for production.
              </p>
              <div className="flex flex-wrap gap-4">
                <button
                  onClick={handleGetStarted}
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

            {/* Right — terminal mockup */}
            <div className="hidden lg:block">
              <div className="rounded-xl border border-zinc-800 bg-zinc-900/80 overflow-hidden shadow-2xl shadow-indigo-500/5">
                {/* Title bar */}
                <div className="flex items-center gap-2 px-4 py-3 border-b border-zinc-800 bg-zinc-900">
                  <div className="w-3 h-3 rounded-full bg-red-500/70" />
                  <div className="w-3 h-3 rounded-full bg-amber-500/70" />
                  <div className="w-3 h-3 rounded-full bg-emerald-500/70" />
                  <span className="ml-3 text-xs text-zinc-500 font-mono">botrus — ansible-playbook</span>
                </div>
                {/* Terminal body */}
                <div className="p-5 font-mono text-sm leading-relaxed">
                  <div className="text-zinc-500 mb-1">
                    $ ansible-playbook site.yml -i production.ini
                  </div>
                  <div className="text-emerald-400 mb-1">
                    PLAY [Bootstrap cluster nodes] **********************
                  </div>
                  <div className="text-zinc-500 mb-1">
                    TASK [Install Kubernetes packages] ******************
                  </div>
                  <div className="text-amber-400 mb-1">
                    changed: [u1] &#x2502; kubeadm v1.30.0 installed
                  </div>
                  <div className="text-amber-400 mb-1">
                    changed: [u2] &#x2502; kubeadm v1.30.0 installed
                  </div>
                  <div className="text-amber-400 mb-1">
                    changed: [u3] &#x2502; kubeadm v1.30.0 installed
                  </div>
                  <div className="text-emerald-400 mb-1">
                    PLAY RECAP ******************************************
                  </div>
                  <div className="text-zinc-500 mb-1">
                    u1: ok=12 changed=5 failed=0
                  </div>
                  <div className="text-zinc-500">
                    u2: ok=12 changed=5 failed=0
                  </div>
                  <div className="flex items-center gap-1 mt-3 text-zinc-400">
                    <span>$</span>
                    <span className="w-2 h-4 bg-zinc-400 animate-pulse" />
                  </div>
                </div>
              </div>
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
            Botrus is an open-source Kubernetes cluster management platform designed for
            bare-metal homelab environments. It combines Ansible-powered provisioning,
            FluxCD-driven GitOps, and a purpose-built web dashboard into a single cohesive
            experience — no cloud dependencies, no vendor lock-in.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <span className="px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm font-medium">
              Open Source
            </span>
            <span className="px-3 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-sm font-medium">
              MIT Licensed
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

          {/* Feature A — Ansible Provisioning */}
          <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
            <div className="order-1 lg:order-1">
              <div className="w-14 h-14 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mb-5">
                <Play className="w-7 h-7 text-emerald-400" />
              </div>
              <h3 className="text-2xl font-bold text-zinc-100 mb-4">
                Ansible-Powered Provisioning
              </h3>
              <p className="text-zinc-400 leading-relaxed mb-4">
                Bring bare-metal machines to a fully operational Kubernetes cluster with a
                single playbook. The integrated Ansible runner streams live output to your
                dashboard — no SSH terminal needed.
              </p>
              <ul className="space-y-2 text-sm text-zinc-400">
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400 mt-0.5">&#x2713;</span>
                  Role-based playbook selection — run all or pick specific roles
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400 mt-0.5">&#x2713;</span>
                  Real-time xterm.js terminal with live streaming output
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400 mt-0.5">&#x2713;</span>
                  Bootstrap, networking, Kubernetes, storage, ingress, DNS — all automated
                </li>
              </ul>
            </div>
            <div className="order-2 lg:order-2 flex justify-center">
              <TerminalMockup lines={[
                "$ ansible-playbook site.yml",
                "PLAY [Bootstrap cluster nodes]",
                "TASK [Install containerd]",
                "changed: [u1]",
                "changed: [u2]",
                "changed: [u3]",
                "PLAY RECAP *** u1: ok=12 changed=5",
              ]} />
            </div>
          </div>

          {/* Feature B — GitOps with FluxCD */}
          <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
            <div className="order-2 lg:order-1 flex justify-center">
              <TerminalMockup lines={[
                "$ kubectl get kustomizations -A",
                "NAMESPACE    NAME          READY",
                "flux-system  test-stack    True",
                "flux-system  media-stack   True",
                "",
                "$ git push origin k8s-rewrite",
                "Flux detects change… applying…",
                "Kustomization reconciled ✓",
              ]} />
            </div>
            <div className="order-1 lg:order-2">
              <div className="w-14 h-14 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center mb-5">
                <GitBranch className="w-7 h-7 text-cyan-400" />
              </div>
              <h3 className="text-2xl font-bold text-zinc-100 mb-4">
                GitOps with FluxCD
              </h3>
              <p className="text-zinc-400 leading-relaxed mb-4">
                Every application and configuration lives in Git. FluxCD watches your
                repository and automatically reconciles the cluster — no manual kubectl
                apply needed.
              </p>
              <ul className="space-y-2 text-sm text-zinc-400">
                <li className="flex items-start gap-2">
                  <span className="text-cyan-400 mt-0.5">&#x2713;</span>
                  Organized into stack-based Kustomizations for clean separation
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-cyan-400 mt-0.5">&#x2713;</span>
                  Automatic drift detection — manual edits get reverted
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
                Monitor and manage every aspect of your cluster from a single interface.
                View nodes, pods, deployments, services, ingresses, and storage — all with
                live kubectl data.
              </p>
              <ul className="space-y-2 text-sm text-zinc-400">
                <li className="flex items-start gap-2">
                  <span className="text-indigo-400 mt-0.5">&#x2713;</span>
                  Hierarchical tree view of all FluxCD resources with expand/collapse
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-indigo-400 mt-0.5">&#x2713;</span>
                  Interactive pod shell and log viewer in the browser
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-indigo-400 mt-0.5">&#x2713;</span>
                  Longhorn distributed storage visibility with PVC/PV tracking
                </li>
              </ul>
            </div>
            <div className="order-2 lg:order-2 flex justify-center">
              <TerminalMockup lines={[
                "$ kubectl get nodes",
                "NAME  STATUS   ROLES           AGE",
                "u1    Ready    control-plane   14d",
                "u2    Ready    worker          14d",
                "u3    Ready    worker          14d",
                "",
                "$ kubectl get pods -A --no-headers | wc -l",
                "42",
              ]} />
            </div>
          </div>

          {/* Feature D — Secrets Engine */}
          <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
            <div className="order-2 lg:order-1 flex justify-center">
              <TerminalMockup lines={[
                "curl -H 'Authorization: Bearer ***'",
                "  /api/vars/lookup?key=k8s_version",
                "{",
                '  "key": "k8s_version",',
                '  "value": "v1.30.0"',
                "}",
                "",
                "# Values never touch the filesystem",
                "# AES-256-GCM encryption at rest",
              ]} />
            </div>
            <div className="order-1 lg:order-2">
              <div className="w-14 h-14 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center mb-5">
                <Key className="w-7 h-7 text-purple-400" />
              </div>
              <h3 className="text-2xl font-bold text-zinc-100 mb-4">
                Encrypted Secrets Engine
              </h3>
              <p className="text-zinc-400 leading-relaxed mb-4">
                All configuration variables and credentials are stored encrypted at rest. An
                Ansible lookup plugin resolves secrets at playbook runtime — values never
                touch the filesystem.
              </p>
              <ul className="space-y-2 text-sm text-zinc-400">
                <li className="flex items-start gap-2">
                  <span className="text-purple-400 mt-0.5">&#x2713;</span>
                  AES-256-GCM encryption for all sensitive data
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-purple-400 mt-0.5">&#x2713;</span>
                  Bearer-token authenticated lookup API for Ansible integration
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-purple-400 mt-0.5">&#x2713;</span>
                  Auto-sync to group_vars/all.yml and Ansible inventory
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* ===== 5. Stats Bar ===== */}
      <section className="py-16 border-t border-zinc-800/50">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-8 md:p-10">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
              {[
                { icon: Star, value: "125+", label: "GitHub Stars", color: "text-amber-400" },
                { icon: Users, value: "8", label: "Contributors", color: "text-indigo-400" },
                { icon: Box, value: "12+", label: "Deployments Managed", color: "text-emerald-400" },
                { icon: Cpu, value: "3", label: "Cluster Nodes", color: "text-cyan-400" },
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
            Provision your cluster, deploy your apps, and take control of your homelab.
          </p>
          <div className="flex flex-wrap justify-center gap-4 mb-6">
            <button
              onClick={handleGetStarted}
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
            Free and open source. MIT Licensed.
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
                Open-source Kubernetes cluster management for bare-metal homelabs.
                Provision, deploy, and manage — all from one dashboard.
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
                    href="https://github.com/jtmb/branconet-homelab/blob/k8s-rewrite/LICENSE"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors inline-flex items-center gap-1.5"
                  >
                    <Shield className="w-3.5 h-3.5" />
                    MIT License
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
            &copy; {new Date().getFullYear()} Botrus Homelab. MIT Licensed.
          </div>
        </div>
      </footer>
    </div>
  );
}

/* ── Terminal mockup sub-component ── */
function TerminalMockup({ lines }: { lines: string[] }) {
  return (
    <div className="w-full max-w-md rounded-xl border border-zinc-800 bg-zinc-900/80 overflow-hidden shadow-lg">
      {/* Title bar */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-zinc-800 bg-zinc-900">
        <div className="w-2.5 h-2.5 rounded-full bg-red-500/60" />
        <div className="w-2.5 h-2.5 rounded-full bg-amber-500/60" />
        <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/60" />
        <span className="ml-2 text-xs text-zinc-600 font-mono">terminal</span>
      </div>
      {/* Body */}
      <div className="p-4 font-mono text-xs leading-relaxed">
        {lines.map((line, i) => {
          const isCommand = line.startsWith("$");
          const isAccent = line.includes("PLAY") || line.includes("RECAP") || line.includes("✓");
          const isJson = line.trim().startsWith('"') || line.trim().startsWith("{") || line.trim().startsWith("}");
          const isComment = line.startsWith("#");
          return (
            <div
              key={i}
              className={`mb-0.5 ${
                isCommand
                  ? "text-zinc-500"
                  : isAccent
                  ? "text-emerald-400"
                  : isJson
                  ? "text-amber-300"
                  : isComment
                  ? "text-zinc-700"
                  : "text-zinc-600"
              }`}
            >
              {line || "\u00A0"}
            </div>
          );
        })}
        <div className="flex items-center gap-1 mt-2 text-zinc-500">
          <span>$</span>
          <span className="w-1.5 h-4 bg-zinc-500 animate-pulse" />
        </div>
      </div>
    </div>
  );
}