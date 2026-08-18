# Storage, and running Postgres in a cluster

## The volume types

**emptyDir** — a scratch directory created with the Pod, deleted with it. For
caches and inter-container handoff within a Pod. Survives a container restart,
not a Pod reschedule.

**hostPath** — a directory on the node. Ties the Pod to that node forever and is
a well-known security hole (mount `/` and you own the node). Avoid.

**PersistentVolumeClaim** — the real answer. A request for durable storage that
outlives the Pod.

## PV / PVC / StorageClass

```
   PersistentVolumeClaim  "I want 10Gi, ReadWriteOnce"
              │
              │  bound by the control plane
              ▼
   PersistentVolume       actual storage: a cloud disk, an NFS export,
              │           a path on a node
              ▼
   StorageClass           the recipe for creating one on demand
```

Static provisioning (you create PVs by hand) is rare. Normally a **StorageClass**
watches for unbound PVCs and provisions a PV automatically.

```bash
kubectl get storageclass
```

- **kind** → `standard` (rancher.io/local-path), a directory on the node
- **k3s** → `local-path`, same idea
- **cloud** → `gp3`, `pd-balanced`, etc., real network-attached disks

**The local-path caveat matters a lot for you.** With local-path, the data lives
on *one specific node's disk*. The Pod is then pinned to that node. If the node
dies, the data is gone — there is no replication. On a single-node cluster
that's a distinction without a difference, so it's fine for now. Just don't
mistake "it has a PVC" for "it's backed up." See `08-operations/02`.

## Access modes — where your media volume gets interesting

| Mode | Meaning |
|---|---|
| **ReadWriteOnce (RWO)** | Mountable read-write by **one node**. Multiple Pods can share it *if they're on the same node*. |
| **ReadOnlyMany (ROX)** | Read-only by many nodes |
| **ReadWriteMany (RWX)** | Read-write by many nodes. Needs a networked filesystem — NFS, CephFS, EFS. |

Note RWO is per *node*, not per Pod — a detail that saves you here.

**Your problem:** compose mounts the `media` volume into `backend`, `worker`
*and* `beat`. In Kubernetes those are three Deployments. On a single-node
cluster, RWO is fine — all Pods land on the one node. **Add a second node and it
breaks**, in a way that looks like random file-not-found errors depending on
which node a Pod happened to schedule onto.

The options:

| Option | Trade-off |
|---|---|
| **Stay single-node** | Free, works today, honest for a personal app. Document the constraint loudly. |
| **Pin with node affinity** | Force all three onto one node. Works, but you've given up rescheduling on node failure. |
| **RWX via NFS** | Real fix. Run an NFS provisioner or use a managed filesystem. More moving parts. |
| **Object storage (S3/R2)** | The actual right answer. `django-storages` + S3 backend, no PVC at all, and the `.fit` files become durable and cheap. |

`CONTEXT.md` says raw `.fit` bytes are kept permanently, deliberately, so a
better parser can re-run over history. That's a growing archive of
write-once/read-rarely blobs — the textbook case for object storage.
Cloudflare R2 has no egress fees and a generous free tier.

**Recommendation:** single-node RWO now, with a comment in the manifest saying
why. Note S3/R2 as the migration when you add a node or the archive grows.
Don't build it yet.

## StatefulSet, and Postgres

A Deployment gives Pods random names (`backend-7d4f8b-x2k9p`) and a shared PVC.
Databases need the opposite:

- **Stable identity** — `db-0` is always `db-0`, with the same DNS name
- **Stable storage** — `db-0` always reattaches to *its* volume
- **Ordered operations** — `db-0` before `db-1`, reverse on scale-down

That's a StatefulSet. Key differences from a Deployment:

```yaml
apiVersion: apps/v1
kind: StatefulSet
spec:
  serviceName: db          # must name a HEADLESS Service — this is what
                           # gives you db-0.db.runproject.svc.cluster.local
  replicas: 1
  volumeClaimTemplates:    # NOT a `volumes:` entry. Each replica gets its
    - metadata:            # OWN PVC, generated from this template.
        name: pgdata
      spec:
        accessModes: [ReadWriteOnce]
        resources:
          requests:
            storage: 10Gi
```

Two things to know about `volumeClaimTemplates`:

- The generated PVC is named `pgdata-db-0`. Predictable, and what you'll
  reference in a restore.
- **Deleting the StatefulSet does not delete the PVCs.** Deliberate — it's a
  safety net. It also means a "clean reinstall" silently reuses the old data and
  you spend an hour wondering why your schema is stale. Check
  `kubectl get pvc` after any teardown.

### The `subPath` trap

Postgres refuses to initialise into a non-empty directory. Most PV
implementations put a `lost+found` in the mount root. So:

```yaml
volumeMounts:
  - name: pgdata
    mountPath: /var/lib/postgresql/data
    subPath: postgres        # ← without this, initdb fails
```

Alternatively set `PGDATA=/var/lib/postgresql/data/pgdata`. Either works; pick
one. Skipping both gives you a CrashLoopBackOff with `directory
"/var/lib/postgresql/data" exists but is not empty` — clear once you've seen it,
baffling the first time.

### Should you run Postgres in Kubernetes at all?

Honest answer: for learning, yes — you should know how. For production data you
care about, **a managed Postgres is usually the better call**, and being able
to say why is more valuable than being able to write the StatefulSet.

**Running it yourself means you own:** backups and *tested* restores, version
upgrades (a major version bump is a dump/restore, not a rolling update),
connection pooling, failover, monitoring, tuning `shared_buffers` against your
memory limit, and the fact that local-path storage has no replication.

**For this project:** run it in-cluster. It's one user, the data is
reconstructible from Garmin plus the raw `.fit` archive, and the learning is the
point. But set up `pg_dump` to object storage on day one (`08-operations/02`)
and actually restore from it once. A backup you have never restored is a
hypothesis.

If it were someone else's health data, the answer would flip.

**Middle ground worth knowing:** operators like CloudNativePG turn Postgres into
a proper Kubernetes citizen — automated failover, backups to S3, point-in-time
recovery, managed major-version upgrades. Genuinely good. Also a lot of
machinery to learn on top of the machinery you're already learning. Write the
plain StatefulSet first so you understand what the operator is doing for you.

## Redis

Your Redis is a Celery broker and result backend. What's in it: queued task
messages and results, all of them regenerable.

So: **a Deployment with no persistence is the right call.** Redis restarts,
queue is empty, beat re-schedules everything within its interval, and
`sweep_unread` (which `celery.py` runs every 10 minutes precisely to heal
missed work) picks up the rest. The system is already designed to tolerate this.

If you later put anything in Redis you can't regenerate, revisit — that means a
PVC and choosing between RDB snapshots and AOF. Not now.

## Resizing

Most StorageClasses support expansion:

```bash
kubectl patch pvc pgdata-db-0 -n runproject -p '{"spec":{"resources":{"requests":{"storage":"20Gi"}}}}'
```

Only **grows**, never shrinks, and only if the StorageClass has
`allowVolumeExpansion: true`. Check that before you pick a size — though
starting small and growing is the right instinct either way.

## Commands

```bash
kubectl get pvc,pv -n runproject
kubectl describe pvc pgdata-db-0 -n runproject
kubectl get storageclass
```

A PVC stuck `Pending` is almost always: no default StorageClass, or an access
mode the StorageClass can't satisfy (asking RWX from local-path). `describe`
says which, in the Events.
