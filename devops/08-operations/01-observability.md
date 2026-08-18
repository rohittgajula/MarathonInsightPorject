# Observability

## Three signals

| | Answers | Cardinality | Cost |
|---|---|---|---|
| **Logs** | What happened, exactly | High | High volume |
| **Metrics** | How much, over time | Low | Cheap, aggregated |
| **Traces** | Where did the time go in *this* request | Very high | Sampled |

They're complementary. A metric tells you error rate rose at 14:02. Logs tell
you *what* the errors were. A trace tells you the time went into a Garmin API
call. Alerting on logs is expensive; debugging from metrics alone is impossible.

## Monitoring vs observability

**Monitoring** — watching things you knew to watch. "Is CPU above 80%?"
**Observability** — being able to answer questions you *didn't* anticipate.
"Why are only Tuesday-morning log extractions slow?"

The distinction matters when you're deciding what to instrument. Dashboards
answer known questions; structured, queryable data answers new ones.

## Logs

Your `settings.py` already does the right thing: everything to stdout at INFO.
The container runtime captures it, and that's the twelve-factor contract.

```bash
kubectl logs deploy/backend -n runproject -f
kubectl logs deploy/backend -n runproject --previous     # the crashed attempt
kubectl logs -n runproject -l app=backend --tail=100     # all replicas
kubectl logs -n runproject --since=1h deploy/worker
```

**`--previous` is the one people forget.** A CrashLoopBackOff's useful output is
in the previous attempt; plain `logs` shows the current one, which may not have
gotten far enough to say anything.

**`kubectl logs` is not durable.** Logs live on the node, rotate at 10MB by
default, and vanish when the Pod is deleted. A Pod that crashed and was
rescheduled has taken its evidence with it. For anything you'd want to look at
tomorrow, you need aggregation.

### Structured logging

Your logs are plain text. Fine for `kubectl logs`, painful the moment you
aggregate — you end up grepping instead of querying.

Switch to JSON (`python-json-logger`) and each line becomes queryable fields:

```json
{"time":"2026-08-18T09:15:22Z","level":"INFO","logger":"apps.journal.tasks",
 "msg":"extraction complete","athlete_id":1,"provider":"anthropic",
 "duration_ms":1840,"log_date":"2026-08-18"}
```

Now "p95 extraction latency by provider" is a query, not an afternoon.

Worth adding as fields, given what this app does:
- `athlete_id` — multi-tenant from the start; every log line should say whose
- `provider` — Gemini vs Claude, so you can compare them honestly
- `duration_ms` on the LLM call and the FIT parse
- `task_id` for Celery work
- `AI_EXTRACTION_VERSION` — so a re-parse is distinguishable from a first read

### Loki

Prometheus for logs: cheap, because it indexes only labels, not content.

```bash
helm install loki grafana/loki-stack -n monitoring --create-namespace \
  --set promtail.enabled=true
```

Promtail runs as a DaemonSet, ships every Pod's stdout to Loki, and adds
Kubernetes labels automatically. Query in Grafana with LogQL:

```
{namespace="runproject", app="worker"} |= "RateLimited"
{namespace="runproject"} | json | duration_ms > 5000
```

**Keep label cardinality low.** Labelling by `athlete_id` or `task_id` creates a
separate stream per value and will destroy Loki's performance. Those belong in
the log *content* (queryable via `| json`), not in labels. This is the single
most common Loki mistake.

## Metrics

### Install

```bash
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace
```

That single chart gives you Prometheus, Grafana, Alertmanager, node-exporter,
kube-state-metrics, and a set of dashboards that are genuinely good out of the
box. Node CPU/memory/disk, per-Pod resource usage, restart counts, PVC capacity
— all working before you write anything.

### The four golden signals

For any user-facing service:

| Signal | For your backend |
|---|---|
| **Latency** | Request duration, p50/p95/p99. **Split success from error** — fast 500s flatter your p99. |
| **Traffic** | Requests per second |
| **Errors** | 5xx rate |
| **Saturation** | CPU/memory vs limits, DB connections vs `max_connections` |

