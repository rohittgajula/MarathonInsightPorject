# Flow: DNS resolution and certificate issuance

## Cold DNS lookup

```
  browser: training.example.com?
      │
      ▼
  OS stub resolver ── cache? ──yes──▶ done
      │ no
      ▼
  recursive resolver (ISP / 1.1.1.1)
      │  cache? ──yes──▶ done
      │ no
      ├──▶ root servers (.)          "who serves .com?"
      │      ◀── NS a.gtld-servers.net …
      │
      ├──▶ .com servers              "who serves example.com?"
      │      ◀── NS ns1.cloudflare.com …
      │
      └──▶ ns1.cloudflare.com        "A record for training?"
             ◀── A 203.0.113.42   TTL 300
      │
      ▼
  cached at every layer for TTL seconds
      │
      ▼
  browser opens TCP to 203.0.113.42:443
```

**Every layer caches.** This is why a wrong record with a 24h TTL is a 24-hour
problem, and why you lower TTL to 300 *before* changing anything
(`04-ingress-dns-tls/03`).

```bash
dig training.example.com +trace     # walks this whole tree, shows the bad step
```

## Certificate issuance (HTTP-01)

```
  you: kubectl apply -f ingress.yaml
       annotation: cert-manager.io/cluster-issuer: letsencrypt-prod
       tls: [{hosts: [training.example.com], secretName: training-tls}]
                    │
                    ▼
  ┌──────────────────────────────────────────────┐
  │ cert-manager ingress-shim                    │
  │   sees the annotation                        │
  │   creates a Certificate object               │
  └────────────────────┬─────────────────────────┘
                       ▼
  ┌──────────────────────────────────────────────┐
  │ Certificate → CertificateRequest → Order     │
  └────────────────────┬─────────────────────────┘
                       ▼
  ┌──────────────────────────────────────────────┐
  │ ACME: "I want a cert for training.example.com"│
  │ Let's Encrypt: "serve <token> at              │
  │   /.well-known/acme-challenge/<token>"        │
  └────────────────────┬─────────────────────────┘
                       ▼
  ┌──────────────────────────────────────────────┐
  │ cert-manager creates a temporary              │
  │   Pod + Service + Ingress for that ONE path   │
  └────────────────────┬─────────────────────────┘
                       ▼
  ┌──────────────────────────────────────────────┐
  │ Let's Encrypt fetches, FROM THE INTERNET:     │
  │   http://training.example.com/.well-known/…   │
  │                                               │
  │   ← needs DNS correct                         │
  │   ← needs port 80 open                        │
  │   ← needs no HTTPS redirect on this path      │
  └────────────────────┬─────────────────────────┘
                       │ token matches
                       ▼
  ┌──────────────────────────────────────────────┐
  │ certificate issued                            │
  │ cert-manager writes Secret training-tls       │
  │   tls.crt + tls.key                           │
  │ temporary solver resources deleted            │
  └────────────────────┬─────────────────────────┘
                       ▼
  ┌──────────────────────────────────────────────┐
  │ ingress-nginx watches the Secret, reloads     │
  │ HTTPS now serves the real cert                │
  └────────────────────┬─────────────────────────┘
                       ▼
              day 60 of 90: renew, unattended
```

**The fetch step is where it fails**, and why DNS must be correct *before* you
request a cert. It is also why this cannot work on kind — Let's Encrypt cannot
reach your laptop.

## Debugging, following the chain

```bash
kubectl get certificate -n runproject
kubectl describe certificate training-tls -n runproject
kubectl get certificaterequest -n runproject
kubectl get order -n runproject
kubectl describe order <name> -n runproject
kubectl get challenge -n runproject
kubectl describe challenge <name> -n runproject     # ← the real error is here
```

Work **down** the list. Each object explains why the next one didn't appear.

| Challenge says | Means |
|---|---|
| `no such host` | DNS. Check `dig` first. |
| connection refused / timeout | Port 80 blocked. Host or provider firewall. |
| `404` | Ingress isn't routing `/.well-known/`. A catch-all rule may be swallowing it. |
| `429 rateLimited` | You were on the production issuer. Switch to staging, fix, switch back, wait. |
| No Certificate object at all | Typo'd `cluster-issuer` annotation. Produces **no error** — check the object exists. |

## The TLS handshake, per request

```
  client                                          ingress-nginx
    │── ClientHello ──────────────────────────────▶
    │     SNI: training.example.com                │
    │     supported ciphers, TLS versions          │
    │                                              │  looks up the cert
    │                                              │  for that SNI name
    │◀── ServerHello + certificate chain ──────────
    │
    │  verify: name matches? chain trusted? in date?
    │  any one fails → full-page browser warning
    │
    │── key exchange ─────────────────────────────▶
    │◀── Finished ────────────────────────────────
    │
    │══ encrypted HTTP ═══════════════════════════▶
    │                                              │
    │                              TLS ENDS HERE   │
    │                                              ├── plain HTTP ──▶ Service
```

**SNI is why one IP serves many hostnames.** The client names the host before
encryption starts, so the proxy knows which certificate to present. Without it
you'd need one IP per cert.

## Renewal

```
  day 0    issued, valid 90 days
  day 60   cert-manager renews (2/3 of lifetime)
           new Secret written, ingress reloads
           ── silent, automatic, no downtime ──
  day 90   original would have expired
```

It fails silently more often than you'd like — DNS moved, port 80 got
firewalled, a rate limit was hit. **The failure is invisible until the cert
expires.**

```bash
kubectl get certificate -A       # READY: True, EXPIRES in the future
```

Alert on `certmanager_certificate_expiration_timestamp_seconds` at 14 days out.
Expired-certificate outages are entirely preventable and entirely embarrassing.
