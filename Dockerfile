FROM python:3.11-slim

WORKDIR /app

# FFmpeg, Node.js ve Deno için gerekli sistem araçları
RUN apt-get update && apt-get install -y ffmpeg nodejs curl unzip && rm -rf /var/lib/apt/lists/*

# Deno'yu doğrudan sistem ana yoluna (/usr/local/bin) kuruyoruz
ENV DENO_INSTALL="/usr/local"
RUN curl -fsSL https://deno.land/install.sh | sh

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "server.py"]