### Instrumenting Django

```
django-prometheus
```

Add the app and its middleware, expose `/metrics`, and you get request counts,
latencies by view and status, and database query timing.

Then a `ServiceMonitor` tells Prometheus to scrape it:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: backend
  namespace: runproject
spec:
  selector:
    matchLabels:
      app: backend
  endpoints:
    - port: http
      path: /metrics
```

**Make sure `/metrics` is not exposed through the ingress.** It leaks internal
structure — view names, error patterns, timings. Serve it on the Service only;
Prometheus scrapes Pods directly and never goes through the ingress.

### Metrics worth having, specific to this app

Beyond the generic ones:

| Metric | Why |
|---|---|
| Celery queue depth | Already your KEDA signal. Graph it. |
| Task duration by task name | Sets `terminationGracePeriodSeconds`. Currently a guess. |
| LLM extraction: success / `RateLimited` / failed | `CONTEXT.md` treats rate limiting as a distinct, retryable status — make that visible |
| Garmin sync success rate | It rides an unofficial library against a saved token. It *will* break. |
| Unread log backlog | Directly measures whether `sweep_unread` is keeping up |
| Postgres connections in use | The ceiling that caps your HPA |
| Certificate expiry | cert-manager exports this. Alert at 14 days. |

The Garmin and LLM ones matter most. `CONTEXT.md` is candid that Garmin is
fragile — no personal API, an unofficial library, a token that can silently
expire. **A silent Garmin failure looks exactly like a healthy system**, because
everything else keeps working. That's the failure mode most worth instrumenting.

## Alerting

Alertmanager routes to email, Slack, or a webhook.

**The only rule that matters: alert on symptoms, not causes.**

| Don't alert on | Alert on |
|---|---|
| CPU above 80% | Latency p95 above 2s |
| A Pod restarted | Error rate above 5% |
| Disk 70% full | Disk will be full in 4 hours |

High CPU with fine latency is a *healthy, efficient* system. Alerting on it
trains you to ignore alerts, and an ignored alerting system is worse than none —
it gives you false confidence while producing nothing.

Sensible set for you:

```
- Any Pod CrashLooping for > 5m
- Backend p95 latency > 2s for 10m
- 5xx rate > 5% for 5m
- Celery queue depth > 100 for 15m
- No successful Garmin sync in 6h        ← silent failure detector
- No successful backup in 36h            ← the one that matters most
- Certificate expires in < 14d
- PVC > 85% full
- Postgres connections > 80% of max
```

The backup alert is the most important one on that list. A backup system that
stopped working two months ago and told nobody is the classic disaster, and it's
entirely preventable with one alert.

**Route by severity.** Everything paging you at 3am means you'll mute the
channel. Critical (app down, backups failing) → push notification. Warning
(disk filling, cert expiring) → email or a daily digest.

## Traces

OpenTelemetry, into Tempo or Jaeger. A trace follows one request across
services, showing where the time went.

**Skip this for now.** Traces earn their keep when a request crosses many
services and you can't tell which is slow. You have one backend; latency
metrics by view answer the same question at a fraction of the effort.

Where it *would* pay off here: seeing a request fan out into a Celery task
that calls Garmin, then Anthropic, then writes to Postgres, with each span
timed. If the LLM pipeline ever gets complicated, revisit.

## What to do, in order

1. **kube-prometheus-stack.** Free dashboards, immediate value.
2. **Alerts on backups, CrashLoop, cert expiry.** The silent killers.
3. **Loki + promtail.** Durable logs that survive a Pod dying.
4. **Structured JSON logging** in Django.
5. **django-prometheus + ServiceMonitor.** App-level metrics.
6. **Custom metrics** for Garmin and LLM health.
7. Traces — only if the system gets more distributed.

Steps 1 and 2 give you most of the value. Don't build the full stack before
you've had one incident; let the incidents tell you what you wish you'd had.
