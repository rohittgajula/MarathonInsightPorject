# YAML gotchas

YAML is more surprising than it looks. These will each cost you at least twenty
minutes once.

## The Norway problem

```yaml
country: NO        # → the boolean false, not the string "NO"
```

YAML 1.1 treats `yes no true false on off y n` (any case) as booleans.

```yaml
DJANGO_DEBUG: no          # ✗ boolean → "ConfigMap data must be strings"
DJANGO_DEBUG: "0"         # ✓
ssl_redirect: on          # ✗ boolean
ssl_redirect: "true"      # ✓
```

**Quote every ConfigMap value.** ConfigMap and Secret `data` must be strings;
an unquoted `no` is a type error with a confusing message.

## Numbers that aren't

```yaml
version: 1.20      # → the float 1.2 (trailing zero lost)
version: "1.20"    # ✓

build: 010         # → 8 (octal!)
build: "010"       # ✓

port: 8080         # ✓ genuinely a number here
tag: 680123        # → number; image tags must be STRINGS
tag: "680123"      # ✓
```

Commit SHAs that happen to be all digits are a real and infuriating case.

## Time strings

```yaml
timeout: 1:30      # → 90 (sexagesimal, seconds)
timeout: "1:30"    # ✓
```

## Multi-line strings

```yaml
# | keeps newlines
command: |
  line one
  line two

# > folds newlines into spaces
description: >
  this becomes
  one long line

# |- and >- strip the trailing newline
script: |-
  no trailing newline
```

Your compose file uses `>` for the backend command, which folds it into one
line — correct there. Using `|` would give you a multi-line string the shell
would interpret differently.

## Indentation

**Spaces only. Tabs are a parse error.** Two spaces per level, consistently.

List items under a key:

```yaml
# both valid, pick one and stick to it
containers:
  - name: a
containers:
- name: a
```

## Anchors and aliases

Your compose file uses this:

```yaml
environment: &backend_env    # define
  KEY: value
environment: *backend_env    # reuse
```

Valid YAML, so it works in Kubernetes manifests too. But **Kustomize and Helm
don't preserve them** in output, and they make manifests harder to read
independently. Use `envFrom` with a shared ConfigMap instead — that's the
Kubernetes-native way to express the same thing.

## Multiple documents

```yaml
apiVersion: v1
kind: Service
---
apiVersion: apps/v1
kind: Deployment
```

`---` separates documents in one file. Convenient for a Deployment + Service
pair. Note a leading `---` at the top of a file creates an empty first document
in some parsers.

## Null

```yaml
value:           # → null
value: ""        # → empty string
value: null      # → null
value: ~         # → null
```

`{}` vs omitted matters in Kubernetes: `resources: {}` explicitly means "no
resources", while omitting it may inherit a LimitRange default.

## Kubernetes-specific traps

### Selector must match template labels

```yaml
spec:
  selector:
    matchLabels:
      app: backend      # ← these
  template:
    metadata:
      labels:
        app: backend    # ← must match these
```

Mismatch → Pods created in an infinite loop. And `selector` is **immutable**
after creation; changing it means deleting and recreating the Deployment.

### Quantities

```yaml
cpu: 100m          # 0.1 core.  100 = 100 CORES.
memory: 512Mi      # mebibytes (1024²).  512M = megabytes (1000²).
storage: 10Gi
```

`Mi` vs `M` is a 5% difference — rarely fatal. `cpu: 100` vs `cpu: 100m` is a
1000× difference and your Pod will never schedule.

### Ports

```yaml
containerPort: 8000      # documentation only — does not open anything
port: 8000               # the Service's port
targetPort: http         # by NAME is better than by number
```

`containerPort` is informational. Your container listens on whatever it listens
on; declaring it doesn't change that.

### env vs envFrom

```yaml
env:                     # a LIST of {name, value}
  - name: FOO
    value: "bar"

envFrom:                 # a LIST of sources; imports ALL keys
  - configMapRef:
      name: backend-config
```

Writing `env` as a map is the most common syntax error in Kubernetes YAML.

### String values in env

```yaml
env:
  - name: PORT
    value: 8000        # ✗ "cannot unmarshal number into string"
    value: "8000"      # ✓
```

Env values are always strings. Always quote numbers here.

## Validate before applying

```bash
kubectl apply --dry-run=server -f manifest.yaml    # full API validation
kubectl apply --dry-run=client -f manifest.yaml    # syntax only
kubectl diff -f manifest.yaml                      # what would change
python -c 'import yaml,sys;yaml.safe_load_all(open(sys.argv[1]))' m.yaml
```

`--dry-run=server` catches type errors, unknown fields, and admission rejections
without changing anything. Use it.

For CI: `kubeconform` validates against the Kubernetes schema offline, and
`kube-linter` catches missing probes, missing resource limits, running as root.
Both are fast and worth a CI step.
