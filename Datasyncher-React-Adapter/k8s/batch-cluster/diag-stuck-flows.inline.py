from apps.elttool.models import PipelineRun
from apps.elttool.v1.pipeline_views import (
    _company_active_flow_count,
    _company_max_concurrent_flows,
    _company_redis_fleet_count,
    try_acquire_company_flow_slot,
)

for rid in (14768, 14769, 14770, 14772, 14773, 14774):
    run = PipelineRun.objects.select_related("pipeline__cmp").get(id=rid)
    company = run.pipeline.cmp
    meta = run.metadata or {}
    limit = _company_max_concurrent_flows(company)
    active = _company_active_flow_count(company)
    fleets = _company_redis_fleet_count(company)
    slot = None
    if run.status in ("running", "queued"):
        slot = try_acquire_company_flow_slot(rid)
    print("RUN", rid, "pipeline", run.pipeline_id, run.status)
    print(
        "  company",
        company.cmp_id,
        "cap",
        limit,
        "db_active",
        active,
        "redis_fleets",
        fleets,
        "slot_try",
        slot,
    )
    print(
        "  executor",
        meta.get("executor"),
        "wait",
        meta.get("waiting_for_capacity"),
        "current",
        meta.get("current_node_ids"),
    )
    nodes = meta.get("nodes") or {}
    statuses = {k: (v or {}).get("status") for k, v in nodes.items()}
    print("  node_statuses", statuses)
    print("  error", meta.get("error"))
