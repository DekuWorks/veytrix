FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY services ./services
COPY infra/docker/api-entrypoint.sh /entrypoint.sh

RUN pip install --no-cache-dir . \
    && chmod 755 /entrypoint.sh \
    && useradd --create-home --shell /usr/sbin/nologin --uid 10001 veytrix \
    && chown -R veytrix:veytrix /app

USER veytrix
WORKDIR /app/services/api

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
