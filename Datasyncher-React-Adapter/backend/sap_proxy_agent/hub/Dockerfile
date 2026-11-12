FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

COPY sap_proxy_agent/hub/requirements.txt /tmp/hub-requirements.txt
RUN pip install --no-cache-dir -r /tmp/hub-requirements.txt

COPY sap_proxy_agent/generated /app/sap_proxy_agent/generated
COPY sap_proxy_agent/hub /app/sap_proxy_agent/hub

RUN apt-get update \
    && apt-get install -y --no-install-recommends socat \
    && rm -rf /var/lib/apt/lists/* \
    && sed -i 's/\r$//' /app/sap_proxy_agent/hub/entrypoint.sh \
    && chmod +x /app/sap_proxy_agent/hub/entrypoint.sh

ENV HTTP_HEALTH_PORT=8081
ENV GRPC_HUB_PORT=50051
ENV GRPC_BOOTSTRAP_PORT=50052
ENV HUB_MTLS_DIR=/etc/sap-proxy-agent-hub/mtls
ENV ENABLE_UNARY_LB_TCP_PROXY=1

EXPOSE 50051 50052 50053 8081

CMD ["/bin/sh", "/app/sap_proxy_agent/hub/entrypoint.sh"]
