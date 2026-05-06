# Backend API (uvicorn) + LiveKit voice worker via supervisord.
# UI is deployed separately on Vercel — this image does not ship frontend/dist.

FROM python:3.11-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir supervisor==4.2.5

COPY backend ./backend
COPY artifacts ./artifacts
COPY supervisord.conf .

RUN mkdir -p /app/configs

EXPOSE 8000

CMD ["supervisord", "-n", "-c", "/app/supervisord.conf"]
