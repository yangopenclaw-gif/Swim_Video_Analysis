from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from sqlalchemy import create_engine, Column, Integer, Float, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import json
import uuid
import shutil
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import List, Optional
import logging

from .swim_analyzer import SwimVideoAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_DIR = os.environ.get('STAGING_DIR', os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads"))
if os.environ.get('STAGING_MODE'):
    UPLOAD_DIR = os.path.join(os.environ['STAGING_DIR'], "uploads")
DATA_DIR = os.environ.get('STAGING_DIR', os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"))
if os.environ.get('STAGING_MODE'):
    DATA_DIR = os.path.join(os.environ['STAGING_DIR'], "data")
CHUNKS_DIR = os.path.join(UPLOAD_DIR, ".chunks")
AVATAR_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "avatars")
if os.environ.get('STAGING_MODE'):
    AVATAR_DIR = os.path.join(os.environ['STAGING_DIR'], "avatars")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CHUNKS_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "swim_analysis.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

CHUNK_SIZE = 512 * 1024



class AnalysisRecord(Base):
    __tablename__ = "analysis_records"
    id = Column(String, primary_key=True)
    swimmer_name = Column(String, nullable=False)
    pool_length = Column(Integer, nullable=False)
    race_distance = Column(Integer, nullable=False)
    stroke_type = Column(String, default="自由泳")
    swimmer_position = Column(Integer, default=1)
    video_filename = Column(String)
    analysis_options = Column(Text)
    analysis_result = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    archived = Column(Integer, default=0)
    archive_time = Column(DateTime, nullable=True)
    race_name = Column(String, nullable=True)
    race_date = Column(String, nullable=True)
    race_location = Column(String, nullable=True)
    video_deleted = Column(Integer, default=0)


class Video(Base):
    __tablename__ = "videos"
    id = Column(String, primary_key=True)
    file_name = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    athlete_name = Column(String, nullable=True)
    athlete_id = Column(String, nullable=True)
    competition_name = Column(String, nullable=True)
    competition_id = Column(String, nullable=True)
    upload_time = Column(DateTime, default=datetime.utcnow)
    file_size = Column(Integer, default=0)
    duration = Column(Float, default=0)
    linked_record_id = Column(String, nullable=True)


class VideoMarker(Base):
    __tablename__ = "video_markers"
    id = Column(String, primary_key=True)
    video_id = Column(String, nullable=False, index=True)
    time_seconds = Column(Float, nullable=False)
    label = Column(String, nullable=False)
    color = Column(String, default="#1a73e8")
    marker_key = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Competition(Base):
    __tablename__ = "competitions"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    date = Column(String, nullable=True)
    location = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SwimmerProfile(Base):
    __tablename__ = "swimmer_profiles"
    name = Column(String, primary_key=True)
    birth_date = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    avatar_url = Column(String, nullable=True)


Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    if not db.query(SwimmerProfile).filter(SwimmerProfile.name == "杨钧涵").first():
        db.add(SwimmerProfile(name="杨钧涵", birth_date="2013-06-12"))
    if not db.query(SwimmerProfile).filter(SwimmerProfile.name == "杨涴婷").first():
        db.add(SwimmerProfile(name="杨涴婷", birth_date=None))
    db.commit()
finally:
    db.close()

app = FastAPI(title="泳娃比赛记录平台", version="3.1.0")

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

analysis_tasks = {}
upload_sessions = {}


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "游泳比赛视频分析系统"}


