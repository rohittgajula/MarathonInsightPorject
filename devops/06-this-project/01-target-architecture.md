# Target architecture

What you are building toward. Keep this open while writing manifests.

## The picture

```
                        internet
                            │
                            ▼
              training.example.com  ──── DNS A record
                            │
                            ▼
                    ┌───────────────┐
                    │ VPS :80 :443  │   ufw + provider firewall
                    └───────┬───────┘
                            ▼
   ╔════════════════════ k3s cluster ═══════════════════════════════╗
   ║                                                                ║
   ║   ┌──────────────────────────────────────┐                     ║
   ║   │ ns: ingress-nginx                    │                     ║
   ║   │   ingress-nginx-controller           │◀── TLS terminates   ║
   ║   └───────────────┬──────────────────────┘                     ║
   ║                   │                                            ║
   ║   ┌───────────────┼────────────────────────────────────────┐   ║
   ║   │ ns: runproject│                                        │   ║
   ║   │               │                                        │   ║
   ║   │      ┌────────┴─────────┐                              │   ║
   ║   │  "/"  │                 │ "/api" "/admin" "/static"    │   ║
   ║   │      ▼                  ▼                              │   ║
   ║   │  ┌─────────┐      ┌──────────┐                         │   ║
   ║   │  │ frontend│      │ backend  │  Deployment ×2 → HPA    │   ║
   ║   │  │ Deploy×2│      │ gunicorn │                         │   ║
   ║   │  │  nginx  │      └────┬──┬──┘                         │   ║
   ║   │  └─────────┘           │  │                            │   ║
   ║   │                        │  └──────────────┐             │   ║
   ║   │  ┌──────────┐          │                 │             │   ║
   ║   │  │  worker  │──────────┤                 │             │   ║
   ║   │  │ Deploy×1 │          │                 │             │   ║
   ║   │  │ →KEDA×4  │          │                 │             │   ║
   ║   │  └────┬─────┘          │                 │             │   ║
   ║   │       │                │                 │             │   ║
   ║   │  ┌────┴─────┐          │                 │             │   ║
   ║   │  │   beat   │──────────┤                 │             │   ║
   ║   │  │ Deploy×1 │          │                 │             │   ║
   ║   │  │ NEVER >1 │          │                 │             │   ║
   ║   │  └──────────┘          ▼                 ▼             │   ║
   ║   │                  ┌──────────┐      ┌──────────┐        │   ║
   ║   │                  │  redis   │      │    db    │        │   ║
   ║   │                  │ Deploy×1 │      │StatefulSet│       │   ║
   ║   │                  │ no PVC   │      │  pgdata  │        │   ║
   ║   │                  └──────────┘      │   PVC    │        │   ║
   ║   │                                    └────┬─────┘        │   ║
   ║   │   PVCs: media (RWO)  garmin-tokens (RWO)│              │   ║
   ║   │          ▲     ▲          ▲             │              │   ║
   ║   │          │     │          │             │              │   ║
   ║   │       backend worker    backend/worker  │              │   ║
   ║   └─────────────────────────────────────────┼──────────────┘   ║
   ║                                             │                  ║
   ║   ┌─────────────────┐   ┌──────────────┐    │                  ║
   ║   │ ns: cert-manager│   │ns: monitoring│    │                  ║
   ║   │  ClusterIssuers │   │  Prometheus  │    │                  ║
   ║   └─────────────────┘   │  Grafana     │    │                  ║
   ║                         │  Loki        │    │                  ║
   ║                         └──────────────┘    │                  ║
   ║   CronJob: pg_dump ─────────────────────────┘                  ║
   ╚═══════════════════════════════╪════════════════════════════════╝
                                   ▼
                         object storage (R2/S3)   ← the only off-cluster copy
```

Outbound, from backend and worker: Garmin Connect, Anthropic/Gemini,
Open-Meteo, Nominatim.

## The full object list

Fifteen objects in `runproject`, plus cluster-scoped pieces. This is your
checklist.

| # | Object | Kind | Notes |
|---|---|---|---|
| 1 | `runproject` | Namespace | |
| 2 | `backend-config` | ConfigMap | Non-secret env |
| 3 | `backend-secrets` | Secret | Keys, DB URL. Sealed in git. |
| 4 | `media` | PVC | RWO. Shared by backend + worker. |
| 5 | `garmin-tokens` | PVC | RWO. Must be **writable** — tokens refresh. |
| 6 | `db` | StatefulSet | 1 replica, `volumeClaimTemplates`, `subPath` |
| 7 | `db` | Service | **Headless** (`clusterIP: None`) |
| 8 | `redis` | Deployment | 1 replica, no persistence |
| 9 | `redis` | Service | ClusterIP :6379 |
| 10 | `backend` | Deployment | 2 replicas, probes, both PVCs |
| 11 | `backend` | Service | ClusterIP :8000 |
| 12 | `worker` | Deployment | 1 replica, long grace period, **no Service** |
| 13 | `beat` | Deployment | 1 replica, `Recreate`, **no Service** |
| 14 | `frontend` | Deployment | 2 replicas |
| 15 | `frontend` | Service | ClusterIP :8080 |
| 16 | `runproject` | Ingress | 4 paths, TLS |
| 17 | `migrate-<sha>` | Job | Per deploy |
| 18 | `backend` | HPA | CPU 70%, 2–6 |
| 19 | `worker` | ScaledObject | Redis queue depth, 1–4 |
| 20 | `backend`, `frontend` | PDB | `minAvailable: 1` |
| 21 | `pg-backup` | CronJob | Daily, to object storage |

