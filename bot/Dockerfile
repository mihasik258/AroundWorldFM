FROM python:3.12.14-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH=/opt/venv/bin:$PATH

FROM base AS deps
RUN python -m venv /opt/venv
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM deps AS dev
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
WORKDIR /app
CMD ["python", "-m", "aroundfm_bot"]

FROM base AS runtime
RUN useradd --system --uid 10002 --no-create-home --shell /usr/sbin/nologin bot
COPY --from=deps /opt/venv /opt/venv
WORKDIR /app
COPY --chown=bot:bot aroundfm_bot ./aroundfm_bot
USER bot
CMD ["python", "-m", "aroundfm_bot"]
