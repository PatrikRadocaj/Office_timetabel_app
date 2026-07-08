FROM node:20-slim AS frontend-build

WORKDIR /frontend

COPY react-app/package*.json ./
RUN npm ci

COPY react-app/ ./
RUN npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY call-center-scheduler/backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY call-center-scheduler/backend /app/backend
COPY --from=frontend-build /frontend/dist /app/react-app/dist

WORKDIR /app/backend
ENV PYTHONPATH=/app/backend

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
