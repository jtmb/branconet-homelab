# Front-End Architecture Plan: K8s Cluster Manager (Next.js 16)

## Overview

A Next.js 16 App Router application that provides a Rancher-like UI for provisioning and managing your Kubernetes cluster. The app will:

1. **Store & encrypt** Ansible variables in SQLite
2. **Execute** Ansible playbooks and stream output to an in-app terminal
3. **Manage** the cluster post-deployment (nodes, pods, services, etc.)

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Framework** | Next.js 16 (App Router) | Latest stable, server components, streaming |
| **Database** | SQLite (better-sqlite3 via Prisma) | Zero-config, single file, perfect for homelab |
| **Encryption** | AES-256-GCM via Node.js crypto | Military-grade encryption for stored secrets |
| **Ansible Integration** | `child_process.spawn()` with SSE streaming | Real-time terminal output |
| **Terminal UI** | xterm.js + @xterm/addon-fit | Authentic terminal experience in browser |
| **Cluster API Access** | @kubernetes/client-node | Official K8s JS client for cluster management |
| **UI Framework** | Tailwind CSS v4 + shadcn/ui | Beautiful dark-mode-first components |
| **State Management** | Zustand | Lightweight, no boilerplate |
| **Auth** | `next-auth` v5 with SSH key auth | Secure access to the management UI |

---

## Directory Structure

```
k8s-rewrite/front-end/
├── package.json
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── .env.local                          # Encryption key, app config
├── .gitignore
│
├── prisma/
│   └── schema.prisma                   # SQLite schema (vars, cluster state, job history)
│
├── src/
│   ├── app/
│   │   ├── layout.tsx                  # Root layout (dark theme wrapper)
│   │   ├── page.tsx                    # Dashboard / cluster overview
│   │   │
│   │   ├── vars/
│   │   │   └── page.tsx               # Vars tab - encrypted variable management
│   │   │
│   │   ├── deploy/
│   │   │   └── page.tsx               # Deploy tab - run Ansible + terminal
│   │   │
│   │   ├── cluster/
│   │   │   ├── page.tsx               # Cluster overview (nodes, pods, services)
│   │   │   ├── nodes/
│   │   │   │   └── page.tsx           # Node management
│   │   │   ├── workloads/
│   │   │   │   └── page.tsx           # Pods, deployments, stateful sets
│   │   │   └── storage/
│   │   │       └── page.tsx           # Longhorn volumes, PVCs
│   │   │
│   │   └── api/
│   │       ├── vars/
│   │       │   └── route.ts           # CRUD for encrypted variables
│   │       ├── deploy/
│   │       │   ├── start/route.ts     # Start Ansible playbook
│   │       │   └── stream/route.ts    # SSE stream for terminal output
│   │       ├── cluster/
│   │       │   ├── nodes/route.ts     # K8s node operations
│   │       │   ├── pods/route.ts      # Pod management
│   │       │   └── info/route.ts      # Cluster health/info
│   │       └── auth/
│   │           └── [...]/route.ts     # NextAuth v5 routes
│   │
│   ├── components/
│   │   ├── ui/                        # shadcn/ui components
│   │   ├── layout/
│   │   │   ├── sidebar.tsx            # Collapsible sidebar nav
│   │   │   ├── header.tsx             # Top header bar
│   │   │   └── terminal-panel.tsx     # Reusable terminal component
│   │   ├── vars/
│   │   │   ├── vars-table.tsx         # Editable vars grid
│   │   │   └── var-edit-dialog.tsx    # Modal for adding/editing vars
│   │   ├── deploy/
│   │   │   ├── playbook-selector.tsx  # Select which playbook to run
│   │   │   ├── inventory-editor.tsx   # Edit inventory.ini in-app
│   │   │   └── deploy-terminal.tsx    # Terminal wrapper for Ansible output
│   │   └── cluster/
│   │       ├── node-card.tsx          # Node overview card
│   │       ├── pod-list.tsx           # Pod list with filters
│   │       └── resource-chart.tsx     # CPU/Memory/Disk charts
│   │
│   ├── lib/
│   │   ├── ansible.ts                # Ansible runner (spawn ansible-playbook)
│   │   ├── encryption.ts             # AES-256-GCM encryption/decryption
│   │   ├── k8s-client.ts             # Kubernetes client wrapper
│   │   └── db.ts                     # Prisma/sqlite helpers
│   │
│   └── styles/
│       └── globals.css               # Tailwind + custom terminal styles
│
└── public/
    └── favicon.ico
```