@app.post("/api/upload/init")
async def init_upload(request: Request):
    body = await request.json()
    filename = body.get("filename", "")
    file_size = body.get("file_size", 0)
    swimmer_name = body.get("swimmer_name", "杨钧涵")
    pool_length = body.get("pool_length", 50)
    race_distance = body.get("race_distance", 100)
    swimmer_position = body.get("swimmer_position", 1)

    if not filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
        raise HTTPException(status_code=400, detail="不支持的视频格式")

    upload_id = str(uuid.uuid4())
    ext = os.path.splitext(filename)[1]

    upload_sessions[upload_id] = {
        "upload_id": upload_id,
        "filename": filename,
        "file_size": file_size,
        "ext": ext,
        "swimmer_name": swimmer_name,
        "pool_length": pool_length,
        "race_distance": race_distance,
        "swimmer_position": swimmer_position,
        "chunks_received": set(),
        "total_chunks": (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE if file_size > 0 else 0,
        "created_at": time.time(),
    }

    chunk_dir = os.path.join(CHUNKS_DIR, upload_id)
    os.makedirs(chunk_dir, exist_ok=True)

    logger.info(f"Upload initialized: {filename} ({file_size} bytes) -> {upload_id}")
    return {
        "upload_id": upload_id,
        "chunk_size": CHUNK_SIZE,
        "total_chunks": upload_sessions[upload_id]["total_chunks"],
    }


@app.post("/api/upload/probe")
async def upload_probe(request: Request):
    body = await request.body()
    return {"status": "ok", "echo_len": len(body), "timestamp": time.time()}


@app.post("/api/upload/chunk")
async def upload_chunk(request: Request):
    upload_id = request.query_params.get("upload_id", "")
    chunk_index = int(request.query_params.get("chunk_index", "0"))
    content_type = request.headers.get("content-type", "")

    if upload_id not in upload_sessions:
        raise HTTPException(status_code=404, detail="上传会话不存在")

    session = upload_sessions[upload_id]
    chunk_dir = os.path.join(CHUNKS_DIR, upload_id)
    chunk_path = os.path.join(chunk_dir, f"chunk_{chunk_index}")

    chunk_data = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        file_field = form.get("chunk")
        if file_field is None:
            return JSONResponse(status_code=400, content={"detail": "multipart中缺少chunk字段"})
        chunk_data = await file_field.read()
    elif "application/json" in content_type:
        try:
            json_body = await request.json()
            import base64
            b64_data = json_body.get("data", "")
            if not b64_data:
                return JSONResponse(status_code=400, content={"detail": "JSON中缺少data字段"})
            chunk_data = base64.b64decode(b64_data)
        except Exception as e:
            return JSONResponse(status_code=400, content={"detail": f"Base64解码失败: {str(e)}"})
    else:
        chunk_data = await request.body()

    if chunk_data is None or len(chunk_data) == 0:
        return JSONResponse(status_code=400, content={"detail": "空分片"})
    if len(chunk_data) > CHUNK_SIZE * 4:
        return JSONResponse(status_code=413, content={"detail": f"分片过大: {len(chunk_data)} bytes"})

    with open(chunk_path, "wb") as f:
        f.write(chunk_data)

    session["chunks_received"].add(chunk_index)
    received = len(session["chunks_received"])
    total = session["total_chunks"]
    progress = round(received / total * 100, 1) if total > 0 else 0

    logger.info(f"Chunk {chunk_index} saved for {upload_id}: {len(chunk_data)} bytes ({content_type[:30]}), {received}/{total} ({progress}%)")

    return {
        "upload_id": upload_id,
        "chunk_index": chunk_index,
        "received_chunks": received,
        "total_chunks": total,
        "progress": progress,
    }


@app.get("/api/upload/status/{upload_id}")
def get_upload_status(upload_id: str):
    if upload_id not in upload_sessions:
        raise HTTPException(status_code=404, detail="上传会话不存在")

    session = upload_sessions[upload_id]
    received = len(session["chunks_received"])
    total = session["total_chunks"]
    progress = round(received / total * 100, 1) if total > 0 else 0

    missing = [i for i in range(total) if i not in session["chunks_received"]]
    return {
        "upload_id": upload_id,
        "received_chunks": received,
        "total_chunks": total,
        "progress": progress,
        "missing_chunks": missing,
        "filename": session["filename"],
    }


@app.post("/api/upload/complete")
async def complete_upload(request: Request):
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    upload_id = body.get("upload_id", "") or request.query_params.get("upload_id", "")

    if upload_id not in upload_sessions:
        raise HTTPException(status_code=404, detail="上传会话不存在")

    session = upload_sessions[upload_id]
    total = session["total_chunks"]

    missing = [i for i in range(total) if i not in session["chunks_received"]]
    if missing:
        return {"status": "incomplete", "missing_chunks": missing, "message": f"还有 {len(missing)} 个分片未上传"}

    task_id = upload_id
    ext = session["ext"]
    final_path = os.path.join(UPLOAD_DIR, f"{task_id}{ext}")
    chunk_dir = os.path.join(CHUNKS_DIR, upload_id)

    def _merge_chunks():
        with open(final_path, "wb") as out_f:
            for i in range(total):
                chunk_path = os.path.join(chunk_dir, f"chunk_{i}")
                if os.path.exists(chunk_path):
                    with open(chunk_path, "rb") as in_f:
                        shutil.copyfileobj(in_f, out_f, length=1024 * 1024)
        shutil.rmtree(chunk_dir, ignore_errors=True)

    await asyncio.get_event_loop().run_in_executor(None, _merge_chunks)

    file_size = os.path.getsize(final_path) if os.path.exists(final_path) else 0
    db = SessionLocal()
    try:
        video = Video(
            id=task_id,
            file_name=session["filename"],
            display_name=session["filename"],
            file_size=file_size,
        )
        db.add(video)
        db.commit()
    finally:
        db.close()

    analysis_tasks[task_id] = {
        "status": "uploaded",
        "video_path": final_path,
        "swimmer_name": session["swimmer_name"],
        "pool_length": session["pool_length"],
        "race_distance": session["race_distance"],
        "swimmer_position": session.get("swimmer_position", 1),
        "filename": session["filename"],
        "progress": 0,
        "progress_message": "",
    }

    del upload_sessions[upload_id]
    logger.info(f"Upload completed: {session['filename']} -> {task_id}")
    return {"task_id": task_id, "video_id": task_id, "status": "uploaded", "filename": session["filename"]}


@app.post("/api/upload/cancel")
async def cancel_upload(request: Request):
    body = await request.json()
    upload_id = body.get("upload_id", "")
    if upload_id in upload_sessions:
        chunk_dir = os.path.join(CHUNKS_DIR, upload_id)
        shutil.rmtree(chunk_dir, ignore_errors=True)
        del upload_sessions[upload_id]
        return {"status": "cancelled"}
    return {"status": "not_found"}


def _run_analysis(task_id: str, analysis_options: List[str]):
    task = analysis_tasks[task_id]
    try:
        from backend.analysis_v2.pipeline import AnalysisPipeline
        pipeline = AnalysisPipeline(
            pool_length=task["pool_length"],
            race_distance=task["race_distance"],
            swimmer_position=task.get("swimmer_position", 1),
            progress_callback=lambda pct, msg: task.update({"progress": pct, "progress_message": msg}),
        )
        result = pipeline.analyze(task["video_path"], analysis_options)
        task["status"] = "completed"
        task["result"] = result
        task["progress"] = 100
        task["progress_message"] = "分析完成"

        db = SessionLocal()
        try:
            existing = db.query(AnalysisRecord).filter(AnalysisRecord.id == task_id).first()
            if existing:
                db.delete(existing)
                db.flush()
            record = AnalysisRecord(
                id=task_id,
                swimmer_name=task["swimmer_name"],
                pool_length=task["pool_length"],
                race_distance=task["race_distance"],
                swimmer_position=task.get("swimmer_position", 1),
                video_filename=task["filename"],
                analysis_options=json.dumps(analysis_options, ensure_ascii=False),
                analysis_result=json.dumps(result, ensure_ascii=False),
            )
            db.add(record)
            db.commit()
        finally:
            db.close()

        logger.info(f"Analysis completed for task {task_id}")
    except Exception as e:
        task["status"] = "failed"
        task["error"] = str(e)
        task["progress"] = 0
        task["progress_message"] = f"分析失败: {str(e)}"
        logger.error(f"Analysis failed for task {task_id}: {e}")


@app.post("/api/analyze/{task_id}")
async def analyze_video(task_id: str, analysis_options: List[str] = []):
    if task_id not in analysis_tasks:
        db = SessionLocal()
        try:
            record = db.query(AnalysisRecord).filter(AnalysisRecord.id == task_id).first()
            if record and record.analysis_result:
                return {"task_id": task_id, "status": "completed", "result": json.loads(record.analysis_result)}
        finally:
            db.close()

        video_path = None
        for ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
            path = os.path.join(UPLOAD_DIR, f"{task_id}{ext}")
            if os.path.exists(path):
                video_path = path
                break

        if video_path:
            analysis_tasks[task_id] = {
                "status": "uploaded",
                "video_path": video_path,
                "swimmer_name": "",
                "pool_length": 50,
                "race_distance": 100,
                "swimmer_position": 1,
                "filename": os.path.basename(video_path),
                "progress": 0,
                "progress_message": "",
            }
            logger.info(f"Video found in uploads, created analysis task: {task_id}")
        else:
            raise HTTPException(status_code=404, detail="任务不存在")

    task = analysis_tasks[task_id]
    if task["status"] not in ("uploaded",):
        if task["status"] == "analyzing":
            return {"task_id": task_id, "status": "analyzing", "progress": task.get("progress", 0), "message": task.get("progress_message", "")}
        if task["status"] == "completed":
            return {"task_id": task_id, "status": "completed", "result": task.get("result")}
        raise HTTPException(status_code=400, detail="任务状态不正确，无法分析")

    task["status"] = "analyzing"
    task["analysis_options"] = analysis_options
    task["progress"] = 0
    task["progress_message"] = "正在启动分析..."

    thread = threading.Thread(target=_run_analysis, args=(task_id, analysis_options), daemon=True)
    thread.start()

    return {"task_id": task_id, "status": "analyzing", "progress": 0, "message": "正在启动分析..."}


@app.post("/api/analyze_existing/{task_id}")
async def analyze_existing_video(task_id: str, request: Request):
    body = await request.json()
    analysis_options = body.get("analysis_options", [])
    swimmer_name = body.get("swimmer_name", "")
    pool_length = body.get("pool_length", 50)
    race_distance = body.get("race_distance", 100)
    swimmer_position = body.get("swimmer_position", 1)

    if task_id in analysis_tasks and analysis_tasks[task_id]["status"] == "analyzing":
        return {"task_id": task_id, "status": "analyzing", "progress": analysis_tasks[task_id].get("progress", 0), "message": analysis_tasks[task_id].get("progress_message", "")}

    video_path = None
    for ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
        path = os.path.join(UPLOAD_DIR, f"{task_id}{ext}")
        if os.path.exists(path):
            video_path = path
            break

    if not video_path:
        raise HTTPException(status_code=404, detail="视频文件不存在")

    db = SessionLocal()
    try:
        record = db.query(AnalysisRecord).filter(AnalysisRecord.id == task_id).first()
        if record:
            record.analysis_result = None
            record.analysis_options = None
            record.swimmer_name = swimmer_name or record.swimmer_name
            record.pool_length = pool_length or record.pool_length
            record.race_distance = race_distance or record.race_distance
            record.swimmer_position = swimmer_position or record.swimmer_position
            db.commit()
    finally:
        db.close()

    analysis_tasks[task_id] = {
        "status": "uploaded",
        "video_path": video_path,
        "swimmer_name": swimmer_name,
        "pool_length": pool_length,
        "race_distance": race_distance,
        "swimmer_position": swimmer_position,
        "filename": os.path.basename(video_path),
        "progress": 0,
        "progress_message": "",
    }

    task = analysis_tasks[task_id]
    task["status"] = "analyzing"
    task["analysis_options"] = analysis_options
    task["progress"] = 0
    task["progress_message"] = "正在启动分析..."

    thread = threading.Thread(target=_run_analysis, args=(task_id, analysis_options), daemon=True)
    thread.start()

    return {"task_id": task_id, "status": "analyzing", "progress": 0, "message": "正在启动分析..."}


@app.get("/api/analyze/progress/{task_id}")
def get_analysis_progress(task_id: str):
    if task_id not in analysis_tasks:
        db = SessionLocal()
        try:
            record = db.query(AnalysisRecord).filter(AnalysisRecord.id == task_id).first()
            if record:
                return {"task_id": task_id, "status": "completed", "progress": 100, "message": "分析完成", "result": json.loads(record.analysis_result)}
        finally:
            db.close()
        raise HTTPException(status_code=404, detail="任务不存在")

    task = analysis_tasks[task_id]
    resp = {
        "task_id": task_id,
        "status": task["status"],
        "progress": task.get("progress", 0),
        "message": task.get("progress_message", ""),
    }
    if task["status"] == "completed":
        resp["result"] = task.get("result")
    elif task["status"] == "failed":
        resp["error"] = task.get("error")
    return resp


@app.get("/api/result/{task_id}")
def get_result(task_id: str):
    if task_id not in analysis_tasks:
        db = SessionLocal()
        try:
            record = db.query(AnalysisRecord).filter(AnalysisRecord.id == task_id).first()
            if record:
                return {
                    "task_id": task_id, "status": "completed",
                    "result": json.loads(record.analysis_result),
                    "swimmer_name": record.swimmer_name,
                    "pool_length": record.pool_length,
                    "race_distance": record.race_distance,
                }
        finally:
            db.close()
        raise HTTPException(status_code=404, detail="任务不存在")

    task = analysis_tasks[task_id]
    return {
        "task_id": task_id, "status": task["status"],
        "result": task.get("result"), "error": task.get("error"),
        "swimmer_name": task.get("swimmer_name"),
        "pool_length": task.get("pool_length"),
        "race_distance": task.get("race_distance"),
    }


@app.post("/api/archive/{task_id}")
def archive_analysis(task_id: str, race_name: str = "", race_date: str = "", race_location: str = ""):
    db = SessionLocal()
    try:
        record = db.query(AnalysisRecord).filter(AnalysisRecord.id == task_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="记录不存在")
        record.archived = 1
        record.archive_time = datetime.utcnow()
        record.race_name = race_name
        record.race_date = race_date
        record.race_location = race_location
        db.commit()
        return {"status": "ok", "message": "归档成功"}
    finally:
        db.close()


@app.get("/api/swimmer_profile/{name}")
def get_swimmer_profile(name: str):
    db = SessionLocal()
    try:
        profile = db.query(SwimmerProfile).filter(SwimmerProfile.name == name).first()
        if not profile:
            return {"name": name, "birth_date": None, "gender": None, "notes": None, "avatar_url": None}
        return {"name": profile.name, "birth_date": profile.birth_date, "gender": profile.gender, "notes": profile.notes, "avatar_url": profile.avatar_url}
    finally:
        db.close()


@app.put("/api/swimmer_profile/{name}")
async def update_swimmer_profile(name: str, request: Request):
    body = await request.json()
    db = SessionLocal()
    try:
        profile = db.query(SwimmerProfile).filter(SwimmerProfile.name == name).first()
        if not profile:
            profile = SwimmerProfile(name=name)
            db.add(profile)
        if "birth_date" in body:
            profile.birth_date = body["birth_date"]
        if "gender" in body:
            profile.gender = body["gender"]
        if "notes" in body:
            profile.notes = body["notes"]
        if "avatar_url" in body:
            profile.avatar_url = body["avatar_url"]
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


@app.post("/api/upload_avatar/{name}")
async def upload_avatar(name: str, file: UploadFile = File(...)):
    avatars_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "avatars")
    os.makedirs(avatars_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or ".jpg")[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
        ext = ".jpg"
    filename = f"{name}{ext}"
    filepath = os.path.join(avatars_dir, filename)
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)
    avatar_url = f"/avatars/{filename}"
    db = SessionLocal()
    try:
        profile = db.query(SwimmerProfile).filter(SwimmerProfile.name == name).first()
        if not profile:
            profile = SwimmerProfile(name=name)
            db.add(profile)
        profile.avatar_url = avatar_url
        db.commit()
    finally:
        db.close()
    return {"status": "ok", "avatar_url": avatar_url}


