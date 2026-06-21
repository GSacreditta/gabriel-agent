# GCP Inventory — Gabriel Agent

> Snapshot of what's currently deployed in Google Cloud for the Gabriel Agent project.
> Update this doc when infra changes. Plain Markdown for now — promote to Terraform when
> there's more than one app or more than one environment.

**Last verified:** 2026-06-21

---

## Project

| Field | Value |
|---|---|
| Project ID | `location-19291` |
| Project Number | `709613591310` |
| Primary Region | `us-east1` |
| Owner / SA | `sm18-pa@location-19291.iam.gserviceaccount.com` |

---

## Cloud Run

One service, no staging/dev tier yet.

| Service | Region | URL | Resources | Concurrency | Min/Max | Auth |
|---|---|---|---|---|---|---|
| `gabriel-agent` | us-east1 | https://gabriel-agent-ymerndhsba-ue.a.run.app | 2 CPU / 2Gi RAM | 80 | 1 / 10 | Allow unauthenticated |

- Port: 8081
- Timeout: 900s (15 min)
- Image source: `cloud-run-source-deploy/gabriel-agent` in Artifact Registry
- Service account: `sm18-pa@location-19291.iam.gserviceaccount.com`
- Cloud SQL connection: attached via `--set-cloudsql-instances` to `gabriel-agent-db`

---

## Cloud SQL

| Instance | Engine | Tier | Region | State | Storage | Backups |
|---|---|---|---|---|---|---|
| `gabriel-agent-db` | PostgreSQL 15 | `db-g1-small` (1 vCPU shared, 3.75 GB) | us-east1-b | **STOPPED** | 10 GB SSD, auto-resize on | 2 retained, 7-day txn log |

- Edition: Enterprise
- Deletion protection: **enabled**
- Public IP: `34.138.210.82`
- Authorized networks: Cursor IP, GS Office, GS Home, gabriel-agent service
- Note: instance is currently stopped — bring it up before any deploy that needs DB

---

## Secret Manager (11 secrets)

Names only — values pulled at runtime via Secret Manager API.

- `openai-api-key`
- `slack-bot-token`
- `slack-signing-secret`
- `slack-app-token`
- `db-password`
- `db-host` (`DB_HOST`)
- `db-port`
- `db-name`
- `db-user`
- `GOOGLE_CLOUD_PROJECT_ID`
- `GMAIL_CLIENT_ID`

`USE_SECRET_MANAGER=true` env var on the Cloud Run service triggers the loader at startup.

---

## Cloud Storage

| Bucket | Region | Purpose |
|---|---|---|
| `gabriel-agent-faiss` | us-east1, STANDARD | FAISS vector index persistence |
| `gmail-finanzas` | us-central1, versioning on, uniform ACL | Gmail data archive |
| `location-19291_cloudbuild` | multi-region US | Cloud Build artifacts & source uploads |
| `run-sources-location-19291-us-east1` | us-east1 | Cloud Run source deploys |

---

## Artifact Registry / Container Registry

| Repo | Type | Region | Size | Notes |
|---|---|---|---|---|
| `gcr.io` (legacy) | Container Registry | multi-region | 31.1 GB | Cleanup candidate — migrating to Artifact Registry |
| `cloud-run-source-deploy` | Artifact Registry (Docker) | us-east1 | 9.2 GB | Holds `gabriel-agent` (9 versions) and `gabriel-agent-v2` (6 versions, **orphan since Aug 2025**) |

Image naming pattern: `<build-id-uuid>` + `latest` tag.
Vulnerability scanning: **disabled** (Container Analysis API not enabled).

### Cleanup candidates
- Drop all `gabriel-agent-v2` images (no service consumes them).
- Add image-retention policy on `cloud-run-source-deploy` to keep last 5 versions per family.
- Eventually retire the legacy `gcr.io` registry once all builds publish to Artifact Registry.

---

## Cloud Build

- **Trigger:** none — every build is manual via `gcloud builds submit`. Wire a GitHub trigger when CI volume warrants it.
- **Machine:** `E2_HIGHCPU_8`
- **Pipeline:** see [`cloudbuild.yaml`](../../cloudbuild.yaml) at repo root
- **Build context (post-monorepo move):** `apps/api/` (Dockerfile lives there)
- **Recent history:** 4/5 builds succeeded; 1 failure was at the Cloud Run deploy step, not build

---

## Not enabled / not used

- Pub/Sub topics
- Cloud Tasks queues
- Cloud Scheduler jobs
- Cloud Build GitHub triggers
- Artifact Registry vulnerability scanning
- GitHub Actions CI on the repo

These are intentional gaps for an early-stage project. Revisit once the project has more than one deployable, more than one environment, or a second engineer who needs to deploy.

---

## How to update this doc

When you touch infra, run the matching `gcloud` command and update the table:

```bash
gcloud run services list --project=location-19291
gcloud sql instances list --project=location-19291
gcloud secrets list --project=location-19291
gcloud storage buckets list --project=location-19291
gcloud artifacts repositories list --project=location-19291 --location=us-east1
gcloud builds list --project=location-19291 --limit=5
```
