# Jobs, CronJobs, and the migration problem

## Job

Runs Pods until N complete successfully, then stops. For work that ends.

```yaml
apiVersion: batch/v1
kind: Job
spec:
  backoffLimit: 3        # retries before the Job is marked Failed
  ttlSecondsAfterFinished: 300   # auto-clean the Pod after 5 min. Without this
                                 # completed Jobs accumulate forever.
  template:
    spec:
      restartPolicy: Never   # or OnFailure. NOT Always — that's not a Job.
      containers: [...]
```

Key fields:

- `backoffLimit` — retries with exponential backoff (10s, 20s, 40s…) before
  giving up. Default 6, which for a failing migration means several minutes of
  pointless retrying.
- `activeDeadlineSeconds` — hard wall-clock cap. Kills the Job regardless.
- `ttlSecondsAfterFinished` — cleanup. Set it, or `kubectl get pods` becomes
  unreadable within a week.

## Migrations — the real problem

Today, `docker-compose.yml`:

```yaml
command: >
  sh -c "python manage.py migrate --noinput &&
         python manage.py runserver 0.0.0.0:8000"
```

Migrate, then serve, in one command. Simple and correct for one container.

**In Kubernetes with 2 replicas this is a race.** Both Pods start, both run
`migrate` simultaneously. Django takes a `django_migrations` lock so you
probably won't corrupt anything — but you will get failures, retries, and a
CrashLoopBackOff on one Pod while the other proceeds. On some backends and some
migrations you get worse.

Scale to 3 and it gets worse. Roll out an update and *old* Pods are still
serving while a *new* Pod migrates. That last one is the real problem, and it
doesn't go away with locking.

### The ordering constraint

```
old code running ──┐
                   ├── migration runs ──┐
new code starting ─┘                    ├── new code serving
                                        │
   during this window, OLD code is talking to a NEW schema
```

That window is unavoidable in a rolling update. Which means:

> **Every migration must be backward-compatible with the currently deployed
> code.**

That's not a Kubernetes rule, it's a consequence of ever running two versions at
once. It changes how you write migrations:

| Want to | Do |
|---|---|
| Add a column | Fine — nullable or with a default. One deploy. |
| Drop a column | **Two deploys.** (1) stop using it in code, ship. (2) drop it, ship. |
| Rename a column | **Three deploys.** Add new → write both, read new → drop old. |
| Add a NOT NULL column | **Three.** Add nullable → backfill → add constraint. |
| Add an index on a big table | `CONCURRENTLY`, outside the transaction (`atomic = False`). |

This project is pre-launch with one user, so you can be sloppy today and just
take the downtime. **Learn the discipline now anyway** — it's one of the things
that separates people who have run production from people who have read about
it.

### The pattern: a Job with a Helm/Argo hook

Run migrations as a **Job that completes before the new Deployment rolls**:

```
1. build image :sha
2. apply Job(migrate, image=:sha)     ← same image as the app
3. wait for Job completion             ← kubectl wait
4. apply Deployment(image=:sha)
5. kubectl rollout status
```

Requirements for the Job:

- **Same image** as the app. Migrations are code; they must be the code you're
  deploying. This is twelve-factor XII.
- **Same ConfigMap and Secret.** Same `DATABASE_URL`.
- **Unique name per deploy** — `migrate-<sha>`. Job specs are largely immutable;
  re-applying the same name with a different image fails with a confusing
  `field is immutable` error. Generating the name from the SHA also gives you
  idempotency: re-running the same deploy is a no-op because the Job already
  completed.
- `backoffLimit: 1`. A failing migration will not succeed on retry, and you'd
  rather find out in 30 seconds than 5 minutes.

Waiting for it:

```bash
kubectl wait --for=condition=complete job/migrate-680b5c5 -n runproject --timeout=300s
```

That returns non-zero on timeout, which fails the CI job — exactly what you
want. But it does *not* return when the Job fails, it just waits out the
timeout. Belt and braces:

```bash
kubectl wait --for=condition=complete --timeout=300s job/migrate-$SHA -n runproject &
COMPLETE=$!
kubectl wait --for=condition=failed --timeout=300s job/migrate-$SHA -n runproject && exit 1 &
FAILED=$!
wait -n $COMPLETE $FAILED
```

Ugly. This is one of the places Helm hooks or Argo CD sync waves genuinely earn
their keep — they express "this before that" natively.

### An alternative: initContainers

An `initContainer` runs to completion before the main container starts, in the
same Pod:

```yaml
initContainers:
  - name: migrate
    image: <same image>
    command: ["python", "manage.py", "migrate", "--noinput"]
```

**Careful — this does not solve the race.** Every replica runs its own
initContainer, so with 2 replicas you have 2 concurrent migrations again. It's
the compose problem with extra steps.

Where initContainers *are* right: **waiting for a dependency.** An init
container that blocks until Postgres accepts connections is a clean replacement
for compose's `depends_on: condition: service_healthy`, which has no direct
Kubernetes equivalent.

```yaml
initContainers:
  - name: wait-for-db
    image: busybox:1.36
    command: ['sh','-c','until nc -z db 5432; do sleep 1; done']
```

Though honestly, Kubernetes' answer is "let it crash and retry" — a backend Pod
that can't reach the DB will CrashLoopBackOff and recover on its own once the DB
is up. The initContainer just makes the logs cleaner. Use it or don't; know why.

## CronJob

```yaml
apiVersion: batch/v1
kind: CronJob
spec:
  schedule: "0 3 * * *"
  timeZone: "Asia/Kolkata"          # k8s 1.27+. Otherwise UTC.
  concurrencyPolicy: Forbid          # Allow | Forbid | Replace
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  startingDeadlineSeconds: 300
  jobTemplate:
    spec:
      template: [...]
```

**`concurrencyPolicy: Forbid`** — if the previous run is still going, skip this
one. Default is `Allow`, which for a slow backup means two `pg_dump`s racing.
Set it explicitly.

**`timeZone`** matters here. Django's `TIME_ZONE` is UTC and `CONTEXT.md` is
emphatic that dates come from `Athlete.local_today`, because at 00:48 in
Kolkata UTC still says yesterday. A CronJob at `0 0 * * *` UTC fires at 05:30
Kolkata. If you ever schedule something that must align to the athlete's day,
set `timeZone: "Asia/Kolkata"` and say so in a comment — this is exactly the
class of bug `CONTEXT.md` warns about, reappearing at the infrastructure layer.

### Do you need CronJobs here?

**Mostly no**, and this is worth being clear about. Celery beat already runs
your periodic work — `rebuild-stale-metrics` every 5 min, `sync-all-athletes`
hourly, `sweep-unread-logs` every 10 min. Reimplementing those as CronJobs would
duplicate scheduling in two places, and `celery.py`'s comments explain *why*
each interval is what it is.

Keep beat. Use CronJobs for **infrastructure** work that isn't application
logic:

| CronJob | Schedule | Why not beat |
|---|---|---|
| `pg_dump` to object storage | `0 3 * * *` | Backups must work when the app is broken. That's the whole point. |
| Prune old Jobs / images | weekly | Cluster housekeeping, not app logic |
| Certificate expiry check | daily | Belt-and-braces on cert-manager |

The backup one is the important one. If backups run inside the app, an app that
won't start takes your backups with it.

## Commands

```bash
kubectl get jobs -n runproject
kubectl logs job/migrate-680b5c5 -n runproject
kubectl get cronjob -n runproject
kubectl create job --from=cronjob/pg-backup manual-test-1 -n runproject
```

That last one is how you test a CronJob without waiting for 3am. Do it once,
immediately after writing it. An untested backup CronJob is worse than none,
because you'll believe in it.
