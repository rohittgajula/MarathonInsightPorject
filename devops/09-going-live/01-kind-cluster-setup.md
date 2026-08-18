# Setting up the kind cluster

Your laptop cluster. Everything through section 08 runs here, free.

## Install

```bash
brew install kind kubectl helm kustomize
brew install derailed/k9s/k9s     # optional, excellent
```

Docker Desktop must be running — kind's "nodes" are Docker containers.

Give Docker Desktop **at least 6 GB of RAM** in its settings. The default 2 GB
will not run six workloads plus an ingress controller plus Postgres, and the
failure mode is Pods being `Evicted` seemingly at random, which is a miserable
thing to debug.

## The cluster config

`kind-config.yaml` — and read this carefully, because **two of these settings
cannot be added after the cluster exists.**

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: runproject
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"     # ← required for ingress-nginx
    extraPortMappings:
      - containerPort: 80
        hostPort: 80
        protocol: TCP
      - containerPort: 443
        hostPort: 443
        protocol: TCP
```

**`ingress-ready=true`** — the kind-specific ingress-nginx manifest has a
`nodeSelector` looking for this label. Without it, the controller Pod sits
`Pending` forever.

**`extraPortMappings`** — bridges your Mac's ports 80/443 into the node
container. Without it, nothing you do can reach the ingress from a browser.

Both are cluster-creation-time only. Get them wrong and you delete and recreate.

```bash
kind create cluster --config kind-config.yaml
kubectl cluster-info --context kind-runproject
kubectl get nodes
```

### Single node or multi?

**Start single-node.** It matches your eventual k3s VPS, and it sidesteps the
RWO media-volume constraint from `03-kubernetes/05`.

A multi-node config is worth creating **once**, later, specifically to *see*
the RWO problem happen — a Pod stuck `Pending` with `volume node affinity
conflict` because its PVC lives on another node. Experiencing that once teaches
you more than the paragraph explaining it.

## Ingress controller

Use the **kind-specific** manifest, not the generic one:

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=180s
```

The kind variant sets the `ingress-ready` nodeSelector and uses `hostPort`
instead of a LoadBalancer Service. The generic manifest creates a
`type: LoadBalancer` Service that stays `<pending>` forever, because kind has
nothing to provision one.

## metrics-server

Needed for `kubectl top` and HPA:

```bash
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
helm install metrics-server metrics-server/metrics-server -n kube-system \
  --set 'args={--kubelet-insecure-tls}'
```

`--kubelet-insecure-tls` is required on kind because kubelet serving certs
aren't signed by the cluster CA. **Never do this on a real cluster** — it
disables verification of the kubelet's identity.

```bash
kubectl top nodes     # takes ~60s after install to report
```

## cert-manager

```bash
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager \
  -n cert-manager --create-namespace --set crds.enabled=true
```

Locally, use a `selfSigned` ClusterIssuer. Let's Encrypt cannot validate a
laptop — HTTP-01 requires their servers to reach your host from the public
internet. Browser warnings on self-signed certs are expected and correct.

## KEDA

```bash
helm repo add kedacore https://kedacore.github.io/charts
helm install keda kedacore/keda -n keda --create-namespace
```

## Hosts file

```bash
sudo sh -c 'echo "127.0.0.1 training.local" >> /etc/hosts'
```

Use `.local` or `.test`. **Not `.dev` or `.app`** — those are real TLDs with
HSTS preloaded into browsers, so Chrome will force HTTPS and refuse to let you
click through a self-signed warning. You'd spend an hour on it.

## Getting images into the cluster

Two options while developing:

**`kind load` — no registry needed**
```bash
docker build --target prod -t runproject-backend:dev ./backend
kind load docker-image runproject-backend:dev --name runproject
```
Copies straight from your Docker daemon into the node. Fast, offline, no auth.

Set `imagePullPolicy: IfNotPresent` in your manifests — with `Always`,
Kubernetes tries to pull from a registry, fails, and ignores the loaded image.
This is a common and confusing failure.

**A registry** — what production actually does. Switch to `ghcr.io` before
writing CI, so you exercise the real path including `imagePullSecret`.

Use `kind load` for the first few labs so you're not debugging registry auth
while learning Deployments. Switch at Lab 6 or so.

## Daily workflow

```bash
# start
docker ps | grep kind || kind create cluster --config kind-config.yaml

# rebuild and redeploy after a code change
docker build --target prod -t runproject-backend:dev ./backend
kind load docker-image runproject-backend:dev --name runproject
kubectl rollout restart deploy/backend -n runproject
kubectl rollout status deploy/backend -n runproject

# watch
k9s -n runproject
```

**`kubectl rollout restart` is the key trick** with a fixed tag: the image
changed but the spec didn't, so Kubernetes has nothing to reconcile
(`02-containers/01`). `rollout restart` stamps an annotation, changing the spec,
forcing a roll.

## Resetting

```bash
kubectl delete namespace runproject          # everything in it
kind delete cluster --name runproject        # everything, full stop
```

**Deleting a namespace does not always delete PVCs cleanly**, and a namespace
stuck `Terminating` is usually a finalizer on something. `kind delete cluster`
is the reliable nuclear option, and on a laptop cluster there's no reason not to
use it.

Recreating from scratch and getting a working cluster back in ten minutes is a
good sign your manifests are complete. **Do it deliberately once** — it's a free
disaster-recovery drill and it will find the thing you configured by hand and
forgot to write down.

## Common problems

| Symptom | Cause |
|---|---|
| Pods `Pending`, `insufficient memory` | Docker Desktop RAM too low |
| ingress-nginx `Pending` | Missing `ingress-ready=true` label |
| `https://training.local` refuses | Missing `extraPortMappings` |
| `kubectl top` → "Metrics API not available" | metrics-server missing or lacks `--kubelet-insecure-tls` |
| PVC `Pending` forever | Normal on kind until a Pod mounts it (`WaitForFirstConsumer`) |
| `ErrImageNeverPull` / `ImagePullBackOff` on a loaded image | `imagePullPolicy: Always` — set `IfNotPresent` |
| Everything slow, fans loud | Six workloads on a laptop. Scale replicas to 1 locally. |

## Cost

Free. Uses maybe 4 GB of RAM while running.

Stop it when you're not using it:
```bash
docker stop runproject-control-plane
docker start runproject-control-plane
```
The cluster survives a stop/start, unlike a `kind delete`.
