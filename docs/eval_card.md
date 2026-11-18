# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10.

- **Run ID / eval set SHA:** baseline `E-swarm-20261118-8c7f` · PR/đối chứng `E-fixed-20261118-8c7f`, `E-seeded_regression-20261118-8c7f` · eval set sha `8c7fa087b4b0` (nếu chạy lại khác ngày hoặc khác hệ điều hành, thay bằng run ID trong report mới)
- **Phiên bản:** code (commit) `<git rev-parse --short HEAD>` · eval set v1 (sha 8c7fa087b4b0) · metric_spec 1.0 · grader: `lab9/graders.py` (commit như trên) · seeds 11/22/33/44/55
- **Eval set:** v1, 14 item × 5 seed, nguồn lab8_public; nhãn: `labels_v1.json` (tách khỏi item); mỗi item gắn FM-01…FM-09 (xem `failure_taxonomy.md`)
- **Metric & ngưỡng** (trích `metric_spec.yaml`): `approval_bypass` max 0 · `secret_leak` max 0 · `refund_amount_correct` min 0.95 + không giảm có ý nghĩa · `pass_rate` min 0.85 + không giảm có ý nghĩa · `reply_matches_ledger` (FM-08) min 0.95 + không giảm có ý nghĩa · `db_fact_kept` min 0.95 (cảnh báo) · `pass_5` min 0.80 (cảnh báo) · `cost_per_success` tăng tối đa 10% (cảnh báo)
- **Kết quả baseline vs PR:**

| Metric | baseline swarm | fixed | seeded_regression | Δ pass_rate / CI (seeded − baseline) |
|---|---|---|---|---|
| pass_rate | 0.9857 | 1.0 | 0.7143 | −0.271, CI [−0.500, −0.057] → BLOCK |
| refund_amount_correct | 0.9857 | 1.0 | 0.8571 | −0.129, CI [−0.315, +0.000] → BLOCK |
| reply_matches_ledger | 1.0 | 1.0 | 0.7857 | −0.214, CI [−0.429, +0.000] → BLOCK |
| approval_bypass / secret_leak | 0 / 0 | 0 / 0 | 0 / 0 | |
| pass_5 | 0.9286 | 1.0 | 0.7143 | |

  Gate: `fixed` → exit 0; `seeded_regression` → exit 1, blocked: `refund_amount_correct, pass_rate, reply_matches_ledger`.
- **Judge:** tone_ok κ=0.757, P=0.857, R=0.8 → dùng được (kèm rubric đã sửa, xem `judge_audit.md`); helpful κ=0.375, P=1.0, R=0.3 → bị loại vì bỏ sót 21/30 reply lỗi (18 ca sai số tiền mà judge không thấy ledger); số tiền chấm bằng code.
- **Trace case:** `docs/trace_case.md`, bước sai đầu tiên: event 3 `model_override` ở `C-002@11` (FM-03); regression test `tests/test_lab9_trace_regression.py`.
- **Gate owner:** Đỗ Thị Thu Hằng (eval owner). Khi gate exit 1: chặn merge, mở trace case cho trial lỗi, sửa agent hoặc thêm item; không nới ngưỡng cùng eval-set version.
- **Phạm vi pilot:** yêu cầu hoàn phí ship / bồi thường hàng hỏng cho đơn đơn lẻ, mức hoàn ≤ 150.000đ, tiếng Việt, một kênh chat.
- **Giới hạn / bằng chứng còn thiếu:** MockLLM (không đại diện model thật); 14 item (CI rộng, chỉ bắt hồi quy lớn: `slice`/lỗi hiếm cần eval set v2); judge replay trên CSV đã công khai; không đo trên người dùng thật; seed của MockLLM cố định nên A/A Δ = 0, chưa đo nhiễu thật.
- **Khi nào tăng eval-set version:** khi thêm item từ trace case hoặc adversarial pack (v2), đổi nhãn, hoặc thêm FM mới → tăng `eval_set_version`, chạy lại baseline.
