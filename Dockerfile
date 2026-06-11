FROM python:3.11-slim

WORKDIR /app

# Copy project and install
COPY pyproject.toml .
COPY src/ /app/src/
RUN pip install --no-cache-dir .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Run operator
CMD ["synos", "operator"]
