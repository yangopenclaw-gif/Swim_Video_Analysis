from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, Column, Integer, Float, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import json
import uuid
import shutil
import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import List, Optional
import logging

from .swim_analyzer import SwimVideoAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
CHUNKS_DIR = os.path.join(UPLOAD_DIR, ".chunks")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CHUNKS_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "swim_analysis.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

CHUNK_SIZE = 4 * 1024 * 1024



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


Base.metadata.create_all(bind=engine)

app = FastAPI(title="游泳比赛视频分析系统", version="3.0.0")

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


@app.post("/api/upload/chunk")
async def upload_chunk(request: Request):
    upload_id = request.query_params.get("upload_id", "")
    chunk_index = int(request.query_params.get("chunk_index", "0"))

    if upload_id not in upload_sessions:
        raise HTTPException(status_code=404, detail="上传会话不存在")

    session = upload_sessions[upload_id]
    chunk_dir = os.path.join(CHUNKS_DIR, upload_id)
    chunk_path = os.path.join(chunk_dir, f"chunk_{chunk_index}")

    try:
        body = await request.body()
    except Exception as e:
        logger.warning(f"Chunk {chunk_index} body read error for {upload_id}: {e}")
        return JSONResponse(status_code=400, content={"detail": f"请求中断: {str(e)}"})

    if len(body) == 0:
        return JSONResponse(status_code=400, content={"detail": "空分片"})

    if len(body) > CHUNK_SIZE * 2:
        logger.warning(f"Chunk {chunk_index} too large: {len(body)} bytes for {upload_id}")
        return JSONResponse(status_code=413, content={"detail": f"分片过大: {len(body)} bytes"})

    with open(chunk_path, "wb") as f:
        f.write(body)

    session["chunks_received"].add(chunk_index)
    received = len(session["chunks_received"])
    total = session["total_chunks"]
    progress = round(received / total * 100, 1) if total > 0 else 0

    logger.debug(f"Chunk {chunk_index} received for {upload_id}: {received}/{total} ({progress}%)")

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
    body = await request.json()
    upload_id = body.get("upload_id", "")

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
    return {"task_id": task_id, "status": "uploaded", "filename": session["filename"]}


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


@app.get("/api/records/{swimmer_name}")
def get_records(swimmer_name: str):
    db = SessionLocal()
    try:
        records = db.query(AnalysisRecord).filter(
            AnalysisRecord.swimmer_name == swimmer_name,
            AnalysisRecord.archived == 1,
        ).order_by(AnalysisRecord.created_at.desc()).all()
        result = []
        for r in records:
            result.append({
                "id": r.id, "swimmer_name": r.swimmer_name,
                "pool_length": r.pool_length, "race_distance": r.race_distance,
                "stroke_type": r.stroke_type, "swimmer_position": r.swimmer_position,
                "analysis_result": json.loads(r.analysis_result) if r.analysis_result else {},
                "race_name": r.race_name, "race_date": r.race_date,
                "race_location": r.race_location,
                "archive_time": r.archive_time.isoformat() if r.archive_time else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
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
        ).order_by(AnalysisRecord.created_at.desc()).all()
        result = []
        for r in records:
            result.append({
                "id": r.id, "swimmer_name": r.swimmer_name,
                "pool_length": r.pool_length, "race_distance": r.race_distance,
                "stroke_type": r.stroke_type, "swimmer_position": r.swimmer_position,
                "analysis_result": json.loads(r.analysis_result) if r.analysis_result else {},
                "race_name": r.race_name, "race_date": r.race_date,
                "race_location": r.race_location,
                "archive_time": r.archive_time.isoformat() if r.archive_time else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })
        return result
    finally:
        db.close()


@app.delete("/api/records/{task_id}")
def delete_record(task_id: str):
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

FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.exists(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
