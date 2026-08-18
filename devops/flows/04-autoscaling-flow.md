# Flow: autoscaling

## HPA control loop

```
   every 15s
       │
       ▼
┌──────────────────────────────────────────────────────┐
│ kubelet (cAdvisor) measures container CPU + memory   │
└──────────────────────┬───────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────┐
│ metrics-server scrapes every kubelet                 │
│   holds ~last 60s in memory. NOT durable.            │
└──────────────────────┬───────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────┐
│ metrics.k8s.io API      ← `kubectl top` reads this   │
└──────────────────────┬───────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────┐
│ HPA controller                                       │
│                                                      │
│   current = mean(CPU) / CPU REQUEST   ← not limit,   │
│                                          not node    │
│   desired = ceil(replicas × current / target)        │
│                                                      │
│   e.g.  4 pods, 85% avg, target 70%                  │
│         ceil(4 × 85/70) = ceil(4.86) = 5             │
│                                                      │
│   apply behavior policies (up fast / down slow)      │
│   clamp to [minReplicas, maxReplicas]                │
└──────────────────────┬───────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────┐
│ Deployment.spec.replicas = 5                         │
└──────────────────────┬───────────────────────────────┘
                       ▼
   ReplicaSet creates a Pod → schedule → pull → start
   → startupProbe → readinessProbe → joins endpoints
                       │
              ~30–90 seconds total
```

**That 30–90 seconds is the honest cost of HPA.** A traffic spike is served
badly for up to a minute and a half. For predictable load, pre-scale on a
schedule instead.

## Scale-up vs scale-down asymmetry

```
  load ▲
       │        ╱‾‾‾‾‾‾‾‾‾‾‾╲
       │       ╱             ╲
       │──────╱               ╲──────────────
       └──────────────────────────────────▶ time

  pods ▲
     6 │        ┌───────────┐
     4 │      ┌─┘           └─────┐
     2 │──────┘                   └──────────
       └──────────────────────────────────▶
              ▲                   ▲
         up immediately     down only after
         (stabilization=0)  300s stabilization
```

**Up fast, down slow.** Scaling up late costs an outage; scaling down late costs
a few cents. Without the stabilization window the system oscillates: scale up →
per-Pod load drops → scale down → load rises → scale up, forever.

## KEDA, for the worker

CPU is the wrong signal for a queue consumer:

```
   200 tasks queued, all waiting on the Anthropic API
        │
        ▼
   worker CPU: ~2%      ← blocked on I/O, not computing
        │
        ▼
   CPU-based HPA: "idle, scale DOWN"
        │
        ▼
   queue grows. system is failing. autoscaler is making it worse.
```

Queue depth instead:

```
   every 15s (pollingInterval)
       │
       ▼
┌──────────────────────────────────────────┐
│ KEDA scaler → redis LLEN celery = 200    │
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│ target: listLength 10 per replica        │
│ desired = ceil(200 / 10) = 20            │
│ clamp to maxReplicaCount = 4             │
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│ KEDA drives an ordinary HPA → 4 replicas │
└──────────────────────────────────────────┘
```

Note the clamp doing real work. `maxReplicaCount: 4` is not arbitrary — see
below.

## The ceilings that cap everything

```
  ┌─────────────────────────────────────────────────┐
  │  Postgres max_connections = 100                 │
  │                                                 │
  │  backend  6 replicas × 3 gunicorn workers = 18  │
  │  worker   4 replicas × 4 celery concurrency= 16 │
  │  beat                                    =  1   │
  │                                    total =  35  │
  │                                                 │
  │  conn_max_age=600 → these are PERSISTENT        │
  │  a steady-state floor, not a peak               │
  └─────────────────────────────────────────────────┘
                        │
              exceed it → FATAL: too many clients
              → 500s across the WHOLE app,
                 not a "scaling problem"
                        │
                 fix: PgBouncer
```

```
  ┌─────────────────────────────────────────────────┐
  │  Garmin: rate-limits aggressively               │
  │  Gemini free tier: ~20 requests                 │
  │                                                 │
  │  10 workers hit these 10× faster.               │
  │  Scaling out makes it WORSE.                    │
  │                                                 │
  │  fix: a dedicated queue, ONE worker,            │
  │       Celery task rate_limit                    │
  └─────────────────────────────────────────────────┘
```

**Autoscaling only helps when the bottleneck is your own compute.** When it's
someone else's rate limit, or a shared database, scaling out moves the failure
rather than fixing it. That is the single most important idea in this chapter.

## What scales, and what must not

```
  backend    ■■ ──HPA CPU 70%──▶ ■■■■■■        2–6
  frontend   ■■ ──HPA CPU 70%──▶ ■■■■          2–4
  worker     ■  ──KEDA queue───▶ ■■■■          1–4

  beat       ■  ✗ NEVER   two schedulers = every task twice
  db         ■  ✗ NEVER   vertical only; replicas = a different design
  redis      ■  ✗ NEVER   single broker
```

Three of six must never scale. Knowing which — and why — is what stops an
autoscaler from breaking things.
