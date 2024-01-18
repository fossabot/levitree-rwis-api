FROM python:3.11-alpine as build

ENV PIP_DEFAULT_TIMEOUT=100 \
    # Allow statements and log messages to immediately appear
    PYTHONUNBUFFERED=1 \
    # disable a pip version check to reduce run-time & log-spam
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # cache is useless in docker image, so disable to reduce image size
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.3.2

RUN apk add gcc musl-dev libffi-dev

WORKDIR /app
COPY pyproject.toml poetry.lock ./

RUN pip install "poetry==$POETRY_VERSION" \
    && poetry install --no-root --no-ansi --no-interaction \
    && poetry export -f requirements.txt -o requirements.txt


### Final stage
FROM python:3.11-alpine as final

WORKDIR /app

COPY --from=build /app/requirements.txt .

RUN pip install -r requirements.txt

COPY ./levitree_rwis_api levitree_rwis_api

EXPOSE 8000

CMD ["python", "-m", "sanic", "levitree_rwis_api.app"]