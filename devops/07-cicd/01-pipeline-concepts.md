# What a pipeline is, and what it's for

## CI and CD are different things

**Continuous Integration** — every push is built and tested automatically. The
point is *fast feedback*: you learn something is broken in three minutes, while
you still remember what you changed, instead of three weeks later.

**Continuous Delivery** — every commit that passes CI is *releasable*. The
artifact exists, tested, ready. Releasing is a decision someone makes.

**Continuous Deployment** — the same, but the release happens automatically.
No human in the loop.

Most people say "CI/CD" and mean the last one. The distinction matters when you
choose: automatic to dev, manual approval to prod, is a completely reasonable
and very common shape.

## Why bother, for a personal project

Honest answer: for one developer on one app, `docker build && kubectl apply`
from your laptop works fine, and pretending otherwise is dishonest.

What a pipeline actually buys you:

**Reproducibility.** The build happens in a clean environment every time. No
"works on my machine because of something I installed in 2023 and forgot."

**Your laptop stops being production infrastructure.** Right now, deploying
requires your Mac, your Docker daemon, your kubeconfig, and you being awake. A
pipeline means a deploy is a `git push`, from anywhere, including a phone.

**It becomes a record.** Every deploy is a commit, a workflow run, a log. When
something breaks at 2am you can answer "what changed and when" in ten seconds.

**Arm64 vs amd64 is solved for free.** Your Mac builds arm64; your VPS runs
amd64. CI runners are amd64. The problem disappears rather than needing buildx.

**It's the skill you said you wanted.** This is the part of DevOps that shows
up in every job description.

## The stages

```
  push
    │
    ▼
┌─────────┐   fast, cheap, parallel — fail here if you're going to fail
│  LINT   │   ruff, tsc, yaml validation
└────┬────┘
     ▼
┌─────────┐   your 46 tests. Also fast.
│  TEST   │
└────┬────┘
     ▼
┌─────────┐   the slow bit. Only if the above passed.
│  BUILD  │   two images, tagged with the commit SHA
└────┬────┘
     ▼
┌─────────┐   trivy / grype on the built images
│  SCAN   │
└────┬────┘
     ▼
┌─────────┐   ghcr.io
│  PUSH   │
└────┬────┘
     ▼
┌─────────┐   migrate Job, then rollout, then verify
│ DEPLOY  │
└────┬────┘
     ▼
┌─────────┐   did it actually work?
│ VERIFY  │   rollout status + a smoke test through the ingress
└─────────┘
```

**Order by cost.** Linting takes 20 seconds and catches typos; building takes
four minutes. Running them the other way round wastes four minutes on every
typo. Fail fast, fail cheap.

**Every stage gates the next.** A failing test must stop the build. This sounds
obvious and is routinely violated by pipelines with `continue-on-error: true`
scattered around after someone got annoyed at a flaky test. A gate you've
disabled is worse than no gate — it looks like protection.

## Build once, deploy many

The single most important rule:

> **The artifact you test is the artifact you deploy.**

Build the image **once**, tag it with the commit SHA, and promote that exact
image through environments. Do not rebuild for production.

```
     commit 680b5c5
          │
          ▼
    build ONCE → ghcr.io/…/backend:680b5c5
          │
    ┌─────┴─────┐
    ▼           ▼
   dev        prod        ← same image, different config
```

Rebuilding for prod means dependencies could resolve differently, a base image
could have moved, and the thing you tested is not the thing you shipped. This
is exactly why `npm ci` and a committed lockfile matter (`01-foundations/03`).

The corollary: **environment differences must be config, never build inputs.**

The awkward exception in this repo is `VITE_API_BASE`, which is baked at build
time. Building with `/api` (same-origin) makes the value environment-independent
— the same bundle is correct on `training.local` and `training.example.com`.
That's a second reason for the same-origin decision, beyond deleting CORS.

## Push vs pull deployment

**Push** — CI has cluster credentials and runs `kubectl apply`.

```
GitHub Actions ──kubeconfig──▶ cluster
```

Simple, obvious, easy to debug. But your CI holds credentials to production, and
the cluster's API must be reachable from GitHub's runners — which means either
exposing port 6443 to the internet or setting up a tunnel.

**Pull / GitOps** — an agent inside the cluster watches a git repo and applies
what it finds.

```
GitHub Actions ──▶ git repo ◀──watches── Argo CD (in cluster)
```

CI never touches the cluster. No inbound access needed at all — the agent polls
outward. Git is the source of truth, so `git revert` is a rollback, and drift
(someone `kubectl edit`ing something) is detected and corrected.

Covered properly in `04-gitops.md`. **Start with push** — it's fewer moving
parts and you'll understand what Argo is automating.

## Environments

```
feature branch → CI only (lint, test, build). No deploy.
dev branch     → auto-deploy to runproject-dev
main branch    → auto-deploy to runproject-prod
tag v*         → optional, if you want explicit releases
```

You're already on `dev` with `main` as the release branch, so this maps onto
what you have. `main` is protected — no direct pushes, PR only — which makes the
branch itself the approval gate.

## What to measure

The four DORA metrics, worth knowing by name:

| Metric | Question |
|---|---|
| **Deployment frequency** | How often do you ship? |
| **Lead time for changes** | Commit → running in production? |
| **Change failure rate** | What fraction of deploys cause a problem? |
| **Time to restore** | How fast do you recover? |

The counterintuitive finding from the research: **frequency and stability are
positively correlated.** Teams that deploy more often have *fewer* failures —
because small changes are easier to review, easier to roll back, and the
pipeline gets exercised constantly.

The practical version for you: a deploy should be boring. If deploying is scary,
you'll do it rarely, so each deploy will be huge, so it'll be scarier. The way
out is to make deploys small and frequent until they stop being interesting.

## Pipeline hygiene

- **Fast.** Under 10 minutes end to end, or you'll stop waiting for it. Cache
  aggressively: pip wheels, npm modules, Docker layers.
- **Deterministic.** A pipeline that fails 1 in 5 runs for no reason trains you
  to ignore failures — which is how a real failure gets ignored.
- **Debuggable from logs alone.** You will be reading a failed run from your
  phone at some point.
- **No secrets in logs.** GitHub masks registered secrets, but a secret you
  `echo` in a constructed string can still leak. Never `set -x` a step that
  handles credentials.
