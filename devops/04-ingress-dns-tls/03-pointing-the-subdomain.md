# Pointing `training.<yourdomain>` at your cluster

The concrete DNS procedure. Read `01-foundations/01` for how DNS works; this is
what to actually do.

## Order of operations — this matters

```
1. VPS exists, has a static public IP
2. k3s installed, ingress controller running
3. Ports 80 and 443 open to the internet
4. DNS A record: training → that IP
5. Verify resolution from outside
6. THEN request a certificate
```

**Step 4 before step 6, always.** HTTP-01 validation requires Let's Encrypt to
reach `http://training.example.com/.well-known/...` from the public internet.
If DNS isn't right yet, the challenge fails, and you've spent one of your five
failed validations for that hostname this hour.

## Step 1 — get the IP

```bash
curl -4 ifconfig.me
```

Run that **on the VPS**. Note it. Confirm it's static — every mainstream VPS
gives a static IPv4 by default, but confirm rather than assume.

If you also have IPv6 (`curl -6 ifconfig.me`), you'll add an AAAA record too.

## Step 2 — lower the TTL first

Before creating anything, if you already have DNS records on this domain,
**drop the TTL on the zone (or at least anything you might change) to 300**, and
wait for the old TTL to expire.

Skipping this is the mistake that costs you a day. Create a record with a
24-hour TTL, get the IP wrong, and every resolver that cached the bad answer
keeps it for 24 hours. There is no way to flush other people's caches.

## Step 3 — create the record

At whoever runs your DNS — the registrar, or Cloudflare/Route53 if you've
delegated. Confirm which:

```bash
dig example.com NS +short
```

**Whatever that prints is where you create the record.** Editing records at your
registrar while the NS points at Cloudflare is a genuinely common and
genuinely baffling waste of an hour.

Then:

| Field | Value |
|---|---|
| Type | `A` |
| Name | `training` |
| Value | `203.0.113.42` (your VPS IP) |
| TTL | `300` |
| Proxy (Cloudflare only) | **OFF** initially — see below |

The **Name** field is where people slip. Most control panels want just the
subdomain label, `training`, and append the zone themselves. Some want the full
`training.example.com`. Enter `training`, save, then re-read what it displays.
If it shows `training.example.com.example.com`, you now know which kind you're
using.

Add AAAA the same way if you have IPv6.

## Step 4 — verify from outside

```bash
dig training.example.com A +short
```

Should print your IP.

```bash
dig @1.1.1.1 training.example.com A +short
dig @8.8.8.8 training.example.com A +short
```

Two public resolvers, bypassing your ISP's cache. If these agree with your
expectation, it has propagated where it matters — including to Let's Encrypt.

```bash
dig training.example.com +trace
```

If something's wrong, this walks the delegation from root and shows exactly
which step returns the wrong answer.

**Do not test with your browser.** Browsers cache DNS independently of the OS,
and Chrome's cache in particular will lie to you for a surprisingly long time.

Then verify the path actually works end to end:

```bash
curl -v http://training.example.com/
```

Before TLS exists you should get *something* from nginx — likely a 404 (no rule
matched) or the app. A connection timeout means port 80 is blocked. Connection
refused means nothing is listening. These are very different problems and this
one command distinguishes them.

## Step 5 — firewall

Kubernetes will not open ports for you. On the VPS:

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

Allow 22 **before** enabling, or you lock yourself out of the machine. Everyone
does this once.

Also check the provider's own firewall — Hetzner, DigitalOcean and AWS all have
a cloud-level firewall *in addition* to whatever's on the host. Both must allow
traffic. A cloud firewall silently dropping port 80 looks exactly like a
misconfigured ingress.

k3s also needs 6443 for the API server. **Do not open it to the world** —
restrict it to your home IP, or leave it closed and use SSH tunnelling
(`09-going-live/02` covers this).

## Step 6 — certificate

Only now. Set the Ingress annotation to `letsencrypt-staging`, apply, and watch:

```bash
kubectl get certificate -n runproject -w
kubectl describe challenge -n runproject
```

Staging cert issued → switch the annotation to `letsencrypt-prod`, delete the
staging Secret, apply again.

```bash
kubectl delete secret training-tls -n runproject
```

Then:

```bash
curl -I https://training.example.com/
echo | openssl s_client -connect training.example.com:443 -servername training.example.com 2>/dev/null | openssl x509 -noout -issuer -dates
```

Issuer should say Let's Encrypt (not "STAGING"), and the dates should span ~90
days.

## Step 7 — raise the TTL

Once stable, put the TTL back to 3600. Low TTLs mean more DNS queries and
slightly slower first loads for everyone. Lower it again *before* the next
planned change.

## Cloudflare, if you use it

Cloudflare's orange-cloud proxy mode changes things:

**Proxied (orange)** — traffic goes through Cloudflare. You get DDoS protection,
caching, a free edge certificate, and your origin IP is hidden. But:
- `dig` returns a *Cloudflare* IP, not yours — normal, not a bug
- Cloudflare terminates TLS at the edge; set SSL/TLS mode to **Full (strict)**
  so the Cloudflare↔origin hop is also encrypted and validated. "Flexible" means
  Cloudflare talks plain HTTP to your origin — the padlock lies.
- HTTP-01 still works (Cloudflare passes `/.well-known/` through)
- The real client IP arrives in `CF-Connecting-IP`, so your logs and any
  IP-based rules see Cloudflare's IPs unless you configure `real_ip` handling

**DNS only (grey)** — plain DNS. Simplest, and what you want while setting up.

**Recommendation:** grey cloud until everything works end to end, then decide
whether you want the proxy. If you turn it on, switch to Full (strict) in the
same sitting — the intermediate state is worse than either.

## Local development mapping

While on kind, no real DNS is involved:

```
sudo sh -c 'echo "127.0.0.1 training.local" >> /etc/hosts'
```

`/etc/hosts` short-circuits DNS entirely. Use `training.local` in your local
Ingress and `training.example.com` in production — same manifests, different
overlay value. That keeps the *shape* identical while you develop.

Do not use a `.dev` or `.app` TLD locally — those are real TLDs with HSTS
preloaded, so your browser will force HTTPS and refuse to let you click through
a self-signed warning. `.local` and `.test` are safe.

## Checklist

- [ ] VPS has a static IP, noted
- [ ] Confirmed which nameservers are authoritative
- [ ] TTL lowered to 300 before changes
- [ ] A record `training` → IP created
- [ ] AAAA record if IPv6
- [ ] `dig @1.1.1.1` returns the right IP
- [ ] Host firewall allows 22, 80, 443
- [ ] Provider firewall allows 80, 443
- [ ] `curl http://training.example.com/` reaches nginx
- [ ] Staging cert issues successfully
- [ ] Switched to prod issuer, old Secret deleted
- [ ] `https://` works with a trusted cert
- [ ] TTL raised back to 3600
- [ ] CAA record restricting issuance (optional, cheap)
