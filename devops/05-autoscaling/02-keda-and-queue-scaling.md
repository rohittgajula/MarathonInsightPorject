# KEDA, and scaling the Celery worker properly

## Why CPU is the wrong metric for a worker

Your Celery worker processes FIT file parsing, metric rebuilds, Garmin syncs,
and LLM log extraction.

Consider `journal.tasks` calling Gemini or Claude. That task spends almost all
its time **waiting on an HTTP response**. CPU usage: near zero. Meanwhile 200
unread logs are queued.

HPA on CPU sees an idle worker and scales *down*. The queue grows. The system
is failing and the autoscaler is making it worse.

**The right metric for a queue consumer is queue depth, not CPU.** Always.

## KEDA

Kubernetes Event-Driven Autoscaling. It provides an external metrics adapter
and a `ScaledObject` CRD, and under the hood it creates and drives an ordinary
HPA. So it's not a replacement for HPA — it's a source of better metrics for it.

```bash
helm repo add kedacore https://kedacore.github.io/charts
helm install keda kedacore/keda -n keda --create-namespace
```

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: worker
  namespace: runproject
spec:
  scaleTargetRef:
    name: worker
  minReplicaCount: 1
  maxReplicaCount: 5
  pollingInterval: 15          # how often KEDA checks the queue
  cooldownPeriod: 300          # wait before scaling to minReplicaCount
  triggers:
    - type: redis
      metadata:
        address: redis.runproject.svc.cluster.local:6379
        listName: celery       # the Redis LIST Celery uses for its default queue
        listLength: "10"       # target items per replica
```

That reads: keep roughly 10 queued tasks per worker. 50 queued → 5 workers.
Empty → back to 1.

### Getting `listName` right

Celery with a Redis broker stores messages in a Redis **list** named after the
queue. The default queue is `celery`. Verify rather than trust:

```bash
kubectl exec -n runproject deploy/redis -- redis-cli keys '*'
kubectl exec -n runproject deploy/redis -- redis-cli llen celery
```

If you ever route tasks to named queues (a sensible future step — separate the
slow FIT parsing from the fast LLM calls), each queue needs its own trigger, or
its own Deployment with its own ScaledObject. That's the point where this gets
genuinely useful.

### Scale to zero

KEDA's headline feature: `minReplicaCount: 0`. No work, no Pods, no cost.

**Don't do it here.** Your beat schedule fires `rebuild-stale-metrics` every 5
minutes and `sweep-unread-logs` every 10, so the queue is essentially never idle
for long. You'd get constant scale-up/scale-down churn, and each cold start pays
Django import time before doing any work.

`minReplicaCount: 1` — one worker always warm. Scale-to-zero is for genuinely
bursty workloads with long quiet periods, which this isn't.

## Without KEDA: Prometheus Adapter

If you're already running Prometheus (`08-operations/02`), you can feed custom
metrics to a plain HPA via `prometheus-adapter`, exposing e.g. `celery_queue_length`
as a Kubernetes external metric.

More moving parts than KEDA for this one use case. KEDA is purpose-built and
ships a Redis scaler out of the box. Use KEDA.

## The constraint everything must respect

Scaling the worker means more concurrent connections to Postgres and more
concurrent calls to external APIs. Both have hard ceilings.

### Postgres connections

Default `max_connections` is **100**. Count what you're actually using:

```
backend:  replicas × gunicorn workers          = 10 × 3 = 30
worker:   replicas × celery concurrency        =  5 × 4 = 20
beat:     1
                                        total  = 51
```

Django's `conn_max_age=600` (already set in `settings.py`) means connections are
**persistent** — each gunicorn worker holds one open for 10 minutes. So that 51
is a steady-state floor, not a peak.

Push `maxReplicas` higher and you hit `FATAL: sorry, too many clients already`
— which surfaces as 500s across the whole app, not as a scaling problem.

**The fix is PgBouncer**, a connection pooler. It sits between your app and
Postgres, multiplexing hundreds of client connections onto a few dozen real
ones. Run it as a sidecar or a small Deployment, and point `DATABASE_URL` at it
instead. This is the standard answer and you should know it exists.

**For now:** cap `maxReplicas` so the arithmetic stays under ~80, and write the
calculation in a comment next to the number. A magic `maxReplicas: 10` with no
explanation is how a future you causes an outage.

### Garmin and LLM rate limits

`celery.py` is explicit that Garmin rate-limits aggressively, and hourly sync is
deliberate. `CONTEXT.md` documents Gemini's free tier capping at 20 requests
and notes `reparse_logs` paces itself at 3.5 s per entry to stay under it.

**Scaling workers does not raise those ceilings.** Ten workers hitting Gemini in
parallel get rate-limited ten times as fast. You'd convert a working system into
one that's permanently in backoff.

The design already handles this correctly — `RateLimited` is a distinct status
from `failed`, and `sweep_unread` retries. But scaling out doesn't help, and may
hurt. If Garmin or LLM work becomes the bottleneck, the answer is a **dedicated
queue with a single worker and a rate limit** (Celery's `rate_limit` on the
task), not more workers.

This is worth sitting with: **autoscaling only helps when the bottleneck is your
own compute.** When it's someone else's rate limit, scaling is the wrong tool
entirely.

## What actually scales here

| Workload | Scale on | Min | Max | Why |
|---|---|---|---|---|
| **backend** | CPU 70% | 2 | 6 | Real HTTP concurrency. Cap by DB connections. |
| **worker** | Redis queue depth (KEDA) | 1 | 4 | Queue depth is the honest signal. Cap by DB + external rate limits. |
| **beat** | **never** | 1 | 1 | Two schedulers = every task twice. |
| **frontend** | CPU 70% | 2 | 4 | nginx serving static — will basically never need it. |
| **db** | **never** | 1 | 1 | Vertical only. Read replicas are a different design. |
| **redis** | **never** | 1 | 1 | Single broker. Clustering is a different design. |

Three of six must never scale. **That table, and the reasons in it, is the
actual deliverable of this chapter** — more than the YAML. Knowing which
workloads can't scale, and why, is what stops you breaking things with an
autoscaler.

## Honest note

At one user, none of this triggers. Your backend will sit at 2 replicas
indefinitely and your worker at 1.

That's fine — you're learning the mechanism. But **do generate load and watch it
work**, or you've written YAML you've never seen function:

```bash
kubectl run -it --rm load --image=williamyeh/hey --restart=Never -- \
  -z 60s -c 50 http://backend.runproject.svc.cluster.local:8000/api/health/
```

Watch it in another terminal:

```bash
kubectl get hpa -n runproject -w
kubectl get pods -n runproject -w
```

Seeing the replica count climb and then settle back is the moment autoscaling
stops being theory. Do it once.
