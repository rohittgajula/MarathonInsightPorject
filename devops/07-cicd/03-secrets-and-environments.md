# Secrets in CI, and environment promotion

## The three places secrets live

```
1. GitHub repo/environment secrets   → CI needs them (registry, kubeconfig)
2. Kubernetes Secrets                → the app needs them (API keys, DB)
3. Your .env on disk                 → local dev only, gitignored
```

Keep them separate and know which is which. The kubeconfig belongs in GitHub and
must never be in the cluster's own Secrets; the Anthropic key belongs in the
cluster and has no business in GitHub.

## GitHub secrets

| Scope | Available to | Use for |
|---|---|---|
| **Repository** | every workflow | Things every environment needs |
| **Environment** | only jobs declaring `environment: X` | **Per-environment credentials** |
| **Organization** | selected repos | Not relevant here |

**Use Environment secrets for anything environment-specific.** A `KUBECONFIG`
secret scoped to the `production` environment can only be read by a job that
declares `environment: production` — which is also the job that requires
approval. That's a real control, not a naming convention.

```
Environment: development     Environment: production
  KUBECONFIG (dev SA)          KUBECONFIG (prod SA)
                               required reviewers: you
                               wait timer: 0
```

### Masking is not protection

GitHub replaces registered secret values with `***` in logs. It's a safety net
with real holes:

- A secret you transform (base64, substring, JSON-embed) is **not** masked
- A secret in a *file* you `cat` is not masked
- `set -x` prints commands before masking applies in some shells

Never echo a secret. Never `set -x` in a step handling one. If you think a
secret leaked into a log, **rotate it** — deleting the log run is not enough,
because it may already have been read.

### OIDC, the modern way

Instead of storing a long-lived credential, GitHub can mint a short-lived token
that a cloud provider trusts, scoped to a specific repo and branch.

```yaml
permissions:
  id-token: write
```

No secret is stored anywhere. A leaked workflow file gives an attacker nothing.
Supported by AWS, GCP, Azure, and Vault.

For a self-hosted k3s cluster this doesn't directly apply — there's no cloud IAM
to federate with. Know it exists; it's the right answer the moment a cloud is
involved, and it's what interviewers ask about.

## Secrets in git, for the cluster

Your k8s manifests are in git. Your app needs an Anthropic key. These are in
tension.

**Never commit a plain Secret manifest.** Base64 is not encryption
(`03-kubernetes/04`), and git history is forever — removing it in a later commit
does nothing.

### Sealed Secrets — the right answer here

```bash
helm install sealed-secrets sealed-secrets/sealed-secrets -n kube-system
```

A controller in the cluster generates a keypair. You encrypt with the **public**
key; only the controller can decrypt.

```bash
kubectl create secret generic backend-secrets \
  --from-literal=ANTHROPIC_API_KEY="$KEY" \
  --dry-run=client -o yaml \
  | kubeseal --format yaml > k8s/base/sealed-secrets.yaml
```

The output is safe to commit. Publicly, even. The controller decrypts it into a
real Secret in-cluster.

Two things to know:

**Back up the controller's private key.** Lose it and every SealedSecret you
have is undecryptable — you'd re-seal everything from the original values, which
you'd better still have.

```bash
kubectl get secret -n kube-system -l sealedsecrets.bitnami.com/sealed-secrets-key -o yaml > sealed-secrets-key-BACKUP.yaml
```

Store that somewhere genuinely safe and off-cluster. It is the single most
sensitive file in your setup.

**Sealed values are scoped by namespace and name** by default. A SealedSecret
sealed for `runproject-dev/backend-secrets` will not decrypt as
`runproject-prod/backend-secrets`. This is a feature — it stops someone copying
your dev secret into a namespace they control — and it means you seal separately
per environment.

### Alternatives

**SOPS + age** — encrypt individual values in an otherwise readable file. Nice
diffs (you can see *which* key changed without decrypting). Needs a KSOPS plugin
for Kustomize.

**External Secrets Operator** — syncs from Vault/AWS Secrets Manager into k8s
Secrets. Correct at scale, considerable overhead for one app.

## Promotion between environments

**The image never changes. Only config does.**

```
   commit 680b5c5
        │
   build ONCE
        │
   ghcr.io/…:680b5c5
        │
   ┌────┴────┐
   ▼         ▼
  dev       prod
   │         │
 dev CM    prod CM      ← the only difference
 dev Sec   prod Sec
```

If you rebuild for prod, you're deploying something you never tested. This is
the same rule as `01-pipeline-concepts.md`, restated because it is the one rule
people break.

### What differs per environment

| | dev | prod |
|---|---|---|
| Namespace | `runproject-dev` | `runproject-prod` |
| Host | `dev.training.example.com` | `training.example.com` |
| Replicas | 1 each | 2 |
| Resources | small | real |
| `DJANGO_DEBUG` | `0` | `0` |
| `DJANGO_SECRET_KEY` | different | different |
| Database | separate | separate |
| LLM provider | `gemini` (free tier) | `anthropic` |
| Cert issuer | staging | prod |
| Garmin tokens | ideally a test account | real |

**`DJANGO_DEBUG=0` in dev too.** Dev exists to catch what prod will do. Running
dev with `DEBUG=1` means you find `DisallowedHost`, static-file, and security
middleware bugs in production — which is precisely the parity failure
twelve-factor X warns about.

**Different `SECRET_KEY` per environment**, always. Sharing means a session
cookie minted in dev is valid in prod.

**Gemini in dev is a genuinely good call.** `CONTEXT.md` notes the free tier's
content is used to improve Google's products, and that the trade was made
knowingly for real health logs. Test data has no such concern, and it's free.

### The data problem

Dev needs data to be useful. Options:

- **Synthetic** — a management command generating fake athletes and activities.
  Safest, most work.
- **Anonymised copy of prod** — realistic, and you now have a second copy of
  real health data to protect. `CONTEXT.md` is explicit that these logs are
  sleep, alcohol, injuries and mood.
- **Empty** — fine for structural testing, useless for testing anything about
  plans or readiness.

For one user whose data is their own, a prod copy is defensible. Just be
deliberate: that copy needs the same protection as production, and it doubles
your blast radius if it leaks. Write down which you chose.

## Rules

1. Never commit plaintext secrets. Sealed Secrets or nothing.
2. Different values per environment, always.
3. CI credentials are least-privilege ServiceAccounts, never cluster-admin.
4. `environment:` scoping + required reviewers on production.
5. Rotate anything that's been in a log, a screen share, or shell history.
6. Back up the Sealed Secrets private key off-cluster.
7. If you suspect a leak, rotate first and investigate after.
