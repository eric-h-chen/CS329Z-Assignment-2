FROM python:3.12.16-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337
ENV PYTHONTZPATH="" PYTHONDONTWRITEBYTECODE=1
RUN pip install --no-cache-dir tzdata==2025.2 pytest==8.3.4
WORKDIR /app
COPY app/ /app/
