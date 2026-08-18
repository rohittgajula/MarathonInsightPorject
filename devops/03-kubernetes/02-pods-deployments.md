# Pods, ReplicaSets, Deployments

This file contains **the one fully-worked manifest in the course**. Everything
else you write yourself, patterning off this.

## Pod

The smallest thing Kubernetes schedules. One or more containers that:

- share a network namespace — same IP, they reach each other on `localhost`,
  and they cannot both bind the same port
- can share volumes
- live and die together on the same node

Almost always: **one application container per Pod**. Multiple containers are
for sidecars — a log shipper, a proxy — that are useless without the main one.

Your six services become six kinds of Pod. `backend` and `worker` are separate
Pods, not two containers in one, because they scale differently and fail
independently.

You will rarely write a bare Pod. Nothing restarts it if the node dies, and it
cannot be updated. Write Deployments.

## ReplicaSet

Keeps N identical Pods running. Watches, counts, creates or deletes to match.
You do not write these; Deployments create them. But knowing they exist explains
what you see:

```
Deployment: backend
├── ReplicaSet: backend-7d4f8b        (old, replicas: 0)
└── ReplicaSet: backend-9c2e1a        (new, replicas: 3)
```

The Deployment keeps old ReplicaSets around at zero replicas — that is the
rollback history. `kubectl rollout undo` scales an old one back up.

## Deployment — worked example

Here is the backend Deployment, fully commented. Read every line; you'll write
five more like it.

```yaml
apiVersion: apps/v1          # apps/v1 for Deployment. v1 is core objects only
kind: Deployment
metadata:
  name: backend
  namespace: runproject
  labels:
    app.kubernetes.io/name: backend
    app.kubernetes.io/part-of: runproject
spec:
  replicas: 2                # 2, not 1: one can be unavailable during a rollout
                             # and still serve. This is why zero-downtime works.

  selector:                  # which Pods this Deployment owns.
    matchLabels:             # IMMUTABLE after creation — to change it you
      app: backend           # delete and recreate the Deployment.

  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0      # never drop below `replicas` ready
      maxSurge: 1            # may run one extra during the roll
                             # 0/1 = safest: new Pod ready before old dies

  template:                  # ── the Pod template. Everything below describes
    metadata:                #    a Pod, not the Deployment.
      labels:
        app: backend         # MUST match spec.selector.matchLabels.
                             # Mismatch = Pods created forever in a hot loop.
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        fsGroup: 10001       # mounted volumes get group 10001, so a non-root
                             # process can actually write to the PVC

      containers:
        - name: backend
          image: ghcr.io/rohittgajula/runproject-backend:680b5c5
                             # SHA tag, never :latest. See 02-containers/01.
          imagePullPolicy: IfNotPresent

          ports:
            - name: http     # naming the port lets Services and probes
              containerPort: 8000   # refer to "http" instead of 8000
              protocol: TCP

          envFrom:           # bulk-import every key as an env var
            - configMapRef:
                name: backend-config
            - secretRef:
                name: backend-secrets

          env:               # individual values, and the downward API
            - name: POD_NAME
              valueFrom:
                fieldRef:
                  fieldPath: metadata.name   # useful in logs

          resources:
            requests:        # guaranteed, and what the scheduler packs against
              cpu: 100m      # 100 millicores = 0.1 of a core
              memory: 256Mi
            limits:          # ceiling. CPU over limit = throttled.
              cpu: 500m      #          memory over limit = OOMKilled.
              memory: 512Mi

          startupProbe:      # "has it finished booting?" Django + DRF import
            httpGet:         # is slow-ish; this buys time without making the
              path: /api/health/    # liveness probe lax forever.
              port: http
            failureThreshold: 30
            periodSeconds: 2        # → up to 60s to start

          readinessProbe:    # "should traffic go here?" Fails → removed from
            httpGet:         # Service endpoints. Does NOT restart.
              path: /api/health/
              port: http
            periodSeconds: 10
            timeoutSeconds: 3

          livenessProbe:     # "is it wedged?" Fails → container RESTARTED.
            httpGet:         # Keep this loose. An aggressive liveness probe
              path: /api/health/    # under load turns a slowdown into a
              port: http            # restart storm.
            periodSeconds: 20
            failureThreshold: 3

          volumeMounts:
            - name: media
              mountPath: /data/media

      volumes:
        - name: media
          persistentVolumeClaim:
            claimName: media

      terminationGracePeriodSeconds: 30
        # SIGTERM, then up to 30s to finish in-flight requests, then SIGKILL.
```

