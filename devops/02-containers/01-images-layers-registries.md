# Images, layers, registries

You already use Docker daily. This fills in the parts that matter once images
have to travel to a cluster instead of staying on your Mac.

## An image is a stack of layers

Each Dockerfile instruction that changes the filesystem produces one layer — an
immutable diff. The image is those layers stacked, plus metadata (entrypoint,
env, exposed ports, user).

Your `backend/Dockerfile`:

```
FROM python:3.12-slim            ← layers 1..n  (the base, ~120 MB)
ENV PYTHONUNBUFFERED=1 ...       ← metadata only, no layer content
WORKDIR /app                     ← tiny layer
RUN apt-get install build-essential libpq-dev curl   ← ~300 MB layer
COPY requirements.txt .          ← tiny layer
RUN pip install -r requirements.txt                  ← ~200 MB layer
COPY . .                         ← your source, small
```

Two consequences you must internalise:

**Layers are cached individually, and the cache invalidates forward.** Change
any layer and every layer after it rebuilds. This is why `COPY requirements.txt`
comes *before* `COPY . .` in your Dockerfile — editing a `.py` file only busts
the last layer, so the slow `pip install` is reused. Whoever wrote that got it
right. If you ever "simplify" it to a single `COPY . .` before `pip install`,
every source edit becomes a full dependency reinstall.

**Deleting a file in a later layer does not shrink the image.** The bytes are
still in the earlier layer; the later layer only records a whitespace-out
marker. This:

```dockerfile
RUN wget huge-thing.tar.gz && tar xf huge-thing.tar.gz
RUN rm huge-thing.tar.gz     # image is NOT smaller
```

Must be one instruction to actually save space:

```dockerfile
RUN wget huge-thing.tar.gz && tar xf huge-thing.tar.gz && rm huge-thing.tar.gz
```

Your existing `RUN apt-get update && apt-get install ... && rm -rf /var/lib/apt/lists/*`
is the same trick, done correctly.

The deeper implication: **anything that was ever in a layer is in the image
forever**, including a secret you `COPY`'d and later deleted. `docker history`
and layer extraction will find it. Never put secrets in a build.

## Base image choice

| Base | Size | Notes |
|---|---|---|
| `python:3.12` | ~1 GB | Full Debian. Every tool present. Wasteful. |
| `python:3.12-slim` | ~120 MB | Debian minus docs/locales/compilers. **What you use.** Right default. |
| `python:3.12-alpine` | ~50 MB | musl libc, not glibc. Python wheels are built for glibc, so pip compiles from source — slower builds, and subtle breakage in numeric libs. **Avoid for Python.** |
| `gcr.io/distroless/python3` | ~50 MB | No shell, no package manager. Smallest attack surface. No `kubectl exec` debugging either. |

`node:20-alpine` for the frontend is fine — the Node ecosystem handles musl
well, and the final image only serves static files anyway.

## Tags, digests, and the `:latest` trap

A tag is a mutable pointer. `myapp:latest` means something different after
every push.

Deploying `:latest` to Kubernetes breaks in a way that is genuinely hard to
debug: you push a new image, run `kubectl apply`, and **nothing happens**. The
Deployment spec is byte-identical to what's already there, so the controller
has nothing to reconcile — Kubernetes acts on declared state, not on what
happens to be in a registry. Your Pods keep running the old image. Then a node
restarts, pulls fresh, and *that one Pod* is on new code. Now two versions
serve traffic and you have no idea which is which.

**Rule: tag every image with the git commit SHA.**

```
ghcr.io/rohittgajula/runproject-backend:680b5c5
```

The tag changes → the Deployment spec changes → Kubernetes rolls. And the tag
tells you exactly which commit is live. A moving tag alongside it
(`:main`) is fine for humans, as long as manifests never reference it.

For maximum rigour, reference the **digest**:

```
ghcr.io/…/runproject-backend@sha256:9f2c…
```

Immutable by construction. Slightly less readable; worth it for production.

## Registries

Your image must live somewhere the cluster can pull from. Locally on kind you
can skip this with `kind load docker-image`, which copies straight from your
Docker daemon into the cluster's nodes — useful early, but not how real
deployment works, so move to a registry before CI.

**GitHub Container Registry (`ghcr.io`)** is the obvious choice here: your repo
is already on GitHub, GitHub Actions authenticates to it with a built-in token
(no secret to manage), and private images are free for personal accounts.

```
ghcr.io/rohittgajula/runproject-backend:<sha>
ghcr.io/rohittgajula/runproject-frontend:<sha>
```

Note the repo is **private**, so the cluster needs credentials to pull:
an `imagePullSecret` of type `kubernetes.io/dockerconfigjson`. Forgetting this
gives you `ErrImagePull` / `ImagePullBackOff`, which reads like a network
problem and is actually an auth problem. Check with:

```bash
kubectl describe pod <name> | tail -20
```

The Events section says `unauthorized` when it's auth and `no such host` when
it's network.

## imagePullPolicy

| Value | Behaviour |
|---|---|
| `Always` | Pull every Pod start. Correct for mutable tags, wasteful for SHA tags. |
| `IfNotPresent` | Use local copy if present. **Correct for SHA tags** — the tag is immutable so a cached copy is definitionally right. |
| `Never` | Never pull. Only for `kind load` workflows. |

Default is `IfNotPresent` — *except* when the tag is `latest`, where it silently
becomes `Always`. Another reason not to use `latest`: the behaviour changes
under you.

## Multi-architecture

Your Mac is **arm64** (Apple Silicon). Almost every VPS is **amd64**. An image
built on your laptop with a plain `docker build` will not run on the VPS:

```
exec format error
```

Two ways to handle it:

**Build in CI on an amd64 runner.** GitHub Actions' `ubuntu-latest` is amd64.
The image is built where it will run. Simplest — and you're building in CI
anyway.

**Build multi-arch with buildx.** One tag serving both architectures:

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t ghcr.io/... --push .
```

Slower (arm64 emulation on an amd64 runner is genuinely slow) but the image
works everywhere, including on your Mac. Worth it if you want to run the exact
production image locally.

For this project: build amd64 in CI, and don't spend the extra minutes on
multi-arch until you actually need it.

## Commands worth knowing

```bash
docker history --no-trunc <image>
```
Every layer with its size. Where you find the 400 MB you didn't expect.

```bash
docker image inspect <image> --format '{{.Config.Env}}'
```
Confirms what env is baked in — useful to prove `VITE_API_BASE` really is in
the bundle.

```bash
docker run --rm -it --entrypoint sh <image>
```
Poke around a built image without running the app.

```bash
docker build --no-cache -t x .
```
Prove the build works from cold. Do this before trusting CI.
