# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies (mysqlclient requires pkg-config and default-libmysqlclient-dev)
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    default-libmysqlclient-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy project files
COPY . /app/

# Expose port
EXPOSE 8000

# In Render, environment variables are available during runtime.
# We run collectstatic, migrate, and then start gunicorn.
# Using sh -c to avoid issues with CRLF line endings from Windows scripts.
CMD sh -c "python manage.py collectstatic --noinput && python manage.py migrate && gunicorn kodehax_academy.wsgi:application --bind 0.0.0.0:${PORT:-8000}"
