# Use a Python base image
FROM python:3.11-slim

# Install Tesseract OCR and other dependencies
RUN apt-get update && apt-get install -y tesseract-ocr

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . .

# Install the required Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port your app runs on
EXPOSE 10000

# Start the application using Gunicorn
CMD ["gunicorn", "main:app"]