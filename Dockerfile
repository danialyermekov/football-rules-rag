FROM python:3.13-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.7.12 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    MLFLOW_DISABLE_TELEMETRY=true \
    MLFLOW_DISABLE_AGENT_HINT=1

COPY pyproject.toml uv.lock README.md ./
COPY src/ src/
COPY scripts/ scripts/
COPY docs/source-manifest.json docs/source-manifest.json
COPY data/evaluation/ data/evaluation/

RUN uv sync --locked --no-dev --extra cpu \
    && rm -rf /root/.cache/uv

ENTRYPOINT ["uv", "run", "--no-sync", "football-rules"]
CMD ["--help"]
