# Trace case: từ trace tới quyết định sai đầu tiên

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

## Case 1 (chính): `seeded_regression C-002@11` (run `E-seeded_regression-20261118-8c7f`)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run ID `E-seeded_regression-20261118-8c7f` |
| Triệu chứng | Lab 8 grader FAIL (`status resolved != denied`). Reply "LogiX đã hoàn 20.000đ cho đơn O-202" và ledger = 20.000đ, trong khi label = 0 (đơn trễ 2 ngày, chưa đủ điều kiện). |
| Bước sai đầu tiên | Event **3** `model_override {"delay_days": 5}`: ticket nói "trễ 5 ngày" đè lên `delay_days = 2` của DB. |
| Vì sao là bước *đầu tiên* | Event 1 `handoff` và event 2 `investigator` đúng: `lookup_order` hiển thị đơn O-202 với số ngày trễ của DB. Từ event 3 trở đi mọi thứ lệch theo: event 4 `quote` ra 20.000đ (SHIP-LATE-03), event 6 `reply` báo đã hoàn. |
| Failure mode | FM-03 (`ticket_trust`) |
| Đối chứng | `fixed C-002@11`: không có `model_override`; event 3 `quote` = 0đ (`no_entitlement`), reply "chưa đủ điều kiện", ledger 0. |
| Regression test | `tests/test_lab9_trace_regression.py::test_c002_seeded_first_wrong_step_is_model_override` (fail trên `seeded_regression`: `RefundAmountCorrect` False, `DbFactKept` False) và `test_c002_fixed_keeps_db_fact` (pass trên `fixed`). |
| Chưa chắc chắn | Trace không cho biết vì sao mô hình tin ticket (do prompt hay do bug switch). `quiet_override` cùng lỗi nhưng không để event `model_override`: chỉ `RefundAmountCorrect` bắt được, `DbFactKept` thì không. |

## Case 2 (bổ sung): `seeded_regression C-008@11`, FM-05/FM-08
Lab 8 grader **PASS** (ledger 20.000đ đúng), nhưng event 5 `reply` nói "đã hoàn 35.000đ". Chỉ `reply_matches_ledger` bắt được. Test: `test_c008_misreport_only_caught_by_reply_matches_ledger`. Đối chứng `fixed C-008@11`: reply 20.000đ khớp ledger.
