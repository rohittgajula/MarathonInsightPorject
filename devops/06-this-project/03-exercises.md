# The lab series

You write every manifest. No answer YAML here — specs, constraints, self-checks,
and the mistakes to expect.

**Your references while writing:**
- `03-kubernetes/02` has the one fully-worked Deployment. Pattern off it.
- `kubectl explain <kind>.<path>` is offline API documentation. Use it constantly.
- `reference/yaml-gotchas.md` for the syntax traps.
- `reference/troubleshooting-tree.md` when something won't start.

Prerequisite: **Lab 0** (`02-containers/03`) complete. Production images exist
and run.

Suggested layout:
```
k8s/
├── base/          # every manifest, environment-agnostic
└── overlays/
    ├── dev/
    └── prod/
```
Write everything raw in `base/` first. Restructure into overlays at Lab 9, when
the duplication actually annoys you.

---

## Lab 1 — cluster and namespace

**Task.** kind cluster with ingress support, plus your namespace.

The kind config **must** include the `ingress-ready=true` node label and
`extraPortMappings` for 80 and 443 — **these cannot be added later without
recreating the cluster.** `04-ingress-dns-tls/01` has the config.

Then:
- Namespace `runproject`
- A `LimitRange` with default requests/limits
- Set it as your current context's default namespace

**Self-check**
```bash
kubectl get nodes
kubectl get ns runproject
kubectl config view --minify | grep namespace
docker ps | grep kind          # the node IS a container
```

That last one is worth a moment. Your "cluster node" is a Docker container on
your Mac. `docker exec -it <kind-node> bash` puts you *on the node*, where
`crictl ps` lists the real containers. Demystifying.

---

## Lab 2 — config and secrets

**Task.** ConfigMap `backend-config`, Secret `backend-secrets`.

Split per `02-compose-to-k8s-map.md`. Requirements:

| # | Constraint |
|---|---|
| 1 | Generate a real `DJANGO_SECRET_KEY` — never the compose default |
| 2 | Generate a Postgres password; use it in **both** `POSTGRES_PASSWORD` and `DATABASE_URL` |
| 3 | `DJANGO_DEBUG=0` |
| 4 | `DJANGO_ALLOWED_HOSTS=training.local` for dev |
| 5 | The Secret manifest is **not committed** — write it as a script, or use `kubectl create secret` |

**Watch for**
- `stringData:` takes plain text; `data:` needs base64. Mixing them up gives you
  a double-encoded password and an auth failure you'll debug for an hour.
- `echo "x" | base64` includes a trailing newline. Use `printf` or `base64 -w0`.
  A newline in a password is invisible and fatal.

**Self-check**
```bash
kubectl get cm backend-config -o yaml
kubectl get secret backend-secrets -o jsonpath='{.data.DJANGO_SECRET_KEY}' | base64 -d; echo
```
The decoded value is exactly what you generated. No trailing newline.

---

## Lab 3 — storage

**Task.** Two PVCs: `media` (2Gi) and `garmin-tokens` (100Mi).

**Watch for**
- Omit `storageClassName` to use the default. Naming one that doesn't exist
  leaves the PVC `Pending` forever with a helpful message in `describe`.
- kind's local-path provisioner uses `WaitForFirstConsumer` — the PVC stays
  `Pending` until a Pod mounts it. **This is correct, not broken.** It's the
  most common false alarm at this stage.

**Self-check**
```bash
kubectl get pvc -n runproject
kubectl describe pvc media -n runproject
```

---

## Lab 4 — datastores

**Task.** Postgres StatefulSet + headless Service; Redis Deployment + Service.

**Postgres requirements**

| # | Constraint |
|---|---|
| 1 | StatefulSet, `serviceName: db`, 1 replica |
| 2 | `volumeClaimTemplates`, 10Gi, RWO — not a `volumes:` entry |
| 3 | **`subPath: postgres`** on the data mount |
| 4 | Env from the Secret |
| 5 | `readinessProbe: exec pg_isready -U runproject` |
| 6 | requests == limits (**Guaranteed** QoS) |
| 7 | `terminationGracePeriodSeconds: 60` |
| 8 | Headless Service: `clusterIP: None` |

**#3 is the one that will bite you.** Without `subPath`, initdb finds
`lost+found` and refuses: `directory "/var/lib/postgresql/data" exists but is
not empty`. CrashLoopBackOff, clear message once you read the logs.

**Redis:** Deployment, 1 replica, no PVC, `exec redis-cli ping`, ClusterIP 6379.

