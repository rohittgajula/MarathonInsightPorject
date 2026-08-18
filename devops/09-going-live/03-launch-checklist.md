# Launch checklist

Everything, in order. Tick as you go.

## Phase 0 — code (before any Kubernetes)

- [ ] `npm run build` exits 0 (fix `MetricOverlay.tsx:51`, `Home.tsx:13`)
- [ ] `package-lock.json` committed; Dockerfile uses `npm ci`
- [ ] `STATIC_ROOT` + whitenoise; `collectstatic` works
- [ ] `/api/health/` exists, returns 200, **no auth**, touches no DB
- [ ] `SECURE_PROXY_SSL_HEADER` set
- [ ] `SECRET_KEY` fatal when defaulted at `DEBUG=0`
- [ ] Django security settings added; `check --deploy` clean
- [ ] Dev password from `CONTEXT.md` changed
- [ ] Longest Celery task **measured** (sets the grace period)
- [ ] 46 tests still pass

## Phase 1 — production images

- [ ] Backend: `base`/`dev`/`prod` stages, gunicorn, non-root, collectstatic
- [ ] Frontend: multi-stage → nginx, port 8080, non-root, under 100 MB
- [ ] nginx does SPA fallback (`/activities/42` on refresh → 200)
- [ ] Cache headers: hashed assets long, `index.html` no-cache
- [ ] `/healthz` on the frontend
- [ ] `.dockerignore` files in both
- [ ] Both build from cold with `--no-cache`
- [ ] `docker-compose.prod.yml` runs the whole stack, **no source bind mounts**
- [ ] `/admin` has CSS at `DEBUG=0`

## Phase 2 — local Kubernetes

- [ ] kind cluster with `ingress-ready` label and `extraPortMappings`
- [ ] ingress-nginx (kind variant), cert-manager, metrics-server, KEDA
- [ ] Namespace, ConfigMap, Secret
- [ ] Both PVCs Bound
- [ ] Postgres StatefulSet — **`subPath`**, headless Service, Guaranteed QoS
- [ ] Data survives `kubectl delete pod db-0`
- [ ] Redis Deployment + Service
- [ ] Migration Job, SHA-named, completes
- [ ] backend ×2 — probes, resources, both PVCs, `fsGroup`
- [ ] worker — no Service, long grace period
- [ ] **beat — `replicas: 1`, `Recreate`, both commented**
- [ ] frontend ×2
- [ ] `kubectl get endpoints` populated for backend and frontend, absent for
      worker and beat
- [ ] Ingress, 4 paths, self-signed TLS
- [ ] `https://training.local` works end to end
- [ ] HPA — **observed** scaling under load and back
- [ ] KEDA scaling the worker on real queue depth
- [ ] PDBs on backend and frontend
- [ ] Nothing runs as root; no SA tokens mounted
- [ ] `kind delete cluster` then rebuild from manifests in under 15 min

## Phase 3 — CI/CD

- [ ] `ci.yml` — lint, tests, both images build, on every push and PR
- [ ] Build cache configured (`type=gha`); full run under 10 min
- [ ] Images pushed to ghcr.io, tagged with the commit SHA
- [ ] `imagePullSecret` works for the private registry
- [ ] CI ServiceAccount + Role — **not cluster-admin**
- [ ] `kubectl auth can-i --list` verified for that SA
- [ ] Deploy workflow: migrate Job → wait → apply → **`rollout status`** → smoke test
- [ ] `if: failure()` step dumping Pod state and logs
- [ ] `concurrency` set; deploys never cancel mid-flight
- [ ] GitHub Environments with a required reviewer on production
- [ ] Sealed Secrets installed; **private key backed up off-cluster**
- [ ] A deliberate rollback tested: `kubectl rollout undo`

## Phase 4 — the VPS

- [ ] VPS provisioned; **architecture matches your images**
- [ ] Non-root user, key-only SSH, root login disabled
- [ ] ufw: 22, 80, 443. 6443 **closed**.
- [ ] Provider firewall also open on 80/443
- [ ] Swap enabled
- [ ] fail2ban, unattended-upgrades
- [ ] k3s installed with `--disable traefik`
- [ ] kubeconfig on your Mac via SSH tunnel
- [ ] ingress-nginx (generic manifest), cert-manager, metrics-server, KEDA
- [ ] `EXTERNAL-IP` on the ingress Service is the VPS IP
- [ ] Two ClusterIssuers: staging **and** prod

