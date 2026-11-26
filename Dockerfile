FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=America/Manaus \
    A5_DATA_DIR=/data \
    A5_PORT=5000 \
    A5_BEHIND_PROXY=1 \
    A5_SOCKETIO_ASYNC_MODE=gevent \
    A5_DISABLE_PYTHON_GZIP=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        ca-certificates \
        tzdata \
        curl \
        nodejs \
    && ln -snf /usr/share/zoneinfo/America/Manaus /etc/localtime \
    && echo "America/Manaus" > /etc/timezone \
    && git config --system --add safe.directory /app \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

COPY . /app
RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /data/database /data/backups /data/static/uploads \
                /data/entrada_pdfs /data/arquivados_pdfs \
                /data/entrada_chamados_externos /data/arquivados_chamados_externos \
                /data/rotas_imagens

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:5000/healthz || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
