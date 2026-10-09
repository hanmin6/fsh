FROM python:3.12-slim-bookworm
ARG HTTP_PROXY
ARG HTTPS_PROXY
RUN apt-get update && apt-get install -y --no-install-recommends xvfb fluxbox x11vnc novnc websockify supervisor fonts-noto-cjk fonts-noto-core ca-certificates && rm -rf /var/lib/apt/lists/*
COPY runtime-requirements.txt /tmp/runtime-requirements.txt
RUN pip install --no-cache-dir -r /tmp/runtime-requirements.txt && python -m playwright install --with-deps chromium
RUN mkdir -p /opt/playwright && cp -a /root/.cache/ms-playwright/. /opt/playwright/ && chmod -R a+rX /opt/playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
RUN useradd -m -u 1000 gateway && mkdir -p /srv/gateway /tmp/gateway-runtime && chown gateway:gateway /srv/gateway /tmp/gateway-runtime
ENV DISPLAY=:99 PYTHONUNBUFFERED=1 FUSANHE_OUTBOUND_PAUSED=true
COPY supervisord.conf /etc/supervisor/supervisord.conf
USER gateway
CMD ["supervisord","-n","-c","/etc/supervisor/supervisord.conf"]
