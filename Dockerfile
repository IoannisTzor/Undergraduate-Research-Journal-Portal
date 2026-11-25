# STEM Student Journal: production image (Ubuntu 24.04)
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Python, plus certificates for secure connections (for example to the database)
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# A virtual environment, so packages don't touch the system's Python
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install packages first, so Docker can reuse this layer when only the code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Then copy the site's code
COPY . .

# Run as an ordinary user, not root, and give it the uploads folder
RUN useradd --create-home --uid 10001 journal \
    && mkdir -p /app/uploads \
    && chown -R journal:journal /app/uploads
USER journal

ENV FLASK_APP=app \
    UPLOAD_FOLDER=/app/uploads

EXPOSE 8000

# Bring the database up to date, then start the production web server
CMD ["sh", "-c", "flask db upgrade && exec gunicorn --bind 0.0.0.0:8000 --workers 3 --access-logfile - app:app"]
