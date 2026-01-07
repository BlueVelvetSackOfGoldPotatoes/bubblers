from __future__ import annotations

import hashlib
import math
import uuid
from datetime import datetime, timezone
from typing import Iterable, List


def now_iso_utc() -> str:
    dt = datetime.now(timezone.utc)
    s = dt.isoformat()
    if s.endswith("+00:00"):
        s = s[:-6] + "Z"
    return s


def new_id() -> str:
    return str(uuid.uuid4())


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def l2_norm(v: List[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    denom = l2_norm(a) * l2_norm(b)
    if denom == 0.0:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / denom


def mean_vector(vectors: Iterable[List[float]], dim: int) -> List[float]:
    acc = [0.0] * dim
    n = 0
    for v in vectors:
        n += 1
        for i in range(dim):
            acc[i] += v[i]
    if n == 0:
        return acc
    return [x / n for x in acc]
