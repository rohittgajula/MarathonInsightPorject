# cert-manager: automatic TLS

Read `01-foundations/02-tls-and-https.md` first for what a certificate is and
how ACME proves control. This is the mechanics.

## Install

```bash
helm repo add jetstack https://charts.jetstack.io
helm repo update
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --set crds.enabled=true
```

`crds.enabled=true` installs the CustomResourceDefinitions. Without them,
applying a `ClusterIssuer` fails with `no matches for kind "ClusterIssuer"` —
which reads like a typo and is actually a missing CRD.

```bash
kubectl get pods -n cert-manager
```

Three Pods: `cert-manager`, `cert-manager-webhook`, `cert-manager-cainjector`.
All three must be Running. The webhook validates your Certificate resources; if
it's not ready, your applies fail with a webhook timeout.

## The objects

```
ClusterIssuer  ──▶ Certificate ──▶ Order ──▶ Challenge ──▶ Secret
   (you)           (usually            (cert-manager's internal machinery)
                  auto-created)
```

**ClusterIssuer** — which CA, and how to prove control. Cluster-wide.
**Certificate** — I want a cert for these names, in this Secret.
**Order / Challenge** — cert-manager's internal ACME state. You read these when
debugging, never write them.
**Secret** — the result: `tls.crt` and `tls.key`.

## Two ClusterIssuers, from day one

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging
spec:
  acme:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    email: dev@aais.ai
    privateKeySecretRef:
      name: letsencrypt-staging-account-key
    solvers:
      - http01:
          ingress:
            ingressClassName: nginx
```

And an identical one named `letsencrypt-prod` pointing at
`https://acme-v02.api.letsencrypt.org/directory`.

**Always start on staging.** Production limits you to 5 duplicate certificates
per week and 5 failed validations per hostname per hour. You will get the
challenge wrong the first time. Everyone does. Burn those attempts on staging,
where limits are effectively unlimited.

The `email` gets expiry warnings if renewal ever breaks. Use one you read.

Switching is one annotation on the Ingress:

```yaml
cert-manager.io/cluster-issuer: letsencrypt-staging   # → letsencrypt-prod
```

When you switch, **delete the old Secret** — otherwise cert-manager sees a valid
(staging) cert and doesn't reissue:

```bash
kubectl delete secret training-tls -n runproject
```

## You rarely write a Certificate

Annotate the Ingress and cert-manager writes it for you:

```yaml
metadata:
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
    - hosts:
        - training.example.com
      secretName: training-tls
```

cert-manager watches Ingresses with that annotation, creates a Certificate for
the hosts in `tls:`, and stores the result in `secretName`. This is the
"ingress-shim" and it's how nearly everyone uses cert-manager.

## HTTP-01, step by step

Worth knowing because when it fails, you need to know which step broke.

```
1. cert-manager asks Let's Encrypt for a cert for training.example.com
2. LE: "prove it — serve <token> at
        http://training.example.com/.well-known/acme-challenge/<token>"
3. cert-manager creates a temporary Pod + Service + Ingress for that exact path
4. LE's servers fetch that URL from the public internet
5. Match → certificate issued
6. cert-manager writes tls.crt / tls.key into the Secret
7. ingress-nginx picks up the Secret and serves it
8. cert-manager renews at ~60 days, unattended
```

**Step 4 is the one that fails**, and the requirements are absolute:

- The domain must **publicly resolve to your cluster's IP** — DNS first, cert
  second, always
- **Port 80 must be open** from the internet. Not 443 — HTTP-01 uses 80.
- Your ingress must not blanket-redirect `/.well-known/acme-challenge/` to
  HTTPS. ingress-nginx handles this correctly out of the box; custom nginx
  configs often don't.

**HTTP-01 cannot work on kind or any local cluster**, because Let's Encrypt's
servers cannot reach your laptop. This is not a configuration problem. Locally,
use self-signed certs (below) and save real ACME for the VPS.

## Local TLS on kind

A self-signed ClusterIssuer:

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: selfsigned
spec:
  selfSigned: {}
```

Annotate your local Ingress with it. Your browser will warn; click through. You
are testing that TLS termination, the Secret wiring, and the ingress config all
work — not that a CA trusts you.

Better, if you want green padlocks locally: `mkcert` installs a local CA into
your Mac's trust store. Create a cert with it, load it as a Secret, reference it
in the Ingress `tls:` block with no cert-manager involvement. Nice, optional.

## Renewal

cert-manager renews at **2/3 of lifetime** — day 60 of 90. Fully automatic.

It fails silently more often than you'd like: DNS changed, port 80 got firewalled,
rate limit hit. You find out when the cert expires. So:

```bash
kubectl get certificate -A
```

`READY: True` and an `EXPIRES` well in the future. Put this in a weekly CronJob
that alerts, or in a Prometheus alert on `certmanager_certificate_expiration_timestamp_seconds`.
The `08-operations/01` chapter covers wiring it up.

## Debugging, in order

```bash
kubectl get certificate -n runproject
kubectl describe certificate training-tls -n runproject
kubectl get certificaterequest -n runproject
kubectl get order -n runproject
kubectl describe order <name> -n runproject
kubectl get challenge -n runproject
kubectl describe challenge <name> -n runproject
kubectl logs -n cert-manager deploy/cert-manager -f
```

Work **down** that list. Each object's `describe` explains why the next one
didn't appear. `Challenge` is where the real error lives — it will say things
like "wrong status code 404" or "no such host", which tells you immediately
whether it's DNS or routing.

### Common failures

| Message in the Challenge | Cause |
|---|---|
| `no such host` | DNS doesn't resolve, or hasn't propagated. Check with `dig` before anything else. |
| `Connection refused` / timeout | Port 80 not reachable. Firewall, security group, or no ingress controller. |
| `404` on the challenge path | Ingress isn't routing `/.well-known/` to the solver. Check for a catch-all rule swallowing it. |
| `429 rateLimited` | You were on production. Switch to staging, fix, switch back. Wait out the window — there is no appeal. |
| Certificate stuck `False` with no Order | The webhook isn't ready, or the ClusterIssuer name in the annotation is misspelled. |

That last one is worth a specific check: a typo'd `cluster-issuer` annotation
produces *nothing at all* — no Certificate, no error, no event. Verify the
Certificate object actually got created before debugging further.

## Wildcards

`*.example.com` needs **DNS-01**, not HTTP-01 — Let's Encrypt won't issue a
wildcard from an HTTP challenge.

DNS-01 means giving cert-manager API credentials for your DNS provider so it can
write TXT records. Supported natively for Cloudflare, Route53, and others.

**You don't need this.** One hostname, `training.example.com`, HTTP-01. Only
reach for wildcards when you have several subdomains and re-issuing each is
actually annoying.

## Security notes

- The TLS Secret holds your **private key**. Anyone with `get secrets` in that
  namespace can impersonate your site. This is the strongest argument for the
  RBAC in `03-kubernetes/08`.
- Add a **CAA record** restricting issuance to Let's Encrypt:
  ```
  example.com. CAA 0 issue "letsencrypt.org"
  ```
  Now no other CA will issue for your domain, even if someone tricks them.
  One DNS record, meaningful protection.
- Every issued certificate is published to **Certificate Transparency logs**,
  which are public and searchable. `training.example.com` becomes public
  knowledge the moment you get a cert. Don't treat a subdomain name as a secret
  — this catches people who put `admin-internal.example.com` behind a cert and
  assume nobody knows about it.
