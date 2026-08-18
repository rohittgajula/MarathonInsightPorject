# The VPS, k3s, and cutover

Where it becomes real: a public IP, a real certificate, and your domain.

## Choosing a VPS

| Provider | Spec | ~Price | Notes |
|---|---|---|---|
| **Hetzner** CPX21 | 3 vCPU, 4 GB, 80 GB | **€5.6/mo** | Best value by a distance. EU + US locations. |
| **DigitalOcean** | 2 vCPU, 4 GB, 80 GB | $24/mo | Excellent docs, easy UI |
| **Vultr / Linode** | 2 vCPU, 4 GB | ~$20/mo | Comparable |
| **Oracle Cloud Free** | 4 ARM cores, 24 GB | **free** | Genuinely free forever, but capacity is often unavailable and accounts get reclaimed. Don't put anything you care about on it. |

**4 GB RAM is the real minimum.** Budget roughly:

```
k3s control plane + system   ~700 MB
Postgres                     ~300 MB
Redis                        ~100 MB
backend ×2                   ~800 MB
worker                       ~500 MB   (FIT parsing is the memory-hungry one)
beat                         ~150 MB
frontend ×2                  ~100 MB
ingress-nginx                ~150 MB
cert-manager                 ~150 MB
monitoring (if installed)    ~800 MB
                     total  ~3.7 GB
```

Monitoring is the thing that pushes you over. 8 GB if you want the full
Prometheus stack; 4 GB if you'll run without it initially.

**Location matters.** You're in India. A server in Europe adds ~150ms per
request. Hetzner has no Indian region — DigitalOcean Bangalore or AWS Mumbai
would be noticeably faster for you. For a personal app the latency is
tolerable; it's a real trade against Hetzner's price.

**Note the architecture.** Hetzner's CAX line is ARM (cheaper); CPX is AMD. If
you build amd64 images in CI, get an amd64 server, or your images won't run
(`exec format error`).

## Host setup

```bash
ssh root@<ip>

adduser rohit
usermod -aG sudo rohit
rsync --archive --chown=rohit:rohit ~/.ssh /home/rohit
```

Then in `/etc/ssh/sshd_config`:
```
PasswordAuthentication no
PermitRootLogin no
```
```bash
systemctl restart sshd
```

**Test logging in as `rohit` in a second terminal before closing the first.**
Locking yourself out is a rite of passage worth skipping.

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y ufw fail2ban unattended-upgrades

sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable        # allow 22 BEFORE enabling
```

Swap, as a safety net against OOM on a small box:
```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Kubernetes traditionally wants swap off, and k3s will warn. On a 4 GB box, swap
is the difference between "slow for thirty seconds" and "the OOM killer picks a
process at random." Keep it.

## Install k3s

```bash
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable traefik" sh -
```

**`--disable traefik` is a decision you make now.** k3s ships Traefik as its
default ingress. Disabling it and installing ingress-nginx keeps your VPS
identical to kind — same annotations, same behaviour, dev/prod parity on
infrastructure. Swapping later means rewriting every controller-specific
annotation.

Other flags worth knowing:
```
--disable servicelb        # if you install MetalLB instead
--write-kubeconfig-mode 644
--node-name runproject-1
```

```bash
sudo k3s kubectl get nodes
```

That's a working Kubernetes cluster. On a 4 GB box. In under a minute. k3s is
genuinely impressive — it's full Kubernetes with the cloud-provider and legacy
bits stripped, SQLite instead of etcd, in one ~60 MB binary.

### kubeconfig on your Mac

```bash
sudo cat /etc/rancher/k3s/k3s.yaml
```

Copy it to `~/.kube/config-runproject` on your Mac and **change
`server: https://127.0.0.1:6443`** to your VPS IP.

```bash
export KUBECONFIG=~/.kube/config-runproject
kubectl get nodes
```

**This requires port 6443 open, which you should not do.** Better: an SSH
tunnel.

