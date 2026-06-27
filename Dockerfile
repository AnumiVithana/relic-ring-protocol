# Use an official lightweight Python image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory inside the container
WORKDIR /workspace

# Copy requirements file first for caching optimization
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY app/ ./app/
COPY run.py .
COPY universe-config.json .

# Expose port 8000 (which uvicorn runs on)
EXPOSE 8000

# Command to run the application
CMD ["python", "run.py"]
