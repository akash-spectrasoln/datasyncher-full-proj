import { useCallback, useMemo } from "react";

import useWebSocket from "react-use-websocket";

import { getWebSocketUrl } from "@/helpers/websocket";
import { patchPipelineLatestRunStatusDirect } from "@/queryOptions/pipeline/usePipeline";
import { type PipelineRunStatus } from "@/types/pipeline";

import { useQueryClient } from "@tanstack/react-query";

type CompanyPipelineStatusMessage = {
  event?: string;
  cmp_id?: number;
  pipeline_id?: number;
  pipeline_run_id?: number;
  latest_run_status?: PipelineRunStatus | null;
};

export const useCompanyPipelineStatusWS = (cmpId: number | null) => {
  const queryClient = useQueryClient();

  const socketUrl = getWebSocketUrl(
    cmpId ? `/ws/company_pipeline_status/${cmpId}/` : "",
  );

  const onMessage = useCallback(
    (event: WebSocketEventMap["message"]) => {
      if (!cmpId) return;

      let message: CompanyPipelineStatusMessage;
      try {
        message = JSON.parse(event.data) as CompanyPipelineStatusMessage;
      } catch {
        return;
      }

      if (
        message.event !== "pipeline_latest_run_status" ||
        message.pipeline_id == null
      ) {
        return;
      }

      patchPipelineLatestRunStatusDirect(
        queryClient,
        message.pipeline_id,
        message.latest_run_status ?? null,
      );
    },
    [cmpId, queryClient],
  );

  const options = useMemo(
    () => ({
      onMessage,
      shouldReconnect: (closeEvent: CloseEvent) => closeEvent.code !== 1000,
      reconnectInterval: 3000,
      reconnectAttempts: 10,
      share: true,
      retryOnError: true,
    }),
    [onMessage],
  );

  useWebSocket(socketUrl, options);
};

export default useCompanyPipelineStatusWS;