---

## Feature Modules (Ordered by Implementation Priority)

### Phase 1: Foundation (Day 1-2)

#### 1.1 SQLite Schema (`prisma/schema.prisma`)

```prisma
model Variable {
  id        String   @id @default(cuid())
  key       String   @unique
  value     String                   // AES-256-GCM encrypted
  category  String                    // "kubernetes", "networking", "storage", etc.
  encrypted Boolean  @default(true)
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
}

model Node {
  id        String   @id @default(cuid())
  hostname  String   @unique
  ipAddress String
  role      String                    // "master", "worker"
  status    String   @default("pending") // "pending", "ready", "error"
  createdAt DateTime @default(now())
}

model Job {
  id         String   @id @default(cuid())
  playbook   String
  status     String   @default("running") // "running", "success", "failed"
  output     String   @default("")        // Full terminal output
  startedAt  DateTime @default(now())
  finishedAt DateTime?
}

model ClusterState {
  id          String   @id @default(cuid())
  kubeconfig  String                    // Encrypted kubeconfig for cluster access
  deployed    Boolean  @default(false)
  deployedAt  DateTime?
  updatedAt   DateTime @updatedAt
}
```

#### 1.2 Encryption Layer (`lib/encryption.ts`)

- AES-256-GCM using Node.js `crypto` module
- Encryption key stored in `.env.local` (`ENCRYPTION_KEY=...`)
- Functions: `encrypt(plaintext: string): string`, `decrypt(ciphertext: string): string`
- All sensitive values (API keys, kubeconfig, passwords) encrypted at rest in SQLite

#### 1.3 Dark-Mode UI Foundation

- Root layout with dark theme (`bg-zinc-950 text-zinc-100`)
- Glassmorphism cards (`bg-zinc-800/60 border border-zinc-700/40`)
- Sidebar navigation with icons
- Indigo accent color (`#6366f1`) for interactive elements
- Font: Geist Sans (Next.js default) for body, JetBrains Mono for terminal

### Phase 2: Vars Management (Day 2-3)

#### 2.1 Vars Tab (`src/app/vars/page.tsx`)

- **Grid view** of all Ansible variables, grouped by category
- Categories match `group_vars/all.yml` sections:
  - Kubernetes Version Settings
  - Cluster Networking
  - Node Configuration
  - Storage Settings
  - Container Runtime
  - Component Toggles
  - Longhorn Settings
  - Traefik Settings
- **Inline editing** with save button per row
- **Add/Delete** variables
- **Export** to `group_vars/all.yml` format (generates the YAML file)
- **Import** from existing `group_vars/all.yml` (parses the YAML)

#### 2.2 API Routes (`src/app/api/vars/route.ts`)

- `GET /api/vars` — list all variables (decrypt on read)
- `POST /api/vars` — create/update variable (encrypt on write)
- `DELETE /api/vars/[id]` — remove variable
- `POST /api/vars/export` — generate `all.yml` file for Ansible

### Phase 3: Ansible Deployment (Day 3-5)

#### 3.1 Ansible Runner (`lib/ansible.ts`)

```typescript
// Pseudo-API
export function runAnsiblePlaybook(playbook: string, inventory: string, vars: string) {
  // 1. Write vars to group_vars/all.yml
  // 2. Write inventory to inventory/production.ini
  // 3. Spawn: ansible-playbook playbooks/site.yml -i inventory/production.ini
  // 4. Return EventEmitter that emits 'data', 'error', 'close'
}
```

- Uses `child_process.spawn()` with `shell: false`
- Streams stdout/stderr line-by-line via EventEmitter
- Captures exit code and full output to `Job` model
- Handles ANSI color codes and escape sequences for terminal display

#### 3.2 Streaming Terminal (`src/app/deploy/page.tsx`)

- **xterm.js** terminal embedded in the page
- SSE endpoint `/api/deploy/stream` for real-time output
- Terminal auto-fits to container, scrolls with output
- Shows play-by-play Ansible output with color
- **Progress sidebar** showing each role's status (running/success/failed)
- **Stop button** to kill the Ansible process
- **Job history** — list of past deployments with status and re-run button

#### 3.3 Deploy API Routes

- `POST /api/deploy/start` — accepts `{ playbook: string, roles: string[] }`, starts the job, returns `{ jobId: string }`
- `GET /api/deploy/stream?jobId=xxx` — SSE stream of terminal output for a running job
- `POST /api/deploy/stop?jobId=xxx` — kill the running job
- `GET /api/deploy/history` — list past jobs

