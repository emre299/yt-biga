import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from mcp.server import Server
from mcp.server.sse import SseServerTransport
import mcp.types as types
import yt_dlp

app = FastAPI()

# 1. MCP Sunucusunu saf (raw) yapıda oluşturuyoruz
mcp = Server("YouTubeMusicStreamer")
transport = SseServerTransport("/messages")

# CORS Güvenlik Duvarı İzinleri (mcphub 421 ve bağlantı hatalarını kökten çözer)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Asistanın göreceği araçları (tool) sisteme tanıtıyoruz
@mcp.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="play_youtube_music",
            description="Kullanıcı YouTube'dan müzik istediğinde arama yapar ve ESP32 cihazı için doğrudan ses akışı URL'sini döndürür.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sarki_adi": {"type": "string", "description": "Aranacak şarkının adı (Örn: Ali Babanın Çiftliği)"}
                },
                "required": ["sarki_adi"]
            }
        )
    ]

# 3. Asistan aracı tetiklediğinde çalışacak asıl işlem (YouTube araması)
@mcp.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name != "play_youtube_music":
        raise ValueError(f"Bilinmeyen komut: {name}")
        
    sarki_adi = arguments.get("sarki_adi")
    
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
                
                mesaj = (f"BAŞARILI: '{title}' adlı şarkı bulundu. "
                         f"Lütfen hoparlörden çalması için ESP32 cihazına şu doğrudan ses akışı URL'sini komut olarak gönder: {url}")
                         
                return [types.TextContent(type="text", text=mesaj)]
            
            return [types.TextContent(type="text", text="Şarkı bulunamadı.")]
            
    except Exception as e:
        return [types.TextContent(type="text", text=f"Hata oluştu: {str(e)}")]

# 4. SSE Ağ Tünelleri (mcphub'ın Coolify ağından bize bağlandığı yerler)
@app.get("/sse")
async def handle_sse(request: Request):
    async with transport.connect_sse(request.scope, request.receive, request._send) as stream:
        await mcp.run(stream, stream, mcp.create_initialization_options())

@app.post("/messages")
async def handle_messages(request: Request):
    await transport.handle_post_message(request.scope, request.receive, request._send)

# 5. Uvicorn'u doğrudan (yamasız) 0.0.0.0 ve 8000 portunda başlatıyoruz
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
