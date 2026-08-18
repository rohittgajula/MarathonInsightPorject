# Rollouts, rollbacks, and deployment strategies

## The two built-in strategies

### RollingUpdate (default)

Replace Pods gradually, controlled by two knobs:

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 0    # never go below `replicas` ready
    maxSurge: 1          # may run one extra
```

| Setting | Behaviour |
|---|---|
| `maxUnavailable: 0, maxSurge: 1` | Safest. New Pod ready *before* old dies. Needs capacity for one extra. **Use this.** |
| `maxUnavailable: 1, maxSurge: 0` | No extra capacity needed, but you dip below full strength. For resource-tight clusters. |
| `25%, 25%` (the default) | Sensible for large deployments, meaningless at 2 replicas (rounds to 1 and 1). |

With `replicas: 2` and `0/1`, a rollout looks like `03-kubernetes/02` describes:
never fewer than 2 ready, one extra briefly, done in two steps.

**This only works if two versions can run simultaneously.** That's the migration
constraint from `06-jobs-cronjobs-migrations.md` again, and it's the recurring
tax of zero-downtime deployment.

### Recreate

Kill everything, then start the new version. Downtime equal to your startup
time.

```yaml
strategy:
  type: Recreate
```

Correct when two versions **must not** coexist:

- **`beat`** — two schedulers means every periodic task fires twice.
- Anything holding an exclusive lock or a singleton resource.

Use `Recreate` for beat. It's not a compromise there, it's the correct choice,
and it deserves the same comment as `replicas: 1`.

## Rollback

```bash
kubectl rollout history deploy/backend -n runproject
kubectl rollout history deploy/backend --revision=3 -n runproject
kubectl rollout undo deploy/backend -n runproject
kubectl rollout undo deploy/backend --to-revision=3 -n runproject
```

The Deployment keeps old ReplicaSets at zero replicas —
`revisionHistoryLimit` (default 10) controls how many. Rollback is just scaling
one back up, so it is **fast**: no image pull, no build, seconds.

By default `rollout history` shows `<none>` for CHANGE-CAUSE, which makes it
useless. Fix it with an annotation you set on every deploy:

```yaml
metadata:
  annotations:
    kubernetes.io/change-cause: "deploy 680b5c5 — production images"
```

In CI, set it from the commit message. Then `rollout history` is an actual
deployment log.

### The thing rollback does not undo

**Rollback does not reverse migrations.** Code goes back; the schema does not.

```
deploy v2 → migration adds NOT NULL column
rollback to v1 → v1 doesn't know the column → every INSERT fails
```

You are now in a worse state than before the rollback. This is why
backward-compatible migrations aren't optional discipline — they're what makes
rollback a real safety net rather than a second outage.

If a migration is genuinely irreversible (a data transformation, a dropped
column), your rollback plan is **roll forward**: fix and deploy again. Know
which of the two you're in *before* you need it. Write it in the PR.

## Manual controls

```bash
kubectl rollout pause deploy/backend -n runproject
kubectl rollout resume deploy/backend -n runproject
kubectl rollout restart deploy/backend -n runproject
kubectl rollout status deploy/backend -n runproject --timeout=5m
```

**`pause`** mid-rollout is the poor man's canary: let one new Pod take traffic,
watch metrics, then resume or undo. Crude, free, and genuinely useful.

**`restart`** does a rolling restart with no spec change — it stamps a new
annotation on the template. This is how you pick up a changed ConfigMap
(`04-config-and-secrets.md`) or force a fresh image pull on a mutable tag.

**`status`** blocks until complete or `progressDeadlineSeconds` elapses,
returning non-zero on failure. **This must be the last step of every CI deploy
job.** Without it, CI goes green the instant `apply` returns — which is before
anything has rolled, so a Pod that crashloops reports as a successful deploy.

## Advanced strategies

Kubernetes has no native support for these. They need Argo Rollouts, Flagger, or
a service mesh. Worth understanding; not worth building for one user.

### Blue/green

Two full environments. Flip all traffic at once by changing the Service
selector.

```
Service: backend  ──selector: version=blue──▶  [blue Pods v1]
                                               [green Pods v2]  ← idle, warm

kubectl patch svc backend -p '{"spec":{"selector":{"version":"green"}}}'

Service: backend  ──selector: version=green──▶ [green Pods v2]
```

Instant cutover, instant rollback (flip back), and you can smoke-test green
before sending it traffic. Costs double the resources during the switch.

Genuinely doable by hand: two Deployments labelled `version: blue` and
`version: green`, one Service, one `kubectl patch`. Try it once — it's a good
way to feel what a Service selector actually does.

### Canary

Send a small fraction to the new version, watch, increase.

Crudely, by replica count: 9 stable Pods + 1 canary Pod behind one Service ≈ 10%
of traffic. Free, imprecise, and depends on connection distribution — with HTTP
keep-alive, "10% of Pods" is not "10% of requests" (see `03-services-and-dns.md`).

Properly, ingress-nginx supports weighted canaries by annotation:

```yaml
nginx.ingress.kubernetes.io/canary: "true"
nginx.ingress.kubernetes.io/canary-weight: "10"
```

A second Ingress for the same host, marked canary, taking 10%. This is real
traffic splitting, and it's available to you without any extra tooling.

Also supports `canary-by-header`, so you can route *yourself* to the new version
with a header while everyone else stays on stable. For an app with one user
that's arguably more useful than percentage splitting.

### Progressive delivery

Automated canary: shift traffic gradually while watching metrics, roll back
automatically if error rate rises. Argo Rollouts + Prometheus.

This is where the industry is. It also requires meaningful traffic to produce
statistically valid metrics, which one user does not generate. Understand it,
mention it in interviews, don't build it here.

## What to actually use

| Workload | Strategy |
|---|---|
| backend | RollingUpdate 0/1 |
| frontend | RollingUpdate 0/1 |
| worker | RollingUpdate 0/1, long grace period |
| **beat** | **Recreate** |
| db | StatefulSet, `RollingUpdate` with `partition` — but at 1 replica it's just a restart. Accept the downtime. |
| redis | Recreate (no persistence, nothing to coordinate) |

## Debugging a stuck rollout

```bash
kubectl rollout status deploy/backend -n runproject
kubectl describe deploy/backend -n runproject
kubectl get rs -n runproject
kubectl get pods -n runproject
kubectl describe pod <new-pod> -n runproject
kubectl logs <new-pod> -n runproject --previous
```

Read them in that order. The common causes, and their signatures:

| Symptom | Cause |
|---|---|
| New Pod `Pending` | Not schedulable — no node with enough CPU/RAM, or a PVC that can't bind. `describe pod` Events says which. |
| New Pod `ImagePullBackOff` | Wrong tag, or missing `imagePullSecret` on a private registry. Events distinguishes `unauthorized` from `not found`. |
| New Pod `Running` but rollout stuck | **Readiness probe failing.** Very common. `describe pod` shows the probe failure; `logs` shows why. |
| New Pod `CrashLoopBackOff` | App exits on start. `logs --previous` is the one that shows you why — plain `logs` shows the *current* attempt, which may not have gotten far. |
| Rollout stuck at exactly one new Pod | `maxUnavailable: 0` doing its job — it will not proceed until that Pod is Ready. Working as designed; fix the Pod. |

`--previous` is the flag people forget. A CrashLooping container's useful output
is in the *previous* attempt.
