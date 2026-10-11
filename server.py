from mcp.server.fastmcp import FastMCP
import yt_dlp
import uvicorn

# --- UVICORN YAMASI ---
# Uvicorn'un varsayılan olarak 127.0.0.1'de (kapalı ağda) çalışmasını engelleyip
# onu zorla 0.0.0.0'da (dışarıya tam açık) ve 8000 portunda çalıştırıyoruz.
original_run = uvicorn.run
def custom_run(*args, **kwargs):
    kwargs['host'] = '0.0.0.0'
    kwargs['port'] = 8000
    original_run(*args, **kwargs)
uvicorn.run = custom_run
# -----------------------

mcp = FastMCP("YouTubeMusicStreamer")

@mcp.tool()
def play_youtube_music(sarki_adi: str) -> str:
    """
    Kullanıcı bir şarkı veya müzik istediğinde YouTube'da arama yapar ve 
    ESP32'nin doğrudan hoparlöründen çalabilmesi için 
    saf ses akışı (.m4a) URL'sini döndürür.
    """
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
            
            return "Şarkı bulunamadı. Lütfen başka bir kelimeyle dene."
            
    except Exception as e:
        return f"Arama sırasında hata oluştu: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport='sse')