Cluster-scoped: ingress-nginx, cert-manager, two ClusterIssuers, metrics-server,
KEDA, and the CI ServiceAccount + Role + RoleBinding.

## The six workloads, decided

| Workload | Kind | Replicas | Service? | Strategy | Scaling |
|---|---|---|---|---|---|
| backend | Deployment | 2 | ✅ :8000 | RollingUpdate 0/1 | HPA CPU 2–6 |
| frontend | Deployment | 2 | ✅ :8080 | RollingUpdate 0/1 | HPA CPU 2–4 |
| worker | Deployment | 1 | ❌ | RollingUpdate 0/1 | KEDA queue 1–4 |
| beat | Deployment | 1 | ❌ | **Recreate** | **never** |
| db | StatefulSet | 1 | ✅ headless | — | **never** |
| redis | Deployment | 1 | ✅ :6379 | Recreate | **never** |

## Decisions, and why

**Same-origin `/api`.** `VITE_API_BASE=/api` at build time, ingress routes both
under one host. Deletes CORS, mixed content, cookie-domain questions, and the
build-time-config problem in one move. (`01-foundations/03`)

**Postgres in-cluster, backed up off-cluster.** Learning value, one user,
reconstructible data. The backup CronJob to object storage is non-negotiable —
local-path PVCs have no replication. (`03-kubernetes/05`)

**Redis unpersisted.** Everything in it is regenerable, and `sweep_unread` plus
beat already heal a lost queue by design. (`03-kubernetes/05`)

**Media on RWO, single node.** Works because there is one node. **Document that
this breaks on node #2.** Migration path is object storage via `django-storages`,
which is where a permanent `.fit` archive belongs anyway. (`03-kubernetes/05`)

**Garmin tokens on a writable PVC**, seeded once by `kubectl cp`. A Secret is
read-only and would break token refresh silently. (`03-kubernetes/04`)

**Migrations as a Job per deploy**, named by commit SHA, run before the rollout.
Not in the container command, not an initContainer.  (`03-kubernetes/06`)

**Beat pinned at 1 with `Recreate`.** Two schedulers double every periodic task,
including the hourly Garmin sync that `celery.py` says is rate-limited on
purpose. Comment this in the YAML. (`03-kubernetes/02`)

**Worker scales on queue depth, not CPU.** LLM calls are I/O-bound and invisible
to CPU-based HPA. (`05-autoscaling/02`)

## Code changes this requires

Not YAML. Actual edits to this repo, and they gate everything:

| # | Change | Why | Where |
|---|---|---|---|
| 1 | Fix two `tsc` errors | `npm run build` fails → no image, no CI | `02-containers/03` |
| 2 | Commit `package-lock.json`, use `npm ci` | Reproducible builds | `01-foundations/03` |
| 3 | `STATIC_ROOT` + whitenoise | Admin has no CSS at `DEBUG=0` | `02-containers/02` |
| 4 | `/api/health/`, **no auth**, no DB | Probes. DRF's default `IsAuthenticated` would 403 the kubelet. | `03-kubernetes/07` |
| 5 | `SECURE_PROXY_SSL_HEADER` | Behind a proxy; else redirect loops | `04-ingress-dns-tls/01` |
| 6 | Fail hard on default `SECRET_KEY` when `DEBUG=0` | Forgeable sessions | `01-foundations/03` |
| 7 | Prod Dockerfiles: gunicorn, nginx, non-root | Dev servers aren't production | `02-containers/02` |
| 8 | Measure the longest Celery task | Sets `terminationGracePeriodSeconds` | `03-kubernetes/07` |

Do 1–7 before writing any manifest. They're small, and every one of them is
something you'd otherwise discover at the worst moment.

## What this deliberately is not

- **No service mesh.** mTLS between six Pods on one node solves nothing here.
- **No multi-cluster, no HA control plane.** One node, honestly labelled.
- **No Postgres operator.** Write the StatefulSet first; understand what
  CloudNativePG would be doing for you.
- **No progressive delivery.** One user generates no statistically meaningful
  canary metrics.

Every one of these is a real technique worth knowing. None is warranted at this
scale, and being able to say why is worth more than having built it.
