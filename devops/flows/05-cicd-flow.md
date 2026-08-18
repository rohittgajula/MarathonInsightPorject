# Flow: the branch and environment model

## Branches to environments

```
  feature/xyz ──┐
                │  push
                ▼
        ┌───────────────┐
        │ CI only       │   lint · test · build (not pushed)
        │ no deploy     │   fast feedback, nothing shipped
        └───────┬───────┘
                │ PR
                ▼
             ┌─────┐
             │ dev │ ────push───▶ CI ─▶ build ─▶ ghcr ─▶ runproject-dev
             └──┬──┘                                     auto, no approval
                │ PR (reviewed)
                ▼
             ┌──────┐
             │ main │ ───push───▶ CI ─▶ build ─▶ ghcr ─▶ runproject-prod
             └──────┘                                    ⏸ approval gate
```

You are already on `dev` with `main` as the release branch, so this maps onto
what you have. Protect `main`: PR required, CI must pass, no direct pushes.

## The artifact, promoted not rebuilt

```
              commit 680b5c5
                    │
              ┌─────▼─────┐
              │ BUILD ONCE│
              └─────┬─────┘
                    ▼
        ghcr.io/…/backend:680b5c5
        ghcr.io/…/frontend:680b5c5
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
    ┌───────────┐       ┌───────────┐
    │    dev    │       │   prod    │
    ├───────────┤       ├───────────┤
    │ ns: -dev  │       │ ns: -prod │
    │ 1 replica │       │ 2 replicas│
    │ dev CM    │       │ prod CM   │
    │ dev Secret│       │ prod Secret│
    │ gemini    │       │ anthropic │
    │ LE staging│       │ LE prod   │
    └───────────┘       └───────────┘

    SAME IMAGE. Only config differs.
```

**If you rebuild for prod, you deploy something you never tested.** This is the
rule people break, and it's what `npm ci` plus a committed lockfile exist to
protect.

The awkward exception here is `VITE_API_BASE`, baked into the JS at build time.
Building with `/api` (same-origin) makes the bundle host-independent, so one
image is correct in both environments. That's the second reason for the
same-origin decision.

## Job graph in one workflow

```
                  ┌──────────┐
                  │ checkout │
                  └────┬─────┘
              ┌────────┼────────┐
              ▼        ▼        ▼
        ┌────────┐┌────────┐┌────────┐   parallel — fail fast, fail cheap
        │  lint  ││  test  ││ tsc/   │
        │  ruff  ││ pytest ││ build  │
        └────┬───┘└───┬────┘└───┬────┘
             └────────┼─────────┘
                      ▼ needs: [lint, test, build]
              ┌───────────────┐
              │ build & push  │   the slow bit, only if the above passed
              │  amd64, :sha  │
              └───────┬───────┘
                      ▼ needs: build
              ┌───────────────┐
              │    scan       │   trivy HIGH,CRITICAL
              └───────┬───────┘
                      ▼
              ┌───────────────┐
              │    deploy     │   environment: production
              │               │   ⏸ required reviewer
              │  1. migrate   │
              │  2. apply     │
              │  3. rollout   │
              │     status    │   ← blocks. without it CI lies.
              │  4. smoke     │
              └───────────────┘
```

Ordered by cost: 20-second checks before 4-minute builds. Running them the other
way wastes four minutes on every typo.

## Where secrets live

```
  ┌──────────────────────────────────────────────────────┐
  │ GITHUB                                               │
  │   repo secrets       → things every env needs        │
  │   environment secrets→ KUBECONFIG (per env, gated)   │
  │   GITHUB_TOKEN       → ghcr push, automatic          │
  └──────────────────────────────────────────────────────┘
                          │  never crosses
  ┌──────────────────────────────────────────────────────┐
  │ GIT REPO                                             │
  │   SealedSecret ciphertext  ← safe to commit          │
  └──────────────────┬───────────────────────────────────┘
                     ▼ controller decrypts in-cluster
  ┌──────────────────────────────────────────────────────┐
  │ CLUSTER                                              │
  │   Secret backend-secrets                             │
  │     DJANGO_SECRET_KEY, DATABASE_URL, API keys        │
  └──────────────────────────────────────────────────────┘
                     ▲
  ┌──────────────────┴───────────────────────────────────┐
  │ YOUR MAC                                             │
  │   .env (gitignored)  ← local dev only                │
  │   sealed-secrets private key BACKUP ← off-cluster    │
  └──────────────────────────────────────────────────────┘
```

The kubeconfig belongs in GitHub and never in the cluster. The Anthropic key
belongs in the cluster and never in GitHub. Keeping that straight is most of
secret hygiene.

## Push vs GitOps

```
  PUSH                              PULL (GitOps)

  Actions ──kubeconfig──▶ cluster   Actions ──▶ git ◀──polls── Argo CD
                                                              (in cluster)
  ✅ simple, easy to debug          ✅ no cluster creds in CI
  ✅ obvious ordering               ✅ NO inbound access needed
  ❌ CI holds prod credentials      ✅ drift detected + corrected
  ❌ 6443 must be reachable         ✅ git revert = rollback
                                    ❌ another component to run
                                    ❌ ordering needs sync waves
```

Start with push. Move to Argo when exposing 6443 to CI starts to bother you —
that discomfort is correct.

## A failed deploy

```
  push main
     │
     ▼
  tests pass, image built and pushed
     │
     ▼
  migrate Job ── FAILS (bad migration)
     │
     ▼
  kubectl wait → non-zero exit
     │
     ▼
  ✗ workflow red
     │
     ▼
  ⛔ rollout NEVER RAN
     old code, old schema, still serving
     users saw nothing
```

Gating the rollout on the migration Job is what makes this safe. Without it,
you'd have rolled new code against a half-migrated schema — a much worse place
to be at 2am.
