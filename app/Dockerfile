FROM python:3.11-slim

# Set the working directory to a parent folder
WORKDIR /service

# Copy requirements from the build context (which is ./app)
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the content of the build context (./app) into a subdirectory named 'app'
COPY . ./app

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Run uvicorn from /service so it can find the 'app' package
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
