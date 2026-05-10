FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile

COPY frontend/ ./
COPY docs /app/docs
RUN pnpm build


FROM python:3.12-slim AS app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LEARNINGPYRAMID_DATA_DIR=/data

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY adapter ./adapter
COPY backend ./backend
COPY tools ./tools
COPY README.md ./
COPY docs ./docs
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

EXPOSE 8001

CMD ["python", "tools/run_hosted_server.py"]
