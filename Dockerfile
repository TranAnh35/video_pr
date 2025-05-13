FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        ffmpeg \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir poetry==1.7.1

COPY pyproject.toml poetry.lock* ./
ENV POETRY_VIRTUALENVS_CREATE=false

RUN poetry install --no-interaction --no-root --only main \
    && rm -rf /root/.cache/pip /root/.cache/pypoetry

COPY . ./

EXPOSE 8000

CMD ["poetry", "run", "uvicorn", "app.web.application:app", "--host", "0.0.0.0", "--port", "8000"]