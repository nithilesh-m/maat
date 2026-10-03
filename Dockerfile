FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl libpango-1.0-0 libpangoft2-1.0-0 \
 && curl -L -o /usr/local/bin/opa https://openpolicyagent.org/downloads/v1.21.1/opa_linux_amd64_static \
 && chmod +x /usr/local/bin/opa && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev
ENV MAAT_API_RUNS_DIR=/data/runs OLLAMA_HOST=http://host.docker.internal:11434
EXPOSE 8080
CMD ["uv", "run", "--frozen", "--no-dev", "maat", "serve", "--host", "0.0.0.0", "--port", "8080"]