**Note `/api/health/` does not exist yet.** This project has no health endpoint.
You need to add one: a view that returns 200 without touching the database.

Why not touch the database? Because a readiness probe that checks Postgres
means a brief database hiccup marks *every* backend Pod unready simultaneously,
removing all of them from the Service and turning a 2-second blip into a full
outage. Liveness and readiness should test *this process*, not its dependencies.

## The rolling update

```
t0   RS-old: ■■   (2 ready)        RS-new: —
t1   RS-old: ■■   (2 ready)        RS-new: ▨       maxSurge=1: one extra starts
t2   RS-old: ■■                    RS-new: ■       new passes readiness
t3   RS-old: ■                     RS-new: ■       one old terminates
t4   RS-old: ■                     RS-new: ■▨      next new starts
t5   RS-old: —                     RS-new: ■■      done
```

Never fewer than 2 ready. That is `maxUnavailable: 0` doing its job, and it
only works because the readiness probe is honest about when the new Pod can
serve. A readiness probe that returns 200 before the app can handle a request
gives you a rollout that "succeeds" straight into an outage.

```bash
kubectl rollout status deploy/backend -n runproject
kubectl rollout history deploy/backend -n runproject
kubectl rollout undo deploy/backend -n runproject
kubectl rollout undo deploy/backend --to-revision=3 -n runproject
```

`rollout status` blocks until done or failed — which makes it exactly the right
last step in a CI deploy job. Without it, CI reports success the moment
`apply` returns, which is before anything has actually rolled.

Add `progressDeadlineSeconds: 600` (default) and the rollout is marked failed —
not rolled back, just marked — if it stalls. Combined with `rollout status`
returning non-zero, that's your CI failure signal.

## Labels and selectors — the #1 beginner bug

```yaml
spec:
  selector:
    matchLabels:
      app: backend      # ← these
  template:
    metadata:
      labels:
        app: backend    # ← must match these
```

If they don't match, the Deployment creates a Pod, doesn't recognise it as its
own, creates another, forever. You get hundreds of Pods and a very confusing
`kubectl get pods`.

Separately, and just as common: your **Service** selector must match the Pod
labels too. Mismatch there gives a Service with no endpoints — connections
refused or hanging, with nothing in any log. Always check:

```bash
kubectl get endpoints backend -n runproject
```

Empty `ENDPOINTS` means selector mismatch or no Pod passing readiness. That one
command diagnoses a large fraction of "my service doesn't work".

## Recommended labels

Kubernetes suggests a standard set. Use them; tooling reads them.

```yaml
app.kubernetes.io/name: backend
app.kubernetes.io/instance: runproject
app.kubernetes.io/component: api        # api | worker | scheduler | web | database
app.kubernetes.io/part-of: runproject
app.kubernetes.io/managed-by: kubectl
```

Keep a short, stable `app: backend` for selectors (remember: immutable) and use
the long-form labels for everything else. Then:

```bash
kubectl get pods -n runproject -l app.kubernetes.io/component=worker
```

## Your six workloads

| Compose service | Kind | Replicas | Why |
|---|---|---|---|
| `backend` | Deployment | 2 → HPA | Stateless HTTP |
| `worker` | Deployment | 1 → HPA on queue | Stateless, scales on backlog |
| `beat` | Deployment | **exactly 1** | DatabaseScheduler; 2 = every task twice |
| `frontend` | Deployment | 2 | Static files, trivially scalable |
| `db` | StatefulSet | 1 | Stable identity + storage |
| `redis` | Deployment | 1 | Broker; see `05-storage` on persistence |

`beat` deserves a comment in the YAML explaining *why* it's pinned to 1.
Six months from now, "replicas: 1" looks like something nobody got round to
tuning, and doubling it silently doubles your Garmin sync rate into a service
`celery.py` already notes rate-limits aggressively.

Use `strategy: type: Recreate` for beat, not RollingUpdate — a rolling update
briefly runs two beats, which is the exact thing you're preventing.
