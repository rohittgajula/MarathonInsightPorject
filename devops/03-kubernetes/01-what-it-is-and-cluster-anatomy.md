# What Kubernetes actually does, and what it's made of

## The one idea

You describe the state you want. Controllers continuously compare that to
reality and act to close the gap. Forever.

```
        ┌──────────────────────────────────────┐
        │  desired state (your YAML, in etcd)  │
        └──────────────────┬───────────────────┘
                           │  compare
        ┌──────────────────▼───────────────────┐
        │  actual state (what's running)       │
        └──────────────────┬───────────────────┘
                           │  act to close the gap
                           └──────────► repeat, forever
```

Nothing in Kubernetes is a command. You never "start a Pod". You record that a
Pod *should exist*, and a controller notices it doesn't, and creates it. Delete
a Pod that a Deployment owns and it comes back — not because deletion failed,
but because you changed reality, not desire.

Get this and Kubernetes becomes predictable. Miss it and it feels haunted.

The practical corollaries:

- **`kubectl apply` is not "deploy".** It is "record this desired state." What
  happens next is the controller's business.
- **If the spec doesn't change, nothing happens.** This is why `:latest` doesn't
  redeploy (see `02-containers/01`).
- **Nothing is manual and permanent.** Hand-edit a running Pod and the next
  reconcile or restart discards it. Fix things in the manifest, always.

## What it buys you over docker compose

Your compose file already does multi-container orchestration, dependency
ordering, health checks and volumes. Honestly, for one app on one machine,
compose is fine. Be clear-eyed about what you're actually gaining:

| Capability | compose | Kubernetes |
|---|---|---|
| Restart a crashed container | ✅ | ✅ |
| Multiple replicas | awkward | native |
| Rolling update, zero downtime | ✗ | native |
| Rollback to previous version | ✗ | `kubectl rollout undo` |
| Autoscale on load | ✗ | HPA |
| Spread across machines | ✗ | native |
| Reschedule when a machine dies | ✗ | native |
| Declarative config + secrets | partial | native |
| Self-healing on failed health check | restart only | restart, reschedule, remove from load balancer |

And what it costs: a control plane to run, a much larger vocabulary, YAML by the
hundred lines, and a genuinely harder debugging story.

**For this app specifically, at one user, k8s is over-engineering** — and that's
fine, because you said the goal is to learn DevOps. Just don't confuse "I
learned Kubernetes" with "this app needed Kubernetes". Knowing when *not* to
reach for it is part of the skill.

## Cluster anatomy

```
┌─────────────────────── CONTROL PLANE ────────────────────────┐
│                                                              │
│   kube-apiserver ◀── the only door. everything talks here    │
│         │                                                    │
│         ├── etcd                  all cluster state          │
│         ├── kube-scheduler        which node gets this Pod   │
│         └── controller-manager    the reconcile loops        │
│                                                              │
└──────────────────────────┬───────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   ┌─────────┐       ┌─────────┐        ┌─────────┐
   │ NODE 1  │       │ NODE 2  │        │ NODE 3  │
   │ kubelet │       │ kubelet │        │ kubelet │
   │ kube-   │       │ kube-   │        │ kube-   │
   │  proxy  │       │  proxy  │        │  proxy  │
   │containerd│      │containerd│       │containerd│
   │ ┌─────┐ │       │ ┌─────┐ │        │ ┌─────┐ │
   │ │ Pod │ │       │ │ Pod │ │        │ │ Pod │ │
   │ └─────┘ │       │ └─────┘ │        │ └─────┘ │
   └─────────┘       └─────────┘        └─────────┘
```

### Control plane parts

**kube-apiserver** — the only component anything talks to. `kubectl`, the
kubelets, the controllers, your CI. It validates requests, enforces RBAC, and
persists to etcd. Everything else is stateless and could be restarted freely.

**etcd** — a distributed key-value store holding *all* cluster state. **This is
the thing to back up.** Lose etcd and you have lost your cluster, though not
your PVCs' data. On k3s it's SQLite by default, which is simpler and perfectly
adequate for one node.

**kube-scheduler** — watches for Pods with no node assigned, picks one. Filters
first (does it have enough CPU/RAM? do node selectors and taints allow it? are
the required volumes attachable there?) then scores the survivors. A Pod stuck
`Pending` means the filter stage eliminated every node — and `kubectl describe
pod` tells you which filter, in plain English.

**kube-controller-manager** — a bundle of reconcile loops. The Deployment
controller, ReplicaSet controller, Node controller, and about thirty others,
each watching one resource type and doing one job.

### Node parts

**kubelet** — the agent on each machine. Asks the API server "what should run
here?", tells containerd to run it, reports status back, runs your liveness and
readiness probes. If kubelet dies, the node goes `NotReady` and after a grace
period its Pods are rescheduled elsewhere.

**kube-proxy** — makes Services work. Programs iptables (or IPVS) so that
traffic to a Service's virtual IP is DNAT'd to one of its Pod IPs. This is why
a Service IP doesn't answer ping and has nothing listening on it — it isn't a
real interface, it's a routing rule.

**containerd** — actually runs containers. (Docker was deprecated as a k8s
runtime in 1.20 and removed in 1.24; it was always a wrapper around containerd
for this purpose. Your images are unaffected — they're OCI images, not "Docker
images", and always were.)

### Add-ons that aren't optional in practice

**CoreDNS** — in-cluster DNS. Without it nothing resolves `db` and everything
breaks in a way that looks like a database outage.

**CNI plugin** — the network layer giving each Pod a routable IP (Calico,
Cilium, Flannel; kind ships kindnet, k3s ships Flannel). The rule it must
satisfy: **every Pod can reach every other Pod directly, no NAT.** That flat
network is why you never do port mapping between Pods.

**metrics-server** — collects CPU/memory from kubelets. `kubectl top` and HPA
both depend on it, and **neither kind nor a bare cluster ships it**. You will
install it in `05-autoscaling`. On kind it needs `--kubelet-insecure-tls`
because the kubelet serving certs aren't signed by the cluster CA.

## Distributions

| | What | Use |
|---|---|---|
| **kind** | Cluster nodes as Docker containers on your laptop | Learning, CI. **Start here.** |
| **minikube** | A VM (or Docker) with a cluster in it | Same role; heavier, more built-in add-ons |
| **k3s** | Full but trimmed k8s, one ~60 MB binary, SQLite instead of etcd | **Your VPS.** Genuinely production-capable |
| **GKE/EKS/AKS** | Cloud runs the control plane | Real jobs. Teaches cloud, hides cluster internals |

The plan is kind → k3s. kind teaches you objects safely; k3s teaches you what
running a control plane involves, without a cloud bill.

## Your first ten minutes with a cluster

```bash
kubectl cluster-info
kubectl get nodes -o wide
kubectl get pods -A
```

That last one shows the system Pods — CoreDNS, kube-proxy, the CNI. Read the
list. Those are the pieces above, running as Pods, in `kube-system`. Kubernetes
runs itself on itself, which is either elegant or alarming depending on your
mood.

```bash
kubectl api-resources
```

Every object type the cluster knows, with its short name and whether it's
namespaced. Come back to this when you install cert-manager and suddenly have
`Certificate` and `ClusterIssuer` types that weren't there before — that's what
a CRD is.

```bash
kubectl explain deployment.spec.template.spec.containers
```

**The offline documentation.** Full field reference for any object, from the
cluster's own schema, no internet needed. On a train with no signal this is your
API reference. Learn to use it now.
