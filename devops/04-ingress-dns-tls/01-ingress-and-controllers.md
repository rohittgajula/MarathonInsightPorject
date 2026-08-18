# Ingress and ingress controllers

## The distinction that confuses everyone

**Ingress** is a Kubernetes object describing HTTP routing rules. It is *data*.
Applying it does nothing on its own.

**An ingress controller** is a Pod running a real reverse proxy (nginx, Traefik,
HAProxy, Envoy) that watches Ingress objects and reconfigures itself to match.

No controller installed → your Ingress sits there, `ADDRESS` column empty,
nothing happens, no error. This is the number one "my ingress doesn't work"
cause and it produces no diagnostic at all.

```bash
kubectl get pods -n ingress-nginx
```

If that's empty, install one before debugging anything else.

## Why not just LoadBalancer Services

A LoadBalancer Service per app means:

- One cloud load balancer each — real money, per Service, per month
- One IP each — one DNS record each
- TLS configured per Service
- No path routing at all — a Service can't send `/api` one place and `/` another

An Ingress gives you **one entry point, one IP, one certificate setup, many
routes**. For this project you need exactly that: `training.example.com/api`
→ backend, `training.example.com/` → frontend.

```
                    ┌──────────────────┐
   one IP ──────────▶ ingress controller│
                    └────────┬─────────┘
              reads Ingress rules
                     ┌───────┴────────┐
              /api ──▶ backend Service │
              /    ──▶ frontend Service│
                     └────────────────┘
```

## Choosing a controller

| Controller | Notes |
|---|---|
| **ingress-nginx** | The de facto standard. Enormous annotation surface, huge amount of writing about it, works everywhere. **Use this.** |
| **Traefik** | k3s ships it by default. Nice dashboard, good CRDs (IngressRoute). Fewer examples online. |
| **HAProxy / Envoy / Gateway API** | Gateway API is the successor to Ingress — better designed, role-separated, still maturing. Worth knowing it exists. |

Note: **k3s installs Traefik by default.** When you get to the VPS you either
use Traefik or disable it (`--disable traefik` at install) and install
ingress-nginx. Decide before installing k3s — swapping later means rewriting
your annotations, which are controller-specific.

Recommendation: **ingress-nginx everywhere**, so kind and k3s behave
identically. Dev/prod parity applies to infrastructure too.

## Your Ingress

Conceptually:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: runproject
  namespace: runproject
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"   # .fit uploads
spec:
  ingressClassName: nginx        # NOT the old kubernetes.io/ingress.class annotation
  tls:
    - hosts: [training.example.com]
      secretName: training-tls   # cert-manager creates this
  rules:
    - host: training.example.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend: {service: {name: backend, port: {number: 8000}}}
          - path: /admin
            pathType: Prefix
            backend: {service: {name: backend, port: {number: 8000}}}
          - path: /static
            pathType: Prefix
            backend: {service: {name: backend, port: {number: 8000}}}
          - path: /
            pathType: Prefix
            backend: {service: {name: frontend, port: {number: 8080}}}
```

You write the real one. Points that matter:

### Path ordering and specificity

ingress-nginx sorts by length, longest first — so `/api` wins over `/` and you
don't have to order them yourself. **Do not rely on this across controllers**;
it's implementation-specific. Order them longest-first in the file anyway, for
the human reading it.

### pathType

| Value | Meaning |
|---|---|
| `Prefix` | Path segment prefix. `/api` matches `/api/foo`, **not** `/apixyz`. |
| `Exact` | Exact match only |
| `ImplementationSpecific` | Controller decides. Avoid — it's how you get portable-looking config that isn't. |

`Prefix` matching on segments, not characters, is the useful subtlety.

### The four paths

- **`/api`** — your DRF API.
- **`/admin`** — Django admin. Consider whether this should be public at all;
  `08-operations/04` covers restricting it by source IP.
- **`/static`** — only needed if you serve static via Django/whitenoise (lab
  0.2). With whitenoise, these are served by gunicorn, so they route to backend.
- **`/`** — everything else to the frontend, whose nginx does the SPA fallback.

### Same-origin, and what it deletes

Because `/api` and `/` share `training.example.com`, the browser sees one
origin. Consequences:

- **No CORS.** `CORS_ALLOWED_ORIGINS` in `settings.py` becomes irrelevant. You
  can leave the middleware in, but it's doing nothing.
- **No mixed content risk.**
- **Cookies just work** — no `SameSite`/domain puzzles.
- `VITE_API_BASE=/api` — a relative path, so the bundle works on any hostname.
  The build-time-baking problem from `01-foundations/03` stops mattering,
  because the baked value is correct everywhere.

This is why `01-foundations/03` recommended same-origin. It removes four
separate classes of problem at once.

## Annotations you will need

ingress-nginx is configured almost entirely by annotation.

```yaml
# Uploads — a .fit file is a few MB; the default limit is 1m and produces
# a 413 that looks like a frontend bug.
nginx.ingress.kubernetes.io/proxy-body-size: "50m"

