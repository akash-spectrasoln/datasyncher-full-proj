from __future__ import annotations

import json
from typing import Optional

from channels.generic.websocket import AsyncWebsocketConsumer

from apps.elttool.websocket.auth import (
    authenticate_ws_user_async,
    user_owns_pipeline_run_async,
)

_PIPELINE_ID_CACHE: dict[int, int] = {}


async def _pipeline_id_for_run(run_id: int) -> Optional[int]:
    if run_id in _PIPELINE_ID_CACHE:
        return _PIPELINE_ID_CACHE[run_id]

    from asgiref.sync import sync_to_async
    from apps.elttool.models import PipelineRun

    @sync_to_async
    def _load() -> Optional[int]:
        try:
            row = PipelineRun.objects.only("pipeline_id").get(pk=run_id)
            return int(row.pipeline_id)
        except PipelineRun.DoesNotExist:
            return None

    pipeline_id = await _load()
    if pipeline_id is not None:
        _PIPELINE_ID_CACHE[run_id] = pipeline_id
    return pipeline_id


class PipelineRunStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.run_id = int(self.scope["url_route"]["kwargs"]["run_id"])
        user = await authenticate_ws_user_async(self.scope)
        if not user.is_authenticated:
            await self.close(code=4401)
            return
        if not await user_owns_pipeline_run_async(user, self.run_id):
            await self.close(code=4403)
            return

        self.scope["user"] = user
        pipeline_id = await _pipeline_id_for_run(self.run_id)
        if pipeline_id is None:
            await self.close(code=4404)
            return

        self.run_group_name = f"pipeline_run_{self.run_id}"
        self.pipeline_group_name = f"pipeline_runs_{pipeline_id}"
        await self.channel_layer.group_add(self.run_group_name, self.channel_name)
        await self.channel_layer.group_add(
            self.pipeline_group_name,
            self.channel_name,
        )
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "run_group_name"):
            await self.channel_layer.group_discard(
                self.run_group_name,
                self.channel_name,
            )
        if hasattr(self, "pipeline_group_name"):
            await self.channel_layer.group_discard(
                self.pipeline_group_name,
                self.channel_name,
            )

    async def pipeline_run_update(self, event):
        await self.send(
            text_data=json.dumps(
                {"type": "run_detail", "payload": event.get("payload")},
            ),
        )

    async def pipeline_runs_update(self, event):
        await self.send(
            text_data=json.dumps(
                {"type": "run_summary", "payload": event.get("payload")},
            ),
        )
