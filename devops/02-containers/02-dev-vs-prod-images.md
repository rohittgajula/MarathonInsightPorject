# Your Dockerfiles are development-only

This is lab zero. Read it, then do the exercise in `03-exercise-production-images.md`.

## What's wrong today

**`backend/Dockerfile`** ends with:

```dockerfile
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

Django's own docs say, in bold, do not use `runserver` in production. Concretely
it is single-threaded-ish, does no process management, has known performance
characteristics that are fine for one developer and nothing else, and serves
static files only when `DEBUG=1`.

`gunicorn==23.0.0` is already in `requirements.txt`. Nothing uses it.

**`frontend/Dockerfile`** ends with:

```dockerfile
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

That is the Vite dev server: it ships an unminified bundle, a websocket for hot
module reload, source maps, and a full Node runtime — around 400 MB of image to
serve files that should be a few hundred KB of static assets behind nginx.

**`docker-compose.yml` overrides both** with bind mounts and its own `command:`,
so what you run locally isn't even what the Dockerfile says. Perfectly sensible
for development — and it means the Dockerfiles have never actually been
exercised as production artifacts.

## The four problems to solve

### 1. Real application servers

Django behind **gunicorn**:

```
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60
```

Worker count: `(2 × cores) + 1` is the folk rule, but under Kubernetes you
should size to the CPU *limit* you give the Pod, not the node's cores —
gunicorn cannot see your cgroup limit and will happily fork 17 workers on a
Pod limited to 500m CPU, then thrash. For this app, **2–3 workers** and let HPA
add Pods. That is the whole point of horizontal scaling: scale Pods, not
processes inside a Pod.

Frontend behind **nginx**, serving pre-built static files. No Node in the final
image at all.

### 2. Multi-stage builds

The frontend build needs Node, npm, TypeScript, and `node_modules` (~300 MB).
The frontend *runtime* needs none of it — just `dist/` and a web server.

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci                      # not npm install — see 01-foundations/03
COPY . .
ARG VITE_API_BASE=/api          # build-time, and it must be
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build               # → /app/dist

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
```

Everything in the `build` stage is discarded. Final image ~45 MB.

That is the *pattern* — you write the real one, including the nginx config,
in the exercise.

Note `ARG VITE_API_BASE` sitting in the build stage. It has to be there. As
covered in `01-foundations/03`, Vite inlines it into the JavaScript. Defaulting
it to `/api` commits you to the same-origin approach, which is the
recommendation.

### 3. Static files — the gap in `settings.py`

`settings.py` has:

```python
STATIC_URL = "static/"
```

and **no `STATIC_ROOT`**. With `DEBUG=1`, Django's staticfiles app serves admin
CSS/JS straight from the installed packages. With `DEBUG=0` it refuses, and
`collectstatic` has nowhere to write.

Result in production: `/admin` renders as unstyled HTML, and DRF's browsable API
is equally bare. It *works*, it just looks broken — which is worse, because you
won't be sure whether it's a real failure.

Two fixes; pick one.

**whitenoise** — Django serves its own static files, compressed and hashed:

```python
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
# MIDDLEWARE: whitenoise.middleware.WhiteNoiseMiddleware
#             immediately after SecurityMiddleware
```
plus `whitenoise` in `requirements.txt` and `RUN python manage.py collectstatic --noinput`
in the Dockerfile.

Simplest, and entirely adequate for admin + DRF assets on a personal app.
**Take this one.**

**nginx serves them** — mount the collected static into the frontend image or a
shared volume and route `/static/` there in the ingress. Faster, more moving
parts, unnecessary at your traffic.

Note `collectstatic` at build time needs settings to import cleanly without a
database — it does here, `dj_database_url.parse` on the default string doesn't
connect. If it ever doesn't, that's what `DJANGO_SETTINGS_MODULE` overrides or
a build-only settings module are for.

### 4. Not running as root

Both images run as root. If someone escapes the app they are root in the
container, which is a much shorter hop to root on the node than it should be.

```dockerfile
RUN useradd --create-home --uid 10001 app
USER app
```

Then the Pod can also declare `runAsNonRoot: true` and mean it. Two catches:

- Anything writing to disk needs ownership — `MEDIA_ROOT`, `GARMIN_TOKEN_ROOT`,
  `STATIC_ROOT`. `chown` them in the build, and set `fsGroup` on the Pod so the
  PVC mount is group-writable.
- nginx's stock image wants to bind port 80, which needs root. Use
  `nginxinc/nginx-unprivileged` or reconfigure it to listen on 8080. **Listen on
  8080** — ports above 1024 need no privileges, and inside a cluster the port
  number is arbitrary anyway.

## Dev images stay

You are not deleting `docker-compose.yml`. Hot reload and bind mounts are the
right development experience and `CONTEXT.md` documents its quirks already.

You are **adding** a second build target. Two clean ways:

**Separate files** — `backend/Dockerfile` (dev) and `backend/Dockerfile.prod`.
Obvious, slightly duplicated.

**One file, multiple stages** — a `base` stage with deps, then `dev` and `prod`
stages diverging at the end. Build with `--target dev` or `--target prod`.
Less duplication, and the shared base guarantees the same Python and the same
installed packages in both. **Prefer this.**

## What "done" looks like

```bash
docker build --target prod -t runproject-backend:test ./backend
docker run --rm -p 8000:8000 \
  -e DJANGO_DEBUG=0 \
  -e DJANGO_SECRET_KEY=test-only \
  -e DJANGO_ALLOWED_HOSTS=localhost \
  -e DATABASE_URL=postgres://... \
  runproject-backend:test
```

- `/admin` loads **with CSS**
- `docker exec` shows the process is gunicorn, not runserver
- `whoami` inside the container is not root
- `docker images` shows the frontend well under 100 MB

Then run the whole prod stack locally with a `docker-compose.prod.yml` before
Kubernetes ever enters the picture. Debugging a broken gunicorn config is much
easier when it isn't also your first Deployment.
