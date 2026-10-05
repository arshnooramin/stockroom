FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
# instance/ holds the SQLite database when DATABASE_URL isn't set.
RUN mkdir -p /app/instance && useradd --create-home app && chown -R app /app
USER app

ENV FLASK_APP=stockroom PORT=8000
EXPOSE 8000
# Create any missing tables, then serve. Production never seeds demo data.
CMD flask init-db && exec gunicorn "stockroom:create_app()" --bind 0.0.0.0:$PORT --workers 2 --access-logfile -
