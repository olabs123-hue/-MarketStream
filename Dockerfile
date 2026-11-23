FROM node:22-alpine AS ui
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM gcc:14 AS native
WORKDIR /app
COPY engine/book_native.cpp engine/book_native.cpp
RUN g++ -std=c++17 -O2 -fPIC -shared -Wall -Wextra -Werror engine/book_native.cpp -o /app/engine/libmarketbook.so

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=native /app/engine/libmarketbook.so /app/engine/libmarketbook.so
ENV MARKETSTREAM_REQUIRE_NATIVE=1 MARKETSTREAM_DB=/tmp/marketstream.sqlite3
COPY --from=ui /ui/dist /app/frontend/dist
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