@app.get("/avatars/{filename}")
def get_avatar(filename: str):
    avatars_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "avatars")
    filepath = os.path.join(avatars_dir, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="头像不存在")
    try:
        return FileResponse(filepath)
    except Exception as e:
        logger.error(f"Avatar serve error: {e}, path: {filepath}")
        raise HTTPException(status_code=500, detail=f"头像读取失败: {str(e)}")


@app.get("/api/records/{swimmer_name}")
def get_records(swimmer_name: str):
    db = SessionLocal()
    try:
        records = db.query(AnalysisRecord).filter(
            AnalysisRecord.swimmer_name == swimmer_name,
            AnalysisRecord.archived == 1,
        ).order_by(AnalysisRecord.archive_time.desc(), AnalysisRecord.created_at.desc()).all()
        result = []
        for r in records:
            linked_video_id = None
            if r.video_filename:
                vid = db.query(Video).filter(Video.id == r.video_filename).first()
                if vid:
                    linked_video_id = vid.id
            if not linked_video_id:
                vid = db.query(Video).filter(Video.linked_record_id == r.id).first()
                if vid:
                    linked_video_id = vid.id
            result.append({
                "id": r.id, "swimmer_name": r.swimmer_name,
                "pool_length": r.pool_length, "race_distance": r.race_distance,
                "stroke_type": r.stroke_type, "swimmer_position": r.swimmer_position,
                "analysis_result": json.loads(r.analysis_result) if r.analysis_result else {},
                "race_name": r.race_name, "race_date": r.race_date,
                "race_location": r.race_location,
                "archive_time": r.archive_time.isoformat() if r.archive_time else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "linked_video_id": linked_video_id,
            })
        return result
    finally:
        db.close()


