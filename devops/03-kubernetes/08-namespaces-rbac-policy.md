# Namespaces, RBAC, and policy

## Namespaces

A naming and access boundary inside one cluster. Names must be unique within a
namespace, not across the cluster — so `dev/backend` and `prod/backend` coexist.

```bash
kubectl create namespace runproject
kubectl config set-context --current --namespace=runproject
```

That second command saves you typing `-n runproject` several hundred times.
Also: it will eventually make you run something destructive against the wrong
namespace because you forgot which one is current. Put the namespace in your
shell prompt (`kube-ps1`, or the built-in in oh-my-zsh's kubectl plugin).

**A namespace is not a security boundary by itself.** Pods in different
namespaces can still reach each other over the network by default. It becomes a
boundary when you add RBAC (who can act) and NetworkPolicy (what can connect).

### Your layout

```
runproject-dev     ← what you build first
runproject-prod    ← later, same manifests, different config
ingress-nginx      ← the ingress controller
cert-manager       ← cert-manager
monitoring         ← Prometheus, Grafana, Loki
kube-system        ← don't touch
```

Same manifests, different namespace and ConfigMap per environment. That's the
whole environment story on one cluster, and it's a perfectly good one to start
with. Separate *clusters* per environment is stronger isolation and twice the
cost; for a personal project namespaces are the right trade.

**What namespaces do not isolate:** node CPU and memory. A runaway dev worker
starves prod on the same node. `ResourceQuota` is how you fix that.

### ResourceQuota and LimitRange

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: dev-quota
  namespace: runproject-dev
spec:
  hard:
    requests.cpu: "2"
    requests.memory: 4Gi
    limits.cpu: "4"
    limits.memory: 8Gi
    persistentvolumeclaims: "5"
```

**A ResourceQuota has a sharp edge:** once one exists on a namespace, every Pod
must declare requests and limits, or creation is *rejected*. Suddenly-failing
deploys with `must specify limits.memory` is what that looks like.

`LimitRange` softens it by setting namespace defaults:

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: defaults
spec:
  limits:
    - type: Container
      default:            # becomes the limit if unset
        cpu: 500m
        memory: 512Mi
      defaultRequest:     # becomes the request if unset
        cpu: 100m
        memory: 128Mi
```

Use both: LimitRange for sane defaults, ResourceQuota for the ceiling.

## RBAC

Four objects, two axes:

```
        namespaced          cluster-wide
rules   Role                ClusterRole
bind    RoleBinding         ClusterRoleBinding
```

A **Role** lists permitted verbs on resources. A **RoleBinding** attaches it to
a subject (user, group, or ServiceAccount).

Note the useful hybrid: a **RoleBinding can reference a ClusterRole**, granting
those cluster-defined permissions within just one namespace. That's how you
reuse the built-in `edit` role per-namespace instead of writing your own.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: runproject
  name: deployer
rules:
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "list", "patch", "update"]
  - apiGroups: ["batch"]
    resources: ["jobs"]
    verbs: ["get", "list", "create", "delete"]
  - apiGroups: [""]
    resources: ["pods", "pods/log"]
    verbs: ["get", "list"]
```

Note `apiGroups: [""]` — the empty string is the core API group (Pods, Services,
ConfigMaps, Secrets). `apps` holds Deployments and StatefulSets, `batch` holds
Jobs. Getting the group wrong is the most common RBAC mistake and produces a
`forbidden` error that names the right resource, making it look like a verbs
problem.

### Where this matters for you: the CI ServiceAccount

Your GitHub Actions pipeline needs cluster credentials to deploy. **Do not give
it `cluster-admin`.** A leaked CI token with cluster-admin is total cluster
compromise; a leaked token that can only patch three Deployments in one
namespace is a bad afternoon.

Minimum for a push-based deploy:

- `apps/deployments`: get, list, patch — to update the image
- `batch/jobs`: get, list, create, delete — for migrations
- `pods`, `pods/log`: get, list — to read failure logs
- `apps/deployments/status`: get — for `rollout status`

Nothing on Secrets. Nothing cluster-wide. Nothing in other namespaces.

```bash
kubectl auth can-i --list --as=system:serviceaccount:runproject:ci
kubectl auth can-i delete secrets -n runproject --as=system:serviceaccount:runproject:ci
```

`auth can-i` is how you *verify* RBAC instead of hoping. Run it after every RBAC
change — it's the unit test for permissions.

### ServiceAccounts

Every Pod runs as one; unspecified, it's `default`, and its token is mounted
into the Pod at `/var/run/secrets/kubernetes.io/serviceaccount/`.

**Your app does not talk to the Kubernetes API.** So turn the token off:

```yaml
spec:
  automountServiceAccountToken: false
```

One line, and it removes an entire escalation path if the app is ever
compromised. Do it on all six workloads.

## NetworkPolicy

By default, **every Pod can reach every other Pod in the cluster.** Flat network,
no restrictions. A compromised frontend Pod can connect straight to Postgres.

NetworkPolicy is how you close that. The model:

- Policies are **allow-only**; there is no deny rule.
- A Pod with **no policy selecting it** allows everything.
- A Pod with **any policy selecting it** denies everything not explicitly
  allowed, *for the directions that policy mentions*.

That last clause catches people: a policy with only an `Ingress` section leaves
egress wide open. Specify `policyTypes` explicitly.

Sensible target for this app:

| From | To | Allow |
|---|---|---|
| ingress-nginx | frontend:8080, backend:8000 | ✅ |
| backend | db:5432, redis:6379 | ✅ |
| worker, beat | db:5432, redis:6379 | ✅ |
| backend, worker | internet:443 (Garmin, Anthropic, Gemini, Open-Meteo) | ✅ |
| frontend | anything internal | ❌ — it serves static files, it needs nothing |
| anything | db | ❌ except backend/worker/beat |

Two things that will catch you out:

**DNS.** Lock down egress and you block port 53 to CoreDNS, and *everything*
breaks in a way that looks like a total network failure. Every egress policy
needs:

```yaml
- to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
  ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
```

**The CNI must support it.** Calico and Cilium do. **kind's default kindnet
does not** — policies apply silently and enforce nothing. So you can write them
on kind and get false confidence. To actually test, create the kind cluster with
`disableDefaultCNI: true` and install Calico.

Given that: write NetworkPolicies when you get to the VPS (k3s ships Flannel;
same caveat — you'd add Calico). It's a genuinely valuable exercise, but do it
knowing whether it's being enforced.

## Pod Security Standards

Replaced PodSecurityPolicy (removed in 1.25). Three levels, applied by
namespace label:

```yaml
metadata:
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/warn: restricted
```

| Level | Allows |
|---|---|
| `privileged` | Everything |
| `baseline` | Blocks known escalations (hostNetwork, privileged, hostPath) |
| `restricted` | + must run non-root, drop ALL capabilities, seccomp profile, no privilege escalation |

**Target `restricted`.** Your images from lab 0 already run non-root, so you're
most of the way there. The remaining requirements:

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true      # see below
  capabilities:
    drop: ["ALL"]
  seccompProfile:
    type: RuntimeDefault
```

`readOnlyRootFilesystem: true` is the one that requires thought. Django writes
nothing to the root filesystem in normal operation, but Python may want
`/tmp`, and gunicorn wants a heartbeat directory. Mount `emptyDir` at `/tmp`
and pass `--worker-tmp-dir /dev/shm` to gunicorn.

Start with `warn` before `enforce`. You get told what would break without
anything actually breaking.
