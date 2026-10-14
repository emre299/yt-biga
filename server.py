import os
import subprocess
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from mcp.server import Server
from mcp.server.sse import SseServerTransport
import mcp.types as types
import yt_dlp

app = FastAPI()
mcp = Server("YouTubeMusicStreamer")
transport = SseServerTransport("/messages")

PUBLIC_URL = "http://d8izg6hveevjybbi6xc9h3y2.138.2.176.169.sslip.io"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    if request.url.path not in ["/sse", "/messages"]:
        print(f"[GELEN ISTEK] {request.method} {request.url}", flush=True)
    return await call_next(request)

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

@app.get("/stream_pcm")
@app.get("/stream_pcm/stream_pcm")
async def handle_stream_pcm(
    request: Request,
    song: str = "",
    song_name: str = "",
    artist: str = "",
    singer: str = "",
    url: str = ""
):
    print(f"[ESP32 MUZIK ISTEGI] Parametreler: {request.query_params}", flush=True)
    
    s_name = song or song_name
    s_artist = artist or singer
    search_query = f"{s_name} {s_artist}".strip()
    
    if not search_query:
        return JSONResponse({"error": "Sarki adi belirtilmedi"}, status_code=400)

    try:
        entry = find_youtube_video(search_query)
        if not entry:
            return JSONResponse({"error": "Sarki bulunamadi"}, status_code=404)

        video_id = entry.get('id')
        title = entry.get('title', s_name)
        mp3_path = f"/play/{video_id}.mp3"
        mp3_full_url = f"{PUBLIC_URL}{mp3_path}"

        if url.lower() == "true":
            return stream_mp3(video_id)

        return JSONResponse({
            "title": title,
            "artist": s_artist or "YouTube",
            "audio_url": mp3_path,
            "url": mp3_full_url,
            "lyric_url": "",
            "duration": int(entry.get('duration') or 240)
        })
    except Exception as e:
        print(f"[HATA] {str(e)}", flush=True)
        return JSONResponse({"error": str(e)}, status_code=500)

# .mp3 UZANTI HATASININ DÜZELTİLDİĞİ YER
@app.get("/play/{video_id}")
def stream_mp3(video_id: str):
    # Eğer ID'nin sonunda .mp3 varsa temizle (Örn: SCZgGVqVsbY.mp3 -> SCZgGVqVsbY)
    clean_id = video_id.replace(".mp3", "").strip()
    print(f"[MP3 YAYINI BASLIYOR] Temiz Video ID: {clean_id}", flush=True)
    
    youtube_url = f"https://www.youtube.com/watch?v={clean_id}"
    
    # ESP32'nin MP3 çözücüsü (helix/libmad) için en uyumlu ayarlar (-write_xing 0 ve 44100Hz/24000Hz)
    cmd = (
        f'yt-dlp --cookies cookies.txt --js-runtimes deno,node --no-playlist -f "ba/b" -o - "{youtube_url}" | '
        f'ffmpeg -hide_banner -loglevel error -i pipe:0 -vn -acodec libmp3lame -ab 64k -ac 1 -ar 24000 -write_xing 0 -id3v2_version 0 -f mp3 -'
    )
    
    # Hataları Runtime Logs'da görebilmek için stderr'i gizlemiyoruz
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)

    def generate():
        try:
            while chunk := process.stdout.read(4096):
                yield chunk
        finally:
            process.kill()

    return StreamingResponse(generate(), media_type="audio/mpeg")

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
    return Response()

@app.post("/messages")
async def handle_messages(request: Request):
    await transport.handle_post_message(request.scope, request.receive, request._send)
    return Response()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