**Self-check**
```bash
kubectl get statefulset,pod,pvc -n runproject
kubectl exec -it db-0 -n runproject -- psql -U runproject -c '\l'
kubectl exec -it deploy/redis -n runproject -- redis-cli ping
kubectl get pod db-0 -n runproject -o jsonpath='{.status.qosClass}'   # Guaranteed
```

Then prove persistence — this is the point of a StatefulSet:
```bash
kubectl exec -it db-0 -n runproject -- psql -U runproject -c 'CREATE TABLE probe(id int);'
kubectl delete pod db-0 -n runproject
# wait for it to come back
kubectl exec -it db-0 -n runproject -- psql -U runproject -c '\dt'
```
`probe` is still there. If it isn't, your volume isn't persisting and you'd have
found out much later, with real data.

---

## Lab 5 — migrations

**Task.** A Job that runs `manage.py migrate`.

| # | Constraint |
|---|---|
| 1 | Same image as the backend |
| 2 | `envFrom` the same ConfigMap and Secret |
| 3 | `restartPolicy: Never`, `backoffLimit: 1` |
| 4 | `ttlSecondsAfterFinished: 300` |
| 5 | Name includes the image tag: `migrate-<sha>` |
| 6 | An initContainer that waits for Postgres |

**On #5:** Job specs are largely immutable. Reusing one name across deploys
fails with `field is immutable`. SHA-naming also makes re-deploys idempotent.

**Self-check**
```bash
kubectl apply -f k8s/base/migrate-job.yaml
kubectl wait --for=condition=complete job/migrate-<sha> -n runproject --timeout=300s
kubectl logs job/migrate-<sha> -n runproject
kubectl exec -it db-0 -n runproject -- psql -U runproject -c '\dt'
```
Django's tables exist, and the log shows your `journal` and `athletes`
migrations applying.

---

## Lab 6 — the application workloads

The big one. Four Deployments, two Services.

### 6a — backend

Pattern off `03-kubernetes/02`. Requirements beyond that file:

| # | Constraint |
|---|---|
| 1 | 2 replicas |
| 2 | `envFrom` ConfigMap + Secret |
| 3 | Mounts `media` at `/data/media`, `garmin-tokens` at `/data/garmin_tokens` |
| 4 | startup + readiness + liveness on `/api/health/` |
| 5 | requests and memory limits set |
| 6 | `securityContext`: non-root, uid 10001, `fsGroup: 10001` |
| 7 | `automountServiceAccountToken: false` |
| 8 | `preStop` sleep 5, grace period 30 |
| 9 | Service, ClusterIP 8000, `targetPort` by **name** |

**`/api/health/` must exist and must not require auth.** Your DRF default is
`IsAuthenticated`; a DRF view there returns 403, every Pod stays unready, and
the rollout hangs with no obvious cause. Use a plain Django view.

**`fsGroup` matters.** Without it, a uid-10001 process cannot write to a PVC
owned by root, and you get permission errors at runtime rather than at deploy.

### 6b — worker

Same image, `command: ["celery","-A","config","worker","-l","info"]`.

- **No Service.**
- `terminationGracePeriodSeconds` from your measured longest task — not a guess.
  If you haven't measured it, measure it now.
- Same volumes and env as backend.
- No probes, with a comment saying why (nothing routes traffic to it).

### 6c — beat

`command: ["celery","-A","config","beat","-l","info","--scheduler","django_celery_beat.schedulers:DatabaseScheduler"]`

- **`replicas: 1`, `strategy: Recreate`** — both with comments explaining that
  two beats double every periodic task, including a rate-limited Garmin sync.
- No Service.

### 6d — frontend

- 2 replicas, port 8080
- `httpGet /healthz`
- No env — the API base is baked in
- Tiny resources (nginx serving static)

**Self-check**
```bash
kubectl get pods -n runproject
kubectl get endpoints -n runproject
kubectl port-forward svc/backend 8000:8000 -n runproject &
curl localhost:8000/api/health/
kubectl port-forward svc/frontend 8080:8080 -n runproject &
open http://localhost:8080
kubectl logs deploy/worker -n runproject | head -30
kubectl logs deploy/beat -n runproject | head -30
```

Worker logs list registered tasks including `apps.journal.tasks.sweep_unread`.
Beat logs its three scheduled entries. `endpoints` shows 2 IPs each for backend
and frontend, and **no** endpoints object for worker or beat.

**If `ENDPOINTS` is empty:** selector mismatch or readiness failing. That one
symptom covers most failures at this stage — see `03-kubernetes/03`.

---

## Lab 7 — ingress and local TLS

**Task.** One Ingress, four paths, self-signed TLS on `training.local`.

