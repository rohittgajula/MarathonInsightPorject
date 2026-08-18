# DevOps, from this repo to a live site

A self-contained course. Everything you need is in these files — no links you
have to open, no videos, nothing that needs signal. Written to be read on a
train.

It is **not** generic. Every concept is taught against the six services this
project actually runs, and the exercises ask you to deploy *this* app, not a
toy nginx.

## What you are building

Today `docker compose up` gives you six containers on your laptop. By the end
of this you will have the same six running on Kubernetes, reachable at
`training.<yourdomain>` over HTTPS, redeployed automatically when you push to
`main`, and scaling when load arrives.

The route:

```
  docker compose            you are here
        │
        ▼
  production images         gunicorn + nginx instead of dev servers
        │
        ▼
  kind cluster (laptop)     write every manifest by hand
        │
        ▼
  ingress + TLS locally     fake certs, real ingress
        │
        ▼
  k3s on a VPS              real IP, real Let's Encrypt cert
        │
        ▼
  DNS: training.<domain>    the subdomain points at it
        │
        ▼
  GitHub Actions            push to main → it deploys itself
        │
        ▼
  HPA, metrics, backups     the parts that make it survivable
```

## How this folder works

You said you want to **write the manifests and run the commands yourself**. So
this is structured as concept → worked example → exercise brief.

- **Concept files** explain the idea and why it exists. Read these anywhere.
- **Worked examples** — there is exactly one fully-written manifest in the whole
  course (`03-kubernetes/02` builds the backend Deployment line by line). It is
  your pattern to copy from. Everything else you write.
- **Exercise briefs** (`06-this-project/03-exercises.md`) give you a spec, the
  constraints that make it hard, a self-check command, and the mistakes people
  make. No answer YAML. If you want an answer key, ask me when you're back
  online — but try first, because the mistakes are where the learning is.

Read in order the first time. The numbering is a dependency order, not a
suggestion; `05-autoscaling` will not land if you skipped `03-kubernetes/07`
on resource requests, because HPA is arithmetic over requests.

## Reading order

| # | Folder | What you get out of it |
|---|---|---|
| 00 | `00-glossary.md` | Every term used later, defined once. Skim now, return often. |
| 01 | `01-foundations` | Networking, DNS, TLS, and a 12-factor audit of this repo. |
| 02 | `02-containers` | Images, layers, registries — and why both Dockerfiles here are dev-only. |
| 03 | `03-kubernetes` | The core objects. The longest section. This is the substance. |
| 04 | `04-ingress-dns-tls` | Getting traffic in, and `training.<domain>` resolving to it. |
| 05 | `05-autoscaling` | HPA, VPA, cluster autoscaler, KEDA — and what here can actually scale. |
| 06 | `06-this-project` | Target architecture, compose→k8s map, and the lab series. |
| 07 | `07-cicd` | Pipelines, GitHub Actions, secrets, GitOps. |
| 08 | `08-operations` | Observability, backups, debugging, hardening. |
| 09 | `09-going-live` | kind setup, k3s on a VPS, launch checklist. |
| — | `flows/` | ASCII diagrams of each end-to-end flow. Read these when lost. |
| — | `reference/` | kubectl cheatsheet, YAML gotchas, troubleshooting tree. |

## Before you start: three things in this repo are broken for production

You will hit these. They are not your fault and they are not optional.

1. **`npm run build` fails.** Two unused-variable errors (`MetricOverlay.tsx:51`,
   `Home.tsx:13`) — `tsc -b` runs before `vite build` and refuses. Dev works,
   production build does not. **Fix this first**: nothing downstream (prod image,
   CI, deploy) can work until `npm run build` exits 0.

2. **Django has no `STATIC_ROOT`.** There is no `collectstatic` target, and
   nothing serves static files when `DEBUG=0`. The admin will load with no CSS.
   `02-containers/02` covers the fix.

3. **Both Dockerfiles run development servers.** `manage.py runserver` and
   `vite` are not production processes. `gunicorn` is already in
   `requirements.txt` and unused. `02-containers/02` covers this too.

Treat these three as lab zero.

## A note on cost

The whole course through section 07 runs on your laptop for free. You only
spend money at `09-going-live`, and then it is one small VPS
(~$5–7/month at Hetzner, ~$6 at DigitalOcean) plus whatever your domain
already costs. Managed Kubernetes is 8–10× that and teaches you less about
what a cluster actually is, which is why kind-then-k3s is the path here.
