# Debugging runbook

When something is broken and you need a procedure, not a concept.

## The universal first four commands

```bash
kubectl get pods -n runproject
kubectl describe pod <name> -n runproject
kubectl logs <name> -n runproject
kubectl logs <name> -n runproject --previous
```

In that order, always. `describe`'s **Events** section at the bottom is where
Kubernetes explains itself in plain English — scheduling failures, image pull
errors, probe failures, volume problems all say exactly what's wrong there.

Most people skip `describe` and go straight to logs. `describe` answers "why
isn't it running"; logs answer "why isn't it working". Different questions.

Also, cluster-wide:

```bash
kubectl get events -n runproject --sort-by=.lastTimestamp | tail -30
```

## Pod status decoder

| Status | Means | First check |
|---|---|---|
| `Pending` | Not scheduled | `describe` → no node fits (CPU/RAM), or PVC unbound |
| `ContainerCreating` | Scheduled, starting | Stuck > 2m → volume mount or image pull |
| `ImagePullBackOff` | Can't fetch the image | Tag typo, or missing `imagePullSecret` (private repo!) |
| `CrashLoopBackOff` | Starts, exits, repeat | `logs --previous` |
| `Running` but not `Ready` | **Readiness probe failing** | `describe` shows the probe error |
| `OOMKilled` | Exceeded memory limit | Raise the limit, or find the leak |
| `Error` | Exited non-zero | `logs --previous` |
| `Terminating` (stuck) | Grace period, or a finalizer | Wait; then investigate finalizers |
| `Evicted` | Node under pressure | Disk or memory on the node; check QoS class |

**`Running` but `0/1 Ready` is the one that confuses people.** The container is
fine. The readiness probe is failing. Nothing is in the logs because nothing is
wrong with the app — the probe is hitting a path that 404s, or a port that isn't
open, or (in your case, very plausibly) a DRF endpoint returning 403 because of
the default `IsAuthenticated` permission.

## Symptom → cause

### The site is down

Walk the request path in order. Do not skip steps.

```bash
dig training.example.com +short                      # 1. DNS
curl -I https://training.example.com/                # 2. reaches anything?
kubectl get pods -n ingress-nginx                    # 3. controller alive?
kubectl get ingress -n runproject                    # 4. ADDRESS populated?
kubectl get endpoints -n runproject                  # 5. ← usually here
kubectl get pods -n runproject                       # 6. Pods ready?
kubectl logs -n runproject -l app=backend --tail=50  # 7. app errors?
```

**Step 5 catches it most often.** Empty `ENDPOINTS` means the Service matches
no ready Pod — either a selector mismatch or a failing readiness probe.

### HTTP status decoder

| Code | Where it came from | Cause |
|---|---|---|
| **Connection refused** | Nothing listening | Ingress controller down, or the port isn't open |
| **Timeout** | Firewall | ufw or the provider's firewall dropping packets |
| **404 (nginx)** | Ingress | No rule matched — host typo or wrong path |
| **503** | Ingress | Rule matched, **no ready endpoints** |
| **502** | Ingress | Reached a Pod, got garbage — wrong `targetPort` |
| **504** | Ingress | Upstream too slow — `proxy-read-timeout` |
| **413** | Ingress | Body too large — `proxy-body-size` (your `.fit` uploads) |
| **400 DisallowedHost** | Django | `DJANGO_ALLOWED_HOSTS` |
| **500** | Django | A real application error. Read the logs. |
| Redirect loop | Django | Missing `SECURE_PROXY_SSL_HEADER` |

Knowing whether a 503 came from nginx or from Django saves enormous time. Check
the response body — nginx's error pages say `nginx` in them.

### A Pod won't start

```bash
kubectl describe pod <name> -n runproject | tail -30
```

| Event says | Fix |
|---|---|
| `0/1 nodes available: insufficient cpu` | Lower requests, or the node is full |
| `pod has unbound immediate PersistentVolumeClaims` | Check the PVC; on kind, `WaitForFirstConsumer` is normal |
| `Back-off pulling image` | Wrong tag, or auth. `unauthorized` vs `not found` distinguishes them. |
| `CreateContainerConfigError` | A ConfigMap or Secret key referenced in `env` doesn't exist |
| `MountVolume.SetUp failed` | Secret/ConfigMap not found, or a permissions problem |
| `Readiness probe failed: 403` | **Your health endpoint requires auth** |
| `Readiness probe failed: connection refused` | App not listening on the probe's port yet — needs a startupProbe |

