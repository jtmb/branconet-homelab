<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# Botrus K8s — AGENTS.md

> LLM-readable project overview for the Botrus Kubernetes management dashboard.

## ⚠️ CRITICAL: Update docs alongside code

**When you edit, create, or delete any source file, you MUST check every doc
in `docs/` and update anything that is now wrong.** Treat docs as part of the
feature — not an afterthought. If docs and code disagree, fix the docs. Code is
ground truth.

This means: after EVERY `replace_string_in_file`, `create_file`, or
`run_in_terminal` that changes behavior — re-read the affected doc(s) and apply
updates before marking the task complete. Never defer docs.

---

## Project Identity

| Key | Value |
|-----|-------|
| **App name** | Botrus K8s Manager |
| **Purpose** | Bare-metal homelab Kubernetes cluster provisioning & management dashboard |
| **Stack** | Next.js 15 (App Router), TypeScript, Prisma, SQLite, Tailwind CSS |
| **Runtime** | Node.js (Next.js dev server on port 4000) |
| **Repo** | `github.com/jtmb/branconet-homelab` — branch `k8s-rewrite` |
| **Front-end root** | `k8s-rewrite/front-end/` |

---

## Directory Map

```
front-end/
├── prisma/
│   └── schema.prisma          # DB schema — Variable, User, Node, Job, ClusterState, Deployment, GitRepo, AppSetting
├── src/
│   ├── app/
│   │   ├── layout.tsx          # Root layout: <html class="dark">, bg-zinc-950, font-sans
│   │   ├── globals.css         # Tailwind directives + CSS custom properties for dark zinc theme
│   │   ├── middleware.ts       # Auth gate — /api/cluster/info & /api/auth/* are public; everything else requires cookie
│   │   ├── (dashboard)/        # Protected pages (sidebar + topnav layout)
│   │   │   ├── layout.tsx      # ClusterLayout: flex row with ClusterSidebar + TopNav + {children}
│   │   │   ├── page.tsx        # / — cluster overview
│   │   │   ├── sidebar.tsx     # Collapsible nav: Nodes, Pods, Namespaces, Deployments, Services, Ingresses, Storage, Flux, Provisioning, Secrets, Users
│   │   │   ├── topnav.tsx      # Top bar: refresh cluster, settings gear, user dropdown (logout)
│   │   │   ├── nodes/          # /nodes — node list, detail
│   │   │   ├── pods/           # /pods — pod list, detail, logs, shell, YAML
│   │   │   ├── name-spaces/    # /name-spaces — namespace list, delete
│   │   │   ├── deployments/    # /deployments — deployment list, detail
│   │   │   ├── services/       # /services — service list, detail
│   │   │   ├── ingresses/      # /ingresses — ingress list, detail
│   │   │   ├── storage/        # /storage — PVC list, detail
│   │   │   ├── flux/           # /flux — GitRepositories & Kustomizations
│   │   │   ├── deploy/         # /deploy — Ansible provisioning runner
│   │   │   ├── secrets/        # /secrets — variable CRUD, sync, encryption
│   │   │   ├── settings/       # /settings — app settings, registration toggle, AppSetting CRUD
│   │   │   └── users/          # /users — user CRUD (write-only for mutations)
│   │   ├── api/
│   │   │   ├── auth/           # login, register, logout, session
│   │   │   ├── cluster/        # info, pods, nodes, deployments, services, ingresses, namespaces, volumes, refresh, remove
│   │   │   ├── deploy/         # start, stop, history, stream (SSE)
│   │   │   ├── flux/           # repos CRUD, sync
│   │   │   ├── nodes/          # node CRUD
│   │   │   ├── users/          # user CRUD (write-gated)
│   │   │   ├── vars/           # variable CRUD, lookup (Bearer auth), sync
│   │   │   └── settings/       # AppSetting CRUD
│   │   └── welcome/            # Unauthenticated landing → redirects to /auth/login
│   ├── components/
│   │   ├── ui/
│   │   │   └── sortable-header.tsx  # useSort() hook + SortIcon + SortHeader
│   │   ├── cluster/            # Cluster status cards
│   │   ├── deploy/             # Ansible output viewer, progress tracker
│   │   ├── layout/             # (empty — layout is in (dashboard)/layout.tsx)
│   │   └── vars/               # Variable form, category filter
│   └── lib/
│       ├── db.ts               # Prisma singleton (globalThis caching)
│       ├── auth.ts             # JWT sign/verify with jose, cookie helpers, getSession(), getSessionFromHeaders()
│       ├── auth-server.ts      # ensureJwtSecret() — auto-generates BOTRUS_JWT_SECRET if missing
│       ├── permissions.ts      # requireWrite() → 401/403 gate; getCurrentRole() → "readonly"|"write"|null
│       ├── k8s.ts              # kubectl wrapper (local or SSH), kubectlJSON(), kubectlExec()
│       ├── flux.ts             # Flux repo CRUD, bootstrap, delete with progress tracking
│       ├── ansible.ts          # runAnsiblePlaybook() — spawns ansible-playbook with SSE events
│       ├── cluster-cache.ts    # In-memory TTL cache for cluster data (kubectl → JSON)
│       ├── cluster-secrets.ts  # Encryption helpers for cluster secrets
│       ├── sync-vars.ts        # syncVarsToYAML(), syncNodesFromVars(), syncInventoryToFile()
│       └── active-jobs.ts      # Track running Ansible jobs in globalThis
├── lib/
│   ├── ansible.ts              # Re-export for import compatibility
│   └── encryption.ts           # encryptWithKey / decrypt (AES-256-GCM)
├── public/                     # Static assets
├── styles/                     # (Tailwind — styles are in globals.css)
├── package.json                # Dependencies & scripts
├── tsconfig.json               # TypeScript config — strict, ESNext modules, bundler resolution
├── tailwind.config.ts          # Dark zinc theme + indigo accent
├── postcss.config.js           # PostCSS with Tailwind plugin
└── next.config.ts              # Next.js config
```

