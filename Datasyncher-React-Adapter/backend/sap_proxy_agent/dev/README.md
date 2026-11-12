# Local dev — SAP proxy hub client mTLS

Production uses **`PROXY_AGENT_HUB_*_PEM`** env vars or mounted secrets.

One **`config.json`** bundle is used by the on-prem ODATA agent and dev smoke scripts. Same mTLS material dials every public port on the hub LoadBalancer:

| Field | Port | Use |
|-------|------|-----|
| `server_host` + `server_port` | **50051** | Hub Connect stream, **ReportProgress** |
| `server_host` + `bootstrap_port` | **50052** | Cert enroll / renew |
| `server_host` + `unary_port` | **50053** | Unary (**GCP token**, legacy status RPCs) |

`config.batch.hub.json` and `config.batch.unary.json` are batch copies of the same shape (credentials + progress HTTPS fields)—not mounted in GKE.

For local migration-function / smoke scripts:

1. Copy `config.json.example` → `config.json` (this folder is gitignored).
2. Optionally place dev certs under `mtls/` (see `mtls/README.md`).
3. Or set `SAP_PROXY_AGENT_GRPC_CONFIG` to an absolute path to your JSON.

Run with **`PYTHONPATH`** including `backend` (and `backend/migration-function` when using MF as cwd):

```powershell
$env:PYTHONPATH = "backend;backend\migration-function"
```
