# Flow: a request, end to end

What happens when you open `https://training.example.com/api/dashboard`, and
how to test each hop when it breaks.

```
┌────────────────────────────────────────────────────────────────────┐
│ 1. BROWSER                                                         │
│    needs an IP for training.example.com                            │
└──────────────────────────┬─────────────────────────────────────────┘
                           │  dig training.example.com +short
┌──────────────────────────▼─────────────────────────────────────────┐
│ 2. DNS                                                             │
│    stub → recursive resolver → root → .com → your NS               │
│    ← A 203.0.113.42                              (cached per TTL)  │
└──────────────────────────┬─────────────────────────────────────────┘
                           │  curl -v https://training.example.com/
┌──────────────────────────▼─────────────────────────────────────────┐
│ 3. TCP + TLS to 203.0.113.42:443                                   │
│    ClientHello carries SNI: training.example.com                   │
│    ingress-nginx picks the cert for that name and terminates TLS   │
│    ── everything past this point is plain HTTP ──                  │
└──────────────────────────┬─────────────────────────────────────────┘
                           │  kubectl get ingress -n runproject
┌──────────────────────────▼─────────────────────────────────────────┐
│ 4. INGRESS RULES                                                   │
│    host matches? path matches?                                     │
│      /api    → backend:8000     ← this request                     │
│      /admin  → backend:8000                                        │
│      /static → backend:8000                                        │
│      /       → frontend:8080                                       │
│    no match → 404 from nginx                                       │
└──────────────────────────┬─────────────────────────────────────────┘
                           │  kubectl get endpoints backend -n runproject
┌──────────────────────────▼─────────────────────────────────────────┐
│ 5. SERVICE  backend  ClusterIP 10.96.14.7:8000                     │
│    kube-proxy iptables DNAT → one READY endpoint                   │
│    no ready endpoints → 503                                        │
└──────────────────────────┬─────────────────────────────────────────┘
                           │  kubectl get pods -n runproject
┌──────────────────────────▼─────────────────────────────────────────┐
│ 6. POD  10.244.1.7:8000                                            │
│    gunicorn master → one of 3 workers                              │
│    wrong targetPort / nothing listening → 502                      │
└──────────────────────────┬─────────────────────────────────────────┘
                           │  kubectl logs -n runproject -l app=backend
┌──────────────────────────▼─────────────────────────────────────────┐
│ 7. DJANGO                                                          │
│    ALLOWED_HOSTS check          → 400 DisallowedHost               │
│    SecurityMiddleware           → redirect loop if no proxy header │
│    CORS (no-op: same origin)                                       │
│    URL resolve → DRF view                                          │
│    TokenAuthentication          → 401 / 403                        │
└──────────────────────────┬─────────────────────────────────────────┘
                           │  kubectl get endpoints db -n runproject
┌──────────────────────────▼─────────────────────────────────────────┐
│ 8. POSTGRES                                                        │
│    CoreDNS: db → 10.96.x.x → db-0 → 5432                           │
│    conn_max_age=600, so the connection is reused                   │
└──────────────────────────┬─────────────────────────────────────────┘
                           │
                    response back up the same path
```

## Testing each hop in isolation

```bash
# 2. DNS only
dig @1.1.1.1 training.example.com +short

# 3. TLS only
echo | openssl s_client -connect training.example.com:443 \
  -servername training.example.com 2>/dev/null | openssl x509 -noout -dates -issuer

# 4. ingress rules
kubectl describe ingress runproject -n runproject
kubectl logs -n ingress-nginx deploy/ingress-nginx-controller --tail=20

# 5. Service — the highest-yield check
kubectl get endpoints -n runproject

# 6. bypass the ingress entirely
kubectl port-forward svc/backend 8000:8000 -n runproject
curl localhost:8000/api/health/

# 7. app logs
kubectl logs -n runproject -l app=backend --tail=50

# 8. from inside the cluster
kubectl run -it --rm net --image=nicolaka/netshoot --restart=Never -n runproject -- \
  sh -c 'nc -zv db 5432 && curl -s http://backend:8000/api/health/'
```

**The port-forward at step 6 is the key diagnostic.** It bypasses DNS, TLS, the
ingress, and the Service's external path. Works → the problem is in hops 2–5.
Fails → the problem is the Pod or the app.

## Where each error comes from

```
DNS fails ─────────────── "could not resolve host"
Firewall blocks ───────── connection timeout
Nothing listening ─────── connection refused
Cert wrong/expired ────── browser TLS warning
No ingress rule match ─── 404, page says "nginx"
No ready endpoints ────── 503
Wrong targetPort ──────── 502
Upstream slow ─────────── 504   (proxy-read-timeout)
Body too big ──────────── 413   (proxy-body-size)
ALLOWED_HOSTS ─────────── 400 DisallowedHost
Missing proxy header ──── infinite redirect
App exception ─────────── 500
```

## The static-asset path

A different journey, and where the SPA fallback matters:

```
GET /                     → ingress → frontend Service → nginx
                          → /usr/share/nginx/html/index.html
                            Cache-Control: no-cache

GET /assets/index-a3f9.js → nginx → the hashed file
                            Cache-Control: max-age=31536000, immutable

GET /activities/42        → nginx: no such file
                          → try_files … /index.html
                          → SPA boots, React Router renders the route
                            WITHOUT the fallback this is a 404 on refresh

GET /api/dashboard        → ingress matches /api FIRST (longer prefix)
                          → backend, never reaches the frontend
```

## The async path

Not every request ends at a response:

```
POST /api/logs/  → backend → writes DailyLog → queues a Celery task
                 → 201 immediately         ← user is not waiting
                          │
                          ▼
                    redis LIST "celery"
                          │
                          ▼
                     worker Pod
                          │
              ai_extract.analyse() → Anthropic / Gemini
                          │
                    ┌─────┴─────┐
                 success    RateLimited
                    │           │
              write chips   leave unread
                                │
                       beat: sweep_unread every 10 min
                                │
                            retry ─────┘
```

**Nothing in this path is visible to the request flow above.** A worker that is
down, or an LLM quota that is spent, produces a perfectly healthy-looking web
app that quietly stops reading logs. That's exactly why `08-operations/01`
argues for metrics on extraction status and queue depth — the request path
can't tell you.