@app.get("/api/compare")
def compare_records(id1: str, id2: str):
    db = SessionLocal()
    try:
        r1 = db.query(AnalysisRecord).filter(AnalysisRecord.id == id1).first()
        r2 = db.query(AnalysisRecord).filter(AnalysisRecord.id == id2).first()
        if not r1 or not r2:
            raise HTTPException(status_code=404, detail="记录不存在")
        return {
            "record1": {
                "id": r1.id, "swimmer_name": r1.swimmer_name,
                "pool_length": r1.pool_length, "race_distance": r1.race_distance,
                "race_name": r1.race_name, "race_date": r1.race_date,
                "analysis_result": json.loads(r1.analysis_result) if r1.analysis_result else {},
            },
            "record2": {
                "id": r2.id, "swimmer_name": r2.swimmer_name,
                "pool_length": r2.pool_length, "race_distance": r2.race_distance,
                "race_name": r2.race_name, "race_date": r2.race_date,
                "analysis_result": json.loads(r2.analysis_result) if r2.analysis_result else {},
            },
        }
    finally:
        db.close()


@app.get("/api/all_records")
def get_all_records():
    db = SessionLocal()
    try:
        records = db.query(AnalysisRecord).filter(
            AnalysisRecord.archived == 1,
        ).order_by(AnalysisRecord.archive_time.desc(), AnalysisRecord.created_at.desc()).all()
        result = []
        for r in records:
            linked_video_id = None
            if r.video_filename:
                vid = db.query(Video).filter(Video.id == r.video_filename).first()
                if vid:
                    linked_video_id = vid.id
            if not linked_video_id:
                vid = db.query(Video).filter(Video.linked_record_id == r.id).first()
                if vid:
                    linked_video_id = vid.id
            result.append({
                "id": r.id, "swimmer_name": r.swimmer_name,
                "pool_length": r.pool_length, "race_distance": r.race_distance,
                "stroke_type": r.stroke_type, "swimmer_position": r.swimmer_position,
                "analysis_result": json.loads(r.analysis_result) if r.analysis_result else {},
                "race_name": r.race_name, "race_date": r.race_date,
                "race_location": r.race_location,
                "archive_time": r.archive_time.isoformat() if r.archive_time else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "linked_video_id": linked_video_id,
            })
        return result
    finally:
        db.close()


@app.get("/api/competitions")
def list_competitions():
    db = SessionLocal()
    try:
        comps = db.query(Competition).order_by(Competition.created_at.desc()).all()
        return [{"id": c.id, "name": c.name, "date": c.date, "location": c.location} for c in comps]
    finally:
        db.close()


@app.post("/api/competitions")
async def create_competition(request: Request):
    body = await request.json()
    name = body.get("name", "")
    if not name:
        raise HTTPException(status_code=400, detail="比赛名称不能为空")
    date = body.get("date", "")
    location = body.get("location", "")
    comp_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        comp = Competition(id=comp_id, name=name, date=date, location=location)
        db.add(comp)
        db.commit()
        return {"id": comp_id, "name": name, "date": date, "location": location}
    finally:
        db.close()


@app.delete("/api/competitions/{comp_id}")
def delete_competition(comp_id: str):
    db = SessionLocal()
    try:
        comp = db.query(Competition).filter(Competition.id == comp_id).first()
        if not comp:
            raise HTTPException(status_code=404, detail="比赛不存在")
        db.delete(comp)
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


