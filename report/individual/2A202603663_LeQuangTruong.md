# Báo cáo cá nhân — Day 6

## Dữ liệu và pipeline
- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:** truy xuất thông tin cho hỏi đáp về nhập môn Khoa học máy tính. Nguồn: sách *Introduction to Computer Science* (OpenStax, Rice University), giấy phép **CC BY-NC-SA 4.0** (ghi công, chỉ dùng phi thương mại, chia sẻ tương tự; xác nhận ở trang bản quyền PDF trang 4), bản `WEB.pdf` 939 trang vật lý, truy cập 2026-11-13. Bài làm chỉ dùng cho học tập; các trích đoạn trong repo (evidence, nội dung chunk trong trace) được ghi nguồn "Access for free at openstax.org" và chia sẻ lại theo cùng giấy phép (xem `README.md`). Dùng Chương 1 (PDF trang 19–42, 24 trang, 78.694 ký tự) và Chương 3 (PDF trang 99–137, 39 trang, 123.158 ký tự): **63 trang nội dung, 201.852 ký tự** sau chuẩn hóa. Quy tắc: trang PDF = trang in + 10; bỏ trang Chapter Review và mọi trang ngoài phạm vi (xem `starter/data/manifest.json`). File PDF không đưa vào repo (xem README để tải lại).
- **Chuẩn hóa, lỗi và giới hạn:** `pypdf` đọc từng trang; chuẩn hóa Unicode NFC và khoảng trắng; loại dòng header/footer lặp của sách (`Access for free at openstax.org`, số trang kèm tên chương) bằng regex. Ranh giới đoạn **suy ra bằng heuristic** (dòng ngắn kết thúc bằng dấu câu, dòng bắt đầu bằng `•` hoặc `Figure N.N` mở khối mới) vì PDF không có dòng trống giữa đoạn. Kết quả: 0 trang rỗng, 0 lỗi đọc (`starter/results/ingestion_log.json`). Giới hạn: heuristic có thể sai ở vài chỗ (ví dụ danh sách đánh số bị tách giữa hai chunk); chú thích hình, chú thích cuối trang và URL vẫn nằm trong văn bản; công thức toán đôi khi mất khi trích PDF; hai dòng ở trang mở đầu chương chưa lọc; không dùng OCR.
- **Embedding, vector store, metric, lệnh chạy, chi phí:** `sentence-transformers/all-MiniLM-L6-v2` chạy trên CPU, **384 chiều**, vector chuẩn hóa độ dài 1, tài liệu và câu hỏi mã hóa cùng cách. `sentence-transformers` 6.3.0, `torch` 2.15.0, `psycopg` 3.3.8, `pypdf` 6.21.4, Python 3.13.15, Windows 11. Vector store: PostgreSQL 16.16 + pgvector 0.8.7 (Docker), **cosine, tìm chính xác** (không dùng index xấp xỉ). Lệnh cài và chạy: xem mục "Bài làm của học viên" trong `README.md`. Chi phí: **0 USD** (không dùng API trả phí). Cấu hình đầy đủ: `starter/results/run_config.json`.
- **Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn:** bắt buộc `document_id`, `source`, `page` (số trang PDF vật lý). Trường lọc: `category` (`chapter_1` / `chapter_3`, lấy từ manifest). Lý do: hai chương có chủ đề khác nhau nhưng cùng chia sẻ một số khái niệm (algorithm, binary search, Turing), nên lọc theo chương phân biệt được phạm vi. Có thêm `language` (`en` cho toàn bộ corpus) — **không hữu ích để lọc** vì chỉ có một giá trị. Hạn chế: `category` chỉ chia được hai nhóm lớn, không phân biệt mục nhỏ trong chương.

## Cấu hình và benchmark
- **A / B / C:**
  - A: `fixed_size`, 500 ký tự, chồng 50, không lọc.
  - B: `by_paragraph`, tối đa 800 ký tự (gom các đoạn, đoạn quá dài cắt theo câu), không lọc.
  - C: **giống hệt B** (dùng lại chính chỉ mục của B), khác duy nhất là lọc theo `category` khi câu hỏi có filter; câu không có filter thì chạy không lọc.
