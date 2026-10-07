from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Response, Depends
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
import bcrypt
import jwt

from .swim_analyzer import SwimVideoAnalyzer
from .agent_llm import chat as agent_llm_chat, stream_chat as agent_llm_stream, default_provider as agent_default_provider
from .agent_core import Tool, run_agent

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
AGENT_FILES_DIR = os.path.join(DATA_DIR, "agent_files")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CHUNKS_DIR, exist_ok=True)
os.makedirs(AGENT_FILES_DIR, exist_ok=True)

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


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id = Column(String, primary_key=True)
    entry_type = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=False)
    note = Column(String, nullable=True)
    entry_date = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    currency = Column(String, default="CNY")
    amount_cny = Column(Float, default=0.0)
    amounts = Column(Text, nullable=True)
    user_id = Column(String, nullable=True, index=True)


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    currency = Column(String, primary_key=True)
    rate = Column(Float, nullable=False)


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True)
    conversation_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class Memory(Base):
    __tablename__ = "memories"
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    mem_type = Column(String, default="semantic")
    content = Column(Text, nullable=False)
    importance = Column(Float, default=0.5)
    created_at = Column(DateTime, default=datetime.now)
    last_accessed_at = Column(DateTime, nullable=True)


class Schedule(Base):
    __tablename__ = "schedules"
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=True)
    remind_at = Column(String, nullable=False)
    repeat = Column(String, default="none")
    enabled = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.now)


class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=True)
    filename = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)


class Note(Base):
    __tablename__ = "notes"
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=True)
    note_date = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


LEDGER_CATEGORIES = {
    "expense": ["自我消费", "请客吃饭", "娱乐", "餐饮", "交通", "购物", "居住", "医疗", "教育", "人情往来", "AI", "云机", "其他"],
    "income": ["工资", "奖金", "理财", "红包", "其他"]
}

# 货币列表：code -> 中文名
CURRENCIES = {
    "CNY": "人民币",
    "USD": "美元",
    "EUR": "欧元",
    "GBP": "英镑",
    "EGP": "埃镑",
    "HKD": "港币",
    "JPY": "日元",
}

