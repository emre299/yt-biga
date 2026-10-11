import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from mcp.server import Server
from mcp.server.sse import SseServerTransport
import yt_dlp

# Uygulama ve MCP Sunucusunu Başlat
app = FastAPI()
mcp = Server("YouTubeMusicStreamer")
transport = SseServerTransport("/messages")

# 421 ve CORS Hatalarını Kökten Çözen Güvenlik İzinleri
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@mcp.tool()
async def play_youtube_music(sarki_adi: str) -> str:
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'extract_flat': False
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{sarki_adi}", download=False)
            
            if 'entries' in info and len(info['entries']) > 0:
                entry = info['entries'][0]
                title = entry.get('title', 'Bilinmeyen Şarkı')
                url = entry.get('url', '')
                
                return (f"BAŞARILI: '{title}' adlı şarkı bulundu. "
                        f"Lütfen ESP32 cihazına şu doğrudan ses akışı URL'sini "
                        f"çaldırması için komut gönder: {url}")
            
            return "Şarkı bulunamadı."
            
    except Exception as e:
        return f"Hata oluştu: {str(e)}"

# SSE Bağlantı Noktaları (mcphub'ın bağlandığı yerler)
@app.get("/sse")
async def handle_sse(request: Request):
    async with transport.connect_sse(request.scope, request.receive, request._send) as stream:
        await mcp.run(stream, stream, mcp.create_initialization_options())

@app.post("/messages")
async def handle_messages(request: Request):
    await transport.handle_post_message(request.scope, request.receive, request._send)

# Doğal yollardan, yamasız 0.0.0.0 başlatma
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
