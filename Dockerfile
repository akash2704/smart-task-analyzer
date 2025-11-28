# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install uv from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Compile bytecode during installation for faster startup
ENV UV_COMPILE_BYTECODE=1
# Use the system python environment, not a venv (since we are in Docker)
ENV UV_SYSTEM_PYTHON=1

# Set work directory
WORKDIR /app

# Install system dependencies (needed for psycopg2/Postgres)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first (for caching)
COPY pyproject.toml uv.lock* /app/

# Install dependencies using uv
# --system installs into the system python, avoiding the need for activation
RUN uv pip install --system -r pyproject.toml

# Explicitly install postgres adapter for Docker environment
RUN uv pip install --system psycopg2-binary

# Copy project
COPY . /app/

# Entrypoint script
COPY ./docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]