### The app can't reach the database

```bash
kubectl exec -it deploy/backend -n runproject -- python -c "import os;print(os.environ['DATABASE_URL'])"
kubectl get endpoints db -n runproject
kubectl run -it --rm net --image=nicolaka/netshoot --restart=Never -n runproject -- \
  sh -c 'nc -zv db 5432; dig db.runproject.svc.cluster.local'
kubectl logs db-0 -n runproject --tail=50
```

Usual causes, in order of likelihood: wrong password (the
`POSTGRES_PASSWORD`/`DATABASE_URL` mismatch from `03-kubernetes/04`), the
Service name doesn't match what the URL says, or Postgres is still starting.

### Celery isn't processing tasks

```bash
kubectl logs deploy/worker -n runproject --tail=100
kubectl exec -it deploy/redis -n runproject -- redis-cli llen celery
kubectl exec -it deploy/redis -n runproject -- redis-cli keys '*'
kubectl logs deploy/beat -n runproject --tail=50
kubectl exec -it deploy/worker -n runproject -- celery -A config inspect active
```

| Symptom | Cause |
|---|---|
| Queue growing, worker idle | Worker connected to a different Redis, or consuming a different queue |
| Worker logs show connection errors | `REDIS_URL` wrong, or Redis down |
| Beat logs nothing | Wrong scheduler flag, or `django_celery_beat` migrations not applied |
| Tasks run **twice** | **Two beat replicas.** Check `kubectl get deploy beat`. |
| `RateLimited` everywhere | Expected — LLM quota. `sweep_unread` will retry. Not a bug. |

That last one is important: `CONTEXT.md` is explicit that a rate limit is a
distinct, retryable status, not a failure. Seeing `RateLimited` in the logs is
the system working as designed.

### Everything is slow

```bash
kubectl top pods -n runproject
kubectl top nodes
kubectl get hpa -n runproject
kubectl exec -it db-0 -n runproject -- psql -U runproject -c \
  "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
```

CPU throttling from a too-low limit is invisible in `kubectl top` — it shows
usage, not throttling. Check the container's cgroup, or look at
`container_cpu_cfs_throttled_seconds_total` in Prometheus. A Pod pinned at
exactly its limit with terrible latency is the signature.

Postgres connections near `max_connections` (100) is the other likely culprit —
see `05-autoscaling/02` for the arithmetic.

## Emergency procedures

**Roll back now**
```bash
kubectl rollout undo deploy/backend -n runproject
kubectl rollout status deploy/backend -n runproject
```
Remember: **this does not undo migrations** (`03-kubernetes/09`).

**Stop everything**
```bash
kubectl scale deploy --all --replicas=0 -n runproject
```

**Get a shell**
```bash
kubectl exec -it deploy/backend -n runproject -- bash
kubectl exec -it deploy/backend -n runproject -- python manage.py shell
```

**Debug a crashlooping Pod** — override the command so it starts but does
nothing, then poke around:
```bash
kubectl debug -it <pod> --image=nicolaka/netshoot --target=backend -n runproject
```
`kubectl debug` attaches an ephemeral container sharing the target's namespaces.
The right tool when your image is minimal and has no shell.

**Copy files out**
```bash
kubectl cp runproject/backend-xxxxx:/data/media/file.fit ./file.fit
```

## The debugging Pod

Keep this in muscle memory:

```bash
kubectl run -it --rm debug --image=nicolaka/netshoot --restart=Never -n runproject -- bash
```

`dig`, `curl`, `nc`, `tcpdump`, `ss`, `mtr`, `psql`. It costs nothing when not
running and answers most network questions in one shot.

## Before you escalate to yourself

Ask, in order:

1. **What changed?** `kubectl rollout history`, `git log`. Almost always the
   answer.
2. **Is it one Pod or all of them?** One → that Pod/node. All → config, image,
   or a dependency.
3. **When did it start?** Correlate with a deploy, a cert expiry, a disk filling.
4. **Does it reproduce?** Once is a blip; consistent is a bug.
5. **Which layer?** DNS / network / ingress / Service / Pod / app. Test each hop
   with `flows/01-request-flow.md` rather than guessing.

Step 5 is the discipline that separates fast debugging from thrashing. Guessing
which layer is broken and changing three things at once means you won't know
what fixed it — and next time you'll be no faster.