- **≥20 câu:** `benchmark/questions.json`, 20 câu: **15 dev (q01–q15) / 5 test (q16–q20)**, chia trước khi chạy; trang gold của dev và test **không trùng** nhau. Có **5 câu filter** (3 dev, 2 test); giá trị filter là ngữ cảnh người dùng cung cấp trước, không nằm trong câu hỏi. Loại câu: trực tiếp 5, diễn đạt lại 6, điều kiện 4, lọc metadata 5. Kiểm chứng evidence: `starter/scripts/verify_benchmark.py` xác nhận mỗi đoạn evidence xuất hiện ở trang gold sau chuẩn hóa và không trùng ở trang khác. Câu hỏi được soạn nháp với sự hỗ trợ của AI (xem mục công cụ AI).
- **Tiêu chí chọn chiến lược (chốt trước khi xem test):** Evidence Hit@3 trên dev, sau đó Hit@1, sau đó grounding thủ công, sau đó tài nguyên (số chunk, thời gian). Lưu ý: grounding chỉ được chấm trên tập test nên trên dev tiêu chí chỉ phân biệt được đến Hit@1; phần còn lại xử lý ở mục Kết luận.
- **Về tập test:** chạy một lần (2026-11-13 18:30) cùng lần chạy dev. Sau khi xem kết quả test, **không** sửa cấu hình, code truy xuất hay câu hỏi.

## Kết quả

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian ingest | Chi phí |
|---|---|---|---|---|---|---|
| A | dev | 7/15 | 11/15 | 475 | 4,58 s | 0 |
| A | test | 3/5 | 4/5 | 475 | | 0 |
| B | dev | 10/15 | 14/15 | 355 | 4,51 s | 0 |
| B | test | 2/5 | 4/5 | 355 | | 0 |
| C | dev | 10/15 | 14/15 | 355 (dùng chỉ mục B) | 0 thêm | 0 |
| C | test | 3/5 | 5/5 | 355 (dùng chỉ mục B) | | 0 |

Thời gian ingest = tạo chunk + embedding + ghi database (CPU, một lần chạy). Thời gian truy vấn trung bình (embedding câu hỏi + tìm kiếm, 20 câu): A 24,8 ms, B 24,0 ms, C 23,7 ms. Độ dài chunk: A trung bình 468 ký tự (5 chunk dưới 100 ký tự), B trung bình 567 ký tự (2 chunk dưới 100 ký tự). Nạp lại cùng dữ liệu không nhân đôi: A 475 → 475, B 355 → 355 dòng.

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N hoặc N/A) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| A | 1,0 (n = 10) | 15/15 | test 1/2 (dev 3/3) | 0 / 1 / 4 — 1,8 |
| B | 1,9 (n = 10) | 15/15 | test 1/2 (dev 1/3) | 0 / 1 / 4 — 1,8 |
| C | = B (dùng cùng chunk, n = 10) | 15/15 | test 2/2 (dev 3/3) | 0 / 0 / 5 — 2,0 |

Metadata: 5 câu test × top-3 = 15 bản ghi mỗi chiến lược (45 bản ghi tổng), mọi bản ghi có `source`, `page`, `category` khớp nguồn. Filter tuân thủ của A và B chỉ là "top-3 có tình cờ nằm đúng chương hay không" (chúng không áp dụng filter).

Đường dẫn: trace `starter/results/traces.jsonl`; thống kê `summary.json`, `chunk_stats.json`, `run_config.json`; nhãn `starter/results/audit_coherence.csv` (10 vị trí chọn cố định trước khi xem điểm: trang thứ `i*63//10` trong danh sách trang đã sắp xếp, i = 0..9; vị trí là đoạn chứa điểm giữa trang), `audit_metadata.csv`, `audit_grounding.csv` (cột `labeled_by` ghi rõ nguồn từng nhãn).

## Phân tích và kết luận
- **So sánh A–B (đổi cách chunk):** trên dev, B cao hơn A (Hit@1 10/15 so với 7/15; Hit@3 14/15 so với 11/15). Trên test kết quả lẫn lộn: Hit@3 bằng nhau (4/5) và Hit@1 của A cao hơn B (3/5 so với 2/5). Chênh lệch chỉ từ một đến ba câu nên **không đủ kết luận B tốt hơn A về truy xuất**. Khác biệt rõ nhất là **coherence nháp: A 1,0/2 so với B 1,9/2**: mọi chunk cố định ở mẫu đều bị cắt giữa từ hoặc giữa câu, còn chunk theo đoạn hầu hết trọn ý. Về tài nguyên, B ít chunk hơn (355 so với 475) và thời gian ingest gần như bằng nhau (4,5 giây).
- **So sánh B–C (chỉ thêm filter):** C bằng B ở dev (10/15, 14/15) và hơn B một câu ở test (Hit@3 5/5 so với 4/5; Hit@1 3/5 so với 2/5). Khác biệt đó đến từ q16. Top-3 theo filter: C luôn tuân thủ (dev 3/3, test 2/2), B chỉ 1/3 và 1/2.
- **Hai ví dụ sai:**
  1. **q16 ("How does binary search locate a number?", nguồn ocs-ch1 trang 20, filter chapter_1), A và B:** top-3 toàn Chương 3 (trang 111, 127, 103) vì binary search được giải thích ở cả hai chương và A/B không có filter; C lọc `chapter_1` nên top-1 đúng trang 20. Grounding A và B chấm 1 vì phạm vi sai chương dù ý đúng.
  2. **q20 ("What does experimental analysis ... measure?", nguồn ocs-ch3 trang 115), B và C:** top-1 đúng trang 115 nhưng là đoạn khác (đoạn về performance bugs); câu evidence nằm ở top-2. Hit@3 bắt được, Hit@1 thì không. Tương tự A ở q18 (trang 130): top-1 là chunk 500 ký tự bị cắt nên thiếu câu evidence.