### Phase 4: Cluster Management (Day 5-7)

#### 4.1 K8s Client (`lib/k8s-client.ts`)

- Reads kubeconfig from SQLite (stored during deployment)
- Uses `@kubernetes/client-node` for all cluster operations
- Auto-detects if cluster is deployed (checks `ClusterState.deployed`)

#### 4.2 Dashboard Overview (`src/app/cluster/page.tsx`)

- **Cluster health** — status indicator (green/red/yellow)
- **Node count** — 3 nodes, how many ready
- **Pod count** — running/pending/failed
- **Resource usage** — CPU, memory, disk per node
- **Longhorn status** — volumes, replicas, health
- Auto-refresh every 10s

#### 4.3 Node Management (`src/app/cluster/nodes/page.tsx`)

- List all nodes with status, IP, CPU, memory
- Node details (labels, taints, conditions)
- Cordone/uncordone operations
- Drain node
- Delete node

#### 4.4 Workloads (`src/app/cluster/workloads/page.tsx`)

- Pod list with namespace filter
- Pod logs viewer (using xterm.js)
- Pod exec terminal (interactive shell into pod)
- Delete/restart pods
- Deployment/statefulset list with scale operations

#### 4.5 Storage (`src/app/cluster/storage/page.tsx`)

- Longhorn volume list with health status
- PVC list with status and capacity
- Create new PVCs
- Snapshot management

### Phase 5: Single Node Testing (Day 7-8)

#### 5.1 Test Server Configuration

- SSH to `45.79.160.12` using `~/.ssh/cardventory_deploy`
- Deploy a single-node cluster (master only, no workers)
- Test all playbook roles: bootstrap → kubernetes → network → dns → storage → ingress → gitops
- Verify cluster management features work with single node

---

## API Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/vars` | GET | List all variables |
| `/api/vars` | POST | Create/update variable |
| `/api/vars/[id]` | DELETE | Remove variable |
| `/api/vars/export` | POST | Export to all.yml |
| `/api/deploy/start` | POST | Start Ansible job |
| `/api/deploy/stream?jobId=xxx` | GET | SSE terminal stream |
| `/api/deploy/stop?jobId=xxx` | POST | Kill running job |
| `/api/deploy/history` | GET | Job history |
| `/api/cluster/nodes` | GET | List K8s nodes |
| `/api/cluster/pods` | GET | List pods |
| `/api/cluster/pods/[name]/logs` | GET | Pod logs stream |
| `/api/cluster/info` | GET | Cluster health/version |

---

## Design System (Dark Mode First)

| Element | Class |
|---------|-------|
| Page background | `bg-zinc-950` |
| Card | `bg-zinc-800/60 border border-zinc-700/40 rounded-xl` |
| Sidebar | `bg-zinc-900 border-r border-zinc-800 w-[260px]` |
| Text primary | `text-zinc-100` |
| Text secondary | `text-zinc-400` |
| Accent | `text-indigo-400 hover:text-indigo-300` |
| Button primary | `bg-indigo-600 hover:bg-indigo-500 text-white` |
| Terminal bg | `bg-zinc-950 border border-zinc-800` |
| Terminal text | `text-green-400 font-mono` |
| Success badge | `bg-emerald-500/20 text-emerald-400` |
| Error badge | `bg-red-500/20 text-red-400` |
| Warning badge | `bg-amber-500/20 text-amber-400` |

---

## Deployment

For single-node testing:
```bash
cd k8s-rewrite/front-end
npm run dev                          # Local dev server on :3000
```

The frontend will run on your local machine and SSH to `45.79.160.12` for the single-node cluster deployment.

---

## Implementation Timeline

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| **Phase 1: Foundation** | Day 1-2 | Next.js scaffold, SQLite schema, encryption lib, dark UI shell |
| **Phase 2: Vars Tab** | Day 2-3 | Encrypted CRUD, YAML export/import |
| **Phase 3: Ansible Deployment** | Day 3-5 | Runner, xterm.js streaming terminal, job history |
| **Phase 4: Cluster Management** | Day 5-7 | Dashboard, nodes, workloads, storage (Rancher-like) |
| **Phase 5: Single Node Testing** | Day 7-8 | Deploy on 45.79.160.12 with ~/.ssh/cardventory_deploy |

---

## Next Steps

Ready to begin implementation? Toggle to **ACT MODE** and I'll start scaffolding the project.