# 默认汇率：1 外币 = 多少人民币（CNY）
DEFAULT_EXCHANGE_RATES = {
    "CNY": 1.0,
    "USD": 7.2,
    "EUR": 7.8,
    "GBP": 9.1,
    "EGP": 0.15,
    "HKD": 0.92,
    "JPY": 0.048,
}

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "swim-ledger-2026-secret-key-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 365


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def get_current_user_id(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = auth[7:].strip()
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload.get("sub", "")
    except Exception:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")


Base.metadata.create_all(bind=engine)


def _migrate_ledger_columns():
    import sqlite3
    conn = engine.raw_connection()
    try:
        cur = conn.cursor()
        cols = [r[1] for r in cur.execute("PRAGMA table_info(ledger_entries)").fetchall()]
        if "currency" not in cols:
            cur.execute("ALTER TABLE ledger_entries ADD COLUMN currency VARCHAR DEFAULT 'CNY'")
        if "amount_cny" not in cols:
            cur.execute("ALTER TABLE ledger_entries ADD COLUMN amount_cny FLOAT DEFAULT 0.0")
        if "user_id" not in cols:
            cur.execute("ALTER TABLE ledger_entries ADD COLUMN user_id VARCHAR")
        if "amounts" not in cols:
            cur.execute("ALTER TABLE ledger_entries ADD COLUMN amounts TEXT")
        conn.commit()
    finally:
        conn.close()


_migrate_ledger_columns()


def _fix_created_at_timezone():
    import sqlite3
    conn = engine.raw_connection()
    try:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        cur.execute("SELECT value FROM meta WHERE key='created_at_tz_fixed'")
        if cur.fetchone():
            return
        cur.execute(
            "UPDATE ledger_entries SET created_at = datetime(created_at, '+8 hours') "
            "WHERE created_at IS NOT NULL"
        )
        cur.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('created_at_tz_fixed', '1')")
        conn.commit()
    finally:
        conn.close()


_fix_created_at_timezone()

EXCHANGE_RATES = {}


def _init_exchange_rates():
    dbs = SessionLocal()
    try:
        existing = {r.currency for r in dbs.query(ExchangeRate).all()}
        for code, rate in DEFAULT_EXCHANGE_RATES.items():
            if code not in existing:
                dbs.add(ExchangeRate(currency=code, rate=rate))
        dbs.commit()
        for r in dbs.query(ExchangeRate).all():
            EXCHANGE_RATES[r.currency] = r.rate
    finally:
        dbs.close()


_init_exchange_rates()


def _backfill_ledger_amount_cny():
    dbs = SessionLocal()
    try:
        for e in dbs.query(LedgerEntry).all():
            rate = EXCHANGE_RATES.get(e.currency or "CNY", 1.0)
            if e.amount_cny == 0.0 and e.amount != 0:
                e.amount_cny = round(e.amount * rate, 2)
        dbs.commit()
    finally:
        dbs.close()


_backfill_ledger_amount_cny()


def _backfill_ledger_amounts():
    dbs = SessionLocal()
    try:
        for e in dbs.query(LedgerEntry).filter(LedgerEntry.amounts == None).all():
            cur = e.currency or "CNY"
            acny = e.amount_cny if e.amount_cny else round(e.amount * EXCHANGE_RATES.get(cur, 1.0), 2)
            e.amounts = json.dumps(
                [{"currency": cur, "amount": e.amount, "amount_cny": round(acny, 2)}],
                ensure_ascii=False
            )
        dbs.commit()
    finally:
        dbs.close()


_backfill_ledger_amounts()

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


@app.get("/api/upload/status/{upload_id}")
def upload_status(upload_id: str):
    if upload_id not in upload_sessions:
        raise HTTPException(status_code=404, detail="上传会话不存在")
    session = upload_sessions[upload_id]
    return {
        "upload_id": upload_id,
        "chunks_received": sorted(list(session["chunks_received"])),
        "total_chunks": session["total_chunks"],
        "file_size": session["file_size"],
        "filename": session["filename"],
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


@app.put("/api/competitions/{comp_id}")
async def update_competition(comp_id: str, request: Request):
    body = await request.json()
    db = SessionLocal()
    try:
        comp = db.query(Competition).filter(Competition.id == comp_id).first()
        if not comp:
            raise HTTPException(status_code=404, detail="比赛不存在")
        old_name = comp.name
        if "name" in body:
            comp.name = body["name"]
        if "date" in body:
            comp.date = body["date"]
        if "location" in body:
            comp.location = body["location"]
        new_name = comp.name
        if old_name != new_name:
            records = db.query(AnalysisRecord).filter(AnalysisRecord.race_name == old_name).all()
            for r in records:
                r.race_name = new_name
                if comp.date:
                    r.race_date = comp.date
                if comp.location:
                    r.race_location = comp.location
        db.commit()
        return {"status": "ok", "updated_records": len(records) if old_name != new_name else 0}
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
    metrics = body.get("metrics") or {}
    total_time = body.get("total_time", "")
    if total_time and "比赛总用时" not in metrics:
        metrics["比赛总用时"] = total_time
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
        threshold = global_p95 * 0.3

        search_start = int(sr * 0.3)
        search_end = min(len(envelope), int(sr * 15))

        candidates = []
        i = search_start
        while i < search_end:
            if envelope[i] > threshold:
                local_max = 0
                local_max_idx = i
                check_end = min(i + int(sr * 0.15), search_end)
                for j in range(i, check_end):
                    if envelope[j] > local_max:
                        local_max = envelope[j]
                        local_max_idx = j
                if local_max > global_p95 * 0.4:
                    onset_idx = i
                    pre_window = int(sr * 0.05)
                    onset_threshold = envelope[max(0, i - pre_window)] * 2
                    for k in range(i, max(i - pre_window, 0), -1):
                        if envelope[k] < onset_threshold:
                            onset_idx = k
                            break
                    pre_start = max(0, onset_idx - int(sr * 0.3))
                    pre_seg = envelope[pre_start:onset_idx]
                    pre_mean = pre_seg.mean()
                    pre_min = pre_seg.min()
                    contrast = local_max / (pre_mean + 1e-6)
                    above_half = np.where(envelope[local_max_idx:min(local_max_idx + int(sr * 0.3), len(envelope))] > local_max * 0.5)[0]
                    duration_ms = len(above_half) / sr * 1000 if len(above_half) > 0 else 500
                    rise_start = local_max_idx
                    for k in range(local_max_idx, max(local_max_idx - int(sr * 0.1), 0), -1):
                        if envelope[k] < local_max * 0.1:
                            rise_start = k
                            break
                    rise_ms = (local_max_idx - rise_start) / sr * 1000
                    if rise_ms < 5:
                        rise_ms = 5
                    dur_score = max(0, 1 - (duration_ms - 10) / 90)
                    rise_score = max(0, 1 - (rise_ms - 10) / 40)
                    impulse_factor = 1 + dur_score * 0.4 + rise_score * 0.4
                    quietness = 1.0 / (pre_min + 0.002)
                    t_sec = onset_idx / sr
                    time_factor = 1 + max(0, 1 - t_sec / 8) * 0.5
                    score = np.log1p(contrast) * np.log1p(contrast) * quietness * impulse_factor * time_factor
                    candidates.append((onset_idx, local_max_idx, local_max, contrast, duration_ms, rise_ms, t_sec, pre_min, quietness, score))
                i = check_end
                continue
            i += 1

        if not candidates:
            return None

        candidates.sort(key=lambda x: -x[9])
        best = candidates[0]
        onset_idx = best[0]
        peak_idx = best[1]

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


@app.post("/api/compare_timeline")
async def compare_timeline(request: Request):
    body = await request.json()
    record_ids = body.get("record_ids", [])
    if len(record_ids) < 2:
        raise HTTPException(status_code=400, detail="至少选择2条记录")
    db = SessionLocal()
    try:
        records = []
        for rid in record_ids:
            r = db.query(AnalysisRecord).filter(AnalysisRecord.id == rid).first()
            if not r:
                raise HTTPException(status_code=404, detail=f"记录不存在: {rid}")
            records.append({
                "id": r.id, "swimmer_name": r.swimmer_name,
                "pool_length": r.pool_length, "race_distance": r.race_distance,
                "stroke_type": r.stroke_type,
                "race_name": r.race_name, "race_date": r.race_date,
                "race_location": r.race_location,
                "analysis_result": json.loads(r.analysis_result) if r.analysis_result else {},
            })
        return {"records": records}
    finally:
        db.close()


@app.post("/api/compare_evaluate")
async def compare_evaluate(request: Request):
    if not LLM_API_KEY:
        raise HTTPException(status_code=500, detail="未配置LLM API密钥")
    body = await request.json()
    records = body.get("records", [])
    if len(records) < 2:
        raise HTTPException(status_code=400, detail="至少2条记录")
    import httpx
    swimmer_name = records[0].get("swimmer_name", "")
    birth_date = None
    db = SessionLocal()
    try:
        profile = db.query(SwimmerProfile).filter(SwimmerProfile.name == swimmer_name).first()
        if profile and profile.birth_date:
            birth_date = profile.birth_date
    finally:
        db.close()

    record_desc = ""
    for i, r in enumerate(records):
        ar = r.get("analysis_result", {})
        total = ar.get("比赛总用时", "未知")
        date = r.get("race_date", "未知")
        race = r.get("race_name", "未知")
        dist = r.get("race_distance", "未知")
        stroke = r.get("stroke_type", "未知")
        halves = []
        for j in range(1, 9):
            ht = ar.get(f"第{j}半程用时")
            hs = ar.get(f"第{j}半程划水次数")
            hb = ar.get(f"第{j}半程换气次数")
            hk = ar.get(f"第{j}半程打腿次数")
            if ht is not None:
                parts = [f"第{j}半程{ht:.2f}秒"]
                if hs is not None: parts.append(f"划水{int(hs)}次")
                if hb is not None: parts.append(f"换气{int(hb)}次")
                if hk is not None: parts.append(f"打腿{int(hk)}次")
                halves.append("/".join(parts))
        total_str = f"{total:.2f}秒" if isinstance(total, (int, float)) else str(total)
        age_info = ""
        if birth_date and date and len(date) >= 7:
            try:
                by, bm = int(birth_date[:4]), int(birth_date[5:7])
                ry, rm = int(date[:4]), int(date[5:7])
                age_months = (ry - by) * 12 + (rm - bm)
                age_info = f"（当时约{age_months/12:.1f}岁）"
            except: pass
        record_desc += f"记录{i+1}: {date}{age_info} {race} {dist}米{stroke} 总成绩{total_str}"
        if halves: record_desc += f" ({'; '.join(halves)})"
        record_desc += "\n"

    age_context = ""
    if birth_date:
        age_context = f"\n运动员出生日期：{birth_date}"
        try:
            age = (datetime.now() - datetime.strptime(birth_date, "%Y-%m-%d")).days / 365.25
            age_context += f"，当前年龄约{age:.1f}岁"
        except: pass

    prompt = f"""你是一位资深青少年游泳教练和运动科学专家，请根据以下运动员在不同时间的比赛成绩记录，进行专业、深入的分析和评价。

要求：
1. 结合运动员年龄和身体发育阶段分析（青春期前/青春期/青春期后，不同阶段训练重点不同）
2. 分析成绩变化趋势（进步/退步/持平），计算月均进步幅度
3. 分析技术指标变化趋势（划水次数减少=效率提升，打腿次数变化等）
4. 前后半程配速分析（是否前快后慢，配速策略是否合理）
5. 针对当前年龄和水平，给出具体、可执行的训练建议（技术/体能/策略）
6. 语言专业但易懂，300字以内

运动员：{swimmer_name}{age_context}

成绩记录：
{record_desc}"""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json={"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 800},
            )
            if resp.status_code == 200:
                data = resp.json()
                evaluation = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return {"evaluation": evaluation}
            return {"evaluation": "AI评价暂时不可用"}
    except Exception as e:
        return {"evaluation": f"AI评价请求失败: {str(e)}"}


def _normalize_amount_items(raw_amounts) -> list:
    """把 [{'currency':..., 'amount':...}] 规范化为带 amount_cny 的列表，过滤非法项"""
    items = []
    for a in (raw_amounts or []):
        if not isinstance(a, dict):
            continue
        cur = str(a.get("currency") or "CNY").upper()
        if cur not in CURRENCIES:
            cur = "CNY"
        try:
            amt = float(a.get("amount", 0))
        except (TypeError, ValueError):
            continue
        if amt <= 0:
            continue
        rate = EXCHANGE_RATES.get(cur, 1.0)
        items.append({"currency": cur, "amount": amt, "amount_cny": round(amt * rate, 2)})
    return items


def _parse_entry_amounts(body: dict):
    """解析请求体中的多币种金额，返回 (items, currency, amount, amount_cny, amounts_json) 或 None"""
    items = _normalize_amount_items(body.get("amounts"))
    if not items:
        try:
            amt = float(body.get("amount", 0))
        except (TypeError, ValueError):
            amt = 0.0
        if amt <= 0:
            return None
        cur = str(body.get("currency") or "CNY").upper()
        if cur not in CURRENCIES:
            cur = "CNY"
        rate = EXCHANGE_RATES.get(cur, 1.0)
        items = [{"currency": cur, "amount": amt, "amount_cny": round(amt * rate, 2)}]
    amount_cny = round(sum(i["amount_cny"] for i in items), 2)
    currency = items[0]["currency"]
    amount = items[0]["amount"]
    amounts_json = json.dumps(items, ensure_ascii=False)
    return items, currency, amount, amount_cny, amounts_json


def _load_amounts(raw) -> list:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


@app.post("/api/ledger/entries")
async def create_ledger_entry(request: Request, user_id: str = Depends(get_current_user_id)):
    body = await request.json()
    entry_type = body.get("entry_type", "expense")
    if entry_type not in ("expense", "income"):
        raise HTTPException(status_code=400, detail="entry_type 必须为 expense 或 income")
    parsed = _parse_entry_amounts(body)
    if not parsed:
        raise HTTPException(status_code=400, detail="金额必须大于0")
    items, currency, amount, amount_cny, amounts_json = parsed
    category = body.get("category", "其他")
    note = body.get("note", "")
    entry_date = body.get("entry_date", datetime.now().strftime("%Y-%m-%d"))
    entry_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.add(LedgerEntry(
            id=entry_id, entry_type=entry_type, amount=amount,
            category=category, note=note or None, entry_date=entry_date,
            currency=currency, amount_cny=amount_cny, amounts=amounts_json,
            user_id=user_id
        ))
        db.commit()
        return {"status": "ok", "id": entry_id}
    finally:
        db.close()


@app.get("/api/ledger/entries")
async def list_ledger_entries(year: Optional[str] = None, month: Optional[str] = None, user_id: str = Depends(get_current_user_id)):
    db = SessionLocal()
    try:
        q = db.query(LedgerEntry).filter(LedgerEntry.user_id == user_id)
        if year:
            if month:
                q = q.filter(LedgerEntry.entry_date.like(f"{year}-{month:0>2}-%"))
            else:
                q = q.filter(LedgerEntry.entry_date.like(f"{year}-%"))
        entries = q.order_by(LedgerEntry.entry_date.desc(), LedgerEntry.created_at.desc()).all()
        return [
            {
                "id": e.id, "entry_type": e.entry_type, "amount": e.amount,
                "category": e.category, "note": e.note or "",
                "entry_date": e.entry_date,
                "currency": e.currency or "CNY",
                "amount_cny": round(e.amount_cny or 0.0, 2),
                "amounts": _load_amounts(e.amounts),
                "created_at": e.created_at.strftime("%Y-%m-%d %H:%M:%S") if e.created_at else None
            }
            for e in entries
        ]
    finally:
        db.close()


@app.put("/api/ledger/entries/{entry_id}")
async def update_ledger_entry(entry_id: str, request: Request, user_id: str = Depends(get_current_user_id)):
    body = await request.json()
    db = SessionLocal()
    try:
        entry = db.query(LedgerEntry).filter(LedgerEntry.id == entry_id, LedgerEntry.user_id == user_id).first()
        if not entry:
            raise HTTPException(status_code=404, detail="记录不存在")
        if "entry_type" in body:
            entry.entry_type = body["entry_type"]
        if "amount" in body:
            entry.amount = float(body["amount"])
        if "category" in body:
            entry.category = body["category"]
        if "note" in body:
            entry.note = body["note"]
        if "entry_date" in body:
            entry.entry_date = body["entry_date"]
        if "amounts" in body:
            parsed = _parse_entry_amounts(body)
            if parsed:
                items, currency, amount, amount_cny, amounts_json = parsed
                entry.currency = currency
                entry.amount = amount
                entry.amount_cny = amount_cny
                entry.amounts = amounts_json
        else:
            if "amount" in body:
                entry.amount = float(body["amount"])
            if "currency" in body:
                cur = str(body["currency"]).upper()
                if cur in CURRENCIES:
                    entry.currency = cur
            rate = EXCHANGE_RATES.get(entry.currency or "CNY", 1.0)
            entry.amount_cny = round(entry.amount * rate, 2)
            entry.amounts = json.dumps(
                [{"currency": entry.currency or "CNY", "amount": entry.amount,
                  "amount_cny": round(entry.amount_cny, 2)}],
                ensure_ascii=False
            )
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


@app.delete("/api/ledger/entries/{entry_id}")
async def delete_ledger_entry(entry_id: str, user_id: str = Depends(get_current_user_id)):
    db = SessionLocal()
    try:
        entry = db.query(LedgerEntry).filter(LedgerEntry.id == entry_id, LedgerEntry.user_id == user_id).first()
        if not entry:
            raise HTTPException(status_code=404, detail="记录不存在")
        db.delete(entry)
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


@app.get("/api/ledger/summary")
async def ledger_summary(year: Optional[str] = None, month: Optional[str] = None, user_id: str = Depends(get_current_user_id)):
    db = SessionLocal()
    try:
        q = db.query(LedgerEntry).filter(LedgerEntry.user_id == user_id)
        if year:
            if month:
                q = q.filter(LedgerEntry.entry_date.like(f"{year}-{month:0>2}-%"))
            else:
                q = q.filter(LedgerEntry.entry_date.like(f"{year}-%"))
        entries = q.all()
        expense_total = 0.0
        income_total = 0.0
        expense_map = {}
        income_map = {}
        for e in entries:
            amt = e.amount_cny if e.amount_cny else e.amount
            if e.entry_type == "expense":
                expense_total += amt
                expense_map[e.category] = expense_map.get(e.category, 0.0) + amt
            else:
                income_total += amt
                income_map[e.category] = income_map.get(e.category, 0.0) + amt

        def to_list(m):
            return [
                {"category": k, "amount": round(v, 2)}
                for k, v in sorted(m.items(), key=lambda x: -x[1])
            ]

        return {
            "expense_total": round(expense_total, 2),
            "income_total": round(income_total, 2),
            "expense_by_category": to_list(expense_map),
            "income_by_category": to_list(income_map)
        }
    finally:
        db.close()


@app.get("/api/ledger/calendar")
async def ledger_calendar(year: Optional[str] = None, month: Optional[str] = None, user_id: str = Depends(get_current_user_id)):
    db = SessionLocal()
    try:
        q = db.query(LedgerEntry).filter(LedgerEntry.user_id == user_id)
        if year:
            if month:
                q = q.filter(LedgerEntry.entry_date.like(f"{year}-{month:0>2}-%"))
            else:
                q = q.filter(LedgerEntry.entry_date.like(f"{year}-%"))
        entries = q.all()
        daily = {}
        for e in entries:
            amt = e.amount_cny if e.amount_cny else e.amount
            day = e.entry_date
            if day not in daily:
                daily[day] = {"date": day, "expense": 0.0, "income": 0.0}
            if e.entry_type == "expense":
                daily[day]["expense"] += amt
            else:
                daily[day]["income"] += amt
        items = []
        for d in sorted(daily.keys()):
            v = daily[d]
            items.append({"date": d, "expense": round(v["expense"], 2), "income": round(v["income"], 2)})
        return {"items": items}
    finally:
        db.close()


@app.post("/api/ledger/parse_voice")
async def parse_voice(request: Request, user_id: str = Depends(get_current_user_id)):
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="缺少语音识别文本")
    today = datetime.now().strftime("%Y-%m-%d")

    if LLM_API_KEY:
        import httpx
        prompt = f"""你是个人记账助手，请把用户的口语化描述解析成一条记账记录。
可选支出分类：{"/".join(LEDGER_CATEGORIES["expense"])}
可选收入分类：{"/".join(LEDGER_CATEGORIES["income"])}
可选币种代码：CNY(人民币/元/块)、USD(美元/美金)、EUR(欧元)、GBP(英镑)、EGP(埃镑)、HKD(港币)、JPY(日元)
规则：
1. type：支出为"expense"，收入为"income"（如"工资"、"赚了"、"收入"、"奖金"、"到账"等属于收入）
2. amounts：金额列表，支持多币种，每项格式 {{"currency":"币种代码","amount":数字}}。金额按币种原币记录，"一百块"转100。用户没说明币种时默认CNY。例如"700人民币加上300埃镑"应返回 [{{"currency":"CNY","amount":700}},{{"currency":"EGP","amount":300}}]
3. amount：amounts 第一项的金额数字
4. currency：amounts 第一项的币种代码
5. category：从上面分类中选择最匹配的一个，支出若无法判断选"其他"
6. note：一句话简要备注（可选，可为空字符串）
7. date：日期 YYYY-MM-DD，若用户没说明日期则用今天 {today}

用户说：{text}

只返回JSON，格式：{{"type":"expense","amount":100,"currency":"CNY","amounts":[{{"currency":"CNY","amount":100}}],"category":"餐饮","note":"午饭","date":"{today}"}}"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{LLM_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                    json={"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.1}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    raw = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    raw = raw.strip()
                    if raw.startswith("```"):
                        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                        raw = raw.rsplit("```", 1)[0]
                    result = json.loads(raw)
                    result["type"] = result.get("type", "expense")
                    if result["type"] not in ("expense", "income"):
                        result["type"] = "expense"
                    result.setdefault("category", "其他")
                    result.setdefault("note", "")
                    result.setdefault("date", today)
                    items = _normalize_amount_items(result.get("amounts"))
                    if items:
                        result["amounts"] = items
                        result["amount"] = items[0]["amount"]
                        result["currency"] = items[0]["currency"]
                    else:
                        try:
                            amt = float(result.get("amount", 0) or 0)
                        except (TypeError, ValueError):
                            amt = 0.0
                        cur = str(result.get("currency") or "CNY").upper()
                        if cur not in CURRENCIES:
                            cur = "CNY"
                        result["amount"] = amt
                        result["currency"] = cur
                        result["amounts"] = (
                            [{"currency": cur, "amount": amt,
                              "amount_cny": round(amt * EXCHANGE_RATES.get(cur, 1.0), 2)}]
                            if amt > 0 else []
                        )
                    return {"status": "ok", "data": result}
        except Exception as e:
            logger.error(f"Voice parse error: {e}")

    return {"status": "ok", "data": basic_parse_voice(text, today)}


def basic_parse_voice(text: str, today: str):
    import re
    entry_type = "expense"
    for kw in ["工资", "奖金", "收入", "赚", "到账", "红包", "理财", "进账", "发了"]:
        if kw in text:
            entry_type = "income"
            break
    category = "其他"
    for cat in LEDGER_CATEGORIES["expense"] + LEDGER_CATEGORIES["income"]:
        if cat in text:
            category = cat
            break

    kw_map = [
        ("CNY", ["人民币", "元", "块", "rmb", "cny"]),
        ("USD", ["美元", "美金", "美刀", "usd"]),
        ("EUR", ["欧元", "eur"]),
        ("GBP", ["英镑", "gbp"]),
        ("EGP", ["埃镑", "egp"]),
        ("HKD", ["港币", "港元", "hkd"]),
        ("JPY", ["日元", "日币", "jpy"]),
    ]

    def currency_after(pos):
        best = None
        best_pos = None
        for code, kws in kw_map:
            for kw in kws:
                idx = text.find(kw, pos)
                if idx == -1:
                    continue
                if best_pos is None or idx < best_pos:
                    best_pos = idx
                    best = code
        return best

    amounts = []
    for m in re.finditer(r'(\d+(?:\.\d+)?)', text):
        amt = float(m.group(1))
        if amt <= 0:
            continue
        code = currency_after(m.end()) or "CNY"
        merged = False
        for item in amounts:
            if item["currency"] == code:
                item["amount"] = round(item["amount"] + amt, 2)
                merged = True
                break
        if not merged:
            amounts.append({"currency": code, "amount": amt})

    for item in amounts:
        item["amount_cny"] = round(item["amount"] * EXCHANGE_RATES.get(item["currency"], 1.0), 2)

    if not amounts:
        return {"type": entry_type, "amount": 0.0, "currency": "CNY", "amounts": [],
                "category": category, "note": text, "date": today}
    return {"type": entry_type, "amount": amounts[0]["amount"], "currency": amounts[0]["currency"],
            "amounts": amounts, "category": category, "note": text, "date": today}


@app.post("/api/auth/register")
async def register(request: Request):
    body = await request.json()
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    if not username or len(username) > 32:
        raise HTTPException(status_code=400, detail="用户名不能为空且不超过32个字符")
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="密码至少4位")
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            raise HTTPException(status_code=409, detail="用户名已存在")
        is_first_user = db.query(User).count() == 0
        uid = str(uuid.uuid4())
        db.add(User(id=uid, username=username, password_hash=hash_password(password)))
        db.commit()
        if is_first_user:
            db.query(LedgerEntry).filter(LedgerEntry.user_id == None).update({LedgerEntry.user_id: uid})
            db.commit()
        return {"status": "ok", "token": create_token(uid), "username": username}
    finally:
        db.close()


@app.post("/api/auth/login")
async def login(request: Request):
    body = await request.json()
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        return {"status": "ok", "token": create_token(user.id), "username": user.username}
    finally:
        db.close()


@app.get("/api/auth/me")
async def auth_me(user_id: str = Depends(get_current_user_id)):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="用户不存在")
        return {"status": "ok", "username": user.username}
    finally:
        db.close()


@app.get("/api/ledger/currencies")
async def get_currencies(user_id: str = Depends(get_current_user_id)):
    return {
        "currencies": [
            {"code": c, "name": CURRENCIES[c], "rate": EXCHANGE_RATES.get(c, 1.0)}
            for c in CURRENCIES
        ]
    }


@app.put("/api/ledger/rates/{currency}")
async def update_rate(currency: str, request: Request, user_id: str = Depends(get_current_user_id)):
    body = await request.json()
    rate = float(body.get("rate", 0))
    if rate <= 0:
        raise HTTPException(status_code=400, detail="汇率必须大于0")
    code = currency.upper()
    if code not in CURRENCIES:
        raise HTTPException(status_code=400, detail="未知货币")
    db = SessionLocal()
    try:
        rec = db.query(ExchangeRate).filter(ExchangeRate.currency == code).first()
        if rec:
            rec.rate = rate
        else:
            db.add(ExchangeRate(currency=code, rate=rate))
        db.commit()
        EXCHANGE_RATES[code] = rate
        return {"status": "ok"}
    finally:
        db.close()


# ============================================================
# 个人智能体（Agent）：记忆 / 工具 / ReAct / 知识库 / 日程
# ============================================================

def build_system_prompt(memories: List[str], today_date: str) -> str:
    mem_text = ""
    if memories:
        mem_text = "\n[关于用户的长期记忆]\n" + "\n".join(f"- {m}" for m in memories)
    return (
        f"你是用户的私人智能体「小咩」，温暖简洁。今天：{today_date}。\n"
        f"工具：记账 ledger_add/ledger_query/ledger_summary；"
        f"提醒 schedule_add/schedule_list/schedule_delete；"
        f"知识 kb_add/kb_search；记录本 note_add/note_list。\n"
        f"规则：金额默认 CNY，未说日期用今天；用简体中文简洁回复；涉及金额时间务必准确。\n"
        f"重要：当用户告诉你关于他/她自己的信息（偏好、习惯、目标、重要事实、约定等）时，"
        f"务必调用 kb_add 将其保存到知识库，不要只在对话中回应就丢掉。"
        f"{mem_text}"
    )


def _is_duplicate(text: str, existing: List[str]) -> bool:
    def toks(s: str):
        return set(c for c in s if c.strip())
    t = toks(text)
    if not t:
        return True
    for e in existing:
        et = toks(e)
        if not et:
            continue
        inter = len(t & et)
        if inter / len(t) > 0.7 or inter / len(et) > 0.7:
            return True
    return False


def recall_memories(user_id: str, query: str, top_k: int = 5) -> List[str]:
    try:
        from . import kb
        results = kb.search(user_id, DATA_DIR, query, top_k=top_k)
        contents = [r.get("content", "").strip() for r in results if (r.get("content") or "").strip()]
        if contents:
            return contents[:top_k]
    except Exception as e:
        logger.warning("向量记忆召回失败，回退字符匹配: %s", e)

    db = SessionLocal()
    try:
        memories = db.query(Memory).filter(Memory.user_id == user_id).all()
    finally:
        db.close()
    if not memories:
        return []
    q_toks = set(c for c in query if c.strip())
    scored = []
    for m in memories:
        m_toks = set(c for c in m.content if c.strip())
        overlap = len(q_toks & m_toks) if q_toks and m_toks else 0
        scored.append((overlap + (m.importance or 0.0) * 2, m.content))
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:top_k]]


async def extract_and_save_memories(user_id: str, user_text: str, assistant_text: str):
    if not agent_default_provider():
        return
    prompt = (
        f"从下面的对话中提取关于用户的稳定事实、偏好或值得长期记住的信息。\n"
        f"只提取长期有用的信息（例如：用户的工作、兴趣、习惯、喜好、重要日期、财务目标等）。\n"
        f"忽略一次性、琐碎的内容。\n\n"
        f"用户说：{user_text}\n"
        f"助手说：{assistant_text}\n\n"
        f"只返回JSON数组，每项格式："
        f'{{"type":"semantic|episodic|preference","content":"一句话描述","importance":0到1的小数}}。\n'
        f"若没有值得记住的信息，返回空数组 []。"
    )
    try:
        resp = await agent_llm_chat(
            [{"role": "user", "content": prompt}], temperature=0.2, max_tokens=500
        )
        raw = resp.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            raw = raw.rsplit("```", 1)[0]
        items = json.loads(raw)
        if not isinstance(items, list):
            return
        db = SessionLocal()
        new_memories: List[str] = []
        try:
            existing = [m.content for m in db.query(Memory).filter(Memory.user_id == user_id).all()]
            for it in items:
                if not isinstance(it, dict):
                    continue
                content = (it.get("content") or "").strip()
                if not content:
                    continue
                try:
                    imp = float(it.get("importance") or 0.5)
                except (TypeError, ValueError):
                    imp = 0.5
                if imp < 0.3:
                    continue
                if _is_duplicate(content, existing):
                    continue
                db.add(Memory(
                    id=str(uuid.uuid4()), user_id=user_id,
                    mem_type=it.get("type") or "semantic",
                    content=content, importance=imp
                ))
                existing.append(content)
                new_memories.append(content)
            db.commit()
        finally:
            db.close()
        if new_memories:
            try:
                from . import kb
                kb.add_chunks(user_id, DATA_DIR, f"mem_{uuid.uuid4()}", "记忆", new_memories)
            except Exception as e:
                logger.warning("记忆向量化失败: %s", e)
    except Exception as e:
        logger.warning("记忆提取失败: %s", e)


def _find_agent_file(file_id: str) -> Optional[str]:
    """根据 file_id 在暂存目录中查找文件路径（保留原始扩展名）。"""
    if not file_id or os.path.sep in file_id or ".." in file_id:
        return None
    prefix = file_id + "."
    for name in os.listdir(AGENT_FILES_DIR):
        if name.startswith(prefix):
            return os.path.join(AGENT_FILES_DIR, name)
    return None


async def _extract_image_text(content: bytes, filename: str) -> str:
    """调用视觉模型识别图片文字，返回整理后的文本。"""
    import base64
    import httpx
    b64 = base64.b64encode(content).decode()
    ext = os.path.splitext(filename or ".jpg")[1].lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".webp": "image/webp", ".bmp": "image/bmp"}
    mime = mime_map.get(ext, "image/jpeg")
    prompt = """请仔细查看这张图片，提炼其中的关键信息，用简体中文、结构化要点形式整理输出。
若是票据/文档/截图，请尽量完整还原其中的重要文字信息并归类整理；若是照片，请概括主要内容。
直接输出整理后的文本内容，不要加任何解释性前缀或后缀。"""
    async with httpx.AsyncClient(timeout=60) as client:
        messages = [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
        ]}]
        resp = await client.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json={"model": LLM_MODEL, "messages": messages, "temperature": 0.2}
        )
        if resp.status_code != 200:
            raise RuntimeError(f"视觉模型调用失败: {resp.status_code}")
        data = resp.json()
        return (data["choices"][0]["message"]["content"] or "").strip()


def build_agent_tools(user_id: str) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")

    async def ledger_add(args):
        entry_type = args.get("entry_type", "expense")
        if entry_type not in ("expense", "income"):
            entry_type = "expense"
        try:
            amount = float(args.get("amount", 0) or 0)
        except (TypeError, ValueError):
            amount = 0.0
        if amount <= 0:
            return {"error": "金额必须大于0"}
        currency = str(args.get("currency") or "CNY").upper()
        if currency not in CURRENCIES:
            currency = "CNY"
        amount_cny = round(amount * EXCHANGE_RATES.get(currency, 1.0), 2)
        category = args.get("category") or "其他"
        note = args.get("note") or ""
        date = args.get("date") or today
        entry_id = str(uuid.uuid4())
        amounts_json = json.dumps(
            [{"currency": currency, "amount": amount, "amount_cny": amount_cny}],
            ensure_ascii=False
        )
        db = SessionLocal()
        try:
            db.add(LedgerEntry(
                id=entry_id, entry_type=entry_type, amount=amount, category=category,
                note=note or None, entry_date=date, currency=currency,
                amount_cny=amount_cny, amounts=amounts_json, user_id=user_id
            ))
            db.commit()
        finally:
            db.close()
        return {"status": "ok", "message": f"已记账：{category} {amount} {currency}"}

    async def ledger_query(args):
        year = args.get("year")
        month = args.get("month")
        category = args.get("category")
        entry_type = args.get("entry_type")
        db = SessionLocal()
        try:
            q = db.query(LedgerEntry).filter(LedgerEntry.user_id == user_id)
            if year:
                if month:
                    q = q.filter(LedgerEntry.entry_date.like(f"{year}-{int(month):02d}-%"))
                else:
                    q = q.filter(LedgerEntry.entry_date.like(f"{year}-%"))
            if category:
                q = q.filter(LedgerEntry.category == category)
            if entry_type in ("expense", "income"):
                q = q.filter(LedgerEntry.entry_type == entry_type)
            entries = q.order_by(LedgerEntry.entry_date.desc()).limit(50).all()
            items = [
                {"date": e.entry_date, "type": e.entry_type, "category": e.category,
                 "amount": e.amount, "currency": e.currency or "CNY", "note": e.note or ""}
                for e in entries
            ]
            total_cny = round(sum((e.amount_cny if e.amount_cny else e.amount) for e in entries), 2)
            return {"count": len(items), "total_cny": total_cny, "items": items}
        finally:
            db.close()

    async def ledger_summary(args):
        year = args.get("year")
        month = args.get("month")
        db = SessionLocal()
        try:
            q = db.query(LedgerEntry).filter(LedgerEntry.user_id == user_id)
            if year:
                if month:
                    q = q.filter(LedgerEntry.entry_date.like(f"{year}-{int(month):02d}-%"))
                else:
                    q = q.filter(LedgerEntry.entry_date.like(f"{year}-%"))
            entries = q.all()
            expense_total = 0.0
            income_total = 0.0
            expense_map = {}
            income_map = {}
            for e in entries:
                amt = e.amount_cny if e.amount_cny else e.amount
                if e.entry_type == "expense":
                    expense_total += amt
                    expense_map[e.category] = expense_map.get(e.category, 0.0) + amt
                else:
                    income_total += amt
                    income_map[e.category] = income_map.get(e.category, 0.0) + amt

            def to_list(m):
                return [{"category": k, "amount": round(v, 2)} for k, v in sorted(m.items(), key=lambda x: -x[1])]

            return {
                "expense_total": round(expense_total, 2),
                "income_total": round(income_total, 2),
                "balance": round(income_total - expense_total, 2),
                "expense_by_category": to_list(expense_map),
                "income_by_category": to_list(income_map),
            }
        finally:
            db.close()

    async def schedule_add(args):
        title = (args.get("title") or "").strip()
        remind_at = (args.get("remind_at") or "").strip()
        if not title:
            return {"error": "提醒标题不能为空"}
        if not remind_at:
            return {"error": "提醒时间不能为空"}
        content = args.get("content") or ""
        repeat = args.get("repeat") or "none"
        sid = str(uuid.uuid4())
        db = SessionLocal()
        try:
            db.add(Schedule(id=sid, user_id=user_id, title=title, content=content or None,
                            remind_at=remind_at, repeat=repeat))
            db.commit()
        finally:
            db.close()
        return {"status": "ok", "message": f"已添加提醒：{title}（{remind_at}）", "id": sid}

    async def schedule_list(args):
        db = SessionLocal()
        try:
            items = db.query(Schedule).filter(Schedule.user_id == user_id, Schedule.enabled == 1)\
                .order_by(Schedule.remind_at.asc()).all()
            return {"items": [{"id": s.id, "title": s.title, "content": s.content or "",
                               "remind_at": s.remind_at, "repeat": s.repeat} for s in items]}
        finally:
            db.close()

    async def schedule_delete(args):
        sid = args.get("id")
        title = args.get("title")
        db = SessionLocal()
        try:
            if sid:
                s = db.query(Schedule).filter(Schedule.id == sid, Schedule.user_id == user_id).first()
            elif title:
                s = db.query(Schedule).filter(Schedule.user_id == user_id, Schedule.title == title).first()
            else:
                s = None
            if not s:
                return {"error": "未找到该提醒"}
            db.delete(s)
            db.commit()
            return {"status": "ok", "message": f"已删除提醒：{s.title}"}
        finally:
            db.close()

    async def kb_search(args):
        query = (args.get("query") or "").strip()
        if not query:
            return {"error": "查询内容不能为空"}
        try:
            from . import kb
            chunks = kb.search(user_id, DATA_DIR, query, top_k=5)
        except Exception as e:
            return {"error": f"知识库检索失败: {e}"}
        if not chunks:
            return {"results": [], "message": "知识库中未找到相关内容"}
        return {"results": chunks}

    async def kb_add(args):
        title = (args.get("title") or "知识").strip()
        content = (args.get("content") or "").strip()
        if not content:
            return {"error": "内容不能为空"}
        try:
            from . import kb
            chunks = kb.chunk_text(content)
            if not chunks:
                return {"error": "无法解析出有效内容"}
            doc_id = str(uuid.uuid4())
            n = kb.add_chunks(user_id, DATA_DIR, doc_id, title, chunks)
        except Exception as e:
            return {"error": f"知识存储失败: {e}"}
        db = SessionLocal()
        try:
            db.add(Document(id=doc_id, user_id=user_id, title=title, content=content, chunk_count=n))
            db.commit()
        finally:
            db.close()
        return {"status": "ok", "message": f"已记住：{title}"}

    async def note_add(args):
        title = (args.get("title") or "").strip()
        content = (args.get("content") or "").strip()
        if not title:
            return {"error": "标题不能为空"}
        note_date = args.get("date") or today
        nid = str(uuid.uuid4())
        db = SessionLocal()
        try:
            db.add(Note(id=nid, user_id=user_id, title=title, content=content or None, note_date=note_date))
            db.commit()
        finally:
            db.close()
        return {"status": "ok", "message": f"已记录：{title}（{note_date}）", "id": nid}

    async def note_list(args):
        db = SessionLocal()
        try:
            items = db.query(Note).filter(Note.user_id == user_id)\
                .order_by(Note.note_date.desc()).limit(50).all()
            return {"items": [{"id": n.id, "title": n.title, "content": n.content or "",
                               "date": n.note_date} for n in items]}
        finally:
            db.close()

    async def pdf_generate(args):
        title = (args.get("title") or "文档").strip() or "文档"
        content = args.get("content") or ""
        if not content.strip():
            return {"error": "PDF 内容不能为空"}
        from . import doc_parser
        try:
            pdf_bytes = doc_parser.text_to_pdf(content)
        except Exception as e:
            logger.error(f"PDF 生成失败: {e}")
            return {"error": f"PDF 生成失败: {str(e)}"}
        gen_dir = os.path.join(DATA_DIR, "generated")
        os.makedirs(gen_dir, exist_ok=True)
        safe_title = "".join(c if c.isalnum() or c in "._-" else "_" for c in title)[:40]
        filename = f"{safe_title}_{uuid.uuid4().hex[:8]}.pdf"
        path = os.path.join(gen_dir, filename)
        with open(path, "wb") as f:
            f.write(pdf_bytes)
        return {
            "status": "ok",
            "message": f"已生成 PDF：{title}",
            "filename": filename,
            "url": f"/api/agent/generated/{filename}",
            "attachment": {
                "kind": "pdf",
                "filename": filename,
                "title": title,
                "url": f"/api/agent/generated/{filename}",
            },
        }

    async def doc_parse(args):
        file_id = (args.get("file_id") or "").strip()
        if not file_id:
            return {"error": "缺少 file_id，请先让用户上传文件"}
        path = _find_agent_file(file_id)
        if not path:
            return {"error": "文件不存在或已过期，请重新上传"}
        try:
            from . import doc_parser
            with open(path, "rb") as f:
                content = f.read()
            text = doc_parser.parse_document(content, os.path.basename(path))
        except Exception as e:
            logger.error(f"文档解析失败: {e}")
            return {"error": f"文档解析失败: {str(e)}"}
        if not text.strip():
            return {"error": "未能从文档中提取到文字内容"}
        return {"status": "ok", "filename": os.path.basename(path), "text": text}

    async def image_extract(args):
        file_id = (args.get("file_id") or "").strip()
        if not file_id:
            return {"error": "缺少 file_id，请先让用户上传图片"}
        if not LLM_API_KEY:
            return {"error": "未配置视觉模型 API 密钥"}
        path = _find_agent_file(file_id)
        if not path:
            return {"error": "图片不存在或已过期，请重新上传"}
        try:
            with open(path, "rb") as f:
                content = f.read()
            text = await _extract_image_text(content, os.path.basename(path))
        except Exception as e:
            logger.error(f"图片识别失败: {e}")
            return {"error": f"图片识别失败: {str(e)}"}
        return {"status": "ok", "text": text}

    return {
        "ledger_add": Tool(
            "ledger_add", "新增一条记账记录",
            {"type": "object", "properties": {
                "entry_type": {"type": "string", "enum": ["expense", "income"], "description": "支出expense或收入income"},
                "amount": {"type": "number", "description": "金额数字"},
                "currency": {"type": "string", "description": "币种代码，默认CNY，可选CNY/USD/EUR/GBP/EGP/HKD/JPY"},
                "category": {"type": "string", "description": "分类，支出：餐饮/交通/购物/居住/医疗/教育/娱乐/人情往来/自我消费/请客吃饭/AI/云机/其他；收入：工资/奖金/理财/红包/其他"},
                "note": {"type": "string", "description": "备注"},
                "date": {"type": "string", "description": "日期YYYY-MM-DD，默认今天"},
            }, "required": ["entry_type", "amount"]},
            ledger_add
        ),
        "ledger_query": Tool(
            "ledger_query", "查询记账记录",
            {"type": "object", "properties": {
                "year": {"type": "string", "description": "年份，如2026"},
                "month": {"type": "integer", "description": "月份1-12"},
                "category": {"type": "string", "description": "按分类筛选"},
                "entry_type": {"type": "string", "enum": ["expense", "income"], "description": "支出或收入"},
            }},
            ledger_query
        ),
        "ledger_summary": Tool(
            "ledger_summary", "统计汇总支出/收入/结余",
            {"type": "object", "properties": {
                "year": {"type": "string", "description": "年份，如2026"},
                "month": {"type": "integer", "description": "月份1-12"},
            }},
            ledger_summary
        ),
        "schedule_add": Tool(
            "schedule_add", "添加一条日程/提醒",
            {"type": "object", "properties": {
                "title": {"type": "string", "description": "提醒标题"},
                "content": {"type": "string", "description": "提醒内容备注"},
                "remind_at": {"type": "string", "description": "提醒时间 YYYY-MM-DD HH:MM"},
                "repeat": {"type": "string", "enum": ["none", "daily", "weekly"], "description": "重复方式，默认none"},
            }, "required": ["title", "remind_at"]},
            schedule_add
        ),
        "schedule_list": Tool(
            "schedule_list", "查看用户的日程/提醒列表",
            {"type": "object", "properties": {}},
            schedule_list
        ),
        "schedule_delete": Tool(
            "schedule_delete", "删除一条日程/提醒",
            {"type": "object", "properties": {
                "id": {"type": "string", "description": "提醒ID"},
                "title": {"type": "string", "description": "提醒标题"},
            }},
            schedule_delete
        ),
        "kb_search": Tool(
            "kb_search", "在个人知识库中检索相关内容",
            {"type": "object", "properties": {
                "query": {"type": "string", "description": "检索关键词或问题"},
            }, "required": ["query"]},
            kb_search
        ),
        "kb_add": Tool(
            "kb_add", "将用户告知的知识/事实/偏好存入个人知识库",
            {"type": "object", "properties": {
                "title": {"type": "string", "description": "知识标题"},
                "content": {"type": "string", "description": "知识内容"},
            }, "required": ["title", "content"]},
            kb_add
        ),
        "note_add": Tool(
            "note_add", "按日期记一条重要事情到记录本",
            {"type": "object", "properties": {
                "title": {"type": "string", "description": "标题"},
                "content": {"type": "string", "description": "详细内容"},
                "date": {"type": "string", "description": "日期YYYY-MM-DD，默认今天"},
            }, "required": ["title"]},
            note_add
        ),
        "note_list": Tool(
            "note_list", "查看记录本中的记录列表",
            {"type": "object", "properties": {}},
            note_list
        ),
        "pdf_generate": Tool(
            "pdf_generate", "根据标题和文字内容生成一份中文 PDF 文档，返回下载链接",
            {"type": "object", "properties": {
                "title": {"type": "string", "description": "文档标题"},
                "content": {"type": "string", "description": "要写入 PDF 的正文内容，支持多行"},
            }, "required": ["content"]},
            pdf_generate
        ),
        "doc_parse": Tool(
            "doc_parse", "解析用户上传的文档（PDF/Word/Excel/文本）为纯文本。用户需先上传文件并拿到 file_id，再把 file_id 传入。",
            {"type": "object", "properties": {
                "file_id": {"type": "string", "description": "用户上传文件后返回的文件ID"},
            }, "required": ["file_id"]},
            doc_parse
        ),
        "image_extract": Tool(
            "image_extract", "识别用户上传的图片中的文字/内容，整理为结构化文本。用户需先上传图片并拿到 file_id，再把 file_id 传入。",
            {"type": "object", "properties": {
                "file_id": {"type": "string", "description": "用户上传图片后返回的文件ID"},
            }, "required": ["file_id"]},
            image_extract
        ),
    }


@app.post("/api/agent/chat")
async def agent_chat(request: Request, user_id: str = Depends(get_current_user_id)):
    body = await request.json()
    text = (body.get("message") or body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="消息不能为空")
    conversation_id = body.get("conversation_id") or ""
    today_date = datetime.now().strftime("%Y-%m-%d")

    db = SessionLocal()
    try:
        if conversation_id:
            conv = db.query(Conversation).filter(
                Conversation.id == conversation_id, Conversation.user_id == user_id
            ).first()
            if not conv:
                raise HTTPException(status_code=404, detail="会话不存在")
        else:
            conv = Conversation(id=str(uuid.uuid4()), user_id=user_id, title=text[:20])
            db.add(conv)
            db.commit()
            conversation_id = conv.id
        db.add(Message(id=str(uuid.uuid4()), conversation_id=conversation_id,
                       user_id=user_id, role="user", content=text))
        db.commit()
        history = db.query(Message).filter(Message.conversation_id == conversation_id)\
            .order_by(Message.created_at.asc()).all()
        recent = history[-20:]
    finally:
        db.close()

    memories = recall_memories(user_id, text, top_k=5)
    system = build_system_prompt(memories, today_date)
    messages = [{"role": "system", "content": system}]
    for m in recent:
        messages.append({"role": m.role, "content": m.content})

    tools = build_agent_tools(user_id)

    async def event_stream():
        assistant_parts = []
        yield f"data: {json.dumps({'type': 'meta', 'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"
        try:
            async for ev in run_agent(agent_llm_stream, messages, tools):
                if ev["type"] == "token":
                    assistant_parts.append(ev["text"])
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            assistant_text = "".join(assistant_parts)
            db = SessionLocal()
            try:
                db.add(Message(id=str(uuid.uuid4()), conversation_id=conversation_id,
                               user_id=user_id, role="assistant", content=assistant_text))
                db.query(Conversation).filter(Conversation.id == conversation_id)\
                    .update({Conversation.updated_at: datetime.now()})
                db.commit()
            finally:
                db.close()
            if assistant_text:
                asyncio.create_task(extract_and_save_memories(user_id, text, assistant_text))

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/agent/conversations")
async def agent_list_conversations(user_id: str = Depends(get_current_user_id)):
    db = SessionLocal()
    try:
        convs = db.query(Conversation).filter(Conversation.user_id == user_id)\
            .order_by(Conversation.updated_at.desc()).all()
        return {"items": [
            {"id": c.id, "title": c.title or "新对话",
             "updated_at": c.updated_at.strftime("%Y-%m-%d %H:%M:%S") if c.updated_at else None}
            for c in convs
        ]}
    finally:
        db.close()


@app.get("/api/agent/conversations/{conversation_id}/messages")
async def agent_get_messages(conversation_id: str, user_id: str = Depends(get_current_user_id)):
    db = SessionLocal()
    try:
        msgs = db.query(Message).filter(
            Message.conversation_id == conversation_id, Message.user_id == user_id
        ).order_by(Message.created_at.asc()).all()
        return {"items": [{"role": m.role, "content": m.content} for m in msgs]}
    finally:
        db.close()


@app.delete("/api/agent/conversations/{conversation_id}")
async def agent_delete_conversation(conversation_id: str, user_id: str = Depends(get_current_user_id)):
    db = SessionLocal()
    try:
        conv = db.query(Conversation).filter(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        ).first()
        if not conv:
            raise HTTPException(status_code=404, detail="会话不存在")
        db.query(Message).filter(Message.conversation_id == conversation_id).delete()
        db.delete(conv)
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


@app.get("/api/agent/schedules")
async def agent_list_schedules(user_id: str = Depends(get_current_user_id)):
    db = SessionLocal()
    try:
        items = db.query(Schedule).filter(Schedule.user_id == user_id, Schedule.enabled == 1)\
            .order_by(Schedule.remind_at.asc()).all()
        return {"items": [{"id": s.id, "title": s.title, "content": s.content or "",
                           "remind_at": s.remind_at, "repeat": s.repeat} for s in items]}
    finally:
        db.close()


@app.post("/api/agent/schedules")
async def agent_create_schedule(request: Request, user_id: str = Depends(get_current_user_id)):
    body = await request.json()
    title = (body.get("title") or "").strip()
    remind_at = (body.get("remind_at") or "").strip()
    if not title or not remind_at:
        raise HTTPException(status_code=400, detail="标题和提醒时间不能为空")
    content = body.get("content") or ""
    repeat = body.get("repeat") or "none"
    sid = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.add(Schedule(id=sid, user_id=user_id, title=title, content=content or None,
                        remind_at=remind_at, repeat=repeat))
        db.commit()
        return {"status": "ok", "id": sid}
    finally:
        db.close()


@app.delete("/api/agent/schedules/{schedule_id}")
async def agent_delete_schedule(schedule_id: str, user_id: str = Depends(get_current_user_id)):
    db = SessionLocal()
    try:
        s = db.query(Schedule).filter(Schedule.id == schedule_id, Schedule.user_id == user_id).first()
        if not s:
            raise HTTPException(status_code=404, detail="提醒不存在")
        db.delete(s)
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


@app.post("/api/agent/upload_file")
async def agent_upload_file(file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件内容为空")
    fid = str(uuid.uuid4())
    ext = os.path.splitext(file.filename or "")[1].lower()
    path = os.path.join(AGENT_FILES_DIR, f"{fid}{ext}")
    with open(path, "wb") as f:
        f.write(content)
    return {"status": "ok", "file_id": fid, "filename": file.filename or ""}


@app.post("/api/agent/doc/parse")
async def agent_doc_parse(file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件内容为空")
    try:
        from . import doc_parser
        text = doc_parser.parse_document(content, file.filename or "")
    except Exception as e:
        logger.error(f"文档解析失败: {e}")
        raise HTTPException(status_code=500, detail=f"文档解析失败: {str(e)}")
    if not text.strip():
        raise HTTPException(status_code=400, detail="未能从文档中提取到文字内容")
    return {"status": "ok", "text": text, "filename": file.filename or ""}


@app.get("/api/agent/generated/{filename}")
async def agent_generated_download(filename: str, user_id: str = Depends(get_current_user_id)):
    gen_dir = os.path.join(DATA_DIR, "generated")
    path = os.path.join(gen_dir, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path, media_type="application/pdf", filename=filename)


@app.post("/api/agent/kb/extract_image")
async def agent_kb_extract_image(file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)):
    if not LLM_API_KEY:
        raise HTTPException(status_code=500, detail="未配置LLM API密钥")
    import base64
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="图片内容为空")
    b64 = base64.b64encode(content).decode()
    ext = os.path.splitext(file.filename or ".jpg")[1].lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".bmp": "image/bmp"}
    mime = mime_map.get(ext, "image/jpeg")
    import httpx
    prompt = """请仔细查看这张图片，提炼其中的关键信息，用简体中文、结构化要点形式整理输出。
若是票据/文档/截图，请尽量完整还原其中的重要文字信息并归类整理；若是照片，请概括主要内容。
直接输出整理后的文本内容，不要加任何解释性前缀或后缀。"""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            messages = [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
            ]}]
            resp = await client.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json={"model": LLM_MODEL, "messages": messages, "temperature": 0.2}
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"LLM API调用失败: {resp.status_code}")
            data = resp.json()
            text = (data["choices"][0]["message"]["content"] or "").strip()
            return {"status": "ok", "text": text}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image extract error: {e}")
        raise HTTPException(status_code=500, detail=f"图片信息抽取失败: {str(e)}")


@app.post("/api/agent/kb/upload")
async def agent_kb_upload(request: Request, user_id: str = Depends(get_current_user_id)):
    body = await request.json()
    title = (body.get("title") or "未命名文档").strip()
    content = body.get("content") or ""
    if not content.strip():
        raise HTTPException(status_code=400, detail="内容不能为空")
    from . import kb
    chunks = kb.chunk_text(content)
    if not chunks:
        raise HTTPException(status_code=400, detail="无法解析出有效内容")
    doc_id = str(uuid.uuid4())
    try:
        n = kb.add_chunks(user_id, DATA_DIR, doc_id, title, chunks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"知识库写入失败（embedding 模型未就绪？）: {e}")
    db = SessionLocal()
    try:
        db.add(Document(id=doc_id, user_id=user_id, title=title, content=content, chunk_count=n))
        db.commit()
    finally:
        db.close()
    return {"status": "ok", "id": doc_id, "chunk_count": n}


@app.get("/api/agent/kb/documents")
async def agent_kb_documents(user_id: str = Depends(get_current_user_id)):
    db = SessionLocal()
    try:
        docs = db.query(Document).filter(Document.user_id == user_id)\
            .order_by(Document.created_at.desc()).all()
        return {"items": [
            {"id": d.id, "title": d.title, "chunk_count": d.chunk_count,
             "created_at": d.created_at.strftime("%Y-%m-%d %H:%M:%S") if d.created_at else None}
            for d in docs
        ]}
    finally:
        db.close()


@app.delete("/api/agent/kb/documents/{doc_id}")
async def agent_kb_delete(doc_id: str, user_id: str = Depends(get_current_user_id)):
    db = SessionLocal()
    try:
        d = db.query(Document).filter(Document.id == doc_id, Document.user_id == user_id).first()
        if not d:
            raise HTTPException(status_code=404, detail="文档不存在")
        db.delete(d)
        db.commit()
    finally:
        db.close()
    try:
        from . import kb
        kb.delete_doc(user_id, DATA_DIR, doc_id)
    except Exception as e:
        logger.warning("删除向量失败: %s", e)
    return {"status": "ok"}


@app.get("/api/agent/notes")
async def agent_list_notes(user_id: str = Depends(get_current_user_id)):
    db = SessionLocal()
    try:
        items = db.query(Note).filter(Note.user_id == user_id)\
            .order_by(Note.note_date.desc(), Note.created_at.desc()).all()
        return {"items": [
            {"id": n.id, "title": n.title, "content": n.content or "",
             "date": n.note_date,
             "created_at": n.created_at.strftime("%Y-%m-%d %H:%M:%S") if n.created_at else None}
            for n in items
        ]}
    finally:
        db.close()


@app.post("/api/agent/notes")
async def agent_create_note(request: Request, user_id: str = Depends(get_current_user_id)):
    body = await request.json()
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="标题不能为空")
    content = body.get("content") or ""
    note_date = (body.get("date") or datetime.now().strftime("%Y-%m-%d")).strip()
    nid = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.add(Note(id=nid, user_id=user_id, title=title, content=content or None, note_date=note_date))
        db.commit()
        return {"status": "ok", "id": nid}
    finally:
        db.close()


@app.put("/api/agent/notes/{note_id}")
async def agent_update_note(note_id: str, request: Request, user_id: str = Depends(get_current_user_id)):
    body = await request.json()
    db = SessionLocal()
    try:
        n = db.query(Note).filter(Note.id == note_id, Note.user_id == user_id).first()
        if not n:
            raise HTTPException(status_code=404, detail="记录不存在")
        if "title" in body:
            n.title = (body["title"] or "").strip() or n.title
        if "content" in body:
            n.content = body["content"]
        if "date" in body:
            n.note_date = (body["date"] or n.note_date).strip()
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


@app.delete("/api/agent/notes/{note_id}")
async def agent_delete_note(note_id: str, user_id: str = Depends(get_current_user_id)):
    db = SessionLocal()
    try:
        n = db.query(Note).filter(Note.id == note_id, Note.user_id == user_id).first()
        if not n:
            raise HTTPException(status_code=404, detail="记录不存在")
        db.delete(n)
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


if os.path.exists(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
