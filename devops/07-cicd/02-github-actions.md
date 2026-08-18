# GitHub Actions for this repo

## Anatomy

```
Workflow (.github/workflows/*.yml)
└── triggered by an event (push, pull_request, schedule, workflow_dispatch)
    └── Jobs — run in PARALLEL by default, each on a fresh runner
        └── Steps — run in SEQUENCE, share the runner's filesystem
            └── `uses:` a published action, or `run:` a shell command
```

Key facts that shape everything:

- **Each job gets a clean VM.** Nothing carries between jobs — not files, not
  the Docker daemon, not the checkout. To pass data between jobs you use
  `outputs` (small values) or `actions/upload-artifact` (files). This surprises
  people who expect a shared workspace.
- **Jobs are parallel unless you add `needs:`.** That's how you build the stage
  gating from `01-pipeline-concepts.md`.
- **Runners are amd64** on `ubuntu-latest` — which is what your VPS needs, and
  why building in CI sidesteps the arm64 problem entirely.

## Your workflows

Three files, each with one job to do:

| File | Trigger | Does |
|---|---|---|
| `ci.yml` | every push + PR | lint, test, verify both images build |
| `deploy-dev.yml` | push to `dev` | build, push, deploy to `runproject-dev` |
| `deploy-prod.yml` | push to `main` | same, to `runproject-prod`, with approval |

Splitting them means a PR runs a fast CI-only workflow, and the slow deploy path
only runs when it can actually deploy.

## The shape of `ci.yml`

```yaml
name: CI
on:
  push:
    branches: [dev, main]
  pull_request:

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true      # a new push cancels the old run.
                                # Without this, pushing three times queues
                                # three full runs and you wait for all of them.

jobs:
  backend-test:
    runs-on: ubuntu-latest
    services:                   # sidecar containers on the runner
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_USER: runproject
          POSTGRES_DB: runproject_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-retries 5
        ports: ['5432:5432']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip            # caches wheels keyed on requirements.txt
      - run: pip install -r backend/requirements.txt
      - run: python -m pytest tests/ -q
        working-directory: backend

  frontend-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
        working-directory: frontend
      - run: npm run build      # tsc -b runs first — this is your type check
        working-directory: frontend
```

Notes specific to you:

**The `services:` block is worth understanding.** It gives the job a real
Postgres. Your 46 tests are all pure logic (segmentation, metrics, extraction)
and need none of it — but `CONTEXT.md` lists "no database tests" as a known gap,
and the worst bugs lived in plan/readiness/timezone code. Wire up the service
now so adding `pytest-django` later is a two-line change rather than a
project.

**`npm run build` IS your frontend type check**, because `package.json` runs
`tsc -b` before `vite build`. That's why fixing the two `tsc` errors is lab
zero: without it this job can never pass, and nothing downstream runs.

**`cache: pip` / `cache: npm`** are free and cut minutes. The npm cache needs
`cache-dependency-path` pointing at your lockfile since the project isn't at
the repo root.

## The shape of a deploy workflow

```yaml
name: Deploy prod
on:
  push:
    branches: [main]
  workflow_dispatch:            # lets you re-run a deploy by hand from the UI

concurrency:
  group: deploy-prod
  cancel-in-progress: false     # NEVER cancel a deploy mid-flight.
                                # Queue them instead.

permissions:
  contents: read
  packages: write               # to push to ghcr.io
  id-token: write               # for OIDC, if you use it

jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
      sha: ${{ steps.meta.outputs.sha }}
    steps:
      - uses: actions/checkout@v4
      - id: meta
        run: echo "sha=${GITHUB_SHA::7}" >> "$GITHUB_OUTPUT"

      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}    # built in, no setup

      - uses: docker/build-push-action@v6
        with:
          context: ./backend
          target: prod
          push: true
          tags: ghcr.io/${{ github.repository_owner }}/runproject-backend:${{ steps.meta.outputs.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - uses: docker/build-push-action@v6
        with:
          context: ./frontend
          push: true
          build-args: VITE_API_BASE=/api
          tags: ghcr.io/${{ github.repository_owner }}/runproject-frontend:${{ steps.meta.outputs.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment: production      # ← this is where approval gating lives
    steps:
      - uses: actions/checkout@v4
      - uses: azure/setup-kubectl@v4
      - run: |
          mkdir -p ~/.kube
          echo "${{ secrets.KUBECONFIG }}" | base64 -d > ~/.kube/config
          chmod 600 ~/.kube/config

      # 1. migrate, and WAIT
      - run: |
          sed "s|IMAGE_TAG|${{ needs.build.outputs.sha }}|g" k8s/migrate-job.yaml | kubectl apply -f -
          kubectl wait --for=condition=complete job/migrate-${{ needs.build.outputs.sha }} \
            -n runproject-prod --timeout=300s

      # 2. roll
      - run: |
          cd k8s/overlays/prod
          kustomize edit set image ghcr.io/.../runproject-backend=ghcr.io/.../runproject-backend:${{ needs.build.outputs.sha }}
          kustomize edit set image ghcr.io/.../runproject-frontend=ghcr.io/.../runproject-frontend:${{ needs.build.outputs.sha }}
          kubectl apply -k .

      # 3. VERIFY — without this, CI goes green before anything has rolled
      - run: |
          kubectl rollout status deploy/backend -n runproject-prod --timeout=5m
          kubectl rollout status deploy/frontend -n runproject-prod --timeout=5m
          kubectl rollout status deploy/worker -n runproject-prod --timeout=5m

      # 4. smoke test through the real ingress
      - run: curl -fsS https://training.example.com/api/health/

      # 5. on failure, say what went wrong
      - if: failure()
        run: |
          kubectl get pods -n runproject-prod
          kubectl describe pods -n runproject-prod | tail -50
          kubectl logs -n runproject-prod -l app=backend --tail=100 --previous || true
```