@app.post("/api/check_duplicate_record")
async def check_duplicate_record(request: Request):
    body = await request.json()
    swimmer_name = body.get("swimmer_name", "")
    stroke_type = body.get("stroke_type", "自由泳")
    race_distance = int(body.get("race_distance", 100))
    competition_id = body.get("competition_id")
    db = SessionLocal()
    try:
        q = db.query(AnalysisRecord).filter(
            AnalysisRecord.swimmer_name == swimmer_name,
            AnalysisRecord.stroke_type == stroke_type,
            AnalysisRecord.race_distance == race_distance,
            AnalysisRecord.archived == 1,
        )
        if competition_id:
            comp = db.query(Competition).filter(Competition.id == competition_id).first()
            if comp:
                q = q.filter(AnalysisRecord.race_name == comp.name)
        records = q.all()
        if records:
            r = records[0]
            return {"duplicate": True, "record_id": r.id, "swimmer_name": r.swimmer_name, "race_name": r.race_name, "stroke_type": r.stroke_type, "race_distance": r.race_distance}
        return {"duplicate": False}
    finally:
        db.close()


@app.post("/api/manual_record")
async def create_manual_record(request: Request):
    body = await request.json()
    swimmer_name = body.get("swimmer_name", "")
    pool_length = int(body.get("pool_length", 50))
    race_distance = int(body.get("race_distance", 100))
    stroke_type = body.get("stroke_type", "自由泳")
    competition_id = body.get("competition_id")
    race_name = body.get("race_name", "")
    race_date = body.get("race_date", "")
    race_location = body.get("race_location", "")
    metrics = body.get("metrics", {})
    linked_video_id = body.get("linked_video_id")

    if competition_id:
        db_tmp = SessionLocal()
        try:
            comp = db_tmp.query(Competition).filter(Competition.id == competition_id).first()
            if comp:
                race_name = comp.name
                race_date = comp.date or ""
                race_location = comp.location or ""
        finally:
            db_tmp.close()

    record_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        record = AnalysisRecord(
            id=record_id,
            swimmer_name=swimmer_name,
            pool_length=pool_length,
            race_distance=race_distance,
            stroke_type=stroke_type,
            analysis_result=json.dumps(metrics, ensure_ascii=False),
            archived=1,
            archive_time=datetime.utcnow(),
            race_name=race_name or None,
            race_date=race_date or None,
            race_location=race_location or None,
            video_filename=linked_video_id or None,
        )
        db.add(record)
        if linked_video_id:
            video = db.query(Video).filter(Video.id == linked_video_id).first()
            if video:
                video.linked_record_id = record_id
        db.commit()
        return {"status": "ok", "id": record_id}
    finally:
        db.close()


RECORD_PASSWORD = "ycz"


@app.put("/api/records/{record_id}")
async def update_record(record_id: str, request: Request):
    body = await request.json()
    password = body.get("password", "")
    if password != RECORD_PASSWORD:
        raise HTTPException(status_code=403, detail="密码错误")
    db = SessionLocal()
    try:
        record = db.query(AnalysisRecord).filter(AnalysisRecord.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="记录不存在")
        if "swimmer_name" in body:
            record.swimmer_name = body["swimmer_name"]
        if "pool_length" in body:
            record.pool_length = body["pool_length"]
        if "race_distance" in body:
            record.race_distance = body["race_distance"]
        if "stroke_type" in body:
            record.stroke_type = body["stroke_type"]
        if "metrics" in body:
            record.analysis_result = json.dumps(body["metrics"], ensure_ascii=False)
        if "competition_id" in body:
            competition_id = body["competition_id"]
            if competition_id:
                comp = db.query(Competition).filter(Competition.id == competition_id).first()
                if comp:
                    record.race_name = comp.name
                    record.race_date = comp.date
                    record.race_location = comp.location
        if "race_date" in body:
            record.race_date = body["race_date"]
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


@app.delete("/api/records/{task_id}")
async def delete_record(task_id: str, request: Request):
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    password = body.get("password", "")
    if password != RECORD_PASSWORD:
        raise HTTPException(status_code=403, detail="密码错误")
    db = SessionLocal()
    try:
        record = db.query(AnalysisRecord).filter(AnalysisRecord.id == task_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="记录不存在")
        for ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
            path = os.path.join(UPLOAD_DIR, f"{task_id}{ext}")
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"Deleted video: {path}")
        db.delete(record)
        db.commit()
        if task_id in analysis_tasks:
            del analysis_tasks[task_id]
        return {"status": "ok", "message": "删除成功"}
    finally:
        db.close()


