"""Knowledge base: self-hosted embedding (BGE) + ChromaDB. Lazy heavy imports."""
import os
import logging
from typing import List

logger = logging.getLogger("agent.kb")

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

_embedder = None


def _load_embedder():
    global _embedder
    if _embedder is not None:
        return _embedder
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        logger.error("sentence-transformers 未安装，知识库不可用: %s", e)
        return None
    model_name = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
    try:
        _embedder = SentenceTransformer(model_name)
        logger.info("embedding 模型已加载: %s", model_name)
    except Exception as e:
        logger.error("embedding 模型加载失败: %s", e)
        _embedder = None
    return _embedder


def is_ready() -> bool:
    return _embedder is not None


def embed_texts(texts: List[str]) -> List[List[float]]:
    model = _load_embedder()
    if model is None:
        raise RuntimeError("embedding 模型不可用，请安装 sentence-transformers 并确保可下载模型")
    vecs = model.encode(texts, normalize_embeddings=True)
    return vecs.tolist()


def _get_client(data_dir: str):
    import chromadb
    return chromadb.PersistentClient(path=os.path.join(data_dir, "chroma"))


def get_collection(user_id: str, data_dir: str):
    client = _get_client(data_dir)
    return client.get_or_create_collection(f"kb_{user_id}")


def add_chunks(user_id: str, data_dir: str, doc_id: str, title: str, chunks: List[str]) -> int:
    if not chunks:
        return 0
    vecs = embed_texts(chunks)
    coll = get_collection(user_id, data_dir)
    ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
    metadatas = [{"doc_id": doc_id, "title": title or "", "idx": i} for i in range(len(chunks))]
    coll.upsert(ids=ids, documents=chunks, embeddings=vecs, metadatas=metadatas)
    return len(chunks)


def search(user_id: str, data_dir: str, query: str, top_k: int = 5) -> List[dict]:
    vec = embed_texts([query])
    coll = get_collection(user_id, data_dir)
    res = coll.query(query_embeddings=vec, n_results=top_k, include=["documents", "metadatas"])
    docs = res.get("documents") or [[]]
    metas = res.get("metadatas") or [[]]
    out: List[dict] = []
    for i, doc in enumerate(docs[0]):
        meta = (metas[0][i] if i < len(metas[0]) else {}) or {}
        out.append({"title": meta.get("title", ""), "content": doc})
    return out


def delete_doc(user_id: str, data_dir: str, doc_id: str):
    coll = get_collection(user_id, data_dir)
    coll.delete(where={"doc_id": doc_id})


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    text = (text or "").replace("\r\n", "\n").strip()
    if not text:
        return []
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: List[str] = []
    buf = ""
    for para in paragraphs:
        if len(buf) + len(para) + 1 <= chunk_size:
            buf = (buf + "\n" + para).strip() if buf else para
        else:
            if buf:
                chunks.append(buf)
            buf = para
            while len(buf) > chunk_size:
                chunks.append(buf[:chunk_size])
                buf = buf[chunk_size - overlap:]
    if buf:
        chunks.append(buf)
    return chunks