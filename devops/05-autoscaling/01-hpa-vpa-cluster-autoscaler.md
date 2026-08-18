# The three autoscalers

They solve different problems and are frequently confused.

```
   HPA                  VPA                    Cluster Autoscaler
   more Pods            bigger Pods            more Nodes
   ■ → ■■■■             ■ → ▇                  [node] → [node][node]

   "load is up"         "this Pod is           "Pods are Pending —
                         mis-sized"             nowhere to put them"
```

## HPA — Horizontal Pod Autoscaler

Adds and removes Pod replicas based on a metric.

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend
  namespace: runproject
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

### The arithmetic

```
desiredReplicas = ceil( currentReplicas × ( currentMetric / targetMetric ) )
```

4 Pods averaging 85% CPU against a 70% target:

```
ceil(4 × (85/70)) = ceil(4.857) = 5
```

**The critical detail: `averageUtilization` is a percentage of the CPU
*request*, not of the node, not of the limit.**

A Pod with `requests.cpu: 100m` using 85m is at **85%** — even though it's using
8.5% of a core and the node is idle. Set requests too low and the HPA scales
constantly for no reason. Set them too high and it never scales at all.

**Therefore: HPA is downstream of correct resource requests.** If you skipped
`03-kubernetes/07`, go back. This is not optional prerequisite reading; a
wrongly-requested Pod makes the HPA actively harmful.

### It needs metrics-server

Neither kind nor a bare cluster ships it, and HPA silently reports
`<unknown>/70%` without it.

```bash
kubectl top nodes    # "error: Metrics API not available" → not installed
```

On kind, install with `--kubelet-insecure-tls`, because kind's kubelet serving
certificates aren't signed by the cluster CA:

```bash
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
helm install metrics-server metrics-server/metrics-server -n kube-system \
  --set 'args={--kubelet-insecure-tls}'
```

Never do that on a real cluster — it disables verification of the kubelet's
identity. On the VPS, fix the certificates properly instead.

### Flapping, and how `behavior` fixes it

Without tuning, HPA oscillates: scale up, load per Pod drops, scale down, load
rises, scale up. Pods churn continuously and nothing is stable.

```yaml
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300   # consider the last 5 min before
      policies:                          # scaling down; use the HIGHEST
        - type: Percent                  # recommendation in that window
          value: 50
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0     # scale up immediately
      policies:
        - type: Percent
          value: 100                     # may double
          periodSeconds: 30
        - type: Pods
          value: 4                       # or +4, whichever is larger
          periodSeconds: 30
```

The asymmetry is deliberate and is the standard shape: **up fast, down slow.**
Scaling up late costs you an outage; scaling down late costs you a few cents.

Default `scaleDown.stabilizationWindowSeconds` is 300; `scaleUp` is 0. The
defaults are reasonable — you mostly tune the policies.

### What HPA is bad at

- **Slow.** metrics-server scrapes every 15s, HPA evaluates every 15s, then a
  Pod must pull, start and pass readiness. A traffic spike is served badly for
  30–90 seconds. For predictable spikes, schedule capacity instead.
- **CPU is often the wrong signal.** A Django app blocked on database I/O has
  low CPU and terrible latency. HPA sees an idle Pod. This is extremely common.
- **Only helps if the bottleneck is the Pod.** Ten backend Pods hammering one
  Postgres makes things *worse*, not better — you've just added nine more
  connection-pool consumers to a saturated database.

That last point is the one to internalise. Autoscaling moves the bottleneck; it
doesn't remove it.

## VPA — Vertical Pod Autoscaler

Adjusts CPU/memory *requests* based on observed usage. Not built in; install
separately.

Three modes:

| Mode | Behaviour |
|---|---|
| `Off` | **Only recommends.** Read with `kubectl describe vpa`. |
| `Initial` | Sets requests at Pod creation only |
| `Auto` | Evicts and recreates Pods with new requests |

**`Auto` restarts your Pods** to resize them. (In-place resize is landing in
newer Kubernetes but is not yet the default experience.) On a single-replica
service that is an outage every time it decides to tune.

**VPA and HPA on the same metric conflict.** VPA raises requests → utilisation
percentage drops → HPA scales down → load per Pod rises → VPA raises requests
again. Do not run both on CPU for the same workload.

**Use VPA in `Off` mode as a measurement tool.** Let it watch for a week, read
its recommendations, set your requests by hand. That's genuinely useful and
carries no risk. `Auto` mode is for workloads you can't reason about, which
yours are not.

## Cluster Autoscaler

Watches for `Pending` Pods that can't be scheduled and adds nodes. Removes
underutilised nodes after a cooldown.

**Requires cloud infrastructure** — it works by calling an API to create a
machine. On kind and on a single VPS, there is no such API. Not available to
you.

Its relatives:
- **Karpenter** (AWS) — provisions right-sized nodes directly rather than
  scaling fixed groups. Faster and cheaper. The modern approach.
- **Managed node pool autoscaling** — GKE/EKS/AKS built-in.

Worth understanding because it's the layer that makes HPA meaningful in
production: HPA adds Pods, and when the nodes fill up, something must add nodes.
Without it, `maxReplicas: 10` on a cluster with room for 4 means six Pods sit
`Pending` forever, and you have an outage that looks like a scheduling bug.

## PodDisruptionBudget

Not an autoscaler, but it belongs here: it protects you *from* automation.

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: backend
spec:
  minAvailable: 1          # or maxUnavailable: 1
  selector:
    matchLabels:
      app: backend
```

This constrains **voluntary** disruptions — `kubectl drain`, node upgrades,
cluster autoscaler consolidation. Not crashes, not node failure, not OOMKills.

Without a PDB, draining a node evicts every Pod on it at once. With
`minAvailable: 1`, the drain blocks until it can proceed safely.

The trap: `minAvailable: 1` on a Deployment with `replicas: 1` means **a drain
can never complete**. Node maintenance hangs forever with no obvious
explanation. Either run 2 replicas or accept the disruption — say which you
chose.

## Summary

| | Scales | Needs | Use here |
|---|---|---|---|
| **HPA** | Pods | metrics-server | ✅ backend, worker |
| **VPA** | requests | VPA install | ✅ `Off` mode, as a measuring tool |
| **Cluster Autoscaler** | Nodes | cloud API | ❌ not available |
| **KEDA** | Pods, on events | KEDA install | ✅ worker on queue depth — see next file |
| **PDB** | nothing | — | ✅ backend, frontend |
