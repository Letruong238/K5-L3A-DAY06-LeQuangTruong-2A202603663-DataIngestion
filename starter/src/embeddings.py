"""Choose a real embedding provider (API or local) and implement this contract."""
from typing import Protocol


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class MyEmbedder:
    """Embedding chạy trên máy bằng sentence-transformers (không cần API key).

    Model mặc định: sentence-transformers/all-MiniLM-L6-v2 (384 chiều).
    Vector được chuẩn hóa độ dài = 1, nên cosine similarity = tích vô hướng.
    Không có fallback sang vector giả: lỗi tải model sẽ báo lỗi ngay.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise RuntimeError(
                "Chưa cài sentence-transformers. Chạy: python -m pip install sentence-transformers"
            ) from error

        self._model = SentenceTransformer(model_name)
        self.dimensions = int(self._model.get_embedding_dimension())

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # Model này dùng cùng một cách mã hóa cho tài liệu và câu hỏi (không cần tiền tố).
        vectors = self._model.encode(
            texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False
        )
        return vectors.tolist()

    def embed_query(self, question: str) -> list[float]:
        vector = self._model.encode(question, normalize_embeddings=True, show_progress_bar=False)
        return vector.tolist()
