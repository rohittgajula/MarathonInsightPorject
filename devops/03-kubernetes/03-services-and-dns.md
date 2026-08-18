# Services and cluster DNS

## The problem Services solve

Pods are cattle. They get created, killed, rescheduled, and each time they get a
new IP from the CNI's pool. Nothing can hardcode a Pod IP.

A **Service** is a stable virtual IP and DNS name in front of a changing set of
Pods, selected by label.

```
                    Service: backend
                    ClusterIP: 10.96.14.7      ← never changes
                    port: 8000
                          │
              selector: app=backend
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
   Pod 10.244.1.7   Pod 10.244.2.3   Pod 10.244.1.9
                             ▲
                   these change constantly
```

## The virtual IP is not a real thing

Nothing listens on 10.96.14.7. There is no interface with that address. It is an
iptables (or IPVS) rule that kube-proxy programs on every node: *packets to
10.96.14.7:8000 get DNAT'd to one of the current endpoint IPs.*

Consequences that trip people up:

- **You cannot ping a ClusterIP.** No ICMP rule exists. It's not down.
- **Load balancing is per-connection, not per-request.** With HTTP keep-alive,
  one client's connection pins to one Pod for its lifetime. A client that opens
  one connection and holds it will hit exactly one backend Pod regardless of how
  many replicas you run. This surprises people load-testing with `ab -k`.
- **The Service works even from a node with no matching Pod.** The rules are on
  every node.

## Endpoints — your best debugging tool

```bash
kubectl get endpoints backend -n runproject
kubectl get endpointslices -n runproject      # the modern equivalent
```

```
NAME      ENDPOINTS                             AGE
backend   10.244.1.7:8000,10.244.2.3:8000       5m
```

**A Pod appears here only if it matches the selector AND passes its readiness
probe.** So:

| ENDPOINTS shows | Means |
|---|---|
| Correct IPs | Service is fine; look elsewhere |
| `<none>` | Selector doesn't match any Pod's labels, or no Pod is Ready |

That single distinction resolves most "my service returns 503". Check it first,
every time.

## Service types

### ClusterIP (default)

Reachable only inside the cluster. **This is what almost everything should be.**
Your `db`, `redis`, `backend`, `frontend` are all ClusterIP; only the ingress
controller needs an external address.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: backend
  namespace: runproject
spec:
  type: ClusterIP
  selector:
    app: backend           # must match the POD labels, not the Deployment's name
  ports:
    - name: http
      port: 8000           # the Service's port
      targetPort: http     # the container's port — by NAME, not number
```

Using `targetPort: http` (the named port from the Deployment) rather than `8000`
means changing the container's port is a one-line edit in one file. Small thing,
compounds.

### Headless (`clusterIP: None`)

No virtual IP. DNS returns the Pod IPs directly, one A record per Pod.

Needed for StatefulSets, where you want to address `db-0` specifically rather
than "any database Pod". Your Postgres StatefulSet needs one.

### NodePort

Opens the same high port (30000–32767) on **every** node, forwarding to the
Service. Crude. Useful on kind for a quick check; not how you expose anything
real. Fixed weird port numbers, no TLS, no host routing.

### LoadBalancer

Asks the infrastructure for an external IP. On a cloud you get a real load
balancer (and a real monthly bill, per Service). On kind you get `<pending>`
forever, because there is nothing to provision one — this is expected, not
broken. On k3s you get **klipper-lb**, which just binds the port on the host.

The reason you use an **Ingress** instead: one LoadBalancer, many hostnames and
paths behind it. One IP, one cert setup, N services.

### ExternalName

DNS CNAME to something outside. If you ever move to a managed Postgres, an
ExternalName Service called `db` means `DATABASE_URL` never changes.

## Cluster DNS

CoreDNS gives every Service a name:

```
<service>.<namespace>.svc.cluster.local
```

Every Pod's `/etc/resolv.conf` has a search path, so from a Pod in `runproject`:

| You write | Resolves |
|---|---|
| `db` | `db.runproject.svc.cluster.local` |
| `db.runproject` | same |
| `db.runproject.svc.cluster.local` | same, fully qualified |

**This is why the port from compose is easy.** Your settings already say:

```python
DATABASE_URL = "postgres://runproject:runproject@db:5432/runproject"
CELERY_BROKER_URL = "redis://redis:6379/0"
```

Name the Kubernetes Services `db` and `redis` and **these strings do not
change**. Compose's user-defined bridge network already gave you DNS by service
name; Kubernetes gives you the same contract. That is not a coincidence — it's
why compose is decent preparation.

The one gotcha: the trailing search-domain expansion means a lookup for an
external host like `api.anthropic.com` first tries
`api.anthropic.com.runproject.svc.cluster.local`, then `.svc.cluster.local`,
then `.cluster.local`, before succeeding on the fifth try. Five extra DNS
queries per outbound call. If the Gemini/Claude calls feel slow in-cluster,
that's the cause; `dnsConfig.options.ndots: "1"` on the Pod fixes it.

## Testing DNS and connectivity from inside

You cannot curl a ClusterIP from your Mac. Get into the cluster:

```bash
kubectl run -it --rm debug --image=nicolaka/netshoot --restart=Never -n runproject -- bash
```

`netshoot` has dig, curl, nc, tcpdump, ss — everything. Then:

```bash
dig backend.runproject.svc.cluster.local
nc -zv db 5432
curl -sv http://backend:8000/api/health/
```

Learn this Pod. It is the single most useful debugging tool in Kubernetes and
it costs nothing when not running.

For a quick look from your laptop instead, port-forward:

```bash
kubectl port-forward svc/backend 8000:8000 -n runproject
```

Then `localhost:8000` on your Mac reaches the Service. Note this **bypasses the
ingress entirely** — great for isolating "is the app broken or is the ingress
broken", useless for testing ingress rules or TLS.

## Your Services

| Service | Type | Port | Notes |
|---|---|---|---|
| `backend` | ClusterIP | 8000 | Ingress routes `/api` and `/admin` here |
| `frontend` | ClusterIP | 8080 | Ingress routes `/` here |
| `db` | Headless | 5432 | StatefulSet needs stable per-Pod DNS |
| `redis` | ClusterIP | 6379 | |
| `worker` | **none** | — | Pulls from Redis. Nothing connects *to* it. |
| `beat` | **none** | — | Same. |

**Worker and beat get no Service, and that's the point.** A Service exists to
receive traffic. These two only make outbound connections — to Redis for the
queue, to Postgres, to Garmin, to the LLM API. Writing a Service for them is a
reflex worth resisting; noticing they don't need one means you understand what a
Service is for.
