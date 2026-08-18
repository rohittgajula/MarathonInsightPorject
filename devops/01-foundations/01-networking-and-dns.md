# Networking and DNS, enough to not be lost

Most deployment failures are networking failures wearing a costume. This is the
minimum model that makes them legible.

## The four questions every request answers

When your browser loads `https://training.example.com/api/dashboard`:

1. **What IP is that name?** → DNS
2. **How do I reach that IP?** → routing
3. **Which process on that machine?** → port
4. **Who am I actually talking to, and is anyone listening?** → TLS, then HTTP

Every deployment bug you will hit lives in exactly one of these. When something
breaks, work out which one before touching anything.

## Ports

A machine has one IP but 65,535 TCP ports. A port is how one machine runs many
services. Conventions worth memorising:

| Port | What |
|---|---|
| 80 | HTTP |
| 443 | HTTPS |
| 5432 | Postgres |
| 6379 | Redis |
| 8000 | this project's Django dev server |
| 5173 | this project's Vite dev server |

In `docker-compose.yml` you already do port mapping:

```yaml
ports:
  - "${BACKEND_PORT:-8000}:8000"
```

Left is the **host** port, right is the **container** port. Your compose file
maps Postgres to host 5433 and Redis to 6380 — deliberately off the defaults so
they don't collide with anything installed natively on your Mac. Remember that;
it will confuse you the first time you `psql` on 5432 and get nothing.

**In Kubernetes this mapping mostly disappears.** Every Pod gets its own IP, so
there is no host-port collision to dodge. Postgres listens on 5432 in its own
Pod, full stop. This is one of the genuine simplifications k8s buys you.

## DNS: what actually happens

DNS is a distributed, cached, hierarchical key-value store. Reading right to
left:

```
training.example.com.
                    └ root (.)          — 13 root server clusters
             └────── TLD (.com)         — Verisign runs this
     └────────────── your domain        — your registrar's nameservers
└─────────────────── the subdomain      — a record you create
```

Resolution for `training.example.com`, cold cache:

```
browser → OS stub resolver → recursive resolver (your ISP, or 1.1.1.1)
                                  │
                                  ├─→ root servers:  "who handles .com?"
                                  │      ← "these 13 nameservers"
                                  ├─→ .com servers:  "who handles example.com?"
                                  │      ← "ns1.registrar.com"
                                  └─→ ns1.registrar.com: "A record for training?"
                                         ← "203.0.113.42"
browser now opens TCP to 203.0.113.42:443
```

Every step is cached, at every layer, for the record's **TTL**.

## Record types you will use

| Type | Maps | Use here |
|---|---|---|
| **A** | name → IPv4 | `training.example.com → 203.0.113.42`. This is the one you'll create. |
| **AAAA** | name → IPv6 | Same, if your VPS has IPv6. Add it; costs nothing. |
| **CNAME** | name → another name | For load balancers with changing IPs. Cannot exist at a zone apex, and cannot coexist with other records on the same name. |
| **TXT** | name → text | Domain ownership proofs, SPF, and Let's Encrypt DNS-01 challenges. |
| **MX** | mail | Not needed, but never delete existing ones. |
| **NS** | delegation | Who is authoritative. Changing these moves your whole DNS. |
| **CAA** | which CAs may issue | Optional hardening: restrict to `letsencrypt.org`. |

## TTL, and the mistake everyone makes

TTL is seconds a resolver may cache. Default is often 3600 (1h) or 86400 (24h).

**The trap:** you point `training` at the wrong IP with a 24h TTL, fix it ten
minutes later, and it's still wrong for you a day later — because a resolver
somewhere cached the bad answer and will not ask again.

**The fix, always, before any DNS change:** drop the TTL to 300 a day *ahead*
of the change. Make the change. Verify. Raise it back to 3600 once stable.

There is no "flush the internet" button. Cached is cached.

## Checking DNS without trusting your browser

Browsers cache aggressively and lie to you. Use these:

```bash
dig training.example.com A +short
```

```bash
dig @1.1.1.1 training.example.com A
```

The `@1.1.1.1` form asks Cloudflare's resolver directly, bypassing your ISP's
cache — the fastest way to tell "not propagated yet" from "I typed it wrong".

```bash
dig training.example.com +trace
```

Walks the delegation from the root down, showing you exactly which step is
wrong. This is the one that actually diagnoses.

```bash
dig example.com NS +short
```

Confirms which nameservers are authoritative — check this if records you
"definitely created" seem invisible. Usually it means you edited records at the
registrar while the domain's NS points at Cloudflare, or vice versa.

## DNS inside Kubernetes

The cluster runs **CoreDNS**, and every Service gets a name:

```
<service>.<namespace>.svc.cluster.local
```

So your backend reaches Postgres at `db.runproject.svc.cluster.local:5432` —
or just `db:5432` from a Pod in the same namespace, because search domains fill
in the rest.

This is why the migration from compose is gentler than it looks. Compose
already gives you `db`, `redis`, `backend` as hostnames on a user-defined
bridge network, and your `DATABASE_URL` already says `@db:5432`. **That string
does not have to change.** Name the Kubernetes Service `db` and the same URL
resolves. Same for `redis://redis:6379/0`.

## Private vs public IPs

```
10.0.0.0/8       private
172.16.0.0/12    private   ← Docker's default bridge lives here
192.168.0.0/16   private   ← your home network
```

Everything else is publicly routable. Kubernetes hands Pods IPs from a private
range that only exists inside the cluster — which is why `kubectl get pod -o wide`
showing `10.244.1.7` tells you nothing about reachability from outside. To get
in from outside you need a Service of type LoadBalancer or NodePort, or an
Ingress. Nothing else crosses that line.

## The mental model to keep

```
internet ──▶ DNS ──▶ public IP ──▶ port 443 ──▶ ingress controller
                                                      │  TLS ends here
                                                      ▼
                                                 Service (virtual IP)
                                                      │
                                              ┌───────┴───────┐
                                              ▼               ▼
                                            Pod             Pod
```

When the site is down, walk that chain top to bottom and find the first arrow
that doesn't work. `flows/01-request-flow.md` has the full version with the
commands that test each hop.
