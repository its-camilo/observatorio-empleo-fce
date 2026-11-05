# Imagen para servidor propio: API + front compilado + CLI de scraping.
FROM node:22-alpine AS front
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt requirements-scraper.txt ./
RUN pip install --no-cache-dir -r requirements-scraper.txt "uvicorn[standard]>=0.30"
COPY observatorio/ observatorio/
COPY alembic/ alembic/
COPY alembic.ini ./
COPY --from=front /web/dist web/dist
EXPOSE 8000
# Aplica migraciones y arranca la API (sirve también el front y /mcp)
CMD ["sh", "-c", "python -m observatorio.run migrar && uvicorn observatorio.api.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
