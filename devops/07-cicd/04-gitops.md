# GitOps: Argo CD and Flux

## The problem it solves

Push-based deploy means your CI holds cluster credentials and needs network
access to your API server. Two consequences you should be uneasy about:

1. **A compromised GitHub Actions run owns your cluster.** A malicious
   dependency in a workflow, a leaked secret, a hijacked action — any of these
   reach production directly.
2. **Your API server must be reachable from GitHub's runners.** That means
   exposing 6443 to the internet, or maintaining a VPN.

GitOps inverts it:

```
   push:   CI ──credentials──▶ cluster        (cluster trusts CI)

   pull:   CI ──▶ git repo ◀──polls── Argo CD  (cluster trusts only git)
                                    (inside the cluster)
```

The cluster reaches **out** to git. No inbound access. No cluster credentials in
CI. If GitHub Actions is compromised, the attacker can commit to your repo —
which is bad, but it's reviewable, revertable, and auditable in a way that
direct cluster access is not.

## The principles

1. **The entire desired state is declared in git.** Manifests, config, the lot.
2. **Git is the single source of truth.** Not the cluster.
3. **Changes are made by committing.** Not by `kubectl apply`.
4. **An agent continuously reconciles** the cluster toward git.

Point 4 is the one people underrate. It's not "apply on push" — it's a
continuous loop. Someone `kubectl edit`s a Deployment at 3am to fix an incident;
Argo notices the drift, flags it, and (if configured) reverts it. **The cluster
cannot drift from git without you being told.**

That's a genuinely different operational posture from "we applied something once
and hope it's still there."

## Argo CD

The more popular of the two, and the one with a UI worth having.

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

The core object:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: runproject-prod
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/rohittgajula/MarathonInsightPorject
    targetRevision: main
    path: k8s/overlays/prod        # Kustomize is auto-detected
  destination:
    server: https://kubernetes.default.svc
    namespace: runproject-prod
  syncPolicy:
    automated:
      prune: true       # delete objects removed from git
      selfHeal: true    # revert manual changes to the cluster
    syncOptions:
      - CreateNamespace=true
```

`prune` and `selfHeal` are the two switches that turn Argo from "a fancy applier"
into actual GitOps. Both have teeth:

- **`prune: true`** deletes cluster objects no longer in git. Delete a manifest
  by accident, and the object goes. This is correct behaviour and it will scare
  you once.
- **`selfHeal: true`** reverts manual changes. Which means your emergency
  `kubectl scale` during an incident gets undone within minutes. Correct in
  principle; know it, so you commit the change instead of fighting the robot.

The UI is genuinely useful: a live dependency graph of every object, real-time
sync status, diffs between git and cluster, and per-object logs. For learning
Kubernetes it's excellent — you *see* the reconciliation happening.

### Sync waves

Ordering, which plain `kubectl apply` lacks:

```yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "-1"    # lower numbers first
```

This is how you solve the migration ordering problem from `03-kubernetes/06`
cleanly:

| Wave | Objects |
|---|---|
| `-2` | Namespace, ConfigMap, Secret, PVCs |
| `-1` | db, redis |
| `0` | migrate Job (as a `PreSync` hook) |
| `1` | backend, worker, beat, frontend |
| `2` | Ingress, HPA, PDB |

And hooks:

```yaml
argocd.argoproj.io/hook: PreSync
argocd.argoproj.io/hook-delete-policy: BeforeHookCreation
```

A `PreSync` hook Job runs to completion **before** the rest of the sync. That's
your migration, expressed natively, instead of the `kubectl wait` gymnastics
from `03-kubernetes/06`. This is the single biggest practical win of adopting
Argo for this app.

## Flux

The other CNCF GitOps tool. Different philosophy:

| | Argo CD | Flux |
|---|---|---|
| UI | Excellent, built in | None (Weave GitOps is separate) |
| Model | `Application` objects | A set of composable controllers |
| Multi-tenancy | `AppProject` | Namespace-scoped by design |
| Image automation | Separate component | Built in, first-class |
| Learning curve | Gentler | Steeper, more Kubernetes-native |

**Flux's image automation is the notable feature**: it watches your registry,
and when a new tag matching a policy appears, it commits the updated tag back
to git and syncs. Fully automatic image promotion, with git as the record.

**Recommendation: Argo CD.** The UI's value while learning is hard to overstate
— being able to *see* reconciliation, drift, and sync waves happen makes the
concepts concrete in a way YAML doesn't.

## What CI becomes

CI stops deploying. It builds, tests, pushes, and updates a tag in git:

```yaml
- name: Update image tag
  run: |
    cd k8s/overlays/prod
    kustomize edit set image ghcr.io/…/runproject-backend=ghcr.io/…/runproject-backend:${SHA}
    git config user.name  "github-actions[bot]"
    git config user.email "github-actions[bot]@users.noreply.github.com"
    git commit -am "deploy backend ${SHA}"
    git push
```

Argo sees the commit and syncs. CI never has a kubeconfig.

**Watch out for the loop:** this workflow pushes a commit, which triggers the
workflow, which pushes a commit. Either add `[skip ci]` to the message, filter
on `paths-ignore: [k8s/**]`, or use a separate config repo.

## One repo or two?

**Single repo** (`k8s/` alongside the app) — simpler, one PR changes code and
manifests together, easy to see what shipped with what. But every manifest tweak
triggers your app CI, and the image-tag commits pollute your history.

**Separate config repo** — clean separation, no CI loops, and you can give it
different access rules. But a change spans two repos and two PRs.

**Start single-repo.** You have one app. Split when the noise annoys you.

## Is this worth it for one app?

Honestly: the *operational* benefit at your scale is modest. You could run
push-based deploys forever and be fine.

The reasons to do it anyway:

- **It removes the "expose 6443 to the internet" problem**, which is a real
  security improvement and not a hypothetical one.
- **Drift detection** genuinely catches "I fixed it by hand and forgot" — which
  is the most common way a working cluster becomes an unreproducible one.
- **`git revert` as rollback** is the cleanest rollback story there is.
- **It's what the industry does.** Argo CD is in an enormous number of
  production environments. Knowing it is directly valuable.

Do push-based first, get it working end to end, feel where it's awkward. **Then**
adopt Argo. Going straight to GitOps means you'll be debugging Argo and
Kubernetes simultaneously and won't know which layer is lying to you.
