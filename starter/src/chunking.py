"""Implement fixed-size and structure-aware chunking."""
import re

from .models import Chunk, DocumentPage


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Cắt văn bản thành các cửa sổ `size` ký tự, chồng lấn `overlap` ký tự."""
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("Cần size > 0 và 0 <= overlap < size")

    text = page.text
    step = size - overlap
    chunks: list[Chunk] = []
    for start in range(0, len(text), step):
        piece = text[start:start + size].strip()
        if piece:
            index = len(chunks)
            chunks.append(Chunk(
                chunk_id=f"{page.document_id}-p{page.page}-fixed{index}",
                document_id=page.document_id,
                source=page.source,
                page=page.page,
                text=piece,
                metadata={**page.metadata, "strategy": "fixed", "chunk_index": index},
            ))
        if start + size >= len(text): 
            break
    return chunks


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Gom các đoạn văn (ngăn bởi dòng trống) tới `max_size`; đoạn quá dài thì cắt theo câu."""
    if max_size <= 0:
        raise ValueError("max_size phải > 0")
    pieces: list[str] = []
    for paragraph in (p.strip() for p in page.text.split("\n\n")):
        if not paragraph:
            continue
        if len(paragraph) <= max_size:
            pieces.append(paragraph)
            continue
        current = ""
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
            for i in range(0, len(sentence), max_size):
                part = sentence[i:i + max_size]
                if current and len(current) + 1 + len(part) > max_size:
                    pieces.append(current)
                    current = part
                else:
                    current = f"{current} {part}".strip()
        if current:
            pieces.append(current)

    texts: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + 2 + len(piece) > max_size:
            texts.append(current)
            current = piece
        else:
            current = f"{current}\n\n{piece}" if current else piece
    if current:
        texts.append(current)

    return [
        Chunk(
            chunk_id=f"{page.document_id}-p{page.page}-paragraph{index}",
            document_id=page.document_id,
            source=page.source,
            page=page.page,
            text=text,
            metadata={**page.metadata, "strategy": "paragraph", "chunk_index": index},
        )
        for index, text in enumerate(texts)
    ]
