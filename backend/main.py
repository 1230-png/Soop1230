from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import os
import uuid
from datetime import datetime

from app.services.batch_generator import BatchGenerator
from app.services.mastering import MasteringEngine
from app.services.image_generator import ImageGenerator
from app.services.metadata_generator import MetadataGenerator
from app.services.audio_analyzer import AudioAnalyzer
from app.services.lyrics_generator import LyricsGenerator
from app.services.auto_complete import AutoCompleteService

app = FastAPI(title="감성힙합 생성 도구")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# 디렉토리 생성
os.makedirs("uploads", exist_ok=True)
os.makedirs("uploads/audio", exist_ok=True)
os.makedirs("uploads/images", exist_ok=True)
os.makedirs("uploads/batches", exist_ok=True)

# 서비스 초기화
batch_gen = BatchGenerator()
mastering = MasteringEngine()
image_gen = ImageGenerator()
metadata_gen = MetadataGenerator()
analyzer = AudioAnalyzer()
lyrics_gen = LyricsGenerator()
auto_complete = AutoCompleteService()


@app.get("/")
async def root():
    return {"message": "감성힙합 자동화 도구 API"}


@app.post("/api/batch/generate")
async def generate_batch(mood: str = "기본감성", count: int = 10):
    """배치 자동 생성"""
    try:
        batch_data = batch_gen.generate(mood=mood, count=count)
        batch_id = str(uuid.uuid4())[:8]

        # 배치 저장
        batch_path = f"uploads/batches/{batch_id}.json"
        import json
        with open(batch_path, 'w', encoding='utf-8') as f:
            json.dump({
                "batch_id": batch_id,
                "created_at": datetime.now().isoformat(),
                "mood": mood,
                "songs": batch_data
            }, f, ensure_ascii=False, indent=2)

        return {
            "batch_id": batch_id,
            "mood": mood,
            "songs": batch_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mastering/process")
async def process_mastering(file: UploadFile = File(...)):
    """마스터링 처리"""
    try:
        # 파일 저장
        file_id = str(uuid.uuid4())[:8]
        input_path = f"uploads/audio/{file_id}_input.wav"
        output_path = f"uploads/audio/{file_id}_mastered.wav"

        contents = await file.read()
        with open(input_path, 'wb') as f:
            f.write(contents)

        # 마스터링 처리
        mastering.process(input_path, output_path)

        return {
            "file_id": file_id,
            "status": "completed",
            "output_path": output_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/mastering/download/{file_id}")
async def download_mastered(file_id: str):
    """마스터링된 파일 다운로드"""
    output_path = f"uploads/audio/{file_id}_mastered.wav"
    if not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")

    return FileResponse(
        output_path,
        filename=f"mastered_{file_id}.wav",
        media_type="audio/wav"
    )


@app.post("/api/image/generate")
async def generate_cover(title: str, artist: str, mood: str = "감성"):
    """커버 이미지 생성"""
    try:
        image_id = str(uuid.uuid4())[:8]
        output_path = f"uploads/images/{image_id}.png"

        image_gen.generate(
            output_path=output_path,
            title=title,
            artist=artist,
            mood=mood
        )

        return {
            "image_id": image_id,
            "output_path": output_path,
            "title": title,
            "artist": artist
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/image/download/{image_id}")
async def download_image(image_id: str):
    """커버 이미지 다운로드"""
    image_path = f"uploads/images/{image_id}.png"
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다")

    return FileResponse(
        image_path,
        filename=f"cover_{image_id}.png",
        media_type="image/png"
    )


@app.post("/api/metadata/generate")
async def generate_metadata(title: str, mood: str, bpm: int = 90):
    """메타데이터 자동 생성"""
    try:
        metadata = metadata_gen.generate(title=title, mood=mood, bpm=bpm)
        return metadata
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analysis/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    """오디오 파일 분석 및 프리셋 추천 (Premium Feature 1)"""
    try:
        file_id = str(uuid.uuid4())[:8]
        temp_path = f"uploads/audio/{file_id}_temp.wav"

        contents = await file.read()
        with open(temp_path, 'wb') as f:
            f.write(contents)

        analysis = analyzer.analyze(temp_path)

        # 임시 파일 삭제
        if os.path.exists(temp_path):
            os.remove(temp_path)

        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/lyrics/generate")
async def generate_lyrics(request_body: dict):
    """AI 한국 가사 자동 생성 (Premium Feature 2)"""
    try:
        theme = request_body.get("theme", "")
        mood = request_body.get("mood", "감성")
        style = request_body.get("style", "랩")

        if not theme:
            raise HTTPException(status_code=400, detail="테마를 입력해주세요")

        lyrics = lyrics_gen.generate(theme=theme, mood=mood, style=style)
        return lyrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auto-complete")
async def auto_complete_song(request_body: dict = None):
    """원클릭 자동 완성 (Premium Feature 3)"""
    try:
        batch_id = None
        if request_body:
            batch_id = request_body.get("batch_id")

        result = auto_complete.complete(batch_id=batch_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
