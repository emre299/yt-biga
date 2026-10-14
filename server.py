import os
import subprocess
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from mcp.server import Server
from mcp.server.sse import SseServerTransport
import mcp.types as types
import yt_dlp

app = FastAPI()
mcp = Server("YouTubeMusicStreamer")
transport = SseServerTransport("/messages")

# Coolify üzerindeki dış erişim adresin
PUBLIC_URL = "http://d8izg6hveevjybbi6xc9h3y2.138.2.176.169.sslip.io"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@mcp.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="play_youtube_music",
            description="Kullanıcı YouTube'dan müzik istediğinde arama yapar ve doğrudan çalınabilir MP3 ses akışı URL'sini döndürür.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sarki_adi": {"type": "string", "description": "Aranacak şarkının adı"}
                },
                "required": ["sarki_adi"]
            }
        )
    ]

@mcp.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name != "play_youtube_music":
        raise ValueError(f"Bilinmeyen komut: {name}")
        
    sarki_adi = arguments.get("sarki_adi")
    
    # extract_flat='in_playlist' sayesinde şifre çözmeye takılmadan 1 saniyede Video ID bulunur
    ydl_opts = {
        'quiet': True,
        'noplaylist': True,
        'extract_flat': 'in_playlist',
        'cookiefile': 'cookies.txt'
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{sarki_adi}", download=False)
            
            if 'entries' in info and len(info['entries']) > 0:
                entry = info['entries'][0]
                video_id = entry.get('id')
                title = entry.get('title', 'Bilinmeyen Şarkı')
                
                stream_url = f"{PUBLIC_URL}/play/{video_id}.mp3"
                
                mesaj = (f"BAŞARILI: '{title}' adlı şarkı bulundu. "
                         f"Lütfen hoparlörden çalması için ESP32 cihazına şu doğrudan MP3 akışı URL'sini gönder: {stream_url}")
                         
                return [types.TextContent(type="text", text=mesaj)]
            
            return [types.TextContent(type="text", text="Şarkı bulunamadı.")]
            
    except Exception as e:
        return [types.TextContent(type="text", text=f"Hata oluştu: {str(e)}")]

# VPS ÜZERİNDEN CANLI MP3 DÖNÜŞTÜRÜCÜ VE YAYINLAYICI
@app.get("/play/{video_id}.mp3")
def stream_mp3(video_id: str):
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    
    # yt-dlp sesi çerez ve JS motoruyla indirir, doğrudan FFmpeg'e borular (pipe)
    cmd = (
        f'yt-dlp --cookies cookies.txt --js-runtimes deno,node -f "ba/b" -o - "{youtube_url}" | '
        f'ffmpeg -i pipe:0 -vn -acodec libmp3lame -ab 64k -ac 1 -ar 24000 -f mp3 -'
    )
    
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def generate():
        try:
            while chunk := process.stdout.read(4096):
                yield chunk
        finally:
            process.kill()

    return StreamingResponse(generate(), media_type="audio/mpeg")

@app.get("/sse")
async def handle_sse(request: Request):
    async with transport.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
        await mcp.run(read_stream, write_stream, mcp.create_initialization_options())

@app.post("/messages")
async def handle_messages(request: Request):
    await transport.handle_post_message(request.scope, request.receive, request._send)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
