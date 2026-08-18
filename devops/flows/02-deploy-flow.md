# Flow: a deploy

From `git push` to new code serving traffic.

```
  git push origin main
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│ GITHUB ACTIONS                                            │
│                                                           │
│  ┌─────────┐  ┌─────────┐   parallel, fail fast           │
│  │  lint   │  │  test   │                                 │
│  └────┬────┘  └────┬────┘                                 │
│       └─────┬──────┘                                      │
│             ▼                                             │
│      ┌────────────┐                                       │
│      │   BUILD    │  backend:680b5c5                      │
│      │  (amd64)   │  frontend:680b5c5  (VITE_API_BASE=/api)│
│      └─────┬──────┘                                       │
│            ▼                                              │
│      ┌────────────┐                                       │
│      │  push to   │  ghcr.io                              │
│      │   ghcr.io  │                                       │
│      └─────┬──────┘                                       │
└────────────┼──────────────────────────────────────────────┘
             ▼
┌───────────────────────────────────────────────────────────┐
│ DEPLOY JOB                    environment: production      │
│                               ← required reviewer gate     │
│  1. apply Job migrate-680b5c5                             │
│         │                                                 │
│         ▼                                                 │
│     initContainer: wait for postgres                      │
│         ▼                                                 │
│     python manage.py migrate --noinput                    │
│         ▼                                                 │
│     kubectl wait --for=condition=complete  ← BLOCKS       │
│         │                                                 │
│         │  fails → STOP. No rollout. Old code still up.   │
│         ▼                                                 │
│  2. kustomize edit set image …:680b5c5                    │
│     kubectl apply -k overlays/prod                        │
│         │                                                 │
│         ▼                                                 │
│  3. kubectl rollout status  ← BLOCKS until Ready          │
│         ▼                                                 │
│  4. curl https://training.example.com/api/health/         │
│         ▼                                                 │
│  5. on failure: dump pods, describe, logs --previous      │
└───────────────────────────────────────────────────────────┘
```

## What the rollout looks like inside the cluster

```
t0   Deployment spec updated (image tag changed)
     │
t1   Deployment controller creates ReplicaSet-new (replicas: 0)
     │
t2   maxSurge=1 → scale RS-new to 1
     │            ┌── old: ■■ (2 ready)   new: ▨ (starting)
t3   new Pod: image pull → container start
     │
t4   startupProbe passes (Django finished importing)
     │
t5   readinessProbe passes → Pod joins Service endpoints
     │            ┌── old: ■■   new: ■  (3 serving)
t6   maxUnavailable=0 satisfied → scale RS-old to 1
     │   old Pod: removed from endpoints ─┐ concurrent
     │             preStop sleep 5        ─┘
     │             SIGTERM → gunicorn graceful
     │             exits within 30s
     │            ┌── old: ■   new: ■
t7   repeat for the second Pod
     │
t8   old: —   new: ■■     done
     RS-old kept at replicas: 0 → this is your rollback target
```

Never fewer than 2 ready. The whole thing hinges on the readiness probe telling
the truth about when a Pod can serve.

## The rollback path

```
  something is wrong
        │
        ▼
  kubectl rollout undo deploy/backend -n runproject-prod
        │
        ▼
  RS-old scaled back to 2, RS-new to 0
        │
   seconds — no build, no pull, images are still on the node
        │
        ▼
  old code serving
        │
        ▼
  ⚠️  THE SCHEMA IS STILL THE NEW ONE
      migrations were not reversed
      old code + new schema must be compatible
      or you have made things worse
```

This is why backward-compatible migrations matter
(`03-kubernetes/06-jobs-cronjobs-migrations.md`). Rollback is only a safety net
if the schema tolerates it.

## Failure points, and what happens

| Fails at | Result |
|---|---|
| lint / test | No build. Nothing deployed. Old code serving. ✅ |
| build | No image. Nothing deployed. ✅ |
| push to ghcr | No image to pull. Nothing deployed. ✅ |
| **migration Job** | **STOP.** No rollout. Old code + old schema. ✅ |
| image pull in-cluster | New Pod `ImagePullBackOff`. `maxUnavailable: 0` means old Pods keep serving. `rollout status` times out → CI red. ✅ |
| readiness probe | New Pod never Ready. Rollout stalls. Old Pods serving. `rollout status` times out. ✅ |
| smoke test | Deploy already rolled. **Manual rollback needed.** ⚠️ |

**Six of seven failure modes are safe by construction.** That's not luck — it's
`maxUnavailable: 0`, an honest readiness probe, and gating the rollout on the
migration Job. Get those three right and most bad deploys simply don't happen.

The last one is the gap: a deploy that rolls successfully but is functionally
broken. That's what automated rollback on smoke-test failure would cover, and
what progressive delivery (`03-kubernetes/09`) automates properly.

## GitOps variant

```
  git push main
        │
        ▼
  CI: build, test, push image
        │
        ▼
  CI: kustomize edit set image + git commit + push
        │           (CI has NO cluster credentials)
        ▼
  ┌─────────────────────────────────┐
  │ Argo CD (in-cluster) polls git  │
  │   detects drift                 │
  │   sync-wave -2: config, PVCs    │
  │   PreSync hook: migrate Job     │  ← ordering is declarative
  │   sync-wave  1: deployments     │
  │   sync-wave  2: ingress, HPA    │
  │   health checks until Healthy   │
  └─────────────────────────────────┘
```

Same outcome, no inbound cluster access, and the migration ordering is expressed
as a hook rather than a `kubectl wait` in a shell script.
