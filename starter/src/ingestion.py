"""Read and normalize source data."""
from pathlib import Path
from .models import DocumentPage
import re
import unicodedata

_FOOTER = re.compile(
    r"^(Access for free at openstax\.org"
    r"|\d+\s+\d+ • .+"            
    r"|\d+\.\d+ • .+\s\d+)$"      
)
_NEW_BLOCK = re.compile(r"^(•|Figure \d+\.\d+)")
_PARAGRAPH_END = (".", "!", "?", ":", ")", '"', "”")


def load_pdf(
    path: Path,
    document_id: str,
    source: str,
    pages: list[int] | None = None,
    metadata: dict | None = None,
) -> list[DocumentPage]:
    """Đọc từng trang vật lý của PDF, giữ số trang và nguồn.

    - pages: danh sách số trang PDF (đếm từ 1) cần đọc; None = đọc hết.
    - metadata: thông tin chung gắn vào mọi trang (ví dụ category, language).
    - Loại dòng header/footer; giữ ranh giới đoạn bằng dòng trống ("\\n\\n").
    - Trang không có chữ được đánh dấu metadata["empty"] = True (không bỏ qua im lặng).
    """
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    total = len(reader.pages)
    wanted = pages if pages is not None else list(range(1, total + 1))

    result: list[DocumentPage] = []
    for page_no in wanted:
        if not 1 <= page_no <= total:
            raise ValueError(f"Trang {page_no} nằm ngoài PDF ({total} trang)")
        raw = reader.pages[page_no - 1].extract_text() or ""

        lines = [line.strip() for line in raw.split("\n")]
        lines = [line for line in lines if line and not _FOOTER.match(line)]

        max_len = max((len(line) for line in lines), default=0)
        paragraphs: list[str] = []
        current: list[str] = []
        for line in lines:
            if current and _NEW_BLOCK.match(line):
                paragraphs.append("\n".join(current))
                current = []
            current.append(line)
            if line.endswith(_PARAGRAPH_END) and len(line) < 0.85 * max_len:
                paragraphs.append("\n".join(current))
                current = []
        if current:
            paragraphs.append("\n".join(current))

        text = normalize_text("\n\n".join(paragraphs))
        result.append(
            DocumentPage(
                document_id=document_id,
                source=source,
                page=page_no,
                text=text,
                metadata={**(metadata or {}), "empty": not text, "char_count": len(text)},
            )
        )
    return result


def normalize_text(text: str) -> str:
    """Chuẩn hóa Unicode và khoảng trắng; giữ dòng trống làm ranh giới đoạn."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
