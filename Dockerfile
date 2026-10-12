FROM python:3.11-slim

WORKDIR /app

# Deno kurabilmek için curl ve unzip araçlarını da ekliyoruz
RUN apt-get update && apt-get install -y ffmpeg curl unzip && rm -rf /var/lib/apt/lists/*

# Deno JavaScript Motorunu indirip sisteme tanıtıyoruz
RUN curl -fsSL https://deno.land/install.sh | sh
RUN ln -s /root/.deno/bin/deno /usr/bin/deno

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "server.py"]
