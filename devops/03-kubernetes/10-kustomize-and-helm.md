# Managing manifests: raw YAML, Kustomize, Helm

You will have roughly fifteen manifests and two environments. Copy-pasting them
into `dev/` and `prod/` directories works for about a week, then the two drift
and you deploy something you never tested.

Three ways to handle it.

## 1. Raw YAML

A directory of files, `kubectl apply -f k8s/`.

**Good:** zero tooling, zero abstraction, everything is literally what runs. For
*learning*, this is the right start — you should feel the pain before you adopt
the fix, or the fix is just cargo cult.

**Bad:** no way to vary by environment except duplication.

Write everything raw first. Then feel it.

## 2. Kustomize — built into kubectl

Declarative patching. No templating language, no `{{ }}`; you write real
manifests and overlay changes onto them.

```
k8s/
├── base/
│   ├── kustomization.yaml
│   ├── namespace.yaml
│   ├── backend-deployment.yaml
│   ├── backend-service.yaml
│   ├── worker-deployment.yaml
│   ├── beat-deployment.yaml
│   ├── frontend-deployment.yaml
│   ├── frontend-service.yaml
│   ├── db-statefulset.yaml
│   ├── db-service.yaml
│   ├── redis-deployment.yaml
│   ├── redis-service.yaml
│   ├── media-pvc.yaml
│   ├── garmin-tokens-pvc.yaml
│   └── ingress.yaml
└── overlays/
    ├── dev/
    │   ├── kustomization.yaml
    │   └── patch-replicas.yaml
    └── prod/
        ├── kustomization.yaml
        ├── patch-replicas.yaml
        └── patch-resources.yaml
```

`base/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - namespace.yaml
  - backend-deployment.yaml
  # ...
commonLabels:
  app.kubernetes.io/part-of: runproject
```

`overlays/prod/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: runproject-prod
resources:
  - ../../base
patches:
  - path: patch-replicas.yaml
    target:
      kind: Deployment
      name: backend
images:
  - name: ghcr.io/rohittgajula/runproject-backend
    newTag: 680b5c5
configMapGenerator:
  - name: backend-config
    literals:
      - DJANGO_DEBUG=0
      - DJANGO_ALLOWED_HOSTS=training.example.com
```

Then:

```bash
kubectl apply -k k8s/overlays/prod
kubectl kustomize k8s/overlays/prod          # render without applying — do this first
```

**Always render before applying.** `kubectl kustomize` prints the final YAML.
Read it. Kustomize's patch targeting is easy to get subtly wrong (a patch that
matches nothing applies silently, changing nothing).

Two features worth calling out:

**`images:`** is how CI updates the deployed version — one field, no `sed` on
YAML:

```bash
cd k8s/overlays/prod && kustomize edit set image ghcr.io/…/runproject-backend=ghcr.io/…/runproject-backend:$SHA
```

**`configMapGenerator`** appends a content hash to the ConfigMap name
(`backend-config-7g4kd2fm9c`) and rewrites every reference. Change a config
value → new name → Deployment spec changes → **automatic rollout**. This solves
the "env vars don't update" problem from `04-config-and-secrets.md` for free,
and it's the single best reason to use Kustomize.

**Recommendation: use Kustomize.** It's in `kubectl`, it has no templating
language to learn, your manifests stay valid YAML you can read, and Argo CD
supports it natively.

## 3. Helm

A templating engine plus a package manager.

```
chart/
├── Chart.yaml
├── values.yaml
├── values-prod.yaml
└── templates/
    ├── backend-deployment.yaml
    └── _helpers.tpl
```

```yaml
spec:
  replicas: {{ .Values.backend.replicas }}
  template:
    spec:
      containers:
        - image: "{{ .Values.image.repo }}:{{ .Values.image.tag }}"
```

```bash
helm upgrade --install runproject ./chart -f values-prod.yaml -n runproject-prod
helm template runproject ./chart -f values-prod.yaml    # render without applying
helm rollback runproject 3
```

**Good:** genuinely powerful — conditionals, loops, dependencies on other
charts, release history, and a real rollback that reverts *all* objects at once
(not just one Deployment). The ecosystem is the killer feature: you will install
ingress-nginx, cert-manager, and Prometheus as Helm charts regardless of what
you use for your own app.

**Bad:** your manifests stop being YAML and become Go templates that emit YAML.
Whitespace bugs, `nindent` arithmetic, and error messages pointing at line
numbers in generated output. A misplaced `{{- if }}` produces invalid YAML from
a file that looks fine.

**Recommendation:** **use Helm charts** for third-party components — that's what
they ship as, and writing them yourself is absurd. Use **Kustomize for your own
app**. This hybrid is extremely common in practice and is not a fence-sit.

## Comparison

| | Raw | Kustomize | Helm |
|---|---|---|---|
| Install | none | in kubectl | separate binary |
| Manifests stay valid YAML | ✅ | ✅ | ❌ |
| Multi-environment | ❌ | ✅ | ✅ |
| Conditionals / loops | ❌ | ❌ | ✅ |
| Config-change triggers rollout | ❌ | ✅ free | ✅ manual annotation |
| Third-party packages | ❌ | awkward | ✅ the standard |
| Whole-release rollback | ❌ | ❌ | ✅ |
| Learning curve | none | small | real |

## Secrets in either

Neither solves secrets. Both will happily commit your API key to git.

Options:
- **Sealed Secrets** — encrypt with a cluster key, commit the ciphertext.
  Works with both. **The right answer for you.**
- **SOPS + age** — encrypt values in-file; Kustomize can decrypt via a KSOPS
  plugin. Flexible, more setup.
- **External Secrets Operator** — sync from a real secret manager. Overkill.

## What to do

1. **Write raw YAML first.** Every manifest, by hand, applied with
   `kubectl apply -f`. This is the learning.
2. **Then restructure into `base/` + `overlays/`.** Do this when the duplication
   between dev and prod actually annoys you — that's when the abstraction earns
   itself.
3. **Install third-party components with Helm.** ingress-nginx, cert-manager,
   metrics-server, kube-prometheus-stack.
4. **Add Sealed Secrets** before anything goes in a public-ish repo.

The order matters. Reaching for Kustomize on day one means you'll be debugging
patch targeting and Deployment semantics at the same time, and you won't know
which is which.