@app.get("/api/videos")
def list_videos():
    result = []
    for fname in sorted(os.listdir(UPLOAD_DIR)):
        if fname.startswith('.'):
            continue
        fpath = os.path.join(UPLOAD_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        task_id = os.path.splitext(fname)[0]
        fsize = os.path.getsize(fpath)
        mtime = os.path.getmtime(fpath)
        info = {
            "id": task_id,
            "filename": fname,
            "file_size": fsize,
            "upload_time": datetime.fromtimestamp(mtime).isoformat(),
            "has_analysis": False,
            "swimmer_name": None,
            "pool_length": None,
            "race_distance": None,
            "stroke_type": None,
            "swimmer_position": None,
            "archived": False,
            "race_name": None,
        }
        db = SessionLocal()
        try:
            record = db.query(AnalysisRecord).filter(AnalysisRecord.id == task_id).first()
            if record:
                info["has_analysis"] = True
                info["swimmer_name"] = record.swimmer_name
                info["pool_length"] = record.pool_length
                info["race_distance"] = record.race_distance
                info["stroke_type"] = record.stroke_type
                info["swimmer_position"] = record.swimmer_position
                info["archived"] = record.archived == 1
                info["race_name"] = record.race_name
        finally:
            db.close()
        result.append(info)
    return result


@app.delete("/api/videos/{task_id}")
def delete_video(task_id: str):
    deleted = False
    for ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
        path = os.path.join(UPLOAD_DIR, f"{task_id}{ext}")
        if os.path.exists(path):
            os.remove(path)
            deleted = True
            logger.info(f"Deleted video: {path}")

    db = SessionLocal()
    try:
        record = db.query(AnalysisRecord).filter(AnalysisRecord.id == task_id).first()
        if record:
            db.delete(record)
            db.commit()
    finally:
        db.close()

    if task_id in analysis_tasks:
        del analysis_tasks[task_id]

    if deleted:
        return {"status": "ok", "message": "视频已删除"}
    raise HTTPException(status_code=404, detail="视频不存在")


@app.get("/api/videos/{video_id}/stream")
def stream_video(video_id: str, request: Request):
    video_path = None
    for ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
        path = os.path.join(UPLOAD_DIR, f"{video_id}{ext}")
        if os.path.exists(path):
            video_path = path
            break
    if not video_path:
        raise HTTPException(status_code=404, detail="视频不存在")
    file_size = os.path.getsize(video_path)
    mtime = os.path.getmtime(video_path)
    etag = f'"{video_id}-{int(mtime)}"'
    content_type = "video/mp4"
    if video_path.endswith('.webm'):
        content_type = "video/webm"
    elif video_path.endswith('.avi'):
        content_type = "video/x-msvideo"
    cache_headers = {
        "Cache-Control": "public, max-age=31536000, immutable",
        "ETag": etag,
        "Vary": "Accept-Encoding",
    }
    if_none_match = request.headers.get("if-none-match")
    if if_none_match and if_none_match == etag:
        return Response(status_code=304, headers=cache_headers)
    range_header = request.headers.get("range")
    if range_header:
        byte_start = 0
        byte_end = file_size - 1
        match = __import__('re').match(r'bytes=(\d+)-(\d*)', range_header)
        if match:
            byte_start = int(match.group(1))
            if match.group(2):
                byte_end = int(match.group(2))
        content_length = byte_end - byte_start + 1
        with open(video_path, "rb") as f:
            f.seek(byte_start)
            data = f.read(content_length)
        return Response(
            content=data,
            status_code=206,
            media_type=content_type,
            headers={
                "Content-Range": f"bytes {byte_start}-{byte_end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                **cache_headers,
            },
        )
    with open(video_path, "rb") as f:
        data = f.read()
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            **cache_headers,
        },
    )


@app.post("/api/videos/upload")
async def upload_video_simple(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
        raise HTTPException(status_code=400, detail="不支持的视频格式")
    video_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    file_path = os.path.join(UPLOAD_DIR, f"{video_id}{ext}")
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    db = SessionLocal()
    try:
        video = Video(
            id=video_id,
            file_name=file.filename,
            display_name=file.filename,
            file_size=len(content),
        )
        db.add(video)
        db.commit()
    finally:
        db.close()
    return {"id": video_id, "file_name": file.filename, "status": "ok"}


@app.put("/api/videos/{video_id}")
async def update_video(video_id: str, request: Request):
    body = await request.json()
    password = body.get("password", "")
    if password != RECORD_PASSWORD:
        raise HTTPException(status_code=403, detail="密码错误")
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="视频不存在")
        if "display_name" in body:
            video.display_name = body["display_name"]
        if "athlete_name" in body:
            video.athlete_name = body["athlete_name"]
        if "athlete_id" in body:
            video.athlete_id = body["athlete_id"]
        if "competition_name" in body:
            video.competition_name = body["competition_name"]
        if "competition_id" in body:
            video.competition_id = body["competition_id"]
        if "linked_record_id" in body:
            video.linked_record_id = body["linked_record_id"]
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()



@app.get("/api/videos/{video_id}/linked_record")
def get_video_linked_record(video_id: str):
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if video and video.linked_record_id:
            return {"record_id": video.linked_record_id}
        record = db.query(AnalysisRecord).filter(AnalysisRecord.video_filename == video_id).first()
        if record:
            if video:
                video.linked_record_id = record.id
                db.commit()
            return {"record_id": record.id}
        return {"record_id": None}
    finally:
        db.close()


@app.get("/api/videos/{video_id}/markers")
def get_video_markers(video_id: str):
    db = SessionLocal()
    try:
        markers = db.query(VideoMarker).filter(VideoMarker.video_id == video_id).order_by(VideoMarker.time_seconds).all()
        return [{"id": m.id, "time_seconds": m.time_seconds, "label": m.label, "color": m.color, "marker_key": m.marker_key, "created_at": m.created_at.isoformat() if m.created_at else None} for m in markers]
    finally:
        db.close()


@app.post("/api/videos/{video_id}/markers")
async def add_video_marker(video_id: str, request: Request):
    body = await request.json()
    time_seconds = body.get("time_seconds")
    label = body.get("label", "")
    color = body.get("color", "#1a73e8")
    marker_key = body.get("marker_key")
    if time_seconds is None:
        raise HTTPException(status_code=400, detail="缺少time_seconds")
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="视频不存在")
        marker = VideoMarker(
            id=str(uuid.uuid4()),
            video_id=video_id,
            time_seconds=time_seconds,
            label=label,
            color=color,
            marker_key=marker_key,
        )
        db.add(marker)
        db.commit()
        return {"id": marker.id, "time_seconds": time_seconds, "label": label, "color": color, "marker_key": marker_key}
    finally:
        db.close()


@app.delete("/api/videos/{video_id}/markers/{marker_id}")
def delete_video_marker(video_id: str, marker_id: str):
    db = SessionLocal()
    try:
        marker = db.query(VideoMarker).filter(VideoMarker.id == marker_id, VideoMarker.video_id == video_id).first()
        if not marker:
            raise HTTPException(status_code=404, detail="标记不存在")
        db.delete(marker)
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


