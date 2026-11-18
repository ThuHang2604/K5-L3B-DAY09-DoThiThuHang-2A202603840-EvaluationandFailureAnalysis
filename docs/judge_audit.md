# Judge audit

Chạy: `python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5` và `--csv data/eval/judge_helpful_public.csv`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Có (tp 24, fp 4, fn 6, tn 66) | **Dùng** (sau khi sửa rubric bên dưới) |
| helpful | 100 | 0.375 | 1.000 | 0.300 | **Không** (R và κ dưới sàn; tp 9, fp 0, fn 21, tn 70) | **Loại**, không dùng làm gate |

## ≥5 case audit thủ công (tone_ok)
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / sửa rubric |
|---|---|---|---|---|---|
| 1 | H-008 "Em đã hoàn tiền cho anh rồi nha…" | PASS | FAIL | Người | Xưng "em" + "nha" quá suồng sã. Rubric: bắt buộc xưng LogiX / anh-chị, cấm "em/bạn", "nha/nhé" |
| 2 | H-029 "…không cần nhắn thêm." | PASS | FAIL | Người | Giọng ra lệnh bị che bởi "Dạ, vui lòng". Rubric: câu mệnh lệnh / chặn phản hồi = FAIL dù có từ lịch sự |
| 3 | H-042 "Dạ, đơn O-808 đã hoàn 120.000đ…ạ." | FAIL | PASS | Người | Judge phạt "thiếu xin lỗi". Rubric: chỉ cần xin lỗi khi lỗi do LogiX; ngắn gọn có "Dạ…ạ" = PASS |
| 4 | H-051 "…đã refund 90.000đ…" | FAIL | PASS | Người | "refund" được CS LogiX cho phép. Rubric: thêm danh sách thuật ngữ cho phép |
| 5 | H-094 "Da, LogiX da hoan 40.000đ…" | PASS | FAIL | Người | Mất dấu tiếng Việt (dịch máy). Rubric: reply không dấu = FAIL |
| 6 | H-081 "…chưa đủ điều kiện hoàn…" | FAIL | PASS | **Judge** | Người đọc nhầm ticket (note trong CSV). Sửa nhãn người, nhờ người thứ hai chấm lại |
| 7 | H-088 "Dạ, dạ, LogiX đã hoàn…" | FAIL | PASS | Mơ hồ | Lặp "Dạ" là lỗi gõ, không phải giọng điệu. Rubric: tách lỗi chính tả khỏi tone_ok |

Mẫu lỗi: 6/10 bất đồng là judge dễ dãi với giọng suồng sã/ra lệnh (FN), 4/10 là judge khắt khe vô lý (FP). Rubric cần ví dụ PASS/FAIL cụ thể về xưng hô, thuật ngữ, dấu tiếng Việt.

## Kết luận
- **helpful bị loại.** Recall 0.30: judge bỏ sót 21/30 reply lỗi thật (ma trận nhầm lẫn: fn = 21). 18/21 là "sai tiền" (reply nói số khác ledger; judge không thấy ledger) và 3 là sai xưng hô; judge còn chuộng câu dài, nhiều lời xin lỗi (verbosity bias). Tỉ lệ lỗi quan sát 9% sau hiệu chỉnh Rogan-Gladen thành 30%: dùng judge này làm gate sẽ cho qua gần 2/3 lỗi. Số tiền thuộc về code: `reply_matches_ledger`.
- tone_ok qua sàn (κ 0.757, P 0.857, R 0.8) nhưng vẫn cần sửa rubric theo 7 case trên, rồi đo lại.
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật.
