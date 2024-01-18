FROM python:3.11-slim-bullseye

RUN python3 -m venv /opt/venv

# Install dependencies:
COPY requirements.txt .
RUN . /opt/venv/bin/activate && pip install -r requirements.txt

EXPOSE 3001

# Run the application:
COPY * .
CMD . /opt/venv/bin/activate && exec python -m sanic server