@app.post("/api/videos/{video_id}/detect_start_signal")
async def detect_start_signal(video_id: str):
    video_path = None
    for ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
        path = os.path.join(UPLOAD_DIR, f"{video_id}{ext}")
        if os.path.exists(path):
            video_path = path
            break
    if not video_path:
        raise HTTPException(status_code=404, detail="视频文件不存在")

    def _detect():
        import subprocess
        import numpy as np
        cmd = ['ffmpeg', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '1', '-f', 'wav', '-']
        proc = subprocess.run(cmd, capture_output=True, timeout=30)
        if proc.returncode != 0:
            return None
        audio = np.frombuffer(proc.stdout[44:], dtype=np.int16).astype(np.float64) / 32768.0
        sr = 44100
        if len(audio) < sr:
            return None

        window = int(sr * 0.01)
        envelope = np.sqrt(np.convolve(audio ** 2, np.ones(window) / window, mode='same'))

        global_p95 = np.percentile(envelope, 95)
        threshold = global_p95 * 0.5

        search_start = int(sr * 0.5)
        search_end = min(len(envelope), int(sr * 10))

        first_above = None
        for i in range(search_start, search_end):
            if envelope[i] > threshold:
                local_max = 0
                check_end = min(i + int(sr * 0.1), search_end)
                for j in range(i, check_end):
                    if envelope[j] > local_max:
                        local_max = envelope[j]
                if local_max > global_p95 * 0.8:
                    first_above = i
                    break

        if first_above is None:
            return None

        onset_idx = first_above
        pre_window = int(sr * 0.05)
        onset_threshold = envelope[max(0, first_above - pre_window)] * 2
        for i in range(first_above, max(first_above - pre_window, 0), -1):
            if envelope[i] < onset_threshold:
                onset_idx = i
                break

        peak_start = first_above
        peak_end = min(first_above + int(sr * 0.05), len(envelope))
        peak_idx = np.argmax(envelope[peak_start:peak_end]) + peak_start

        onset_time = onset_idx / sr
        peak_time = peak_idx / sr
        return {"onset_time": round(onset_time, 4), "peak_time": round(peak_time, 4), "frame": int(onset_time * 30)}

    import asyncio
    result = await asyncio.get_event_loop().run_in_executor(None, _detect)
    if result is None:
        raise HTTPException(status_code=404, detail="未检测到发令声，请手动标注")
    return result


@app.post("/api/videos/{video_id}/calculate_from_markers")
async def calculate_from_markers(video_id: str, request: Request):
    body = await request.json()
    markers = body.get("markers", {})
    race_distance = int(body.get("race_distance", 100))

    start_signal = markers.get("start_signal")
    dive_complete = markers.get("dive_complete")
    half_touch = markers.get("half_touch")
    turn_emerge = markers.get("turn_emerge")
    finish_touch = markers.get("finish_touch")

    metrics = {}
    warnings = []

    if start_signal is not None and half_touch is not None:
        metrics["前程用时"] = round(half_touch - start_signal, 3)

    if half_touch is not None and turn_emerge is not None:
        metrics["转身出水用时"] = round(turn_emerge - half_touch, 3)

    if half_touch is not None and finish_touch is not None:
        metrics["后程用时"] = round(finish_touch - half_touch, 3)

    if start_signal is not None and finish_touch is not None:
        metrics["比赛总用时"] = round(finish_touch - start_signal, 3)

    num_halves = max(1, race_distance // 50)
    if start_signal is not None and half_touch is not None:
        metrics["第1半程用时"] = round(half_touch - start_signal, 3)
    if num_halves >= 2 and half_touch is not None and finish_touch is not None:
        metrics["第2半程用时"] = round(finish_touch - half_touch, 3)
    for i in range(3, num_halves + 1):
        pass

    if start_signal is None:
        warnings.append("缺少「发令响」标注")
    if half_touch is None:
        warnings.append("缺少「半程触壁」标注")
    if turn_emerge is None:
        warnings.append("缺少「转身出水点」标注")
    if finish_touch is None:
        warnings.append("缺少「全程触壁」标注")

    return {"metrics": metrics, "warnings": warnings}


@app.post("/api/videos/{video_id}/save_marker_result")
async def save_marker_result(video_id: str, request: Request):
    body = await request.json()
    metrics = body.get("metrics", {})
    markers = body.get("markers", {})
    swimmer_name = body.get("swimmer_name", "")
    pool_length = body.get("pool_length", 50)
    race_distance = body.get("race_distance", 100)

    db = SessionLocal()
    try:
        existing = db.query(AnalysisRecord).filter(AnalysisRecord.id == video_id).first()
        if existing:
            existing.analysis_result = json.dumps(metrics, ensure_ascii=False)
            existing.analysis_options = json.dumps(list(markers.keys()), ensure_ascii=False)
            if swimmer_name:
                existing.swimmer_name = swimmer_name
            existing.pool_length = pool_length
            existing.race_distance = race_distance
            db.commit()
            return {"status": "ok", "message": "已更新", "id": video_id}

        record = AnalysisRecord(
            id=video_id,
            swimmer_name=swimmer_name or "未命名",
            pool_length=pool_length,
            race_distance=race_distance,
            stroke_type="自由泳",
            video_filename=video_id,
            analysis_options=json.dumps(list(markers.keys()), ensure_ascii=False),
            analysis_result=json.dumps(metrics, ensure_ascii=False),
            archived=1,
            archive_time=datetime.utcnow(),
        )
        db.add(record)
        db.commit()
        return {"status": "ok", "message": "已保存", "id": video_id}
    finally:
        db.close()


@app.post("/api/videos/{video_id}/link_to_record")
async def link_video_to_record(video_id: str, request: Request):
    body = await request.json()
    record_id = body.get("record_id")
    metrics = body.get("metrics", {})
    if not record_id:
        raise HTTPException(status_code=400, detail="缺少record_id")
    db = SessionLocal()
    try:
        record = db.query(AnalysisRecord).filter(AnalysisRecord.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="记录不存在")
        if metrics:
            existing = json.loads(record.analysis_result) if record.analysis_result else {}
            existing.update(metrics)
            record.analysis_result = json.dumps(existing, ensure_ascii=False)
        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.linked_record_id = record_id
        db.commit()
        return {"status": "ok", "message": f"已关联到记录 {record_id}"}
    finally:
        db.close()


@app.get("/api/videos/list")
def list_videos_db():
    db = SessionLocal()
    try:
        videos = db.query(Video).order_by(Video.upload_time.desc()).all()
        result = []
        for v in videos:
            result.append({
                "id": v.id,
                "file_name": v.file_name,
                "display_name": v.display_name,
                "athlete_name": v.athlete_name,
                "athlete_id": v.athlete_id,
                "competition_name": v.competition_name,
                "competition_id": v.competition_id,
                "upload_time": v.upload_time.isoformat() if v.upload_time else None,
                "file_size": v.file_size,
                "duration": v.duration,
                "linked_record_id": v.linked_record_id,
            })
        return result
    finally:
        db.close()


@app.delete("/api/videos/{video_id}/delete")
async def delete_video_db(video_id: str, request: Request):
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    password = body.get("password", "")
    if password != RECORD_PASSWORD:
        raise HTTPException(status_code=403, detail="密码错误")
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="视频不存在")
        for ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
            path = os.path.join(UPLOAD_DIR, f"{video_id}{ext}")
            if os.path.exists(path):
                os.remove(path)
        db.query(VideoMarker).filter(VideoMarker.video_id == video_id).delete()
        db.delete(video)
        db.commit()
        if video_id in analysis_tasks:
            del analysis_tasks[video_id]
        return {"status": "ok"}
    finally:
        db.close()