- **Chiến lược chọn, đánh đổi, điều kiện áp dụng:** B và C **hòa trên dev** (14/15 và 10/15), nên tiêu chí đã chốt không tách được hai cấu hình; mình không dùng test để chọn. Dựa trên hai điều kiện áp dụng, đề xuất **C khi có filter đáng tin** (ngữ cảnh chương rõ ràng) vì không tốn thêm chunk hay thời gian và đảm bảo top-3 đúng phạm vi; **B khi không có filter**. **A chỉ nên giữ làm baseline** vì chunk bị cắt giữa ý (coherence nháp 1,0/2), dù Hit@3 test tương đương B. Đánh đổi của C: cần giá trị filter biết trước; nếu người dùng chọn sai chương thì C loại bỏ luôn câu trả lời đúng. Kết luận này chỉ áp dụng cho corpus này, không suy rộng.
- **Metadata hữu ích ở đâu:** `source` và `page` cho phép đối chiếu từng kết quả với PDF (45/45 khớp) và hiển thị nguồn khi trả lời; `category` làm top-3 tuân thủ phạm vi (C 2/2 so với B 1/2). Hạn chế: kiểm tra 45/45 chỉ cho thấy metadata **nhất quán với PDF**, không chứng minh nó đủ để chọn đúng đáp án; `category` chỉ có hai giá trị nên chỉ phân biệt ở mức chương; `language` vô dụng khi corpus một ngôn ngữ.
- **Hạn chế:** (1) test chỉ 5 câu, mỗi câu đổi 20 điểm phần trăm, filter chỉ 2 câu; (2) corpus một cuốn sách tiếng Anh, model embedding nhỏ; (3) ranh giới đoạn là heuristic; (4) nhãn coherence và grounding là nháp do AI đề xuất, không chấm mù (nhìn thấy chunk bị cắt là biết thuộc A), mẫu coherence chỉ 10 vị trí nên điểm A–B bị phóng đại bởi cách chọn vị trí; (5) grounding gần như bão hòa (top-3 hầu như luôn chứa câu trả lời) nên khó phân biệt chiến lược; (6) đo thời gian trên một máy, một lần chạy; (7) Hit@3 đo chunk chứa đủ evidence nhưng evidence bị tách qua hai chunk bị tính là lỗi (như q03).
- **Nếu làm lại hoặc mở rộng:** tăng số câu test và đa dạng loại câu; chấm coherence mù bởi người thứ hai; thêm trường lọc mịn hơn (mục/section); thử model đa ngữ lớn hơn và hybrid với BM25; cải thiện việc không tách danh sách đánh số khỏi đoạn dẫn.

## Công cụ AI và cách kiểm tra
Dùng Claude Code (trợ lý lập trình AI) để hỗ trợ viết code các hàm trong `starter/src/`, soạn nháp bộ câu hỏi, khung báo cáo và nhãn nháp coherence/grounding. Cách kiểm tra: chạy từng bước trên dữ liệu thật; `verify_benchmark.py` kiểm chứng evidence và split; thử `store.py` trên database thật (nạp lại không nhân đôi, lọc đúng, chặn tên cột lạ; khi tài liệu đổi từ 3 chunk còn 1 chunk thì 2 chunk cũ bị xóa và tài liệu khác không bị đụng tới); thử logic chấm `evaluation.py` bằng dữ liệu giả **chỉ để kiểm tra logic, không dùng làm kết quả**; metadata được đối chiếu với PDF bằng code. Nhãn coherence và grounding là nháp của AI, tôi phải xem lại và chịu trách nhiệm.
