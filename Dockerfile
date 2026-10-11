FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# İçerideki her şeyi (server.py ve cookies.txt dahil) kopyala
COPY . .

EXPOSE 8000

CMD ["python", "server.py"]
