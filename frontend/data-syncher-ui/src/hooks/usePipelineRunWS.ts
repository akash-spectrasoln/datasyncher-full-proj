import { useCallback } from "react";

import useWebSocket from "react-use-websocket";

import { getWebSocketUrl } from "@/helpers/websocket";
import {
  patchPipelineLatestRunStatusInCache,
  pipelineRunQueryKey,
  pipelineRunsQueryKey,
} from "@/queryOptions/pipeline/usePipeline";
import {
  type PipelineRunDetail,
  type PipelineRunSummary,
} from "@/types/pipeline";

import { useQueryClient } from "@tanstack/react-query";

type PipelineRunWSMessage = {
  type?: string;
  payload?: PipelineRunDetail | PipelineRunSummary;
};

export function usePipelineRunWS(
  pipelineId: number | null,
  runId: number | null,
) {
  const queryClient = useQueryClient();

  const getSocketUrl = useCallback(() => {
    if (!runId) {
      throw new Error("Pipeline run id is required for WebSocket.");
    }
    const url = getWebSocketUrl(`/ws/pipeline_run/${runId}/`);
    if (!url) {
      throw new Error("WebSocket authentication token is not available.");
    }
    return url;
  }, [runId]);

  const onMessage = useCallback(
    (event: WebSocketEventMap["message"]) => {
      if (!pipelineId || !runId) return;

      let message: PipelineRunWSMessage;
      try {
        message = JSON.parse(event.data) as PipelineRunWSMessage;
      } catch {
        return;
      }

      const payload = message.payload;
      if (!payload || typeof payload !== "object") return;

      if (message.type === "run_detail") {
        const detail = payload as PipelineRunDetail;
        if (detail.pipeline_run_id !== runId) return;
        queryClient.setQueryData(
          pipelineRunQueryKey(pipelineId, runId),
          detail,
        );
        patchPipelineLatestRunStatusInCache(queryClient, pipelineId, detail);
        queryClient.setQueryData<{ runs: PipelineRunSummary[] }>(
          pipelineRunsQueryKey(pipelineId),
          (cached) => {
            if (!cached?.runs?.length) return cached;
            let changed = false;
            const runs = cached.runs.map((run) => {
              if (run.pipeline_run_id !== runId) return run;
              changed = true;
              return {
                ...run,
                status: detail.status,
                finished_at: detail.finished_at,
                overall: detail.overall,
                error: detail.error ?? run.error,
                waiting_for_flow_slot: detail.waiting_for_flow_slot,
              };
            });
            return changed ? { runs } : cached;
          },
        );
        return;
      }

      if (message.type === "run_summary") {
        const summary = payload as PipelineRunSummary;
        if (summary.pipeline_run_id !== runId) return;
        patchPipelineLatestRunStatusInCache(queryClient, pipelineId, summary);
        queryClient.setQueryData<{ runs: PipelineRunSummary[] }>(
          pipelineRunsQueryKey(pipelineId),
          (cached) => {
            if (!cached?.runs?.length) return cached;
            let changed = false;
            const runs = cached.runs.map((run) => {
              if (run.pipeline_run_id !== runId) return run;
              changed = true;
              return { ...run, ...summary };
            });
            return changed ? { runs } : cached;
          },
        );
      }
    },
    [pipelineId, queryClient, runId],
  );

  useWebSocket(pipelineId && runId ? getSocketUrl : null, {
    onMessage,
    shouldReconnect: (closeEvent) => closeEvent.code !== 1000,
    reconnectInterval: 3000,
    reconnectAttempts: 10,
    share: true,
    retryOnError: true,
  });
}

export default usePipelineRunWS;
