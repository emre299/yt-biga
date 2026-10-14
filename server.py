import os
import subprocess
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
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

# Yardımcı Fonksiyon: Şarkıyı YouTube'da 1 saniyede bulur
def find_youtube_video(query: str):
    ydl_opts = {
        'quiet': True,
        'noplaylist': True,
        'extract_flat': 'in_playlist',
        'cookiefile': 'cookies.txt'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch1:{query}", download=False)
        if 'entries' in info and len(info['entries']) > 0:
            return info['entries'][0]
    return None

# 1. TIENHUYIOT & NTC95 YAZILIMLARININ DOĞRUDAN BAĞLANDIĞI UÇ NOKTA (/stream_pcm)
@app.get("/stream_pcm")
async def handle_stream_pcm(
    request: Request,
    song: str = "",
    artist: str = "",
    singer: str = "",
    url: str = ""
):
    print(f"[ESP32 MUZIK ISTEGI] URL: {request.url}", flush=True)
    
    search_query = f"{song} {artist} {singer}".strip()
    if not search_query:
        return JSONResponse({"error": "Şarkı adı belirtilmedi"}, status_code=400)

    try:
        entry = find_youtube_video(search_query)
        if not entry:
            return JSONResponse({"error": "Şarkı bulunamadı"}, status_code=404)

        video_id = entry.get('id')
        title = entry.get('title', song)
        mp3_full_url = f"{PUBLIC_URL}/play/{video_id}.mp3"

        # Eğer cihaz doğrudan ses akışı isterse (url=true)
        if url.lower() == "true":
            return stream_mp3(video_id)

        # Cihazın beklediği standart JSON yanıtı
        return JSONResponse({
            "title": title,
            "artist": artist or singer or "YouTube",
            "audio_url": f"/play/{video_id}.mp3",
            "audio_full_url": mp3_full_url,
            "url": mp3_full_url,
            "lyric_url": "",
            "duration": int(entry.get('duration') or 240)
        })
    except Exception as e:
        print(f"[HATA] {str(e)}", flush=True)
        return JSONResponse({"error": str(e)}, status_code=500)

# 2. CANLI MP3 DÖNÜŞTÜRÜCÜ VE YAYINLAYICI
@app.get("/play/{video_id}.mp3")
@app.get("/play/{video_id}")
def stream_mp3(video_id: str):
    print(f"[MP3 YAYINI BASLIYOR] Video ID: {video_id}", flush=True)
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    
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

# 3. MCP SUNUCUSU (Yedek olarak durmaya devam eder)
@mcp.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="play_youtube_music",
            description="YouTube'dan müzik arar ve doğrudan MP3 akışı URL'sini döndürür.",
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
    sarki_adi = arguments.get("sarki_adi", "")
    try:
        entry = find_youtube_video(sarki_adi)
        if entry:
            video_id = entry.get('id')
            title = entry.get('title', 'Bilinmeyen Şarkı')
            stream_url = f"{PUBLIC_URL}/play/{video_id}.mp3"
            return [types.TextContent(type="text", text=f"BAŞARILI: '{title}' bulundu. URL: {stream_url}")]
        return [types.TextContent(type="text", text="Şarkı bulunamadı.")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"Hata oluştu: {str(e)}")]

@app.get("/sse")
async def handle_sse(request: Request):
    async with transport.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
        await mcp.run(read_stream, write_stream, mcp.create_initialization_options())

@app.post("/messages")
async def handle_messages(request: Request):
    await transport.handle_post_message(request.scope, request.receive, request._send)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
