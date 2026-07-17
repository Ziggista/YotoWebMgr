FROM python:3.12-slim

ARG APP_BUILD_SHA=dev

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app

RUN pip install --no-cache-dir .

ENV APP_BUILD_SHA=${APP_BUILD_SHA}

CMD ["python", "-m", "app.worker"]
