# TLS, certificates, and why they expire

## What a certificate actually claims

A TLS certificate is a signed statement: *"the holder of the private key
matching this public key controls `training.example.com`"* — signed by a
Certificate Authority your browser already trusts.

Three things must all be true or the browser refuses:

1. The name in the cert matches the name you typed.
2. The signature chains up to a CA in the browser's trust store.
3. It is inside its validity window.

Any one failing gives the full-page warning. Almost always in practice it is
#1 (you got a cert for `example.com` and browsed to `training.example.com`)
or #3 (renewal silently stopped working two months ago).

## The handshake, briefly

```
client                                         server
  │── ClientHello (SNI: training.example.com) ──▶
  │      "here's the name I want, and my ciphers"
  │◀── ServerHello + certificate chain ─────────
  │      "here's my cert for that name"
  │   [verify chain, name, dates]
  │── key exchange ─────────────────────────────▶
  │◀── Finished ────────────────────────────────
  │═══ encrypted HTTP from here ════════════════
```

**SNI** is the important bit for you. The client announces the hostname *before*
encryption starts, which is how one IP with one ingress controller serves certs
for many hostnames. Without SNI you'd need one IP per certificate. It is why
`training.example.com` and your main site can share a single VPS.

## Let's Encrypt and ACME

Let's Encrypt issues free, 90-day certs automatically via the ACME protocol.
The short lifetime is deliberate: it forces automation, and automated renewal
is the only renewal that reliably happens.

You prove control one of two ways:

**HTTP-01** — the CA tells you to serve a specific token at
`http://training.example.com/.well-known/acme-challenge/<token>`. If it can
fetch it, you clearly control what that name points at.
- Needs port 80 open to the internet.
- Cannot issue wildcards.
- Simplest. **Use this one.**

**DNS-01** — the CA tells you to publish a TXT record at
`_acme-challenge.training.example.com`.
- Works with no inbound ports at all — behind NAT, on a private cluster.
- The only way to get a wildcard (`*.example.com`).
- Needs API credentials for your DNS provider so cert-manager can write the
  record. More moving parts, and now your cluster holds DNS write access.

## cert-manager

In Kubernetes you do not run certbot. You install **cert-manager**, which adds
custom resources:

- **Issuer** / **ClusterIssuer** — "which CA, and how do I prove control".
  ClusterIssuer is cluster-wide; Issuer is namespaced. Use ClusterIssuer.
- **Certificate** — "I want a cert for these names, put it in this Secret."
- cert-manager then handles the ACME order, the challenge, issuance, storing
  the result in a Secret, and **renewing at ~60 days** without you.

The nice part: you rarely write a Certificate by hand. Annotate your Ingress
with `cert-manager.io/cluster-issuer: letsencrypt-prod` and a `tls:` block, and
cert-manager creates the Certificate for you.

## Staging first. Always.

Let's Encrypt production rate limits are real and painful:

- **50 certificates per registered domain per week**
- **5 duplicate certificates per week** (same exact name set)
- **5 failed validations per account per hostname per hour**

You will misconfigure the challenge on your first attempt. Everyone does. Burn
those attempts against the **staging** endpoint:

```
https://acme-staging-v02.api.letsencrypt.org/directory
```

Staging issues certs your browser does *not* trust — that is fine and expected.
You are testing the plumbing, not the trust. Once you see a staging cert land
in a Secret, switch the ClusterIssuer to production and get a real one on the
first try.

Set up **both** ClusterIssuers (`letsencrypt-staging`, `letsencrypt-prod`) from
day one and flip an annotation between them.

## Where TLS ends

In this architecture:

```
browser ══ HTTPS ══▶ ingress controller ── plain HTTP ──▶ Services ──▶ Pods
                          ▲
                     TLS terminates here
```

Traffic inside the cluster is unencrypted. For a single-tenant personal app on
one node that is an entirely reasonable trade — the plaintext never leaves the
host. If this ever held other people's health data across multiple nodes, you'd
want mTLS between services (a service mesh like Linkerd), and the cost/benefit
would change.

Say what you chose and why. That's the whole job.

## Things that will bite you

**Redirect loops.** Ingress redirects HTTP→HTTPS; something upstream also
terminates TLS and forwards as HTTP; the ingress sees HTTP and redirects again.
Forever. Fix: trust `X-Forwarded-Proto`. In Django that means
`SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` — which this
project does **not** currently set. You will need it.

**Mixed content.** Page over HTTPS, `VITE_API_BASE` still
`http://localhost:8000/api` — the browser blocks the request outright and the
app looks empty with a clean-looking network tab. See
`02-containers/02` for why this specific variable is a build-time problem.

**Cert renewed but not served.** cert-manager updated the Secret; the ingress
controller cached the old one. Modern ingress-nginx watches and reloads, but if
you see a stale cert:
```bash
kubectl -n ingress-nginx rollout restart deploy/ingress-nginx-controller
```

**Chain incomplete.** Your browser works (it cached an intermediate once);
`curl` from a fresh machine fails. Test with:
```bash
openssl s_client -connect training.example.com:443 -servername training.example.com
```
and check the chain it prints, not what Chrome tells you.

## Useful commands

```bash
echo | openssl s_client -connect training.example.com:443 -servername training.example.com 2>/dev/null | openssl x509 -noout -dates -subject -issuer
```

```bash
kubectl get certificate -A
```

```bash
kubectl describe certificate training-tls -n runproject
```

The `describe` output narrates the whole ACME order — this is where you find
out the challenge failed and why.
