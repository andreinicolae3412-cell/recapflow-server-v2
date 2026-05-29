from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import yt_dlp
import static_ffmpeg
import tempfile
import os
import uuid
import subprocess
from pydantic import BaseModel

static_ffmpeg.add_paths()

app = FastAPI()

@app.options("/{rest_of_path:path}")
async def preflight_handler(request: Request, rest_of_path: str):
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
    expose_headers=["*"],
)

class DownloadRequest(BaseModel):
    url: str
    cookies: str = ""

def cleanup(path: str):
    import shutil
    if os.path.exists(path):
        shutil.rmtree(path)

def get_base_opts():
    return {
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "retries": 10,
        "fragment_retries": 10,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["web", "android", "ios"],
            }
        },
    }

@app.post("/download-audio")
async def download_audio(request: DownloadRequest, background_tasks: BackgroundTasks):
    tmp_dir = tempfile.mkdtemp()
    unique_id = str(uuid.uuid4())
    output_template = os.path.join(tmp_dir, f"{unique_id}.%(ext)s")
    cookies_file = None
    try:
        if request.cookies and request.cookies.strip():
            cookies_file = os.path.join(tmp_dir, "cookies.txt")
            with open(cookies_file, "w") as f:
                f.write(request.cookies)

        ydl_opts = get_base_opts()
        ydl_opts.update({
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": output_template,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
        if cookies_file:
            ydl_opts["cookiefile"] = cookies_file

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([request.url])

        for f in os.listdir(tmp_dir):
            if f.endswith(".mp3"):
                file_path = os.path.join(tmp_dir, f)
                background_tasks.add_task(cleanup, tmp_dir)
                response = FileResponse(file_path, media_type="audio/mpeg", filename="audio.mp3")
                response.headers["Access-Control-Allow-Origin"] = "*"
                return response

        raise HTTPException(status_code=500, detail="Fisierul audio nu a fost gasit")
    except Exception as e:
        cleanup(tmp_dir)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/download-video")
async def download_video(request: DownloadRequest, background_tasks: BackgroundTasks):
    tmp_dir = tempfile.mkdtemp()
    unique_id = str(uuid.uuid4())
    output_template = os.path.join(tmp_dir, f"{unique_id}.%(ext)s")
    cookies_file = None
    try:
        if request.cookies and request.cookies.strip():
            cookies_file = os.path.join(tmp_dir, "cookies.txt")
            with open(cookies_file, "w") as f:
                f.write(request.cookies)

        ydl_opts = get_base_opts()
        ydl_opts.update({
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": output_template,
            "merge_output_format": "mp4",
        })
        if cookies_file:
            ydl_opts["cookiefile"] = cookies_file

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([request.url])

        for f in os.listdir(tmp_dir):
            if f.endswith(".mp4"):
                file_path = os.path.join(tmp_dir, f)
                background_tasks.add_task(cleanup, tmp_dir)
                response = FileResponse(file_path, media_type="video/mp4", filename="video.mp4")
                response.headers["Access-Control-Allow-Origin"] = "*"
                return response

        raise HTTPException(status_code=500, detail="Fisierul video nu a fost gasit")
    except Exception as e:
        cleanup(tmp_dir)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/blur-video")
async def blur_video(request: DownloadRequest, background_tasks: BackgroundTasks):
    tmp_dir = tempfile.mkdtemp()
    unique_id = str(uuid.uuid4())
    output_template = os.path.join(tmp_dir, f"{unique_id}.%(ext)s")
    cookies_file = None
    try:
        if request.cookies and request.cookies.strip():
            cookies_file = os.path.join(tmp_dir, "cookies.txt")
            with open(cookies_file, "w") as f:
                f.write(request.cookies)

        ydl_opts = get_base_opts()
        ydl_opts.update({
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": output_template,
            "merge_output_format": "mp4",
        })
        if cookies_file:
            ydl_opts["cookiefile"] = cookies_file

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([request.url])

        input_file = None
        for f in os.listdir(tmp_dir):
            if f.endswith(".mp4") and "blurred" not in f:
                input_file = os.path.join(tmp_dir, f)
                break

        if not input_file:
            raise HTTPException(status_code=500, detail="Video nu a fost gasit")

        output_file = os.path.join(tmp_dir, f"{unique_id}_blurred.mp4")

        ffmpeg_cmd = [
            "ffmpeg", "-i", input_file,
            "-vf", "split[original][copy];[copy]crop=iw:ih*0.15:0:ih*0.82,boxblur=25:3[blurred];[original][blurred]overlay=0:H*0.82",
            "-c:a", "copy",
            "-y", output_file
        ]
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)

        background_tasks.add_task(cleanup, tmp_dir)
        response = FileResponse(output_file, media_type="video/mp4", filename="video_blurred.mp4")
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    except subprocess.CalledProcessError as e:
        cleanup(tmp_dir)
        raise HTTPException(status_code=500, detail=f"FFmpeg error: {e.stderr.decode()}")
    except Exception as e:
        cleanup(tmp_dir)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok"}
