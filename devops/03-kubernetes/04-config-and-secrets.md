# ConfigMaps, Secrets, and the Garmin token problem

## The split

Your `docker-compose.yml` has one `&backend_env` block mixing both. In
Kubernetes you separate them:

**ConfigMap** — non-sensitive. Stored plainly, readable by anyone with get
access to the namespace.

```
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=training.example.com
MEDIA_ROOT=/data/media
GARMIN_TOKEN_ROOT=/data/garmin_tokens
REDIS_URL=redis://redis:6379/0
CORS_ALLOWED_ORIGINS=https://training.example.com
LOG_AI_PROVIDER=anthropic
DJANGO_SETTINGS_MODULE=config.settings
```

**Secret** — sensitive.

```
DJANGO_SECRET_KEY
DATABASE_URL          (contains the password)
POSTGRES_PASSWORD
ANTHROPIC_API_KEY
GEMINI_API_KEY
```

`REDIS_URL` is in the ConfigMap because your Redis has no password. That is
acceptable inside a cluster where only your Pods can reach it — and a thing to
revisit if the cluster ever hosts anything else.

## Secrets are base64, not encrypted

```bash
kubectl get secret backend-secrets -o jsonpath='{.data.DJANGO_SECRET_KEY}' | base64 -d
```

That's it. That's the whole protection. Base64 is an encoding, not a cipher.

By default Secrets are stored **in plaintext in etcd**. Anyone with etcd access,
an etcd backup, or `get secrets` RBAC in the namespace has your keys.

What you actually get from Secrets versus ConfigMaps:
- Not printed by `kubectl describe`
- Can be RBAC'd separately
- Never written to node disk — mounted as tmpfs
- Marked as sensitive so tooling can redact them

That's a meaningful improvement over a ConfigMap. It is not encryption.

Real options, in ascending order:

1. **Encryption at rest** — configure an `EncryptionConfiguration` on the API
   server so Secrets are encrypted in etcd. Free, and worth doing on the VPS.
2. **Sealed Secrets (Bitnami)** — encrypt with a cluster public key, commit the
   ciphertext to git safely, a controller decrypts in-cluster. **The right
   answer for a GitOps setup like yours.**
3. **External Secrets Operator** — sync from Vault, AWS Secrets Manager, etc.
   Overkill here.

**Never commit a plain Secret manifest to git.** Sealed Secrets exists precisely
so you can commit the encrypted form.

## Creating them

Imperatively, for things that should never be in a file:

```bash
kubectl create secret generic backend-secrets -n runproject \
  --from-literal=DJANGO_SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(50))')" \
  --from-literal=ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY"
```

From your existing `.env` — convenient, but read it first, it'll pull in
everything including things that belong in the ConfigMap:

```bash
kubectl create secret generic backend-secrets --from-env-file=.env -n runproject
```

Dry-run to see the YAML without applying:

```bash
kubectl create secret generic x --from-literal=a=b --dry-run=client -o yaml
```

## Injecting into Pods

**As env vars, in bulk** — matches your compose setup exactly:

```yaml
envFrom:
  - configMapRef:
      name: backend-config
  - secretRef:
      name: backend-secrets
```

**Individually**, when you need to rename:

```yaml
env:
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: backend-secrets
        key: DATABASE_URL
```

**As files** — when the app wants a file, or when you want live updates:

```yaml
volumeMounts:
  - name: config
    mountPath: /etc/config
    readOnly: true
volumes:
  - name: config
    configMap:
      name: backend-config
```

## The update problem

**Env vars do not update.** Change a ConfigMap and a running Pod keeps the old
values forever — env is set once at process start. You must restart:

```bash
kubectl rollout restart deploy/backend -n runproject
```

**Mounted files do update**, within a minute or so, via a symlink swap. But your
Django process read them at import time and won't notice. Live reload only helps
if the app watches the file, which this one doesn't.

The clean fix, and standard practice: put a hash of the config into the Pod
template annotation, so changing config changes the Pod spec and triggers a
rollout automatically:

```yaml
template:
  metadata:
    annotations:
      checksum/config: "<sha256 of the configmap>"
```

Kustomize does this for free with `configMapGenerator` (it appends a hash to the
ConfigMap *name*, which changes the Deployment's reference). Helm does it with a
`sha256sum` template function. Doing it by hand is why people adopt one of those
two.

## The Garmin token problem — think about this one

Compose does:

```yaml
- ${GARMIN_TOKEN_DIR:-~/Library/Caches/garmin-mcp/garth}:/data/garmin_tokens/athlete_1:ro
```

Three things make this hard in Kubernetes:

1. **Your Mac isn't there.** Nothing to bind-mount.
2. **They're per-athlete**, keyed by directory name (`athlete_1`). Multi-tenant
   by design.
3. **They refresh.** OAuth tokens get rotated by `garminconnect`. `:ro` works
   today only because your Mac's copy is refreshed by other means. In-cluster,
   a read-only mount means the token eventually expires and Garmin sync dies
   silently — the worst kind of failure, because everything else keeps working.

So: **a Secret is the wrong shape.** Secret volumes are read-only, and even if
you made it writable the write wouldn't persist.

Options, with honest trade-offs:

| Option | How | Verdict |
|---|---|---|
| **PVC** | Small RWO volume at `/data/garmin_tokens`, seeded once by copying your Mac's tokens in with `kubectl cp`. Writable, persists, refresh works. | **Do this.** Simple and correct. |
| Secret + init container | Init copies Secret → emptyDir, app writes to emptyDir | Refresh works until the Pod restarts, then silently reverts to the stale token. Worse than it looks. |
| Refactor to DB storage | Store tokens in Postgres on the Athlete model | Cleanest long-term, real code change, and now they're in your DB backups (good and bad) |

Take the PVC now. Note the refactor as a real option — it's the one that scales
to actual multi-tenancy, since a PVC per athlete doesn't.

Seeding it:

```bash
kubectl cp ~/Library/Caches/garmin-mcp/garth \
  runproject/backend-xxxxx:/data/garmin_tokens/athlete_1
```

Write that down in a runbook. It is a manual step that must happen exactly once,
and in six months you will not remember it. `08-operations/03` is where it goes.

## The database password, and why compose's default is a trap

```yaml
POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-runproject}
```

Password `runproject`, in git, as a default. Fine locally. In production the
Secret must hold a generated password, and `DATABASE_URL` must be built from
the same value. Two places, one value — get them out of step and you get an
authentication error that looks like a networking problem.

Generate once:

```bash
openssl rand -base64 24 | tr -d '\n'
```

Put it in the Secret as `POSTGRES_PASSWORD`, and construct `DATABASE_URL` in the
same Secret with the same string. Don't try to be clever with references —
Kubernetes has no string interpolation between Secret keys.

## Rules

1. Never commit plaintext Secrets. Sealed Secrets or nothing.
2. Different values per environment; **never share prod secrets with dev.**
3. `SECRET_KEY` differs between environments. Same key means a dev session cookie
   is valid in prod.
4. Rotate anything that has ever been in a terminal you screen-shared, a log, or
   a git history — including through a `--from-literal` in your shell history.
5. `kubectl get secret -o yaml` prints the base64. Be careful what's on screen.
