FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directory
RUN mkdir -p data

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "run:app", "--host", "0.0.0.0", "--port", "8080"]