You write the real versions. The parts that matter:

**`cache-from/to: type=gha`** — GitHub's own build cache. Layer caching across
runs. Without it every build reinstalls every dependency from scratch. This one
line is often the difference between a 6-minute and a 90-second build.

**`environment: production`** — GitHub Environments give you required reviewers,
wait timers, and environment-scoped secrets. Setting a required reviewer on
`production` turns push-to-main into "push, then approve in the UI." Good middle
ground while you're still learning.

**Step 3 is not optional.** `kubectl apply` returns immediately. Without
`rollout status`, a Pod that CrashLoopBackOffs reports as a successful deploy
and you find out from the app being down.

**Step 5, `if: failure()`.** The dump of pod state on failure is what turns a
red X into a diagnosis. `--previous` on the logs gets the crashed attempt, not
the current one.

## `GITHUB_TOKEN` vs a PAT

Every workflow run gets an automatic `secrets.GITHUB_TOKEN`, scoped to the repo
and expiring when the run ends. With `permissions: packages: write` it can push
to `ghcr.io` under your namespace.

**Use it.** No secret to create, rotate, or leak. Only reach for a Personal
Access Token if you need cross-repo access.

Note: images pushed to `ghcr.io` from a private repo are private, but the
package's visibility is set independently of the repo's. Check it after the
first push, and make sure your cluster's `imagePullSecret` matches.

## Getting a kubeconfig into CI

This is the awkward part of push-based deploy, and the reason GitOps exists.

You need `secrets.KUBECONFIG` — base64 of a kubeconfig. **Not your admin
kubeconfig.** Build one for the CI ServiceAccount from `03-kubernetes/08`, with
permissions limited to: patch Deployments, manage Jobs, read Pods and logs, in
one namespace. Nothing on Secrets, nothing cluster-wide.

You also need GitHub's runners to *reach* your cluster API. Options:

| Option | Trade-off |
|---|---|
| Expose 6443 publicly | Simple. Your control plane is on the internet. Restrict by source IP if your provider allows — GitHub publishes its runner ranges, but they're large and change. |
| Tailscale / WireGuard | Runner joins your private network. `tailscale/github-action` makes this genuinely easy. **Good option.** |
| **GitOps (Argo CD)** | **No inbound access at all.** The cluster polls out. Solves the problem by deleting it. |

That table is the honest argument for GitOps. Start with push to learn the
mechanics; the moment exposing 6443 makes you uncomfortable, that discomfort is
correct, and `04-gitops.md` is the answer.

## Things that will waste your time

- **YAML `on:` gets parsed as boolean true** in some tools. GitHub handles it,
  but if you ever lint workflows with a strict YAML parser, quote it: `"on":`.
- **`${{ }}` inside `run:` is string interpolation before the shell sees it.**
  An untrusted value (a PR title, a branch name) becomes shell code. Pass values
  through `env:` instead of interpolating directly into a script.
- **Matrix builds multiply minutes.** `strategy.matrix` over 3 Python versions
  triples your usage. You need one version.
- **Default `GITHUB_TOKEN` permissions** may be read-only depending on org
  settings. Declare `permissions:` explicitly at the workflow level.
- **`actions/checkout` fetches depth 1** by default. If a step needs history
  (changelog generation, `git describe`), set `fetch-depth: 0`.
