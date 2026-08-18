# Lab 0 — production images

**You write these. No answer YAML here by design.** Specs, constraints,
self-checks, and the mistakes to expect.

Do this before touching Kubernetes. Everything downstream assumes it.

---

## 0.1 — Unblock the build

`npm run build` currently fails: `tsc -b` reports unused variables at
`MetricOverlay.tsx:51` and `Home.tsx:13`.

**Task.** Make `npm run build` exit 0.

**Think about it first.** An unused variable is a symptom. Was it meant to be
used and the wiring got dropped, or is it genuinely dead? Deleting a line that
should have been used hides a bug. Read the surrounding code before you reach
for `_` prefixes or `// @ts-ignore`.

**Self-check**
```bash
cd frontend && npm run build && ls -la dist/
```
`dist/index.html` and a hashed `assets/*.js` exist.

**Also:** there is no `package-lock.json` committed. Generate one (`npm install`
writes it) and commit it. Without it `npm ci` cannot run and builds are not
reproducible.

---

## 0.2 — Static files

**Task.** Make `/admin` render with CSS when `DEBUG=0`.

**Requirements**
- Add `whitenoise` to `requirements.txt`, pinned.
- `STATIC_ROOT` in `settings.py`.
- WhiteNoise middleware **immediately after** `SecurityMiddleware` — order
  matters; too late and requests never reach it.
- `CompressedManifestStaticFilesStorage`.

**Expect this to bite:** the manifest storage raises `ValueError: Missing
staticfiles manifest entry` if any template references a file that
`collectstatic` didn't collect. If that happens, run `collectstatic` and read
what it says it collected.

**Self-check**
```bash
cd backend && DJANGO_DEBUG=0 python manage.py collectstatic --noinput
```
Reports files copied, `staticfiles/staticfiles.json` exists. Add `staticfiles/`
to `.gitignore` — it is a build artifact.

---

## 0.3 — Backend production image

**Task.** Restructure `backend/Dockerfile` into `base` / `dev` / `prod` stages.

**Requirements**

| # | Constraint |
|---|---|
| 1 | `base` installs system packages and pip requirements. Both stages inherit it. |
| 2 | `dev` keeps `runserver` so compose is unaffected. |
| 3 | `prod` runs gunicorn: `config.wsgi:application`, bind `0.0.0.0:8000`, 3 workers, 60s timeout. |
| 4 | `prod` runs `collectstatic --noinput` at build time. |
| 5 | Runs as a non-root user, uid 10001. |
| 6 | `MEDIA_ROOT`, `GARMIN_TOKEN_ROOT` and `STATIC_ROOT` are owned by that user. |
| 7 | `.dockerignore` excludes `.git`, `__pycache__`, `.pytest_cache`, `tests/fixtures/*.fit`, `media/`. |
| 8 | `pip install` stays cached when only `.py` files change. |

**Watch for**
- `build-essential` and `libpq-dev` are only needed to *compile* wheels. Once
  `psycopg` and friends are installed, the compiler is dead weight — a couple
  hundred MB of it. Consider a builder stage that pip-installs into a venv and a
  runtime stage that copies the venv. `libpq5` (runtime) is not `libpq-dev`
  (headers).
- `collectstatic` runs as root by default. If you `USER app` before it, make
  sure `STATIC_ROOT` is already writable.
- Do this in the wrong order and `COPY . .` will re-own everything and undo your
  `chown`.

**Self-check**
```bash
docker build --target prod -t rp-backend:test ./backend
docker run --rm rp-backend:test whoami
docker run --rm rp-backend:test ls -la /app/staticfiles | head
docker history rp-backend:test | head -20
```
`whoami` → `app`. Static files present. No layer you can't account for.

---

## 0.4 — Frontend production image

**Task.** Multi-stage Node-build → nginx-serve.

**Requirements**

| # | Constraint |
|---|---|
| 1 | Build stage uses `npm ci`, not `npm install`. |
| 2 | `ARG VITE_API_BASE` defaulting to `/api`. |
| 3 | Final stage is nginx-based, contains no `node_modules` and no Node. |
| 4 | nginx listens on **8080**, not 80, so it needs no root. |
| 5 | Runs non-root. |
| 6 | nginx config does SPA fallback: unknown paths → `/index.html`. |
| 7 | Hashed assets in `/assets/` get a long `Cache-Control`; `index.html` gets `no-cache`. |
| 8 | A `/healthz` path returns 200 without touching the filesystem. |

**On #6 — this is the one everyone misses.** React Router handles
`/activities/42` client-side. Load that URL directly and nginx looks for a file
at that path, doesn't find it, returns 404. The app appears to work until
someone refreshes a page or opens a bookmark. `try_files $uri $uri/ /index.html;`
is the fix.

**On #7 — why the split.** Vite emits `index-a3f9c2.js`; the hash changes when
content changes, so those files can cache for a year safely. `index.html` names
which hashes are current — cache it and users get last week's app pointing at
deleted assets. `index.html` must always be revalidated.

**On #8 — why not just `/`.** A health probe hitting `/` serves the whole SPA
on every check. Cheap, but a dedicated `return 200 'ok';` location costs nothing
and can't be broken by a frontend bug.

**Self-check**
```bash
docker build -t rp-frontend:test ./frontend
docker images rp-frontend:test          # want < 100 MB
docker run --rm -p 8080:8080 rp-frontend:test
curl -I localhost:8080/                 # 200
curl -I localhost:8080/activities/42    # 200, not 404  ← the SPA fallback
curl localhost:8080/healthz             # ok
docker run --rm rp-frontend:test ls /usr/share/nginx/html
```

And prove the API base is baked in:
```bash
docker run --rm rp-frontend:test sh -c 'grep -o "/api" -m1 /usr/share/nginx/html/assets/*.js | head -1'
```
Finding it in the minified bundle is the point — it demonstrates why a
ConfigMap can never change this value.

---

## 0.5 — Run the production stack locally

**Task.** Write `docker-compose.prod.yml` that runs the prod images.

**Requirements**
- Builds with `target: prod` / the prod Dockerfile.
- `DJANGO_DEBUG=0`, a real `DJANGO_SECRET_KEY`, explicit `DJANGO_ALLOWED_HOSTS`.
- **No bind mounts of source.** The image is the artifact.
- Same Postgres 16 and Redis 7.
- Migrations run as a separate one-shot service that exits, not in the web
  service's command. This mirrors the Kubernetes Job you'll write later.
- Frontend on 8080, backend on 8000.

**Self-check**
```bash
docker compose -f docker-compose.prod.yml up --build
```
- Frontend loads at `localhost:8080`
- `/admin` has CSS
- Logs show gunicorn workers booting, no `runserver`
- Celery worker connects to Redis and shows registered tasks
- Beat logs its schedule — and only **one** beat is running

Then break something on purpose: set `DJANGO_ALLOWED_HOSTS=nope` and confirm
you get `DisallowedHost`. Knowing what each failure *looks like* is worth more
than a clean run.

---

## Done when

- `npm run build` passes; lockfile committed
- Both prod images build from cold with `--no-cache`
- Both run as non-root
- Frontend under 100 MB
- `/admin` styled, deep links work on refresh
- The whole prod stack runs locally with no source bind-mounted

Commit this on `dev`. It is a meaningful change on its own — it's the
difference between "runs on my machine" and "is an artifact".