---

## Documentation (`docs/` at repo root)

> **MANDATORY**: When you add a feature, change behavior, fix a bug, or rework architecture, you MUST check whether any doc in `docs/` needs updating — and if so, update it. Treat docs as part of the feature, not an afterthought.

All documentation lives at **`docs/`** in the repo root (`/home/brajam/repos/branconet-homelab/docs/`). These are the source of truth that AGENTS.md summarizes. An LLM should read the relevant doc before working on that domain, and update it when changes are made.

### Docs Inventory

| File | Covers | Update when… |
|------|--------|--------------|
| `TECH-STACK.md` | Every technology in the stack, versions, role in the project | Adding/removing a dependency, upgrading versions, changing architecture |
| `FLUX-GITOPS.md` | FluxCD setup: GitRepositories, Kustomizations, reconciliation, troubleshooting | Adding/removing GitRepos, changing Flux config, updating sync behavior |
| `SECRETS-ENGINE.md` | Variable storage, encryption, Ansible lookup plugin, sync-vars pipeline | Changing variable schema, encryption, lookup API, sync logic |
| `USER-PERMS.md` | Two-role system, auth flow, JWT/cookie details, middleware, write-gated endpoints | Changing roles, auth behavior, middleware paths, permissions model |
| `API-USAGE.md` | Every API endpoint with curl examples, auth requirements, response shapes | Adding/changing/removing any API route; updating auth gates |
| `BOTRUS-WORKFLOW.md` | End-to-end workflows: setup, provisioning, deploying apps, managing vars, cluster ops | Changing workflow steps, directory structures, deployment models |
| `CONNECTING-TO-A-CLUSTER.md` | How to connect: kubectl, SSH, dashboard; firewall ports, DNS, architecture diagram | Changing node IPs, network config, CNI, DNS, cluster topology |
| `kubectl-cheatsheet.md` | kubectl commands for common operations, namespaces, debugging | Adding/removing namespaces, changing common patterns, new kubectl tricks |
| `ANSIBLE-2-API-INTERACTION.md` | Ansible lookup plugin details, variable resolution at playbook runtime | Changing lookup plugin behavior, API contract, or variable resolution |

### Documentation Rules

1. **Before writing code** in a domain, read the relevant doc(s) — they are the spec.
2. **After making changes**, re-read affected docs and update anything that's now wrong: paths, names, versions, behaviors, commands, diagrams, IPs, examples.
3. **New feature?** If none of the existing docs cover it well, add a section to the most relevant doc. Only create a new doc file if it's a truly distinct domain.
4. **Ground truth**: When docs and code disagree, fix the docs. `kubectl` output, actual file paths, and running code are always correct — docs must match.
5. **Cross-link**: If a change affects multiple docs, update all of them. (e.g., adding a namespace touches `kubectl-cheatsheet.md`, `CONNECTING-TO-A-CLUSTER.md`, and possibly `BOTRUS-WORKFLOW.md`.)

---

## Key Libraries & Versions

