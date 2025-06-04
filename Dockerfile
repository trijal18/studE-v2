# Use official Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system packages required by pdf tools
RUN apt-get update && apt-get install -y \
    build-essential \
    poppler-utils \
 && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy rest of the code
COPY . .

# Create folders used by the app
RUN mkdir -p uploads static

# Expose FastAPI port
EXPOSE 8000

# Start the FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
