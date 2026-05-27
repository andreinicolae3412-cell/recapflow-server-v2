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

        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": output_template,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "quiet": True,
            "no_warnings": True,
        }

        if cookies_file:
            ydl_opts["cookiefile"] = cookies_file

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([request.url])

        for f in os.listdir(tmp_dir):
            if f.endswith(".mp3"):
                file_path = os.path.join(tmp_dir, f)
                background_tasks.add_task(cleanup, tmp_dir)
                response = FileResponse(
                    file_path,
                    media_type="audio/mpeg",
                    filename="audio.mp3"
                )
                response.headers["Access-Control-Allow-Origin"] = "*"
                return response

        raise HTTPException(status_code=500, detail="Fișierul audio nu a fost găsit")

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

        ydl_opts = {
            "format": "bv[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",
            "outtmpl": output_template,
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
        }

        if cookies_file:
            ydl_opts["cookiefile"] = cookies_file

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([request.url])

        for f in os.listdir(tmp_dir):
            if f.endswith(".mp4"):
                file_path = os.path.join(tmp_dir, f)
                background_tasks.add_task(cleanup, tmp_dir)
                response = FileResponse(
                    file_path,
                    media_type="video/mp4",
                    filename="video.mp4"
                )
                response.headers["Access-Control-Allow-Origin"] = "*"
                return response

        raise HTTPException(status_code=500, detail="Fișierul video nu a fost găsit")

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

        ydl_opts = {
            "format": "bv[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",
            "outtmpl": output_template,
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
        }

        if cookies_file:
            ydl_opts["cookiefile"] = cookies_file

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([request.url])

        input_file = None
        for f in os.listdir(tmp_dir):
            if f.endswith(".mp4"):
                input_file = os.path.join(tmp_dir, f)
                break

        if not input_file:
            raise HTTPException(status_code=500, detail="Video nu a fost găsit")

        output_file = os.path.join(tmp_dir, f"{unique_id}_blurred.mp4")

        ffmpeg_cmd = [
            "ffmpeg", "-i", input_file,
            "-vf", "split[original][copy];[copy]crop=iw:ih*0.3:0:ih*0.7,boxblur=20:2[blurred];[original][blurred]overlay=0:H*0.7",
            "-c:a", "copy",
            "-y", output_file
        ]

        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)

        background_tasks.add_task(cleanup, tmp_dir)
        response = FileResponse(
            output_file,
            media_type="video/mp4",
            filename="video_blurred.mp4"
        )
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