| Package | Version | Purpose |
|---------|---------|---------|
| `next` | 15.0.0 | App Router framework |
| `react` / `react-dom` | ^18.3.0 | UI library |
| `typescript` | (via next) | Type checking |
| `prisma` / `@prisma/client` | ^6.0.0 | ORM + SQLite |
| `tailwindcss` | (via postcss) | Utility CSS |
| `jose` | ^6.2.3 | JWT signing & verification |
| `bcryptjs` | ^3.0.3 | Password hashing |
| `zod` | (via next) | Request validation |
| `lucide-react` | ^0.460.0 | Icon library |
| `@radix-ui/react-dialog` | ^1.1.0 | Accessible modal/dialog |
| `@radix-ui/react-dropdown-menu` | ^2.1.0 | Dropdown menu |
| `@radix-ui/react-separator` | ^1.1.0 | Visual divider |
| `@radix-ui/react-slot` | ^1.1.0 | Slot composition |
| `@xterm/addon-fit` | ^0.10.0 | Terminal fit addon |
| `clsx` | ^2.1.0 | Conditional classnames |
| `class-variance-authority` | ^0.7.0 | Variant class composition |
| `date-fns` | ^4.0.0 | Date formatting |

---

## Styling Conventions

### Theme: Dark Zinc + Indigo

- **Background**: `bg-zinc-950` (near-black)
- **Foreground**: `text-zinc-100` (near-white)
- **Cards/surfaces**: `bg-zinc-900/50` with `backdrop-blur-sm`
- **Borders**: `border-zinc-800` / `border-zinc-800/50`
- **Muted text**: `text-zinc-400`, `text-zinc-500`
- **Accent**: `text-indigo-400`, `bg-indigo-500/10`, ring `ring-indigo-500/20`
- **Destructive**: `text-red-400`, `hover:bg-red-500/10`
- **Success**: `text-emerald-400`
- **Warning**: `text-amber-400`

### Patterns

- Always `<html class="dark">` — no light mode
- Layout: `flex min-h-screen` with sticky sidebar + scrollable content
- Sidebar: `w-56` expanded, `w-14` collapsed, `transition-all duration-300`
- Top bar: `h-12`, sticky, `backdrop-blur-sm`
- Icon buttons: `w-8 h-8 rounded-lg` with `hover:bg-zinc-800/30`
- Inputs: `bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2`
- Tables: `w-full text-sm` with `border-b border-zinc-800` rows, `hover:bg-zinc-800/30`
- Cards: `bg-zinc-900/50 rounded-lg border border-zinc-800/50 p-4`

### Tailwind Custom Properties

All colors defined as HSL in `:root` / `.dark`:
- `--primary: 270 60% 50%` (indigo/purple)
- `--background: 240 10% 3.9%` (zinc-950)
- `--border: 240 3.7% 10%`
- `--destructive: 0 62.8% 50.2%`

---

## Common Functions & Imports

### Auth / Permissions (server-side)

```typescript
// Get the current session from cookies
import { getSession } from "@/lib/auth";
const session = await getSession(); // { id, username } | null

// Require write role — returns session or NextResponse(401/403)
import { requireWrite } from "@/lib/permissions";
const auth = await requireWrite();
if (auth instanceof NextResponse) return auth; // 401 or 403

// Get role without enforcing (for UI conditionals)
import { getCurrentRole } from "@/lib/permissions";
const role = await getCurrentRole(); // "write" | "readonly" | null
```

### Kubernetes (server-side)

```typescript
// Run kubectl and parse JSON output
import { kubectlJSON } from "@/lib/k8s";
const pods = await kubectlJSON<PodList>("get pods -A -o json");

// Run kubectl and return raw text
import { kubectlExec } from "@/lib/k8s";
const logs = await kubectlExec("logs my-pod -n default --tail=100");

// Get cached cluster data
import { getCachedClusterData, invalidateCache } from "@/lib/cluster-cache";
const data = await getCachedClusterData(); // cached for 30s TTL
```

### Database (server-side)

```typescript
import prisma from "@/lib/db";

// Variables (secrets engine)
await prisma.variable.findMany({ where: { category: "kubernetes" } });
await prisma.variable.findUnique({ where: { key: "k8s_version" } });

// Users
await prisma.user.findUnique({ where: { id: session.id }, select: { role: true } });
await prisma.user.create({ data: { username, passwordHash, role: "readonly" } });

// Cluster state
await prisma.clusterState.findFirst({ where: { deployed: true } });

// Jobs (Ansible playbook runs)
await prisma.job.create({ data: { playbook: "site.yml", status: "running" } });
await prisma.job.update({ where: { id }, data: { status: "success", finishedAt: new Date() } });
```

### Sorting (client-side)

```typescript
import { useSort, SortIcon, SortHeader } from "@/components/ui/sortable-header";

const { sortKey, sortDir, toggle } = useSort("name");
// toggle("status") — sets sortKey, toggles dir on repeat click
// <SortHeader label="Name" active={sortKey==="name"} dir={sortDir} onClick={() => toggle("name")} />
```

