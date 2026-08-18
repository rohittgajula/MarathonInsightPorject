# Glossary

Defined once, used everywhere. Alphabetical within each group.

## Containers

**Image** — a read-only filesystem snapshot plus metadata (entrypoint, env,
exposed ports). Built once, run many times. Not running.

**Container** — a running instance of an image, with a thin writable layer on
top. Delete it and that writable layer goes with it.

**Layer** — one filesystem diff produced by one Dockerfile instruction. Cached
individually, which is why instruction order controls rebuild speed.

**Registry** — where images live between build and run. Docker Hub, GitHub
Container Registry (`ghcr.io`), or one your cloud runs.

**Tag** — a human label pointing at an image (`myapp:v1.2`). Mutable — `:latest`
can point at a different image tomorrow, which is exactly why you should not
deploy `:latest`.

**Digest** — `sha256:abc…`, the immutable content hash. The only truly
reproducible way to name an image.

**Multi-stage build** — a Dockerfile with several `FROM` lines where early
stages compile and the last stage copies only the artifacts. Turns a 1.2 GB
build image into a 40 MB runtime image.

## Kubernetes objects

**Pod** — the smallest deployable unit: one or more containers sharing a
network namespace (same IP, they reach each other on `localhost`) and
optionally volumes. Almost always you run one real container per Pod.

**ReplicaSet** — keeps N identical Pods running. You rarely write one.

**Deployment** — manages ReplicaSets to give you rolling updates and rollback.
This is what you write for stateless workloads. Backend, worker, beat, frontend.

**StatefulSet** — like a Deployment but Pods get stable names (`db-0`, `db-1`),
stable storage, and ordered startup. For Postgres.

**DaemonSet** — one Pod per node. For log collectors, node exporters.

**Job** — runs Pods until N complete successfully, then stops. For migrations.

**CronJob** — creates Jobs on a schedule.

**Service** — a stable virtual IP and DNS name in front of a changing set of
Pods. Pods die and get new IPs constantly; the Service name does not change.

**Ingress** — HTTP(S) routing rules: host + path → Service. Just data; an
**ingress controller** (nginx, Traefik) is the thing that reads it and actually
proxies traffic.

**ConfigMap** — non-secret key/value config, injected as env vars or files.

**Secret** — same shape, base64-encoded, and *only* base64 — not encrypted at
rest by default. Treat as "slightly hidden", not "safe".

**PersistentVolumeClaim (PVC)** — a request for storage. **PersistentVolume
(PV)** — the actual storage that satisfies it. **StorageClass** — the recipe
for provisioning PVs on demand.

**Namespace** — a naming and access boundary inside one cluster. Not a security
boundary on its own.

**Label** — arbitrary key/value on an object. **Selector** — a query over
labels. This pairing is how a Service finds its Pods; get it wrong and you get
a Service with zero endpoints and a very confusing 503.

**Annotation** — like a label but not selectable; used to pass config to
controllers (cert-manager, ingress-nginx read theirs from annotations).

## Cluster anatomy

**Control plane** — the brain. `kube-apiserver` (the only thing anything talks
to), `etcd` (the database holding all state), `kube-scheduler` (decides which
node a Pod lands on), `kube-controller-manager` (the reconcile loops).

**Node** — a machine that runs Pods. Runs `kubelet` (talks to the API server,
starts containers), `kube-proxy` (implements Service routing), and a container
runtime (containerd).

**Reconciliation loop** — the core idea of Kubernetes: you declare desired
state, controllers continuously compare it to actual state and act to close the
gap. Nothing is imperative; you never "start" a Pod, you declare it should
exist.

## Scaling

**HPA** — Horizontal Pod Autoscaler. More Pods when a metric rises.

**VPA** — Vertical Pod Autoscaler. Bigger Pods (more CPU/RAM).

**Cluster Autoscaler** — more *nodes* when Pods can't be scheduled.

**KEDA** — event-driven autoscaling; scales on queue depth, not just CPU. The
one that matters for the Celery worker.

**Request** — the CPU/RAM a container is guaranteed and scheduled against.
**Limit** — the ceiling before throttling (CPU) or being killed (memory).

**PodDisruptionBudget (PDB)** — "never voluntarily take more than N of these
down at once."

## Networking, DNS, TLS

**A record** — name → IPv4. **AAAA** — name → IPv6. **CNAME** — name → another
name. **TTL** — how long resolvers may cache the answer.

**Cluster DNS (CoreDNS)** — in-cluster resolver. `backend.runproject.svc.cluster.local`
resolves to the backend Service's virtual IP.

**TLS termination** — where encryption stops. Usually the ingress controller;
traffic behind it is plain HTTP inside the cluster.

**ACME / Let's Encrypt** — the protocol and the free CA that issue certs after
you prove you control the domain. **cert-manager** automates it in-cluster.

## CI/CD

**CI** — Continuous Integration: on every push, build and test. Catches breakage
early.

**CD** — Continuous Delivery (always *releasable*) or Deployment (actually
released automatically). Most people mean the latter.

**Pipeline / workflow** — the automated sequence. In GitHub Actions: a workflow
of jobs, each of steps, running on a runner.

**Push-based deploy** — CI has cluster credentials and runs `kubectl apply`.
Simple, but your CI holds the keys to production.

**GitOps / pull-based** — an agent *in* the cluster (Argo CD, Flux) watches a
git repo and applies what it finds. CI never touches the cluster. Git is the
single source of truth and `git revert` is a rollback.

**Artifact** — what a build produces and later stages consume. Here, a container
image.

**Immutable tag** — tagging images by commit SHA instead of `latest`, so a
deploy names exactly one build forever.

## Operations

**Observability** — logs (what happened), metrics (how much, over time), traces
(where the time went in one request).

**SLI / SLO** — the measurement (99.2% of requests under 300ms) and the target
you commit to.

**Runbook** — written steps for a known failure. Written *before* the failure.

**RTO / RPO** — how long you may be down, and how much data you may lose.
Backups are meaningless numbers until you name these two.
