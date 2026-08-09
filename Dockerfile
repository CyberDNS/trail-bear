FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY src ./src
COPY ui ./ui
RUN uv pip install --system .

RUN mkdir -p /data

EXPOSE 8080

ENV TRAILS_DB_PATH=/data/trails.db \
    PORT=8080 \
    MPLCONFIGDIR=/tmp/matplotlib

CMD ["mcp-http"]
