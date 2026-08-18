# Translating docker-compose.yml, line by line

Your compose file is a good spec. Here is what every construct in it becomes.

## Concept mapping

| compose | Kubernetes | Note |
|---|---|---|
| `services:` entry | Deployment/StatefulSet **+ Service** | Two objects, not one |
| `image:` | `spec.template.spec.containers[].image` | Use a SHA tag |
| `build:` | Nothing. Build outside the cluster. | CI's job |
| `command:` | `command:` / `args:` | See the pitfall below |
| `environment:` | ConfigMap + Secret via `envFrom` | Split by sensitivity |
| `env_file:` | `kubectl create secret --from-env-file` | |
| `ports: "8000:8000"` | Service `port` / `targetPort` | Host mapping disappears |
| `volumes:` named | PVC | Pick an access mode deliberately |
| `volumes:` bind mount | PVC, ConfigMap, or **nothing** | Usually a dev-only concern |
| `depends_on: service_healthy` | **No equivalent** | initContainer, or let it crash-loop |
| `healthcheck:` | `readinessProbe` / `livenessProbe` | Two probes, different meanings |
| `restart: always` | Default behaviour | `restartPolicy: Always` |
| `deploy.replicas` | `spec.replicas` | |
| networks | Flat cluster network + NetworkPolicy | Everything can reach everything by default |
| `docker compose up` | `kubectl apply -f` | Declarative in both cases |

## Service by service

### `db` → StatefulSet + headless Service

```yaml
# compose
image: postgres:16-alpine
environment:
  POSTGRES_DB: runproject
  POSTGRES_USER: runproject
  POSTGRES_PASSWORD: runproject      # ← default in git
volumes:
  - pgdata:/var/lib/postgresql/data
ports: ["5433:5432"]
healthcheck: pg_isready -U runproject
```

Becomes:
- **StatefulSet**, 1 replica, `serviceName: db`
- `volumeClaimTemplates` for `pgdata`, **not** a `volumes:` entry
- **`subPath: postgres` on the mount** — or initdb fails on a non-empty dir
  (`03-kubernetes/05`)
- Password from a Secret, generated, never the compose default
- **Headless Service** (`clusterIP: None`) — StatefulSets need per-Pod DNS
- `ports: 5433:5432` **disappears entirely**. That mapping existed to avoid
  colliding with a Postgres on your Mac. Pods have their own IPs; the port is
  5432, full stop.
- `healthcheck` → `readinessProbe: exec: pg_isready`
- **Guaranteed QoS**: requests == limits

### `redis` → Deployment + Service

Straightforward. 1 replica, no PVC, `exec: redis-cli ping` as the probe,
ClusterIP on 6379. Port mapping 6380 disappears for the same reason.

### `backend` → Deployment + Service

```yaml
# compose
command: sh -c "python manage.py migrate --noinput && python manage.py runserver 0.0.0.0:8000"
volumes:
  - ./backend:/app                        # bind mount for hot reload
  - media:/data/media
  - ${GARMIN_TOKEN_DIR}:/data/garmin_tokens/athlete_1:ro
depends_on: {db: healthy, redis: healthy}
```

Four things change:

1. **The `migrate &&` prefix comes out.** With 2 replicas it's a race
   (`03-kubernetes/06`). Migrations become a Job.
2. **`runserver` becomes gunicorn.** The image's CMD, not an override.
3. **`./backend:/app` is deleted.** Hot reload is a development concern; the
   image *is* the code in production. Keeping this in k8s would mean shipping
   an image and then overwriting it — the artifact you tested isn't what runs.
4. **The Garmin bind mount becomes a writable PVC.** Your Mac isn't there, and
   `:ro` breaks token refresh (`03-kubernetes/04`).

`depends_on` has no equivalent. Either an initContainer that waits for Postgres,
or accept a CrashLoopBackOff for the first 20 seconds until the DB is up.
Kubernetes' native answer is the latter — it will converge.

Plus: three probes, resources, `terminationGracePeriodSeconds`, `preStop` sleep,
`automountServiceAccountToken: false`.

### `worker` → Deployment, **no Service**

```yaml
command: celery -A config worker -l info
environment: *backend_env
```

Same image, same config, different command. Nothing connects *to* it — it pulls
from Redis — so it gets no Service. Resisting the urge to write one is a sign
you've understood what a Service is for.

Two specifics:
- **Longest grace period of anything you run.** Celery's SIGTERM is a warm
  shutdown; the period must exceed your longest task. Measure a FIT parse and
  set it from that. (`03-kubernetes/07`)
- Mounts `media` (writes parsed data) and `garmin-tokens` (syncs).

