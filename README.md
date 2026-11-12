# DataSyncher

**DataSyncher** is a multi-tenant **ELT (extract–load–transform)** platform: customers configure source-to-warehouse connections and **pipelines** (directed graphs of sync steps) in a React app; a Django **control plane** stores tenants, RBAC, schedules, and run history; Celery, FastAPI, and **migration-function** workers perform extract, staging, and bulk load into **Snowflake** or **Databricks**. For SAP and other sources that cannot be reached from the cloud cluster, an **on-premises proxy agent** dials out over **mTLS** to a **gRPC hub** in GKE—no inbound hole into the customer network.

This repository is the **full monorepo** used for **batch GKE** (`datasyncher-batch`) rollouts and local development. It is not a single deployable artifact: images are built per service and secrets live in your secret manager or cluster, not in git.

**Primary remote:** [github.com/akash-spectrasoln/datasyncher-full-proj](https://github.com/akash-spectrasoln/datasyncher-full-proj)  
**Default branch:** `main`

---

## What’s in the stack

| Layer | Technology | Role |
|-------|------------|------|
| **UI** | React (Vite), TanStack Query, Chakra UI | Connections, pipeline canvas, run status, billing; API via `queryOptions` + axios only |
| **Control plane** | Django / DRF, Channels | Companies, users, connections, pipeline graph, schedules, migration records—**source of truth** |
| **Scheduler** | APScheduler (Postgres job store, Redis lock) | Cron-style pipeline runs; jitter to spread load |
| **Orchestration** | Celery + FastAPI | Turn a saved pipeline into connector work; per-run **job pod** fleets on Kubernetes |
| **Data plane** | `migration-function` | Registry of source→destination handlers; extract, stage, warehouse bulk load |
| **Private SAP path** | `sap-proxy-agent-hub`, on-prem agent | mTLS gRPC; hub routes by customer `proxy_agent` id |
| **Data stores** | PostgreSQL, Redis | Tenants and runs; Celery broker, scheduler lock, flow queues |

**Design detail (HLD / LLD, one run end-to-end, Fivetran comparison):** [`docs/architecture/hld-lld.md`](docs/architecture/hld-lld.md)

**Security (threat model, tenant isolation, proxy agent):** [`docs/security/README.md`](docs/security/README.md)

### Supported connector directions (representative)

Handlers are registered in `migration-function` via `services.migration_common`—not a one-off script per pair. Examples include **Salesforce** (incl. sandbox), **Dynamics 365 F&O**, **NetSuite**, **SAP** (direct or **proxy** OData), **Snowflake**, and **Databricks**, including warehouse-bound loads and some reverse (warehouse → Salesforce) flows. See [`Datasyncher-React-Adapter/docs/connectors/`](Datasyncher-React-Adapter/docs/connectors/).

### High-level request flow

```text
Browser → React SPA → Django DRF → PostgreSQL
                              ↓
                    APScheduler / Run now
                              ↓
                    Celery pipeline workers → FastAPI → Redis → K8s job pods
                              ↓
                    migration-function → Snowflake / Databricks
                              ↓ (SAP proxy)
                    migration-function → gRPC hub ← on-prem agent → customer SAP
```

The browser **never** talks to customer source systems directly.

---

## Repository layout

| Path | Role |
|------|------|
| [`Datasyncher-React-Adapter/`](Datasyncher-React-Adapter/) | Backend: Django (`apps/elttool`), FastAPI + Celery (`backend/fast-api`), connectors (`backend/migration-function`), shared connectors lib, **SAP proxy agent** (`backend/sap_proxy_agent`), K8s manifests (`k8s/`), Cloud Build (`backend/cloudbuild/`) |
| [`frontend/data-syncher-ui/`](frontend/data-syncher-ui/) | Customer React SPA (Vite) |
| [`frontend/`](frontend/) | Docker/nginx wrappers for batch frontend image build |
| [`ODATA AGENT/`](ODATA%20AGENT/) | Reference / legacy ODATA proxy agent patterns |
| [`docs/`](docs/) | Cross-repo architecture and security |
| [`scripts/`](scripts/) | Workspace rollout helpers |
| [`sap_demo_files/`](sap_demo_files/) | SAP mapping / demo artifacts |

**Agent guides (required for code changes):**

| Scope | File |
|-------|------|
| Whole workspace | [`AGENTS.md`](AGENTS.md) |
| Backend | [`Datasyncher-React-Adapter/AGENTS.md`](Datasyncher-React-Adapter/AGENTS.md) |
| Frontend | [`frontend/data-syncher-ui/AGENTS.md`](frontend/data-syncher-ui/AGENTS.md) |

**Documentation indexes:**

| Topic | Start here |
|-------|------------|
| Monorepo docs | [`docs/README.md`](docs/README.md) |
| Backend API, ops, connectors | [`Datasyncher-React-Adapter/docs/README.md`](Datasyncher-React-Adapter/docs/README.md) |
| Kubernetes | [`Datasyncher-React-Adapter/k8s/README.md`](Datasyncher-React-Adapter/k8s/README.md) |
| Batch cluster rollouts | [`Datasyncher-React-Adapter/k8s/batch-cluster/`](Datasyncher-React-Adapter/k8s/batch-cluster/) |
| SAP proxy agent | [`Datasyncher-React-Adapter/docs/operations/proxy-agent/ARCHITECTURE.md`](Datasyncher-React-Adapter/docs/operations/proxy-agent/ARCHITECTURE.md) |

---

## Development quick start

### Prerequisites

- **Python 3.10+**, **Node 18+** (UI), **Docker** (images)
- **gcloud** + **kubectl** (batch cluster work), **gh** (optional)

### Frontend (local UI)

```powershell
cd frontend/data-syncher-ui
npm ci
npm run dev
# Dev server typically http://localhost:5173 — configure API base URL per project env docs
```

```powershell
npm run lint
npm run build
```

### Backend (adapter)

```powershell
cd Datasyncher-React-Adapter
python manage.py test apps.elttool.tests
cd backend/migration-function
pytest tests/ -q
```

Environment variables and local Postgres/Redis setup are documented under adapter **operations** docs; do not commit `.env` or keys.

### Before a pull request

| Tree | Checks |
|------|--------|
| Adapter | `pre-commit run` or `Datasyncher-React-Adapter/scripts/security_checks.ps1` |
| UI | `npm run lint`, `npm run build`, `npm run audit:deps` |

---

## Batch GKE (datasyncher-batch)

Production-style batch deployment runs on **GKE** (`gke_datasyncher-batch_us-central1_datasyncher-batch-cluster`). Images are tagged `:batch` in `gcr.io/datasyncher-batch/`.

| Deployment | Notes |
|------------|--------|
| `django`, `fastapi`, `frontend` | App pool; ingress-facing |
| `migration-function` | Connector HTTP; SAP proxy **gRPC client** to hub |
| `sap-proxy-agent-hub` | Agent mTLS `:50051`; keep **replicas: 1** until shared registry |
| `sap-proxy-agent-unary`, `proxy-agent-gateway` | Bootstrap / HTTPS fallback—see proxy-agent ops |

**Example rollout (migration-function, build + deploy):**

```powershell
cd Datasyncher-React-Adapter
.\k8s\batch-cluster\rollout-migration-function-batch.ps1 -Build
```

**SAP proxy test path (summary):**

1. UI / Django → connection test with `connection_method=proxy`
2. **migration-function** → mTLS gRPC `Datasynchor.TestSapConnection` on hub
3. Hub → registered on-prem agent (`cust_id`); otherwise `UNAVAILABLE` (*agent not connected*)

| Variable | Typical batch value |
|----------|---------------------|
| `PROXY_AGENT_SERVER_HOST` | `sap-proxy-agent-hub-svc.default.svc.cluster.local` |
| `PROXY_AGENT_SERVER_PORT` | `50051` |
| `PROXY_AGENT_HUB_MTLS_DIR` | `/etc/sap-proxy-agent-hub-client/mtls` |

Network policies: [`Datasyncher-React-Adapter/k8s/network-policies/`](Datasyncher-React-Adapter/k8s/network-policies/).

---

## Git branches

| Branch | Purpose |
|--------|---------|
| `main` | Integration baseline (no secrets in history) |
| `feature/sap-proxy-agent-hub` | Hub, gateway, mTLS, network policies |
| `feature/migration-function-connectors` | Connector routes, SAP proxy tests |
| `feature/frontend-data-syncher-ui` | SPA, connection flows |
| `feature/batch-kubernetes-deploy` | K8s rollouts, ingress, secret **examples** |
| `feature/netsuite-connectors` | NetSuite ODBC / routers |
| `feature/odata-agent` | ODATA agent tree parity |
| `feature/databricks-dynamics-load` | Databricks Dynamics load |

```powershell
git fetch origin
git switch feature/sap-proxy-agent-hub
```

**Mirror to another GitHub remote:**

```powershell
git remote add akashaku32 https://github.com/<user>/datasyncher-full-proj.git
git push -u akashaku32 main
```

---

## What is committed vs excluded

Safe to publish in principle; still use a private remote for proprietary code.

**Included:** application source, k8s manifests, **example** secret YAML, Cloud Build configs, docs, tests, checked-in gRPC stubs where applicable.

**Excluded** ([`.gitignore`](.gitignore))—do not force-add: `.env`, `*.key`, live `secrets.yaml`, agent runtime `config.json`, GCP key JSON, `node_modules/`, `venv/`, local logs.

Restore production secrets from your team secret store or `k8s/batch-cluster/secrets/secrets.example.yaml` + `kubectl`—never commit filled values.

---

## Nested git history (local only)

Subfolders once had separate remotes. For one monorepo tree, nested `.git` dirs were moved aside locally (not pushed). To use the adapter as its own repo again, rename `Datasyncher-React-Adapter/.git.datasyncher-adapter-only` back to `.git` only if you intend a separate upstream.

---

## Contributing

1. Branch from `main` or an existing `feature/*` branch.
2. Follow [`AGENTS.md`](AGENTS.md): minimal diffs, no secrets in source, tenant-scoped `Connection` access on the backend, UI HTTP only through `queryOptions/`.
3. Run lint/tests for touched trees.
4. Open a PR to `main`; batch images via Cloud Build under `backend/cloudbuild/batch/`.

---

## License and ownership

Proprietary DataSyncher / Spectra work product. Do not commit customer credentials or production Secret manifests. GCR and cluster credentials belong in your team’s secret store—not this repository.