# Long requests — a Garmin sync or a FIT parse triggered synchronously.
# Defaults are 60s.
nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
nginx.ingress.kubernetes.io/proxy-send-timeout: "300"

# Force HTTPS (default true when a tls block exists, but be explicit)
nginx.ingress.kubernetes.io/ssl-redirect: "true"

# Rate limiting — cheap protection for a public endpoint
nginx.ingress.kubernetes.io/limit-rps: "20"

# Restrict the admin to your IP (put this on a SEPARATE Ingress for /admin)
nginx.ingress.kubernetes.io/whitelist-source-range: "203.0.113.5/32"
```

That last one needs its own Ingress object, since annotations apply to the whole
Ingress, not per-path. Two Ingresses for one host is fine and normal.

## The proxy header problem

Django is now behind a proxy. Without configuration it sees plain HTTP and
thinks the request is insecure:

- `request.is_secure()` → False
- `SECURE_SSL_REDIRECT` → redirect loop
- Generated absolute URLs → `http://`

`settings.py` does **not** set this. Add:

```python
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
```

**Only set these when actually behind a trusted proxy.** If anything can reach
gunicorn directly, a client can forge `X-Forwarded-Proto: https` and defeat your
security middleware. Inside the cluster, with only the ingress controller
reaching backend:8000, that's satisfied — and it's another argument for the
NetworkPolicy in `03-kubernetes/08`.

And `ALLOWED_HOSTS` must include your real hostname:

```
DJANGO_ALLOWED_HOSTS=training.example.com
```

Get it wrong and every request 400s with `DisallowedHost`. Note `settings.py`
does `os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")` — an unset variable
gives `[""]`, which allows nothing. Fails closed, which is the right behaviour,
but the error message won't obviously point at a missing env var.

## Ingress on kind

kind has no LoadBalancer, so getting traffic in needs setup **at cluster
creation time** — you cannot add it later without recreating the cluster.

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 80
        hostPort: 80
        protocol: TCP
      - containerPort: 443
        hostPort: 443
        protocol: TCP
```

Two things happening: the `ingress-ready=true` label is what the kind-specific
ingress-nginx manifest's nodeSelector looks for, and `extraPortMappings` bridges
your Mac's ports 80/443 into the node container.

Then install the kind-flavoured ingress-nginx (the standard one won't schedule
without that label), and add to `/etc/hosts`:

```
127.0.0.1 training.local
```

Now `https://training.local` on your Mac reaches the ingress. With a
self-signed cert and a browser warning — which is correct and expected. Full
walkthrough in `09-going-live/01`.

## Debugging

```bash
kubectl get ingress -n runproject
```
`ADDRESS` empty after a minute → no controller, or `ingressClassName` doesn't
match any installed class. Check `kubectl get ingressclass`.

```bash
kubectl describe ingress runproject -n runproject
```
Events show controller sync errors. Also shows the resolved backends — if a
backend shows `<error: endpoints "backend" not found>`, your Service name is
wrong or has no endpoints.

```bash
kubectl logs -n ingress-nginx deploy/ingress-nginx-controller -f
```
Every request, and every config reload. When a rule doesn't match, this tells
you what the controller actually decided.

```bash
kubectl exec -n ingress-nginx deploy/ingress-nginx-controller -- cat /etc/nginx/nginx.conf | grep -A20 training
```
The generated nginx config. The ground truth when annotations seem ignored.

### Symptom table

| Symptom | Usual cause |
|---|---|
| 404 from nginx | No rule matched. Host mismatch (check for a typo or a missing `host:`) or wrong path. |
| 503 | Rule matched, Service has **no ready endpoints**. `kubectl get endpoints`. |
| 502 | Reached a Pod, got garbage. Wrong `targetPort`, or the app isn't listening on the port you said. |
| 413 | `proxy-body-size`. |
| 504 | `proxy-read-timeout`. |
| Redirect loop | Missing `SECURE_PROXY_SSL_HEADER`. |
| `DisallowedHost` | `DJANGO_ALLOWED_HOSTS`. |
