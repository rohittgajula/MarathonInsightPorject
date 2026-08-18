# Backups, and actually restoring them

## Two numbers first

Backups are meaningless until you name these:

**RPO — Recovery Point Objective.** How much data may you lose? A nightly backup
means an RPO of 24 hours: a failure at 23:00 loses a day.

**RTO — Recovery Time Objective.** How long may you be down while restoring?

For this project, honestly:

| | Target | Why |
|---|---|---|
| **RPO** | 24h | Most data is re-fetchable from Garmin. Journal entries are not. |
| **RTO** | a few hours | It's a personal training app. Nobody is paged. |

Being honest about this saves you from building a streaming-replication setup
for an app with one user. **But note the asymmetry**: activities and wellness
can be re-synced from Garmin; `JournalEntry` and `DailyLog` text exists nowhere
else. Losing a day of Garmin data is an inconvenience; losing a month of written
logs is losing something irreplaceable.

That asymmetry should shape the schedule — and it argues for backing up more
often than daily once you're writing logs regularly.

## What actually needs backing up

| Data | Where | Recoverable otherwise? | Priority |
|---|---|---|---|
| Postgres | `pgdata` PVC | ❌ **No** | **Critical** |
| Journal / DailyLog text | in Postgres | ❌ Never | **Critical** |
| Raw `.fit` files | `media` PVC | ⚠️ Only if still on Garmin | High |
| Garmin OAuth tokens | `garmin-tokens` PVC | ⚠️ Re-auth manually | Medium |
| Secrets | k8s Secrets | ⚠️ Re-issue API keys | Medium |
| Sealed Secrets private key | `kube-system` | ❌ **No** | **Critical** |
| Manifests | git | ✅ | — |
| Images | ghcr.io | ✅ rebuildable | — |
| etcd / k3s state | the VPS | ✅ reapply manifests | Low |

Two entries on that list are easy to forget and unrecoverable:

**The Sealed Secrets private key.** Lose it and every SealedSecret in git is
undecryptable. Back it up **off-cluster**, today (`07-cicd/03`).

**The raw `.fit` archive.** `CONTEXT.md` says these are kept permanently and
deliberately, so a better parser can re-run over history. That's the entire
point of keeping them — and it only holds if they survive. Garmin may still
have the originals, but relying on an unofficial API and a saved token to
reconstruct your archive is not a backup strategy.

## Postgres backups

```bash
pg_dump -Fc -h db -U runproject runproject > backup.dump
```

`-Fc` is the custom format: compressed, and restorable selectively with
`pg_restore`. Prefer it to plain SQL.

As a CronJob (Lab 10):

| # | Constraint |
|---|---|
| 1 | Daily at 3am, `timeZone: "Asia/Kolkata"` |
| 2 | `concurrencyPolicy: Forbid` |
| 3 | Password from the same Secret the app uses |
| 4 | Upload **off-cluster** — R2, S3, B2 |
| 5 | Date in the filename |
| 6 | Non-zero exit if the upload fails, so the Job actually shows as Failed |

**#4 is the whole point.** A backup on the same PVC, same node, same VPS as the
database is not a backup. It protects against `DROP TABLE`, not against the node
dying — which is the failure mode local-path storage has no answer for
(`03-kubernetes/05`).

Cloudflare R2 is a good fit: S3-compatible, no egress fees, generous free tier.

**On #6:** a common bug is `pg_dump ... | gzip | aws s3 cp -`. If `pg_dump`
fails, the pipeline still succeeds and you upload an empty file — a "successful"
backup that is worthless. Use `set -o pipefail`, and check the resulting object
is a plausible size before declaring victory.

### Retention

```
7 daily
4 weekly
12 monthly
```

Object storage lifecycle rules can do this automatically. Set them; manual
pruning is a job you'll stop doing.

**Why keep old backups at all:** the disaster you're planning for isn't only
"the disk died." It's also "a bug has been silently corrupting data for three
weeks and every recent backup contains the corruption." That's what monthlies
are for.

### Media files

`.fit` bytes on a PVC. Options:

- **`rclone sync` in a CronJob** — simple, incremental, works today
- **Migrate to object storage entirely** — `django-storages` with an S3 backend.
  No PVC, durable by default, and it also fixes the RWO multi-node constraint
  from `03-kubernetes/05`.

The second is the right long-term answer and solves two problems at once. It's
a code change, not just infrastructure — worth scheduling deliberately rather
than doing in a hurry.

## The restore drill

**A backup you have never restored is a hypothesis.**

This is the part everyone skips, and it is the only part that actually
determines whether you have backups. Do it **now**, while nothing is wrong, and
then quarterly.

```bash
# 1. Fetch the most recent backup from object storage
rclone copy r2:runproject-backups/runproject-2026-08-18.dump .

# 2. Restore into a SCRATCH database — never over the live one
kubectl exec -it db-0 -n runproject -- psql -U runproject -c 'CREATE DATABASE restore_test;'
kubectl cp runproject-2026-08-18.dump runproject/db-0:/tmp/
kubectl exec -it db-0 -n runproject -- pg_restore -U runproject -d restore_test /tmp/runproject-2026-08-18.dump

# 3. Verify — count what you actually care about
kubectl exec -it db-0 -n runproject -- psql -U runproject -d restore_test -c '
  SELECT
    (SELECT count(*) FROM activities_activity)   AS activities,
    (SELECT count(*) FROM journal_dailylog)      AS daily_logs,
    (SELECT count(*) FROM journal_journalentry)  AS entries,
    (SELECT max(log_date) FROM journal_dailylog) AS latest_log;
'

# 4. Clean up
kubectl exec -it db-0 -n runproject -- psql -U runproject -c 'DROP DATABASE restore_test;'
```

**Time yourself.** That elapsed time *is* your RTO. If restoring takes four
hours and you assumed one, you've learned something important for free.

Write down what you find:

```
Restore drill — 2026-08-18
  Backup:   runproject-2026-08-17.dump (14 MB)
  Restore:  4m20s
  Verified: 12 activities, 23 daily logs, latest 2026-08-17 ✓
  Issue:    forgot the media files — dump only covers Postgres
```

That last line is the kind of thing a drill surfaces and nothing else does.

## Disaster scenarios

Think through each. Most need no work — you just need to know the answer.

**A Pod dies.** Kubernetes reschedules it. Nothing to do. This is the case
Kubernetes actually solves.

**The database is corrupted / you drop a table.** Restore from last night's
dump. Lose up to 24 hours. This is the case backups solve.

**The PVC is lost.** Same restore, into a fresh PVC. Slightly longer.

**The whole VPS dies.**
```
1. New VPS, install k3s                    ~30 min
2. Reapply manifests from git              ~10 min
3. Restore Postgres from object storage    ~15 min
4. Restore media from object storage       ~20 min
5. Re-seed Garmin tokens (kubectl cp)      ~5 min
6. Repoint DNS to the new IP               ~5 min + TTL
                                    total  ~1.5h + DNS propagation
```

**That runbook only works if steps 3–5 are written down and tested.** Step 5 in
particular — the manual `kubectl cp` of Garmin tokens — is exactly the kind of
one-time setup step you will not remember. Write it down now (`03-kubernetes/04`
flagged this).

**You lose the Sealed Secrets key.** Re-seal every secret from the original
values. You still have the original values... don't you? This is why that key
gets backed up separately.

**Ransomware / a compromised cluster deletes your backups.** This is why
backup credentials should be **write-only** where possible (R2 tokens can be
scoped to `PutObject` without `DeleteObject`), and why object-lock or versioning
on the bucket is worth enabling. A backup an attacker can delete isn't one.

## Checklist

- [ ] Postgres CronJob, daily, to **off-cluster** object storage
- [ ] Media synced off-cluster (or migrated to object storage)
- [ ] Sealed Secrets private key backed up **off-cluster**
- [ ] Garmin token re-seeding documented in a runbook
- [ ] Retention policy set as a lifecycle rule
- [ ] Backup credentials write-only, bucket versioned
- [ ] **Alert if no successful backup in 36h**
- [ ] Restore drill done, timed, and written down
- [ ] Full VPS-loss runbook written
- [ ] Quarterly reminder to repeat the drill
