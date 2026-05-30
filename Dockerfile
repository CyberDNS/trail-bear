FROM python:3.12-slim

# Non-root user for security
RUN addgroup --system mcp && adduser --system --ingroup mcp mcp

WORKDIR /app

# Install uv and project dependencies
RUN pip install --no-cache-dir uv
COPY pyproject.toml README.md ./
COPY src ./src
RUN uv pip install --system .

USER mcp

EXPOSE 8000

CMD ["mcp-http"]
