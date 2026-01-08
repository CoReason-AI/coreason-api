# Dockerfile
# Base: python:3.12-slim-bookworm (Official Python Image)

FROM python:3.12-slim-bookworm

# Set environment variables
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing pyc files to disc
# PYTHONUNBUFFERED: Prevents Python from buffering stdout and stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.3 \
    POETRY_HOME="/opt/poetry" \
    PATH="$POETRY_HOME/bin:$PATH"

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Create user 'coreason'
RUN groupadd -r coreason && useradd -r -g coreason coreason

# Set work directory
WORKDIR /app

# Copy dependency definition
COPY pyproject.toml poetry.lock* ./

# Install dependencies (no dev dependencies)
# We use --no-root because we copy source code later
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --only main --no-interaction --no-ansi

# Copy project files
COPY src/ src/
COPY README.md LICENSE ./

# Install the project itself
RUN poetry install --only main --no-interaction --no-ansi

# Change ownership to non-root user
RUN chown -R coreason:coreason /app

# Switch to non-root user
USER coreason

# Expose port (Uvicorn default)
EXPOSE 8000

# Command to run the application
# We use uvicorn with host 0.0.0.0 to be accessible outside container
CMD ["uvicorn", "coreason_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