### `beat` → Deployment, **no Service, replicas: 1, Recreate**

```yaml
command: celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

The one workload with a hard correctness constraint on replica count. Two beats
= every periodic task fires twice, including the hourly Garmin sync that
`celery.py` explicitly says is rate-limited on purpose.

`strategy: Recreate`, because a RollingUpdate briefly runs two — the exact thing
you're preventing.

Comment both in the YAML. In six months `replicas: 1` looks untuned.

### `frontend` → Deployment + Service

```yaml
command: npm run dev -- --host 0.0.0.0
volumes:
  - ./frontend:/app
  - /app/node_modules
environment:
  VITE_API_BASE: http://localhost:8000/api
```

The biggest change of all. In production this becomes nginx serving pre-built
static files:

- No `command` — the image's nginx CMD
- No volumes at all. `/app/node_modules` as an anonymous volume was a trick to
  stop the bind mount shadowing the installed modules; there's no bind mount
  now, so it's meaningless.
- **`VITE_API_BASE` is not runtime config.** It's baked into the JS at build
  time. Build with `/api` and let the ingress route it. A ConfigMap cannot
  change this and trying is a wasted afternoon. (`01-foundations/03`)
- Port 8080, not 5173. Not 80, so nginx needs no root.

Also worth noting: `CONTEXT.md` warns that Vite's watcher sometimes misses newly
created files and you restart the container. **That entire class of problem
disappears** in production — there is no watcher, just files nginx serves. One
of the quieter wins of a real build step.

## What has no equivalent

**`depends_on` with `condition: service_healthy`.** Kubernetes has no ordering
between Deployments. Options: an initContainer that polls, or let it crash-loop
until the dependency appears. The second is idiomatic and self-healing; the
first makes logs cleaner.

**Bind-mounting source.** Deliberately absent — it's the antithesis of an
immutable artifact. For a k8s dev loop with hot reload, use Tilt or Skaffold,
which handle sync-and-rebuild properly. Don't hand-roll it.

**`docker compose exec`.** `kubectl exec -it deploy/backend -- python manage.py shell`
works, but treat it as debugging only. Anything you'd run routinely should be a
Job (twelve-factor XII).

**`.env` file loading.** compose reads `.env` from disk automatically. In k8s
you create ConfigMaps and Secrets explicitly. This is a genuine improvement —
you can see exactly what a Pod gets.

## Env var split

From the `&backend_env` anchor:

**ConfigMap `backend-config`:**
```
DJANGO_SETTINGS_MODULE=config.settings
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=training.example.com
REDIS_URL=redis://redis:6379/0
MEDIA_ROOT=/data/media
GARMIN_TOKEN_ROOT=/data/garmin_tokens
LOG_AI_PROVIDER=anthropic
CORS_ALLOWED_ORIGINS=https://training.example.com
```

**Secret `backend-secrets`:**
```
DJANGO_SECRET_KEY
DATABASE_URL
POSTGRES_PASSWORD
ANTHROPIC_API_KEY
GEMINI_API_KEY
```

Notes:

- `DATABASE_URL` and `POSTGRES_PASSWORD` must hold **the same password**.
  Kubernetes has no interpolation between Secret keys; you set both by hand
  from one generated value. Out of step → an auth error that reads like a
  network problem.
- `REDIS_URL` sits in the ConfigMap because your Redis is unauthenticated —
  reasonable inside a cluster only your Pods can reach, and worth revisiting if
  that stops being true.
- **`CORS_ALLOWED_ORIGINS` becomes vestigial** under same-origin. Set it
  correctly anyway; a stale wrong value is a landmine if you ever split origins.
- All three of backend, worker and beat consume **both** — exactly as the
  `&backend_env` YAML anchor does today. That anchor is compose's version of
  `envFrom`.

## Migration order

Do it in dependency order so each step is verifiable:

```
1. Namespace, ConfigMap, Secret
2. PVCs                                     kubectl get pvc → Bound
3. db StatefulSet + headless Service        exec pg_isready
4. redis Deployment + Service               exec redis-cli ping
5. migrate Job                              kubectl logs job/migrate
6. backend Deployment + Service             port-forward, curl /api/health/
7. worker Deployment                        logs show registered tasks
8. beat Deployment                          logs show the schedule
9. frontend Deployment + Service            port-forward, load the page
10. Ingress                                 curl through the ingress
11. TLS                                     staging cert, then prod
12. HPA, KEDA, PDB
13. Backup CronJob                          restore-test it
```

**Verify each step before the next.** Applying all fifteen manifests at once and
debugging the result is genuinely miserable — you get a wall of interdependent
failures with no way to tell cause from effect.
