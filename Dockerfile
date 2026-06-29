# Dockerfile — containerizes the FDA drug-safety pipeline.
#
# Build:  docker build -t drug-safety-pipeline .
# Run:    docker run --env-file .env drug-safety-pipeline
#
# The image runs the Prefect flow (ingest -> load -> dbt run -> dbt test) as its
# default command. The openFDA API key is supplied at RUNTIME via an env var and
# is never baked into the image (see .dockerignore, which excludes .env).

# Slim base matching the project's Python version (the venv used Python 3.11).
FROM python:3.11-slim

# - PYTHONUNBUFFERED: stream stdout/stderr immediately so Prefect/task logs show
#   up live instead of being buffered.
# - PYTHONDONTWRITEBYTECODE: don't litter the image with .pyc files.
# - PIP_NO_CACHE_DIR: smaller image (no pip download cache).
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# All app files live under /app.
WORKDIR /app

# Copy ONLY requirements first and install them, so this expensive layer is cached
# and re-used as long as requirements.txt is unchanged (Docker layer caching). The
# rest of the source is copied afterwards, so code edits don't trigger a reinstall.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the remaining project source (.dockerignore keeps secrets/venv/data/etc out).
COPY . .

# Default command: run the orchestrated pipeline. The flow itself resolves paths
# from its location and sets DBT_PROFILES_DIR for the dbt steps, and (with no venv
# present in the image) falls back to the system python/dbt on PATH.
CMD ["python", "orchestration/pipeline_flow.py"]
