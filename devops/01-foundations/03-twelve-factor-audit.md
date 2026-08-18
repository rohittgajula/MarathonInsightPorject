# Twelve-factor, audited against this repo

The twelve-factor app is a 2011 checklist for apps that deploy cleanly. Most of
it is now just "how things are done", but the failures are still the failures.
Here is where *this* codebase stands — honestly.

## ✅ I. Codebase — one repo, many deploys

One repo, will become dev + prod deploys. Fine.

## ⚠️ II. Dependencies — declared and isolated

Python: `requirements.txt` with everything pinned exactly (`Django==5.x`,
`garminconnect==0.3.10`). Good — and the Garmin pin is load-bearing, per
`CONTEXT.md`: 0.2.x and 0.3.x use different token file formats and mixing them
breaks login.

Node: `package.json` uses carets (`^18.3.1`). **There is no `package-lock.json`
committed**, and the Dockerfile runs `npm install`, not `npm ci`. Two builds a
month apart can resolve different dependency trees. That is not reproducible,
and reproducibility is the entire point of building an image.

**Fix:** commit the lockfile, switch the Dockerfile to `npm ci`.

## ⚠️ III. Config — in the environment

Mostly done well. `settings.py` reads everything from `os.environ`:
`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DATABASE_URL`, `REDIS_URL`, `MEDIA_ROOT`,
`GARMIN_TOKEN_ROOT`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `LOG_AI_PROVIDER`,
`CORS_ALLOWED_ORIGINS`. `.env` is gitignored, `.env.example` documents the
shape. This is exactly right and makes the k8s port easy.

Two problems:

**The insecure default.** `SECRET_KEY` falls back to
`"dev-insecure-key-change-me"`. Convenient locally, catastrophic if it ever
reaches production silently — session cookies and password reset tokens are
forgeable. Production must *fail to boot* rather than fall back. One line:

```python
if not DEBUG and SECRET_KEY == "dev-insecure-key-change-me":
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DEBUG=0")
```

**`VITE_API_BASE` is not runtime config at all.** Vite inlines
`import.meta.env.*` into the JavaScript bundle at **build time**. By the time
the image exists, the API URL is a literal string inside a minified `.js` file.
A ConfigMap cannot change it. This genuinely violates factor III and it is the
single most common surprise when moving a Vite app to Kubernetes.

Three ways out, and you should pick one now:

| Approach | How | Cost |
|---|---|---|
| **Same-origin (recommended)** | Build with `VITE_API_BASE=/api`. Ingress routes `/api` to backend, `/` to frontend. Same origin, so no CORS at all. | Ingress does slightly more work. Nothing else. |
| Build per environment | Separate image per env, `--build-arg` | Two images to build/store/track. The artifact you tested isn't the one you ship. |
| Runtime injection | Serve `/config.js` written by an entrypoint script from env; app reads `window.__CONFIG__` | Real runtime config, but code changes and an extra request before boot. |

Take the first. It also deletes your CORS configuration, your mixed-content
risk, and your cookie-domain questions in one move.

## ✅ IV. Backing services — attached resources

Postgres and Redis reached purely by URL. Swapping to a managed Postgres is a
one-variable change. Correct.

## ⚠️ V. Build, release, run — strictly separated

Currently fused. Both Dockerfiles bind-mount source and run dev servers with
hot reload, so "build" and "run" are the same act. Fine for development, and
`CONTEXT.md` even notes the sharp edge it creates (Python deps live in the
image, so `requirements.txt` changes need a rebuild while `.py` changes don't).

For production you need a real separation:

```
build   → image tagged with the commit SHA, immutable
release → that image + this environment's config
run     → the release, running
```

The rule that follows: **never build an image inside the cluster and never
mutate a running Pod**. If you find yourself running `kubectl exec` to fix
something, you have found a gap in build.

## ⚠️ VI. Processes — stateless, share-nothing

Django and Celery are stateless. But two pieces of state hide on local disk:

**`MEDIA_ROOT`** (`/data/media`) — the raw `.fit` bytes.
`CONTEXT.md` says these are kept permanently, deliberately, so a better parser
can re-run over history. Both `backend` and `worker` mount it. In Kubernetes
that means a PVC mounted by two different Deployments — which needs
`ReadWriteMany`, and the default storage on kind and on single-node k3s is
`ReadWriteOnce`. This is a real design decision you must make, covered in
`03-kubernetes/05`.

**`GARMIN_TOKEN_ROOT`** (`/data/garmin_tokens`) — OAuth tokens, currently a
read-only bind mount from your Mac. Two problems in k8s: your laptop is not
there, and **the tokens are refreshed**, so read-only breaks them over time. A
Secret is the wrong shape (Secrets are read-only volumes). Covered in
`03-kubernetes/04`.

## ✅ VII. Port binding — self-contained services

Both bind ports directly. Fine.

## ⚠️ VIII. Concurrency — scale out via the process model

Three process types already: web, worker, beat. Good separation.

But **`beat` can never scale past 1**. It uses
`django_celery_beat.schedulers:DatabaseScheduler`, and two beats means every
periodic task fires twice — two Garmin syncs an hour into a service that
`celery.py` explicitly notes rate-limits aggressively. `replicas: 1` is not a
default here, it is a correctness constraint, and it needs a comment in the
manifest saying so.

## ⚠️ IX. Disposability — fast startup, graceful shutdown

Startup is fine. Shutdown is not configured. A Celery worker killed mid-task
loses that task. You need `terminationGracePeriodSeconds` long enough for the
longest task (a FIT file parse — measure it) and Celery's warm shutdown on
SIGTERM, which it does by default. Covered in `03-kubernetes/07`.

## ⚠️ X. Dev/prod parity

Same Postgres 16 and Redis 7 in both — good, and better than most.

But the *servers* differ completely: `runserver` vs gunicorn, Vite dev server
vs static files behind nginx. Those are not small differences. `DEBUG=1` vs
`DEBUG=0` alone changes static file serving, error pages, `ALLOWED_HOSTS`
enforcement, and security middleware behaviour. You will meet bugs that exist
only in production. Minimise the gap by running the prod images locally
(`docker compose -f docker-compose.prod.yml up`) before ever deploying them.

## ⚠️ XI. Logs — event streams to stdout

`LOGGING` sends everything to console at INFO. Correct — the container runtime
captures stdout and that's the contract.

Gap: logs are unstructured text. Fine for `kubectl logs`, painful the moment
you aggregate. When you add Loki (`08-operations/01`), switch to JSON so you
can query by field instead of grepping.

## ❌ XII. Admin processes — one-off tasks in an identical environment

`docker compose exec backend python manage.py migrate` today. In Kubernetes this
must become a **Job** running the same image with the same config — not a
`kubectl exec` into a running Pod. `03-kubernetes/06` covers migrations
properly, including the ordering problem: migrations must finish before new
code serves traffic, but the new code is what carries the migration.

## Your fix-it list, ordered

1. Fix the two `tsc` errors so `npm run build` passes. **Nothing works until this does.**
2. Commit `package-lock.json`, switch to `npm ci`.
3. Decide same-origin `/api` now — it simplifies four later decisions.
4. Add `STATIC_ROOT` + whitenoise, or serve static via nginx.
5. Make `SECRET_KEY` fatal when `DEBUG=0`.
6. Add `SECURE_PROXY_SSL_HEADER` for the ingress.
7. Decide the media volume access mode.
8. Decide how Garmin tokens get into the cluster, writably.

Items 1–6 are code changes in this repo, before any Kubernetes. Do them as
lab zero.
