# Stage 1: install dependencies
FROM python:3.12-slim-bookworm AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN pip install --upgrade pip && pip install --no-cache-dir \
    "pydantic>=2.7" "pydantic-settings>=2.3" "fastapi>=0.111" \
    "sqlalchemy[asyncio]>=2.0" "asyncpg>=0.29" "alembic>=1.13" \
    "uvicorn>=0.30" "structlog>=24.0" "boto3>=1.34" \
    "pandas>=2.2" "numpy>=1.26" "scipy>=1.17" "statsmodels>=0.14" \
    "pingouin>=0.6" "cyvcf2>=0.33" "pysam>=0.24" \
    "tenacity>=9.0" "httpx>=0.27" "requests>=2.31"

# Stage 2: lean final image
FROM python:3.12-slim-bookworm AS final
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY api/       ./api/
COPY analysis/  ./analysis/

RUN groupadd -r biomarker && useradd -r -g biomarker biomarker
RUN chown -R biomarker:biomarker /app
USER biomarker

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