---

## API Route Patterns

### Route Handler Signature (Next.js 15 App Router)

```typescript
// All params are Promises
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params; // MUST await
  // ...
}
```

### Auth Gate Pattern (write endpoints)

```typescript
import { requireWrite } from "@/lib/permissions";
import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth; // short-circuit on 401/403

  // auth.id, auth.username available
}
```

### Zod Validation Pattern

```typescript
import { z } from "zod";

const schema = z.object({
  username: z.string().min(3).max(30),
  role: z.enum(["readonly", "write"]).optional(),
});

const parsed = schema.safeParse(await request.json());
if (!parsed.success) {
  return NextResponse.json({ error: parsed.error.issues[0]?.message }, { status: 400 });
}
```

### Response Patterns

```typescript
// Success
return NextResponse.json({ id: "123", username: "admin" });
return NextResponse.json({ id: "123" }, { status: 201 });

// Errors
return NextResponse.json({ error: "Not found" }, { status: 404 });
return NextResponse.json({ error: "Forbidden" }, { status: 403 });
```

---

## Auth Flow Summary

1. **Login**: `POST /api/auth/login` → bcrypt verify → sign JWT (HS256, 7d) → set HttpOnly cookie `botrus_auth_token`
2. **Middleware** (`middleware.ts`): Every request passes through. Public paths: `/welcome`, `/auth/*`, `/api/auth/*`, `/api/cluster/info`, `/_next/*`. Everything else requires the cookie.
3. **API authorization**: `requireWrite()` looks up `User.role` from DB on every call (role is NOT in the JWT — always fresh from DB)
4. **Client session**: `GET /api/auth/session` returns `{ authenticated, username, role, hasUsers, registrationOpen }`

---

## Two-Role System

| Role | Can |
|------|-----|
| `write` | Everything — view, create, edit, delete, deploy, sync, manage users |
| `readonly` | View only — dashboards, lists, details. No mutations. |

- First registered user gets `write` automatically
- Subsequent users get `readonly` by default
- A `write` user can promote others at `/users`
- Cannot demote/delete the last `write` user (prevents lockout)

---

## Database Schema (Prisma)

```
Variable   (id, key@unique, value, category, encrypted, createdAt, updatedAt)
User       (id, username@unique, passwordHash, role="readonly", createdAt)
Node       (id, name, hostname@unique, ipAddress, role="master", status="pending", cpu?, memory?, createdAt)
Job        (id, playbook, status="running", output="", startedAt, finishedAt?)
ClusterState (id, kubeconfig, deployed=false, deployedAt?, updatedAt)
Deployment (id, name@unique, namespace, replicas, image, ports?json, env?json, volumes?json, createdAt, updatedAt)
GitRepo    (id, name@unique, url, branch, path, namespace="flux-system", status="unknown", createdAt, updatedAt)
AppSetting (id, key@unique, value, createdAt)
```

---

## Scripts (from package.json)

```bash
npm run dev           # next dev -p 4000
npm run build         # prisma generate && next build
npm run start         # next start
npm run lint          # next lint
npm run db:generate   # prisma generate
npm run db:migrate    # prisma migrate dev
npm run db:studio     # prisma studio
```

---

## Filesystem Conventions

- All source under `src/` with `@/*` alias → `./src/*`
- API routes: `src/app/api/<resource>/route.ts` (list/create) + `src/app/api/<resource>/[id]/route.ts` (get/update/delete)
- Pages: `src/app/(dashboard)/<resource>/page.tsx`
- Components: `src/components/<group>/<name>.tsx`
- Library: `src/lib/<name>.ts` — server-only (Node.js APIs, Prisma, child_process)

---

## Edge Cases & Gotchas

- **JWT secret**: Auto-generated on first startup via `ensureJwtSecret()`. Stored in `.env.local`. If it changes, all cookies invalidate → re-login required.
- **Params are Promises**: In Next.js 15 App Router, `params` in route handlers is `Promise<{ id: string }>` — must `await` before use.
- **Prisma singleton**: Uses `globalThis` pattern to avoid multiple instances in dev HMR.
- **Kubernetes access**: Falls back from local `kubectl` (if `~/.kube/config` exists) to SSH+sudo on master node. Reads `ansible_become_password` from DB for sudo.
- **Sortable headers**: `useSort<K>` uses `string` internally to avoid TypeScript literal type narrowing — call `toggle(key: string)` with any string, not a literal.
- **Delete progress**: Flux repo deletes track progress in `globalThis.__deleteProgress` Map — survives HMR but not server restarts.
- **Cache TTL**: Cluster data cached 30s in `globalThis.__clusterCache`. Stale reads are fine — cache busts on write.
