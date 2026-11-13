# Day 06 · Data Ingestion Engineering

**Lab cá nhân** · **4 giờ** · **Dữ liệu tự chọn**

Biến tài liệu thành kho tri thức có thể truy xuất cho AI agent, rồi đo xem cách chuẩn bị dữ liệu nào hiệu quả nhất.

| 📄 Dữ liệu | 🧩 Chiến lược | 🎯 Benchmark |
|---|---|---|
| Tối thiểu **30 trang nội dung** | Tối thiểu **3 cấu hình** | Tối thiểu **20 câu hỏi** |

## Bắt đầu nhanh

Dùng [starter PostgreSQL + pgvector](starter/README.md) để dựng database và hoàn thiện các hàm TODO, hoặc tự chọn vector store tương đương. Starter chỉ là khung: **bạn tự hiện thực pipeline và benchmark**.

## 1. Xây pipeline

![Đọc tài liệu, chuẩn hóa, chia chunk, tạo vector, lưu và kiểm tra](assets/ingestion-pipeline.svg)

Chọn tài liệu được phép sử dụng; giữ **ID tài liệu, nguồn, trang/vị trí** và metadata phù hợp. Dùng embedding model thật qua API hoặc chạy local; lưu và truy xuất bằng pgvector, Qdrant, Chroma hoặc một store tương đương.

## 2. So sánh và đánh giá

![Ba chiến lược được đánh giá trên cùng corpus và benchmark dev/test](assets/benchmark-workflow.svg)

Dùng cùng dữ liệu, model và câu hỏi cho cả ba cấu hình. Tách **15 câu dev / 5 câu test** trước khi chạy; chọn cấu hình trên dev, rồi đánh giá test sau khi cố định. Mỗi câu hỏi cần có đoạn bằng chứng và trang nguồn; thiết kế bộ câu hỏi và đánh giá theo [BENCHMARK.md](BENCHMARK.md).

Đánh giá theo năm khía cạnh: **độ chính xác truy xuất**, **tính mạch lạc của chunk**, **tính hữu dụng của metadata**, **chất lượng grounding** và **tác động của chiến lược dữ liệu**. Giải thích lựa chọn bằng kết quả, ví dụ lỗi và các đánh đổi.

## 3. Chuẩn bị bài nộp

1. Chạy pipeline và lưu cấu hình, kết quả top-3, trace cùng nhãn đánh giá thủ công.
2. Điền [thông tin học viên](STUDENT.md), [nhật ký thí nghiệm](artifacts/experiment_log.csv) và bản sao [mẫu báo cáo cá nhân](report/individual/MSSV_HoTen.md).
3. Kiểm tra mã nguồn, cách chạy, manifest dữ liệu và checklist trong [SUBMISSION.md](SUBMISSION.md).

## Tài liệu hướng dẫn

| Bạn cần tìm | Tài liệu |
|---|---|
| Setup baseline PostgreSQL + pgvector | [starter/README.md](starter/README.md) |
| Các bước làm và cách tính chỉ số | [GUIDE.md](GUIDE.md) |
| Tiến độ trong 4 giờ | [CHECKPOINTS.md](CHECKPOINTS.md) |
| Năm tiêu chí benchmark và bộ câu hỏi | [BENCHMARK.md](BENCHMARK.md) |
| Tiêu chí chấm điểm | [RUBRIC.md](RUBRIC.md) |
| Quy tắc sử dụng dữ liệu, AI và API | [RULES.md](RULES.md) |
| Cách nộp bài | [SUBMISSION.md](SUBMISSION.md) |

[data/format-example.json](data/format-example.json) chỉ minh họa định dạng, không phải corpus đủ điều kiện. Phần xử lý và benchmark do bạn tự hiện thực; không bắt buộc xây chatbot.

---

## Bài làm của học viên: cách cài và chạy lại

Corpus: OpenStax *Introduction to Computer Science* (CC BY-NC-SA 4.0, chỉ dùng phi thương mại), Chương 1 và 3 (63 trang). File PDF (~56 MB) không nằm trong repo: tải tại <https://openstax.org/details/books/introduction-computer-science>, đặt tên `intro-cs.pdf` vào `starter/data/`. Nguồn, trang và quy tắc tính trang xem `starter/data/manifest.json`.

Chạy từ thư mục `starter/` (Windows PowerShell; cần Docker Desktop đang chạy, Python 3.11–3.14):

```powershell
python -m pip install -r requirements.txt
python -m pip install sentence-transformers==6.3.0   # embedding chạy trên máy, không cần API key
Copy-Item .env.example .env
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py                    # kỳ vọng: Setup OK
python scripts/verify_benchmark.py               # kiểm chứng evidence và split của benchmark
python -m src.run --splits dev                   # chỉ chạy dev
python -m src.run                                # chạy dev + test (chỉ sau khi chốt câu hỏi)
python scripts/make_audit_sheets.py              # tạo phiếu chấm thủ công trong starter/results/
```

- Benchmark: `benchmark/questions.json` (20 câu: 15 dev, 5 test; 5 câu có filter).
- Kết quả: `starter/results/` (`traces.jsonl`, `summary.json`, `chunk_stats.json`, `run_config.json`, `ingestion_log.json`, các phiếu `audit_*.csv`).
- Nhật ký thí nghiệm: `artifacts/experiment_log.csv`. Báo cáo: `report/individual/`.
- Embedding: `sentence-transformers/all-MiniLM-L6-v2` (384 chiều), chi phí 0. Vector store: PostgreSQL 16 + pgvector 0.8.7, cosine, tìm chính xác.

### Ghi nguồn và giấy phép dữ liệu
Nội dung sách do OpenStax (Rice University) tạo ra, theo giấy phép **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 (CC BY-NC-SA 4.0)**. **Access for free at openstax.org.** Nguồn: <https://openstax.org/details/books/introduction-computer-science>.
Repo này chỉ dùng cho **mục đích học tập, phi thương mại**. Repo không chứa file PDF gốc; các trích đoạn ngắn nằm trong `benchmark/questions.json` (đoạn evidence) và `starter/results/` (nội dung chunk trong trace, phiếu chấm) là bản trích/chuyển thể từ sách (đã chuẩn hóa khoảng trắng, loại header/footer), được chia sẻ lại theo cùng giấy phép CC BY-NC-SA 4.0. Tên và logo OpenStax/Rice University không thuộc phạm vi giấy phép.