def _cleanup_expired_uploads():
    expired_sessions = [uid for uid, s in upload_sessions.items() if time.time() - s["created_at"] > 3600]
    for uid in expired_sessions:
        chunk_dir = os.path.join(CHUNKS_DIR, uid)
        shutil.rmtree(chunk_dir, ignore_errors=True)
        del upload_sessions[uid]


def _cleanup_loop():
    while True:
        try:
            _cleanup_expired_uploads()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        time.sleep(600)


cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True)
cleanup_thread.start()

ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "")

LLM_API_KEY = os.environ.get("LLM_API_KEY", ZHIPU_API_KEY)
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
LLM_MODEL = os.environ.get("LLM_MODEL", "glm-4v-flash")


@app.post("/api/recognize_image")
async def recognize_image(file: UploadFile = File(...)):
    if not LLM_API_KEY:
        raise HTTPException(status_code=500, detail="未配置LLM API密钥，请设置环境变量LLM_API_KEY或ZHIPU_API_KEY")
    import base64
    content = await file.read()
    b64 = base64.b64encode(content).decode()
    ext = os.path.splitext(file.filename or ".jpg")[1].lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".bmp": "image/bmp"}
    mime = mime_map.get(ext, "image/jpeg")
    import httpx
    prompt = """你是一个游泳比赛成绩识别助手。请识别这张图片中的游泳比赛成绩信息，以JSON格式返回。
需要识别的字段：
- race_name: 比赛名称（如"2024年XX市游泳锦标赛"）
- race_date: 比赛日期（如"2024-06-15"）
- race_location: 比赛地点（如"XX游泳馆"）
- stroke_type: 泳姿（自由泳/蛙泳/仰泳/蝶泳）
- pool_length: 泳池长度（25或50）
- race_distance: 比赛距离（50/100/200/400）
- 第1半程用时: 第1个50米用时（秒）
- 第2半程用时: 第2个50米用时（秒）
- 第3半程用时: 第3个50米用时（秒，如适用）
- 第4半程用时: 第4个50米用时（秒，如适用）
- 第5半程用时至第8半程用时: 如适用
- 比赛总用时: 比赛总用时（秒）
- 第1半程划水次数: 第1个50米划水次数
- 第1半程换气次数: 第1个50米换气次数
- 第1半程打腿次数: 第1个50米打腿次数
- 第2半程划水次数: 第2个50米划水次数
- 第2半程换气次数: 第2个50米换气次数
- 第2半程打腿次数: 第2个50米打腿次数
- （第3半程及之后的划水/换气/打腿次数，如适用）

50米池标准：每个半程为50米。100米=2个半程，200米=4个半程，400米=8个半程。
只返回JSON，不要其他文字。如果某个字段无法识别则不包含该字段。时间如果是分秒格式请转换为秒数。"""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            messages = [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
            ]}]
            resp = await client.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json={"model": LLM_MODEL, "messages": messages, "temperature": 0.1}
            )
            if resp.status_code != 200:
                logger.error(f"LLM API error: {resp.status_code} {resp.text}")
                raise HTTPException(status_code=502, detail=f"LLM API调用失败: {resp.status_code}")
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                text = text.rsplit("```", 1)[0]
            result = json.loads(text)
            return {"status": "ok", "data": result}
    except json.JSONDecodeError:
        return {"status": "ok", "data": {}, "raw": text}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image recognition error: {e}")
        raise HTTPException(status_code=500, detail=f"识别失败: {str(e)}")


@app.post("/api/recognize_competition")
async def recognize_competition(file: UploadFile = File(...)):
    if not LLM_API_KEY:
        raise HTTPException(status_code=500, detail="未配置LLM API密钥")
    import base64
    content = await file.read()
    b64 = base64.b64encode(content).decode()
    ext = os.path.splitext(file.filename or ".jpg")[1].lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".bmp": "image/bmp"}
    mime = mime_map.get(ext, "image/jpeg")
    import httpx
    prompt = """你是一个游泳比赛信息识别助手。请识别这张图片中的所有游泳比赛基本信息，以JSON数组格式返回。
每个比赛识别以下字段：
- name: 比赛名称（如"2024年XX市游泳锦标赛"）
- date: 比赛日期（格式：YYYY-MM-DD，如无法确定日则用YYYY-MM，如无法确定月则用YYYY）
- location: 比赛地点/场馆（如"XX游泳馆"）

返回格式：{"competitions": [{"name": "...", "date": "...", "location": "..."}, ...]}
如果只识别到一个比赛，也用数组返回。如果某个字段无法识别则不包含该字段。只返回JSON，不要其他文字。"""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            messages = [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
            ]}]
            resp = await client.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json={"model": LLM_MODEL, "messages": messages, "temperature": 0.1}
            )
            if resp.status_code != 200:
                logger.error(f"LLM API error: {resp.status_code} {resp.text}")
                raise HTTPException(status_code=502, detail=f"LLM API调用失败: {resp.status_code}")
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                text = text.rsplit("```", 1)[0]
            result = json.loads(text)
            if isinstance(result, list):
                result = {"competitions": result}
            elif isinstance(result, dict) and "competitions" not in result:
                if result.get("name"):
                    result = {"competitions": [result]}
                else:
                    result = {"competitions": []}
            return {"status": "ok", "data": result}
    except json.JSONDecodeError:
        return {"status": "ok", "data": {"competitions": []}, "raw": text}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Competition recognition error: {e}")
        raise HTTPException(status_code=500, detail=f"识别失败: {str(e)}")

FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")


@app.middleware("http")
async def static_cache_middleware(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/assets/") and ("." in path.split("/")[-1]):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif path == "/" or path == "/index.html":
        response.headers["Cache-Control"] = "no-cache"
    return response


if os.path.exists(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
