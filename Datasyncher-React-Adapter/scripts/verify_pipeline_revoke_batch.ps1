<#
.SYNOPSIS
  Post-rollout smoke checks for pipeline revoke on datasyncher-batch.

.EXAMPLE
  .\scripts\verify_pipeline_revoke_batch.ps1
#>
[CmdletBinding()]
param(
  [string] $Context = "gke_datasyncher-batch_us-central1_datasyncher-batch-cluster",
  [string] $Namespace = "default"
)

$ErrorActionPreference = "Stop"

Write-Host "==> In-cluster wiring check (Django pod)" -ForegroundColor Cyan
kubectl --context=$Context exec deployment/django -n $Namespace -- python scripts/verify_pipeline_revoke.py

Write-Host "==> Confirm revoke symbols in deployed frontend" -ForegroundColor Cyan
$jsCheck = kubectl --context=$Context exec deployment/frontend -n $Namespace -- sh -c "grep -rl 'Revoke flow' /usr/share/nginx/html/assets/*.js 2>/dev/null | head -1" 2>$null
if ($jsCheck) {
  Write-Host "    OK frontend bundle contains revoke UI hooks" -ForegroundColor Green
} else {
  Write-Host "    WARN could not find revoke strings in frontend assets (image may be stale)" -ForegroundColor Yellow
}

Write-Host "==> Confirm revoke API route in Django urls" -ForegroundColor Cyan
$route = kubectl --context=$Context exec deployment/django -n $Namespace -- python -c @"
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datasyncher.settings')
import django
django.setup()
from django.urls import reverse
try:
    print(reverse('pipeline-run-revoke', kwargs={'pipeline_id': 1, 'run_id': 1}))
except Exception as exc:
    raise SystemExit(f'reverse failed: {exc}')
"@
Write-Host "    OK reverse pipeline-run-revoke -> $route" -ForegroundColor Green

Write-Host "`nDone. For live revoke verification, start a flow, click Revoke flow, then confirm run/tables show revoked." -ForegroundColor Green
