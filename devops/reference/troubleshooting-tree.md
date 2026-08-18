# Troubleshooting decision tree

Start at the symptom. Follow the arrows. Don't guess a layer — test it.

## The site doesn't load

```
curl -I https://training.example.com/
│
├─ "could not resolve host"
│     └─▶ DNS.  dig @1.1.1.1 training.example.com
│            ├─ no answer      → record missing, or wrong nameservers
│            │                   dig example.com NS +short
│            └─ wrong IP       → typo, or a stale cache (TTL)
│
├─ connection TIMED OUT
│     └─▶ FIREWALL. Packets dropped.
│            ├─ ufw allow 80,443?
│            ├─ provider firewall too? (both must allow)
│            └─ is the VPS even up?
│
├─ connection REFUSED
│     └─▶ Nothing listening. kubectl get pods -n ingress-nginx
│            ├─ no controller  → install it
│            └─ Pending        → kind: missing ingress-ready label
│
├─ TLS error / warning
│     └─▶ kubectl get certificate -A
│            ├─ READY False    → describe challenge (see below)
│            ├─ expired        → renewal broke; check cert-manager logs
│            └─ wrong name     → cert doesn't cover this hostname
│
├─ 404 (page says nginx)
│     └─▶ No ingress rule matched.
│            kubectl describe ingress runproject
│            ├─ host typo?
│            ├─ path typo?
│            └─ ingressClassName matches an installed class?
│
├─ 503
│     └─▶ kubectl get endpoints -n runproject     ← THE CHECK
│            ├─ <none>  → selector mismatch, OR no Pod passing readiness
│            │             kubectl get pods        (0/1 Ready?)
│            │             kubectl describe pod    (probe error)
│            └─ has IPs → transient; check controller logs
│
├─ 502
│     └─▶ Reached a Pod, got garbage.
│            ├─ Service targetPort wrong?
│            ├─ app listening on a different port?
│            └─ app crashed mid-request? check logs
│
├─ 504  → nginx.ingress.kubernetes.io/proxy-read-timeout
├─ 413  → nginx.ingress.kubernetes.io/proxy-body-size   (.fit uploads)
│
├─ 400 DisallowedHost
│     └─▶ DJANGO_ALLOWED_HOSTS missing the hostname.
│         Note: unset → [""] → allows nothing.
│
├─ infinite redirect
│     └─▶ SECURE_PROXY_SSL_HEADER not set in settings.py
│
└─ 500
      └─▶ A real app error. kubectl logs -l app=backend --tail=100
```

## A Pod won't start

```
kubectl get pods -n runproject
│
├─ Pending
│     └─▶ kubectl describe pod <n> | tail -20
│            ├─ "insufficient cpu/memory"  → lower requests, or node is full
│            ├─ "unbound PVC"              → kubectl get pvc
│            │        └─ Pending on kind = normal (WaitForFirstConsumer)
│            ├─ "node affinity conflict"   → PVC is on another node (RWO)
│            └─ "untolerated taint"        → node is cordoned/tainted
│
├─ ContainerCreating (> 2 min)
│     └─▶ describe: volume mount or image pull
│
├─ ImagePullBackOff
│     └─▶ describe pod | tail
│            ├─ "unauthorized"   → missing/wrong imagePullSecret (private repo)
│            ├─ "not found"      → tag typo
│            └─ "no such host"   → registry unreachable
│         On kind: did you `kind load`? Is imagePullPolicy IfNotPresent?
│
├─ CrashLoopBackOff
│     └─▶ kubectl logs <n> --previous      ← MUST use --previous
│            ├─ ModuleNotFoundError → image missing a dependency
│            ├─ ImproperlyConfigured→ a required env var is missing
│            ├─ could not connect   → DB/Redis not up yet (may self-heal)
│            ├─ permission denied   → non-root user, PVC not group-writable
│            │                        (need fsGroup)
│            └─ initdb "not empty"  → Postgres needs subPath
│
├─ Running, 0/1 READY
│     └─▶ READINESS PROBE FAILING. describe pod → Events
│            ├─ 403          → health endpoint requires auth (DRF default!)
│            ├─ 404          → wrong path
│            ├─ conn refused → app not listening yet; add a startupProbe
│            └─ timeout      → app too slow; raise timeoutSeconds
│
├─ OOMKilled
│     └─▶ Exceeded the memory limit.
│            kubectl top pods → raise limit, or find the leak
│            The worker parsing .fit files is the usual suspect.
│
├─ Evicted
│     └─▶ Node under disk/memory pressure.
│            kubectl describe node → check QoS class; BestEffort dies first
│
└─ Terminating (stuck)
      └─▶ grace period still running, or a finalizer.
             kubectl get pod <n> -o yaml | grep -A5 finalizers
```

## Celery isn't working

```
kubectl logs deploy/worker --tail=100
│
├─ connection refused to redis
│     └─▶ REDIS_URL wrong, or Redis down. kubectl get endpoints redis
│
├─ connects, but no tasks run
│     └─▶ kubectl exec deploy/redis -- redis-cli llen celery
│            ├─ 0    → nothing queued. is beat running? does the API enqueue?
│            └─ > 0  → worker consuming a different queue name
│
├─ tasks run TWICE
│     └─▶ kubectl get deploy beat        ← must be replicas: 1
│         Also check strategy: Recreate, not RollingUpdate.
│
├─ RateLimited everywhere
│     └─▶ Expected. LLM quota. sweep_unread retries every 10 min.
│         Not a bug — this is designed behaviour.
│
└─ tasks vanish on redeploy
      └─▶ terminationGracePeriodSeconds < task duration.
          Consider task_acks_late=True (needs idempotent tasks).
```

## Certificate won't issue

```
kubectl describe certificate training-tls
│
├─ no Certificate object exists at all
│     └─▶ Typo in the cert-manager.io/cluster-issuer annotation.
│         Produces NO error. Verify the object exists first.
│
└─ exists, READY False
      └─▶ kubectl describe challenge <name>       ← the real error
             ├─ "no such host"      → DNS. dig first.
             ├─ conn refused/timeout→ port 80 blocked
             ├─ "404"               → ingress not routing /.well-known/
             ├─ "429 rateLimited"   → you were on prod issuer. Use staging.
             └─ nothing happening   → is cert-manager-webhook Running?
```

## Deploy failed in CI

```
read the workflow log
│
├─ tests failed        → real. fix the code.
├─ build failed        → Dockerfile, or npm run build (tsc errors)
├─ push failed         → permissions: packages: write missing
├─ kubectl auth error  → CI ServiceAccount lacks RBAC.
│                        kubectl auth can-i --list --as=system:serviceaccount:...
├─ can't reach cluster → 6443 unreachable from the runner
├─ migrate Job failed  → kubectl logs job/migrate-<sha>
│                        ✅ rollout correctly did NOT run
└─ rollout status timeout
      └─▶ New Pods aren't becoming Ready.
          Follow "A Pod won't start" above.
          Old Pods are still serving — no outage. maxUnavailable:0 worked.
```

## When you're stuck

Ask in order:

1. **What changed?** `kubectl rollout history`, `git log`. Nearly always this.
2. **One Pod or all?** One → that Pod/node. All → config, image, dependency.
3. **When did it start?** Correlate with a deploy, cert expiry, disk filling.
4. **Which layer?** DNS / firewall / ingress / Service / Pod / app. Test each
   hop with `flows/01-request-flow.md`.
5. **Does `describe` say anything?** The Events section explains most failures
   in plain English, and most people don't read it.

Change **one thing at a time**. Changing three and having it work teaches you
nothing, and next time you'll be no faster.
