"""Lưu và tìm vector bằng PostgreSQL + pgvector (tìm chính xác, không dùng index xấp xỉ)."""
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from .models import Chunk

# Chỉ cho phép lọc theo các cột này (tên cột không bao giờ lấy trực tiếp từ người dùng).
ALLOWED_FILTERS = {"category", "language", "document_id", "source", "page"}


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        """Giữ thông tin kết nối và số chiều vector của embedding model."""
        if not database_url:
            raise ValueError("Thiếu DATABASE_URL")
        if dimensions <= 0:
            raise ValueError("dimensions phải > 0")
        self.database_url = database_url
        self.dimensions = dimensions

    def create_schema(self) -> None:
        """Tạo bảng chunks (nếu chưa có) và kiểm tra số chiều khớp với bảng đang có."""
        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS chunks (
                        strategy    TEXT NOT NULL,
                        chunk_id    TEXT NOT NULL,
                        document_id TEXT NOT NULL,
                        source      TEXT NOT NULL,
                        page        INTEGER NOT NULL,
                        category    TEXT,
                        language    TEXT,
                        content     TEXT NOT NULL,
                        metadata    JSONB NOT NULL DEFAULT '{{}}',
                        embedding   vector({int(self.dimensions)}) NOT NULL,
                        PRIMARY KEY (strategy, chunk_id)
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS chunks_filter_idx "
                    "ON chunks (strategy, category)"
                )
                # Với kiểu vector, atttypmod chính là số chiều của cột.
                cursor.execute(
                    "SELECT atttypmod FROM pg_attribute "
                    "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
                )
                stored = cursor.fetchone()[0]
                if stored != self.dimensions:
                    raise ValueError(
                        f"Bảng chunks có vector {stored} chiều, nhưng model là {self.dimensions} chiều. "
                        "Dùng cùng một model cho mọi chiến lược (không tự xóa dữ liệu)."
                    )

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Ghi chunk theo ID ổn định (chạy lại không nhân đôi) và xóa chunk cũ không còn nữa."""
        if len(chunks) != len(vectors):
            raise ValueError(f"Số chunk ({len(chunks)}) khác số vector ({len(vectors)})")

        rows = []
        for chunk, vector in zip(chunks, vectors):
            if len(vector) != self.dimensions:
                raise ValueError(
                    f"Vector của {chunk.chunk_id} có {len(vector)} chiều, cần {self.dimensions}"
                )
            rows.append((
                strategy, chunk.chunk_id, chunk.document_id, chunk.source, chunk.page,
                chunk.metadata.get("category"), chunk.metadata.get("language"),
                chunk.text, Jsonb(chunk.metadata),
                "[" + ",".join(str(x) for x in vector) + "]",
            ))

        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO chunks (strategy, chunk_id, document_id, source, page,
                                        category, language, content, metadata, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                    ON CONFLICT (strategy, chunk_id) DO UPDATE SET
                        document_id = EXCLUDED.document_id, source = EXCLUDED.source,
                        page = EXCLUDED.page, category = EXCLUDED.category,
                        language = EXCLUDED.language, content = EXCLUDED.content,
                        metadata = EXCLUDED.metadata, embedding = EXCLUDED.embedding
                    """,
                    rows,
                )
                # Tài liệu đổi: xóa chunk cũ của cùng tài liệu mà lần nạp này không còn tạo ra.
                for document_id in {chunk.document_id for chunk in chunks}:
                    keep = [c.chunk_id for c in chunks if c.document_id == document_id]
                    cursor.execute(
                        "DELETE FROM chunks WHERE strategy = %s AND document_id = %s "
                        "AND NOT (chunk_id = ANY(%s))",
                        (strategy, document_id, keep),
                    )

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Lọc metadata trong SQL, xếp theo cosine, trả về top_k kết quả (score = 1 - khoảng cách)."""
        if len(query_vector) != self.dimensions:
            raise ValueError(
                f"Vector câu hỏi có {len(query_vector)} chiều, cần {self.dimensions}"
            )

        conditions = ["strategy = %s"]
        params: list[Any] = [strategy]
        for column, value in (filters or {}).items():
            if column not in ALLOWED_FILTERS:
                raise ValueError(f"Không được lọc theo '{column}'. Cho phép: {sorted(ALLOWED_FILTERS)}")
            conditions.append(f"{column} = %s")  # tên cột đã nằm trong danh sách cho phép
            params.append(value)

        vector_text = "[" + ",".join(str(x) for x in query_vector) + "]"
        sql = (
            "SELECT chunk_id, document_id, source, page, content, metadata, "
            "1 - (embedding <=> %s::vector) AS score "
            "FROM chunks WHERE " + " AND ".join(conditions) + " "
            "ORDER BY embedding <=> %s::vector LIMIT %s"
        )
        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, [vector_text, *params, vector_text, top_k])
                rows = cursor.fetchall()

        return [
            {
                "chunk_id": chunk_id, "document_id": document_id, "source": source,
                "page": page, "text": content, "score": float(score), "metadata": metadata,
            }
            for chunk_id, document_id, source, page, content, metadata, score in rows
        ]