```bash
ssh -L 6443:127.0.0.1:6443 rohit@<ip> -N
```

Leave the kubeconfig pointing at `127.0.0.1:6443` and it works through the
tunnel, with 6443 closed to the world. This is the right default.

For CI, a tunnel isn't practical — that's the argument for Tailscale, or for
GitOps (`07-cicd/04`), which removes the need for inbound access entirely.

## Cluster components

Same as kind, with two differences:

```bash
# Generic manifest here, NOT the kind one — k3s has a real LoadBalancer (klipper)
helm install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx --create-namespace

helm install cert-manager jetstack/cert-manager \
  -n cert-manager --create-namespace --set crds.enabled=true

helm install metrics-server metrics-server/metrics-server -n kube-system
#   ↑ NO --kubelet-insecure-tls here. That was a kind workaround.

helm install keda kedacore/keda -n keda --create-namespace
```

```bash
kubectl get svc -n ingress-nginx
```

`EXTERNAL-IP` should show your VPS IP, via k3s's built-in klipper load balancer.

## Deploy

```bash
kubectl apply -k k8s/overlays/prod
```

The same manifests. That's the payoff for doing kind first: the overlay changes
namespace, hostname, replica counts and the cert issuer, and nothing else.

Then: DNS (`04-ingress-dns-tls/03`), staging cert, prod cert.

## Storage on k3s

k3s ships `local-path`, storing PVC data at `/var/lib/rancher/k3s/storage/`.

**Single node, no replication.** If the disk dies, the data is gone. This is why
`08-operations/02` insists backups go **off** the cluster. Your PVC is not a
backup and was never intended to be.

Watch disk usage — 80 GB fills faster than you'd think once `.fit` files
accumulate:
```bash
df -h
sudo du -sh /var/lib/rancher/k3s/storage/*
```

## Ongoing maintenance

**Automatic security updates:**
```bash
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

**k3s upgrades:** re-run the install script. It upgrades in place. Read the
release notes first; on a single node, an upgrade is downtime.

**Watch for:**
- Disk filling (images, logs, PVCs). `sudo k3s crictl rmi --prune` reclaims
  unused images.
- Memory pressure — `kubectl top nodes`, and check for `Evicted` Pods.
- Certificate renewal actually happening (`kubectl get certificate -A`).

## Cutover checklist

- [ ] VPS provisioned, static IP noted, architecture matches your images
- [ ] Non-root user, key-only SSH, root login disabled
- [ ] ufw: 22, 80, 443. **6443 closed.**
- [ ] Provider firewall also allows 80/443
- [ ] Swap enabled
- [ ] k3s installed with `--disable traefik`
- [ ] kubeconfig on your Mac, via SSH tunnel
- [ ] ingress-nginx, cert-manager, metrics-server, KEDA installed
- [ ] `EXTERNAL-IP` on the ingress Service shows the VPS IP
- [ ] Secrets created (sealed, or by hand)
- [ ] `kubectl apply -k overlays/prod`, all Pods Ready
- [ ] **Garmin tokens seeded** via `kubectl cp` — the manual step you'll forget
- [ ] DNS A record → VPS IP, verified with `dig @1.1.1.1`
- [ ] Staging cert issues, then production
- [ ] `https://training.example.com` loads end to end
- [ ] `manage.py check --deploy` clean
- [ ] Backup CronJob running, **and restored once**
- [ ] Monitoring and alerts live
- [ ] Admin restricted or unexposed

## Cost

```
Hetzner CPX21              €5.60/mo
Domain                     already yours
Cloudflare DNS             free
ghcr.io (private)          free
GitHub Actions             free (2000 min/mo)
Cloudflare R2 backups      free under 10 GB
                    total  ~€6/mo
```

About the price of a coffee, for a real cluster with real TLS, real CI/CD, and
real monitoring. That's a genuinely good deal for what you learn.
