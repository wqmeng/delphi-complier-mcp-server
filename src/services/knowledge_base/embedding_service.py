"""
Embedding 服务 —— 为知识库提供真语义搜索

使用 intfloat/multilingual-e5-small 模型：
- 中英双语支持
- 本地 CPU 运行，无 API 依赖
- 自动降级：模型未安装/加载失败时返回 None，调用方走兜底

模型约 70MB，首次加载约 1-2s，后续 <100ms
"""

import logging
import os
import site
import threading
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# numpy 是可选依赖 —— 未安装时不影响知识库基本功能，仅语义搜索降级为反转索引
np: Any = None  # type: ignore
numpy: Any = None  # type: ignore
try:
    import numpy  # noqa: F401
    import numpy as np
except ImportError:
    pass

# 确保用户 site-packages 在路径中（pip install 默认安装到用户目录）
if site.USER_SITE is not None:
    try:
        site.addsitedir(site.USER_SITE)
    except Exception:
        logger.debug("忽略非致命异常: site.addsitedir")

# 全局单例
_model = None
_model_name = "intfloat/multilingual-e5-small"
_MODEL_LOAD_TIMEOUT = 60  # 模型加载超时秒数（含下载）
_env_lock = threading.Lock()  # 保护 os.environ 的线程安全


def is_available() -> bool:
    """检查 embedding 依赖是否可用"""
    if np is None:
        return False
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


def is_model_loaded() -> bool:
    """检查模型是否已加载（仅用于搜索时的快速判断，不触发加载）"""
    return _model is not None


def load_model(timeout: int = None):
    """懒加载模型（全局单例），带超时保护。

    Args:
        timeout: 超时秒数，None 使用 _MODEL_LOAD_TIMEOUT 默认值。
            超时后返回 None，避免阻塞 MCP tool call。
    """
    global _model
    if _model is not None:
        return _model

    if timeout is None:
        timeout = _MODEL_LOAD_TIMEOUT

    from sentence_transformers import SentenceTransformer

    # 尝试多个镜像源
    # 用户可通过 HF_ENDPOINT 环境变量强制指定
    default_endpoint = os.environ.get("HF_ENDPOINT")
    _endpoints = []
    if default_endpoint:
        _endpoints = [default_endpoint]
    else:
        _endpoints = [
            None,  # huggingface.co（默认）
            "https://hf-mirror.com",
        ]

    # 保存原始环境变量，退出时恢复
    _saved_env = {
        'HF_ENDPOINT': os.environ.get('HF_ENDPOINT'),
        'TRANSFORMERS_OFFLINE': os.environ.get('TRANSFORMERS_OFFLINE'),
        'HF_HUB_OFFLINE': os.environ.get('HF_HUB_OFFLINE'),
    }

    def _restore_env():
        with _env_lock:
            for k, v in _saved_env.items():
                if v is not None:
                    os.environ[k] = v
                else:
                    os.environ.pop(k, None)

    def _try_load(endpoint):
        """尝试从指定 endpoint 加载模型（在子线程中运行，可被超时中断）"""
        result = [None]  # 用列表传递结果（线程间共享引用）
        error = [None]
        def _worker():
            try:
                if endpoint:
                    logger.info(f"加载 embedding 模型（镜像: {endpoint}）: {_model_name}")
                    with _env_lock:
                        os.environ["HF_ENDPOINT"] = endpoint
                else:
                    logger.info(f"加载 embedding 模型: {_model_name}")

                # 优先使用离线模式
                with _env_lock:
                    os.environ["TRANSFORMERS_OFFLINE"] = "1"
                    os.environ["HF_HUB_OFFLINE"] = "1"
                m = SentenceTransformer(_model_name, local_files_only=True)
                logger.info("embedding 模型加载完成（离线模式）")
                result[0] = m
                return
            except Exception as e:
                logger.warning(f"  镜像 {endpoint or 'default'} 离线加载失败: {e}，尝试联网下载...")
                with _env_lock:
                    os.environ.pop("TRANSFORMERS_OFFLINE", None)
                    os.environ.pop("HF_HUB_OFFLINE", None)
                try:
                    m = SentenceTransformer(_model_name, local_files_only=False)
                    logger.info("embedding 模型加载完成（联网模式）")
                    result[0] = m
                except Exception as e2:
                    logger.warning(f"  镜像 {endpoint or 'default'} 联网加载也失败: {e2}")
                    error[0] = e2

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        thread.join(timeout=timeout)
        if thread.is_alive():
            # 线程超时仍在运行（daemon 线程会在主进程退出时自动终止）
            logger.warning(f"加载 embedding 模型超时（{timeout}s），镜像 {endpoint or 'default'}")
            _restore_env()
            return None
        if result[0] is not None:
            _restore_env()
            return result[0]
        _restore_env()
        return None

    for ep in _endpoints:
        m = _try_load(ep)
        if m is not None:
            _model = m
            return _model

    logger.warning("所有镜像源均无法加载 embedding 模型（或加载超时）")
    return None


def encode_texts(texts: List[str], prefix: str = "query") -> Optional[Any]:
    """
    对文本列表进行编码，返回归一化的 embedding 数组

    Args:
        texts: 文本列表
        prefix: E5 前缀，query 搜索时用 "query"，入库时用 "passage"

    Returns:
        numpy.ndarray shape=(n, 384)，归一化后可直接点积算 cosine
        失败时返回 None
    """
    model = load_model()
    if model is None:
        return None

    try:
        prefixed = [f"{prefix}: {t}" for t in texts]
        # normalize_embeddings=True 确保输出已归一化，dot = cosine
        embeddings = model.encode(prefixed, normalize_embeddings=True, show_progress_bar=False)
        return np.array(embeddings, dtype=np.float32)
    except Exception as e:
        logger.warning(f"embedding 编码失败: {e}")
        return None


def encode_single(text: str, prefix: str = "query") -> Optional[Any]:
    """编码单个文本"""
    result = encode_texts([text], prefix=prefix)
    if result is not None:
        return result[0]
    return None


def cosine_similarity(query_emb: Any, db_embs: Any) -> Optional[Any]:
    """
    计算 query 与一批向量的余弦相似度

    Args:
        query_emb: (dim,) 归一化 query 向量
        db_embs: (n, dim) 归一化向量矩阵

    Returns:
        (n,) 相似度分数，numpy 不可用时返回 None
    """
    if np is None:
        return None
    # 已归一化 → dot = cosine
    return np.dot(db_embs, query_emb)


def blob_to_vector(blob: bytes) -> Optional[Any]:
    """SQLite BLOB → numpy 向量"""
    if np is None:
        return None
    try:
        return np.frombuffer(blob, dtype=np.float32)
    except Exception:
        return None


def batch_encode_and_store(cursor, rows, prefix: str = "passage") -> int:
    """
    批量编码 vocabularies 并写入 vector 列

    Args:
        cursor: SQLite cursor
        rows: [(id, name), ...] 待编码的 (vocab_id, name) 列表
        prefix: E5 前缀

    Returns:
        成功编码并写入的数量
    """
    if np is None:
        return 0

    if not rows:
        return 0

    names = [r[1] for r in rows]
    embs = encode_texts(names, prefix=prefix)
    if embs is None:
        return 0

    count = 0
    for (vid, _), vec in zip(rows, embs):
        if vec is not None and not np.all(vec == 0):
            blob = vec.tobytes()
            cursor.execute(
                "UPDATE vocabularies SET vector=?, vector_status='ready' WHERE id=?",
                (blob, vid)
            )
            count += 1
    return count
