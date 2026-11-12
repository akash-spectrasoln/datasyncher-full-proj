#!/bin/sh
set -eu

target="${TOKEN_VALIDATION_GRPC_TARGET:-sap-proxy-agent-unary-svc:50053}"
if [ "${ENABLE_UNARY_LB_TCP_PROXY:-1}" = "1" ]; then
  socat TCP-LISTEN:50053,fork,reuseaddr TCP:${target} &
fi
exec python -m sap_proxy_agent.hub
