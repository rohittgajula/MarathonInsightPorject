# Probes, resources, and graceful shutdown

Three topics that share one theme: telling Kubernetes the truth about your
workload so it can make good decisions.

## The three probes

| Probe | Question | On failure |
|---|---|---|
| **startupProbe** | Has it finished booting? | Keeps the other two from running yet |
| **readinessProbe** | Should traffic go here? | Removed from Service endpoints. **No restart.** |
| **livenessProbe** | Is it permanently wedged? | Container **restarted** |

The distinction between readiness and liveness is the one that matters. Getting
it backwards is how you turn a slow database into a restart storm.

### readinessProbe

Controls Service membership. A Pod failing readiness stays running but receives
no traffic. This is what makes rolling updates safe — a new Pod joins the
Service only once it says it can serve.

Use it for: still booting, temporarily overloaded, shutting down.

### livenessProbe

Failing means "restart this". Reserve it for genuinely unrecoverable states —
deadlock, wedged event loop. **When in doubt, don't set one.** A too-aggressive
liveness probe is actively harmful:

```
load spike → responses slow → liveness times out → container killed
   → capacity drops → remaining Pods slower → they get killed too
      → total outage from what was a slowdown
```

This is a real and common failure mode. If your liveness and readiness probes
hit the same endpoint with the same thresholds, liveness should be *much*
looser: longer `periodSeconds`, higher `failureThreshold`.

### startupProbe

For slow starts. While it's running, liveness and readiness are suspended.

Without it you face a bad trade: a liveness probe patient enough for a 40-second
Django boot is also patient enough to leave a wedged process running for 40
seconds. startupProbe separates the two — generous during boot, strict after.

`failureThreshold × periodSeconds` = your boot budget.

### Probe types

```yaml
httpGet:
  path: /api/health/
  port: http
```
Best when you have HTTP. 200–399 passes.

```yaml
tcpSocket:
  port: 5432
```
Connection opens = pass. For Postgres and Redis. Weak — a hung process may still
accept connections — but better than nothing.

```yaml
exec:
  command: ["celery", "-A", "config", "inspect", "ping", "-d", "celery@$HOSTNAME"]
```
Runs a command; exit 0 passes. Expensive (forks a process every period), so use
long intervals.

### Probes for your six workloads

**backend** — needs a health endpoint that doesn't exist yet. Add:

```python
# apps/.../views.py — no DB, no Redis, no auth
def health(request):
    return JsonResponse({"status": "ok"})
```

Wire it at `/api/health/`, and make sure it's **exempt from
`IsAuthenticated`** — your `REST_FRAMEWORK` default permission class is
`IsAuthenticated`, so a DRF view would 403 the kubelet and every Pod would be
permanently unready. Use a plain Django view, or `@permission_classes([AllowAny])`.

That 403 trap is worth internalising: the probe failing means "unready", and
"unready" from an auth error looks identical to "unready" from a crash.

*Should it check the database?* No. Argued in `03-kubernetes/02` — a shared
dependency in a readiness probe converts a dependency blip into a total outage
because every replica fails at once. Add a **separate** `/api/health/deep/`
that checks DB and Redis, and point *monitoring* at it, not the kubelet.

**worker** — no HTTP server, so no httpGet. Options:
- `exec` with `celery inspect ping` — accurate, expensive, and slow to respond
  when the worker is busy, which can cause false failures
- No liveness probe at all, and rely on the process exiting when broken
- Best: **readiness only**, or nothing. Celery workers pull work; nothing routes
  traffic to them, so readiness has no consumer anyway.

For the worker, "no probes" is a defensible, considered answer. Say so in a
comment so it reads as a decision.

**beat** — same. One process, no traffic.

**frontend** — `httpGet: /healthz` on 8080. The nginx `return 200` location from
lab 0.4. Trivial and reliable.

**db** — `exec: pg_isready -U runproject`. Your compose file already uses
exactly this; carry it over.

**redis** — `exec: redis-cli ping`. Same.

## Resources

```yaml
resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 500m
    memory: 512Mi
```

**Request** = guaranteed, and what the scheduler packs against. Sum of requests
on a node must fit the node.

**Limit** = ceiling.

The two behave completely differently when exceeded:

| | Over limit |
|---|---|
| **CPU** | **Throttled.** Compressible — the process just runs slower. Recoverable. |
| **Memory** | **OOMKilled.** Incompressible — the kernel kills the process. |

So: **a memory limit too low is a crash; a CPU limit too low is a slowdown.** Be
generous with memory limits, and set them close to requests. Be more relaxed
about CPU.

`100m` = 100 millicores = 0.1 of a core. `1000m` = 1 core.

### QoS classes

Kubernetes assigns each Pod a class, which determines eviction order under node
pressure:

| Class | Condition | Evicted |
|---|---|---|
| **Guaranteed** | requests == limits, for every container | Last |
| **Burstable** | requests set, limits higher or absent | Middle |
| **BestEffort** | nothing set | **First** |

Never leave production Pods BestEffort. They get killed first, on a node you
didn't expect, at a time you didn't choose. Your database should be
**Guaranteed** — set requests == limits on `db`.

```bash
kubectl get pod <name> -o jsonpath='{.status.qosClass}'
```

### The CPU limits debate

There is a real argument that **you should not set CPU limits at all** on
latency-sensitive services. The kernel's CFS quota throttles in 100ms periods,
and a process that bursts can be throttled even while the node has idle CPU —
adding latency for no benefit. Requests alone already guarantee a fair share
under contention.

The counter-argument: without limits, one runaway Pod starves its neighbours.

Reasonable position for you: **set requests everywhere, set memory limits
everywhere, be generous with CPU limits or omit them on `backend`.** And know
that this is a live debate, not settled doctrine — being able to argue both
sides is the useful part.

### Starting numbers

Guesses, to be corrected by measurement. Do not treat as gospel.

| Workload | CPU req | Mem req | CPU limit | Mem limit |
|---|---|---|---|---|
| backend (gunicorn, 3 workers) | 100m | 256Mi | 500m | 512Mi |
| worker (FIT parsing — spiky) | 100m | 512Mi | 1000m | 1Gi |
| beat | 50m | 128Mi | 200m | 256Mi |
| frontend (nginx, static) | 10m | 32Mi | 100m | 128Mi |
| db | 200m | 512Mi | 200m | 512Mi (Guaranteed) |
| redis | 50m | 128Mi | 100m | 256Mi |

The worker gets more memory because parsing a `.fit` file into per-second
`ActivityRecord` rows loads a lot at once, and `segmentation.py` works over the
full sample array. That's the workload most likely to OOM. Measure it:

```bash
kubectl top pods -n runproject
```

Then set requests near the p50 and memory limits near the p99 plus headroom.
Requests set far above real usage waste the whole node — that's the most common
resource mistake, and it's expensive.

## Graceful shutdown

What happens on Pod deletion:

```
1. Pod marked Terminating; removed from Service endpoints  ┐ these two happen
2. preStop hook runs (if any)                              ┘ CONCURRENTLY
3. SIGTERM to PID 1
4. ... terminationGracePeriodSeconds ...
5. SIGKILL
```

**Step 1 and 3 race.** Endpoint removal propagates asynchronously to every
node's kube-proxy, which takes a moment. Meanwhile the process already got
SIGTERM. So there's a window where traffic still arrives at a shutting-down Pod
— visible as a handful of 502s during every rollout.

The standard fix is a preStop sleep:

```yaml
lifecycle:
  preStop:
    exec:
      command: ["sh", "-c", "sleep 5"]
```

Five seconds of doing nothing, so endpoint removal wins the race before SIGTERM
arrives. It looks like a hack. It is a hack. It is also what everyone does, and
it works.

### Per workload

**backend (gunicorn)** — SIGTERM triggers graceful shutdown: stop accepting,
finish in-flight, exit. `terminationGracePeriodSeconds: 30` is ample for API
requests. Plus the preStop sleep.

**worker (Celery)** — this is the one that matters. SIGTERM is a **warm
shutdown**: stop consuming new tasks, finish current ones, exit. So the grace
period must exceed your longest task.

How long is a FIT parse? `CONTEXT.md` doesn't say. **Measure it**, then set the
grace period to comfortably more:

```yaml
terminationGracePeriodSeconds: 300   # longest task ~2min, measured, plus margin
```

Too short and SIGKILL lands mid-parse. With `acks_late` unset (the Celery
default), the task was already acked when it started — so it is **lost**, not
requeued. Your derived-metrics sweep would eventually notice, but silently
losing work is not something to rely on a sweeper to fix.

Consider setting `task_acks_late = True` so tasks ack on completion and a killed
worker's task is redelivered. That requires your tasks to be idempotent —
running twice must be safe. For `rebuild_stale_metrics` (recompute, overwrite)
it is. For `sync_all_athletes` hitting Garmin's rate limit, think harder.

**beat** — nothing in flight. Short grace period is fine.

**db** — Postgres does a fast shutdown on SIGTERM and needs to flush. Give it
60s. Killing Postgres mid-write means crash recovery on next start; usually
fine, occasionally not.

## Checklist

- [ ] `/api/health/` exists, returns 200, **needs no auth**, touches nothing
- [ ] readiness on everything serving traffic
- [ ] liveness only where a restart genuinely helps, and looser than readiness
- [ ] startupProbe on the backend
- [ ] requests **and** memory limits on every container
- [ ] db is Guaranteed QoS
- [ ] worker grace period > longest measured task
- [ ] preStop sleep on backend and frontend
