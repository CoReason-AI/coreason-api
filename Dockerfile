# Stage 1: Builder
FROM python:3.12-slim-bookworm AS builder

# Install build dependencies
RUN pip install --no-cache-dir build==1.3.0 poetry

# Set the working directory
WORKDIR /app

# Copy the project files
COPY pyproject.toml poetry.lock ./
COPY src/ ./src/
COPY README.md .
COPY LICENSE .

# Build the wheel (or just install deps if we preferred, but wheel is cleaner)
RUN python -m build --wheel --outdir /wheels

# Stage 2: Runtime
FROM python:3.12-slim-bookworm AS runtime

# Create a non-root user 'coreason' as per requirement
RUN useradd --create-home --shell /bin/bash coreason
USER coreason

# Add user's local bin to PATH
ENV PATH="/home/coreason/.local/bin:${PATH}"

# Set the working directory
WORKDIR /home/coreason/app

# Copy the wheel from the builder stage
COPY --from=builder /wheels /wheels

# Install the application wheel
RUN pip install --no-cache-dir /wheels/*.whl

# Expose port (default for uvicorn)
EXPOSE 8000

# Run the application
CMD ["uvicorn", "coreason_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