| # | Constraint |
|---|---|
| 1 | `ingressClassName: nginx` |
| 2 | `/api`, `/admin`, `/static` → backend; `/` → frontend |
| 3 | `pathType: Prefix` throughout |
| 4 | `proxy-body-size: 50m` for `.fit` uploads |
| 5 | TLS via a `selfSigned` ClusterIssuer |
| 6 | `training.local` in `/etc/hosts` |

Also add to the ConfigMap: `DJANGO_ALLOWED_HOSTS=training.local`, and to
`settings.py`: `SECURE_PROXY_SSL_HEADER`.

**Self-check**
```bash
kubectl get ingress -n runproject          # ADDRESS populated
curl -k https://training.local/api/health/
curl -k https://training.local/activities/42    # SPA fallback → 200
open https://training.local
```
The app loads, the API answers, `/admin` has CSS, and a deep link survives a
refresh.

**Then break it on purpose.** Change a path to `/apiz` and watch the 404. Scale
backend to 0 and watch the 503. Knowing what each failure *looks like* is the
skill.

---

## Lab 8 — scaling

**Task.** metrics-server, HPA, KEDA, PDBs.

- metrics-server (kind needs `--kubelet-insecure-tls`)
- HPA on backend: CPU 70%, 2–6, with a `behavior` block (up fast, down slow)
- KEDA + `ScaledObject` on worker: Redis `celery` list, 1–4
- PDB `minAvailable: 1` on backend and frontend

**Verify the queue name first** — don't trust it:
```bash
kubectl exec -n runproject deploy/redis -- redis-cli keys '*'
```

**Self-check — and actually do the load test.** YAML you've never seen work is
not done.
```bash
kubectl get hpa -n runproject          # must not show <unknown>/70%
kubectl top pods -n runproject

kubectl run -it --rm load --image=williamyeh/hey --restart=Never -- \
  -z 120s -c 50 http://backend.runproject.svc.cluster.local:8000/api/health/
```
In another terminal, `kubectl get hpa,pods -n runproject -w`. Watch replicas
climb, then settle back after the stabilization window.

**`<unknown>/70%`** means metrics-server isn't working, or the Deployment has no
CPU requests. Both are common; check requests first.

---

## Lab 9 — Kustomize

**Task.** Restructure into `base/` + `overlays/{dev,prod}`.

| Overlay | Differences |
|---|---|
| dev | ns `runproject-dev`, 1 replica each, host `training.local`, selfSigned issuer, small resources |
| prod | ns `runproject-prod`, 2 replicas, host `training.example.com`, `letsencrypt-prod`, real resources |

Use `configMapGenerator` for `backend-config` — the name hash means a config
change triggers a rollout automatically, which is the best reason to adopt
Kustomize at all.

**Self-check**
```bash
kubectl kustomize k8s/overlays/prod          # READ this output before applying
diff <(kubectl kustomize k8s/overlays/dev) <(kubectl kustomize k8s/overlays/prod)
kubectl apply -k k8s/overlays/dev
```
The diff shows *only* the intended differences. Anything else is a patch
targeting more than you meant.

---

## Lab 10 — backups

**Task.** A CronJob that `pg_dump`s to object storage.

| # | Constraint |
|---|---|
| 1 | Daily, 3am, `timeZone: "Asia/Kolkata"` |
| 2 | `concurrencyPolicy: Forbid` |
| 3 | `pg_dump -Fc` (custom format, compressed) |
| 4 | Upload to R2/S3, credentials from a Secret |
| 5 | Filename includes the date |
| 6 | History limits set |

**Then restore it.** This is the actual exercise:
```bash
kubectl create job --from=cronjob/pg-backup manual-1 -n runproject
kubectl logs job/manual-1 -n runproject
# download the dump, restore into a scratch database, verify row counts
```

A backup you have never restored is a hypothesis. `08-operations/02` covers the
restore drill properly.

---

## Done when

- [ ] All six workloads Running, correct replica counts
- [ ] `https://training.local` serves the app end to end
- [ ] Deep links survive a refresh; `/admin` has CSS
- [ ] Postgres data survives Pod deletion
- [ ] Migrations run as a Job, not in a container command
- [ ] HPA **observed** scaling under load, then back down
- [ ] KEDA scales the worker on real queue depth
- [ ] Kustomize overlays render correct, minimal diffs
- [ ] A backup has been taken **and restored**
- [ ] Nothing runs as root; no ServiceAccount tokens mounted

Commit the whole `k8s/` tree. Then `07-cicd` makes it deploy itself.
