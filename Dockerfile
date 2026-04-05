FROM python:3.12-slim
LABEL maintainer="viibeware Corp."
LABEL description="Garage Logbook - Car Maintenance Tracker"
RUN apt-get update && apt-get install -y --no-install-recommends sqlite3 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /data/uploads/cars /data/uploads/maintenance
ENV DATABASE_PATH=/data/garage_logbook.db
ENV UPLOAD_FOLDER=/data/uploads
ENV SECRET_KEY=change-me-in-docker-compose
ENV PYTHONUNBUFFERED=1
EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "--access-logfile", "-", "app:app"]
