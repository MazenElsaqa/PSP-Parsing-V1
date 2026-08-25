from __future__ import annotations

import hashlib
from pathlib import Path


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def document_id(path: Path) -> str:
    return f"doc_{file_sha256(path)[:12]}"


def element_id(doc_id: str, page: int, kind: str, index: int) -> str:
    return f"{doc_id}_p{page:03d}_{kind}_{index:03d}"
