# Dockerfile
# Base: python:3.12-slim-bookworm (Official Python Image)

FROM python:3.12-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.3 \
    POETRY_HOME="/opt/poetry"

ENV PATH="$POETRY_HOME/bin:$PATH"

# Install system dependencies
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN curl -sSL https://install.python-poetry.org | python3 -

# Create user 'coreason'
# Set work directory
# Copy dependency definition
# Install dependencies
# Copy project files
# Install project
# Change ownership
RUN groupadd -r coreason && useradd -r -g coreason coreason \
    && mkdir /app \
    && chown coreason:coreason /app

WORKDIR /app

COPY pyproject.toml poetry.lock* ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-root --only main --no-interaction --no-ansi

COPY src/ src/
COPY README.md LICENSE ./

RUN poetry install --only main --no-interaction --no-ansi \
    && chown -R coreason:coreason /app

# Switch to non-root user
USER coreason

# Expose port (Uvicorn default)
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "coreason_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
