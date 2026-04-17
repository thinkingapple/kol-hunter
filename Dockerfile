FROM python:3.11-slim

WORKDIR /app

RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p data && chown -R user:user /app

USER user

EXPOSE 7860

CMD ["python", "-m", "uvicorn", "run:app", "--host", "0.0.0.0", "--port", "7860"]