## Phase 5 — DNS and TLS

- [ ] Confirmed which nameservers are authoritative (`dig NS`)
- [ ] TTL lowered to 300 **before** any change
- [ ] A record `training` → VPS IP (and AAAA if IPv6)
- [ ] `dig @1.1.1.1 training.example.com` correct
- [ ] `curl http://training.example.com/` reaches nginx
- [ ] `DJANGO_ALLOWED_HOSTS` includes the real hostname
- [ ] **Staging** cert issues first
- [ ] Switched to prod issuer, old Secret deleted
- [ ] `https://` with a trusted cert; issuer is not "STAGING"
- [ ] TTL raised back to 3600
- [ ] CAA record (optional)

## Phase 6 — go live

- [ ] `kubectl apply -k overlays/prod`; all Pods Ready
- [ ] Migration Job completed
- [ ] **Garmin tokens seeded via `kubectl cp`** ← the step you will forget
- [ ] Superuser created, strong password
- [ ] Log in, load the dashboard, check the week table renders
- [ ] Post a daily log; confirm the LLM extraction runs
- [ ] Trigger a Garmin sync; confirm it succeeds
- [ ] Upload a `.fit` file (tests `proxy-body-size`)
- [ ] `/admin` has CSS
- [ ] Deep link survives a refresh
- [ ] `curl -s https://training.example.com/nope | grep -ci traceback` → 0
- [ ] Beat logs its three scheduled entries — **once each**

## Phase 7 — operations

- [ ] kube-prometheus-stack installed
- [ ] Loki + promtail
- [ ] Alerts: CrashLoop, 5xx rate, latency, **no backup in 36h**, cert < 14d,
      PVC > 85%, no Garmin sync in 6h
- [ ] Alert routing tested — **send yourself a real one**
- [ ] Backup CronJob to off-cluster object storage
- [ ] **Restore drill completed and timed**
- [ ] Retention lifecycle rules set
- [ ] Backup credentials write-only; bucket versioned
- [ ] Full VPS-loss runbook written, including token re-seeding
- [ ] Admin IP-restricted or unexposed
- [ ] Trivy in CI; Dependabot on
- [ ] NetworkPolicies (with a CNI that enforces them)
- [ ] Pod Security `restricted`
- [ ] Secrets encrypted at rest

## Day-one verification

The morning after, before you trust it:

```bash
kubectl get pods -n runproject-prod          # no restarts overnight
kubectl top pods -n runproject-prod          # usage vs requests sane
kubectl get certificate -A                   # Ready, expiry ~89 days
kubectl get cronjob -n runproject-prod       # backup ran
kubectl logs -n runproject-prod deploy/beat --tail=50   # tasks fired once each
kubectl get hpa -n runproject-prod           # not <unknown>
curl -fsS https://training.example.com/api/health/
```

Then check the app itself: did the hourly Garmin sync run? Did overnight logs
get read by the LLM? Those are the two things that fail silently.

## Known trade-offs — write these down

Not problems. Decisions, with reasons, so future-you doesn't rediscover them
as bugs.

| Decision | Because | Revisit when |
|---|---|---|
| Single node | One user, cost, RWO media volume | You add a node, or need HA |
| Postgres in-cluster | Learning; data reconstructible | Data becomes irreplaceable |
| local-path storage, no replication | Backups are off-cluster | Disk fills, or you add a node |
| Media on RWO PVC | Single node makes it safe | Second node → move to S3/R2 |
| Redis unpersisted | Queue is regenerable by design | Anything unrecoverable enters Redis |
| Garmin tokens on a PVC | Secrets are read-only; tokens refresh | Real multi-tenancy → move to the DB |
| No service mesh | Six Pods, one node | Multi-node with sensitive inter-service traffic |
| Push-based deploys | Simpler to learn | Exposing 6443 to CI feels wrong → Argo CD |
| Gemini free tier in dev | Free; test data only | Any real health data in dev |
| `beat` at 1 replica | Correctness, not tuning | Never. This one is permanent. |
