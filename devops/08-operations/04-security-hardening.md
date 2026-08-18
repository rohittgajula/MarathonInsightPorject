# Security hardening

Ordered by value-for-effort. Do the top half.

## Threat model, honestly

One personal app, one user, real health data — sleep, alcohol, injuries, mood.
`CONTEXT.md` is explicit about that sensitivity.

**Realistic threats:**
- Automated scanning finding an exposed admin, a default credential, or a known
  CVE. This is 99% of what actually hits an internet-facing host.
- A leaked API key from git or a log, running up a bill.
- A dependency compromise.
- The VPS provider or a misconfiguration exposing the database.

**Not realistic:** a targeted attacker. Don't build for one; build against
scanners and your own mistakes, because those are what will actually happen.

## Do these first

### 1. Change the dev credentials

`CONTEXT.md` says the dev login is `rohit` / `runproject-dev`, with a note to
change it before this leaves the machine. It is now leaving the machine.

That password is in a file in a git repo. Treat it as public.

### 2. Fail hard on the default SECRET_KEY

```python
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-key-change-me")
```

A known `SECRET_KEY` means forgeable session cookies and password-reset tokens —
full account takeover, no exploit required.

```python
if not DEBUG and SECRET_KEY == "dev-insecure-key-change-me":
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DEBUG=0")
```

Fail to boot. A production app that refuses to start is infinitely better than
one that starts insecurely.

### 3. `DEBUG=0`, and verify it

`DEBUG=1` in production renders a full traceback — source code, local variables,
settings, and often environment values — to anyone who triggers a 500.

Verify after deploying, don't assume:
```bash
curl -s https://training.example.com/nonexistent-path | grep -ci traceback
```
Must be 0.

### 4. Django's own security settings

None of these are in `settings.py`. All are needed behind the ingress:

```python
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
CSRF_TRUSTED_ORIGINS = ["https://training.example.com"]
```

Then:
```bash
kubectl exec -it deploy/backend -n runproject -- python manage.py check --deploy
```

Django's own audit. It will list what's missing. Run it before every production
deploy — it's free and it's Django telling you exactly what's wrong.

**One caution on HSTS:** `SECURE_HSTS_SECONDS` tells browsers to refuse HTTP for
a year, and it is **not easily reversible** — browsers honour the cached value.
Set a short value (300) first, confirm HTTPS works everywhere, then raise it.

### 5. Restrict the admin

`/admin` is a login form on the public internet, and it will be scanned within
hours of DNS resolving.

A separate Ingress for `/admin` with an IP allowlist:
```yaml
nginx.ingress.kubernetes.io/whitelist-source-range: "203.0.113.5/32"
```

Annotations apply per-Ingress, so this needs its own object. Two Ingresses for
one host is normal.

If your home IP is dynamic, alternatives: a basic-auth annotation on top, or
reaching it through `kubectl port-forward` only. Port-forward is the most secure
— the admin is then not exposed at all.

### 6. Non-root, no capabilities, no token

From `02-containers/02` and `03-kubernetes/08`:

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  allowPrivilegeEscalation: false
  capabilities: {drop: ["ALL"]}
  seccompProfile: {type: RuntimeDefault}
automountServiceAccountToken: false
```

`automountServiceAccountToken: false` is one line and removes an entire
escalation path. Your app never calls the Kubernetes API.

### 7. Firewall

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

**Do not expose 6443** (the k3s API) to the internet. Restrict to your IP, or
tunnel over SSH. And check the *provider's* firewall too — cloud and host
firewalls are independent and both must allow traffic.

### 8. SSH hardening

```
PasswordAuthentication no
PermitRootLogin no
```

Keys only. Then install `fail2ban`. Watch your auth log for a day after going
live — the volume of automated SSH attempts is educational.

## Do these next

### Image scanning in CI

```yaml
- uses: aquasecurity/trivy-action@master
  with:
    image-ref: ghcr.io/…/runproject-backend:${{ github.sha }}
    severity: HIGH,CRITICAL
    exit-code: '1'
```

Scans OS packages and language dependencies against CVE databases.

**Be careful with `exit-code: 1`.** Base images regularly carry unfixed
CRITICAL CVEs in packages you don't use. A pipeline that fails on every build
gets bypassed, and then you're not scanning at all. Start with `exit-code: 0`
(report only), triage what it finds, then enforce once the baseline is clean.

Also enable **Dependabot** on the repo. Free, and it handles the Python and npm
sides automatically.

### NetworkPolicies

`03-kubernetes/08` covers these. The valuable one: **only backend, worker and
beat may reach `db`**. A compromised frontend Pod then can't touch Postgres.

Remember: kind's default CNI silently doesn't enforce them, and k3s ships
Flannel with the same caveat. Install Calico if you want them to actually work,
or you'll have policies that look protective and aren't.

### Pod Security Standards

```yaml
metadata:
  labels:
    pod-security.kubernetes.io/enforce: restricted
```

Start with `warn` to see what breaks, then `enforce`.

### Encryption at rest for Secrets

By default Secrets sit in plaintext in the datastore. Configure
`EncryptionConfiguration` on the API server. Free, and it means a stolen backup
of cluster state doesn't hand over your API keys.

### Rotate what's been exposed

Anything that has been in a terminal you screen-shared, a log, a git history, or
your shell history. Including anything passed via `--from-literal`.

`CONTEXT.md` mentions `GEMINI_API_KEY` and `ANTHROPIC_API_KEY` in `.env`. That's
gitignored — verify it has always been:
```bash
git log --all --full-history -- .env
```
Empty output is what you want.

## Data-specific concerns

This app holds health data. Two things `CONTEXT.md` already flags:

**Gemini's free tier uses content to improve Google's products.** The paid tier
does not. The trade was made knowingly for sleep, alcohol, injury and mood logs.
That's a defensible decision for your own data — but it's worth re-reading that
note before adding anything more sensitive, and before this ever holds someone
else's logs.

**Garmin tokens are OAuth credentials to a third-party account.** Leaked, they
give access to your full Garmin Connect history. They live on a PVC in
plaintext. Restrict who can `exec` into those Pods (RBAC), and treat the
`kubectl cp` seeding step as handling a credential.

## Checklist

**Before going live**
- [ ] Dev password changed
- [ ] `SECRET_KEY` generated, and fatal if defaulted
- [ ] `DEBUG=0`, verified by curl
- [ ] `manage.py check --deploy` clean
- [ ] `ALLOWED_HOSTS` explicit
- [ ] Admin IP-restricted or not exposed
- [ ] All containers non-root, no SA token
- [ ] Firewall: 22, 80, 443 only; 6443 closed
- [ ] SSH keys only, root login off
- [ ] TLS working, HSTS ramped up gradually
- [ ] `.env` never committed (verified in git history)
- [ ] Secrets sealed, private key backed up off-cluster

**Within the first month**
- [ ] Trivy in CI (report-only, then enforce)
- [ ] Dependabot on
- [ ] NetworkPolicies, with a CNI that enforces them
- [ ] Pod Security `restricted`
- [ ] Secrets encrypted at rest
- [ ] fail2ban
- [ ] Unattended security upgrades on the host
