# Use slim Python 3.11
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for pip + optional build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY backend/ .

# Expose port for Flask
EXPOSE 5000

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_ENV=production
ENV WEB_CONCURRENCY=1

# Start the app
CMD ["flask", "run"]