"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []
    m_pr, m_base = pr.get("manifest", {}), base.get("manifest", {})
    rows, brows = pr.get("rows") or [], base.get("rows") or []

    # 1. no NaN / inf anywhere in the reported metrics (nan < min is False: a naive gate passes it)
    for k, v in (pr.get("metrics") or {}).items():
        if isinstance(v, float) and not math.isfinite(v):
            problems.append(f"metric {k} is {v} (NaN/inf is not a result)")

    # 2. grader crashes must not hide behind a green run
    if pr.get("evaluator_failures"):
        problems.append(f"{len(pr['evaluator_failures'])} evaluator failure(s), first: {pr['evaluator_failures'][0]}")

    # 3. row count and duplicates: manifest items x seeds
    want = int(m_pr.get("items", 0)) * len(m_pr.get("seeds") or [])
    if len(rows) != want:
        problems.append(f"{len(rows)} rows, manifest says {m_pr.get('items')} items x {len(m_pr.get('seeds') or [])} seeds = {want} "
                        "(dropped or duplicated rows)")
    pairs = [(r.get("item_id"), r.get("seed")) for r in rows]
    dup = sorted({str(x) for x in pairs if pairs.count(x) > 1})
    if dup:
        problems.append(f"duplicate (item, seed) rows: {', '.join(dup[:5])}")
    if sorted(map(str, {p[0] for p in pairs})) != sorted(map(str, {r.get("item_id") for r in brows})):
        problems.append("item set differs from the baseline's")
    if m_pr.get("seeds") != m_base.get("seeds"):
        problems.append(f"seeds {m_pr.get('seeds')} differ from the baseline's {m_base.get('seeds')}")

    # 4. the (item, seed) set must be the baseline's (cherry-picked seeds / items)
    if set(pairs) != {(r.get("item_id"), r.get("seed")) for r in brows}:
        miss = sorted({(r.get("item_id"), r.get("seed")) for r in brows} - set(pairs), key=str)
        extra = sorted(set(pairs) - {(r.get("item_id"), r.get("seed")) for r in brows}, key=str)
        problems.append(f"(item, seed) set differs from the baseline's: {len(miss)} missing, {len(extra)} extra")

    # 5. a graded spec metric may not be None in any row (a crashed grader drops out of the mean)
    graded = [m for m in (x["id"] for x in spec.get("metrics", [])) if any(m in r for r in rows + brows)]
    for m in graded:
        n_none = sum(1 for r in rows if r.get(m) is None)
        if n_none:
            problems.append(f"{n_none} row(s) with no value for graded metric {m} (grader crashed or row edited)")

    # 6. reported metrics must be what the rows say (a report whose headline was edited by hand)
    kind = {x["id"]: x.get("kind") for x in spec.get("metrics", [])}
    for m in graded:
        vals = [r[m] for r in rows if r.get(m) is not None]
        if not vals or m not in (pr.get("metrics") or {}) or not isinstance(pr["metrics"][m], (int, float)):
            continue
        calc = float(sum(vals)) if kind.get(m) == "safety" else sum(vals) / len(vals)
        if not math.isfinite(pr["metrics"][m]) or abs(calc - pr["metrics"][m]) > 1e-3:
            problems.append(f"metric {m} reported {pr['metrics'][m]} but the rows give {calc:.4f}")
    by_item: dict[str, list[bool]] = {}
    for r in rows:
        if r.get("pass_rate") is not None:
            by_item.setdefault(r["item_id"], []).append(bool(r["pass_rate"]))
    if by_item:
        for name, fn in (("pass_at", stats.pass_at_k), ("pass_hat", stats.pass_hat_k)):
            for k in spec.get("pass_k", []):
                got = (pr.get("metrics") or {}).get(f"{name}_{k}")
                if got is None or not by_item or min(len(v) for v in by_item.values()) < k:
                    continue
                calc = sum(fn(len(v), sum(v), k) for v in by_item.values()) / len(by_item)
                if not math.isfinite(got) or abs(calc - got) > 1e-3:
                    problems.append(f"metric {name}_{k} reported {got} but the rows give {calc:.4f}")

    # 7. slice tags must be the baseline's (relabelling an item out of a slice hides its regression)
    tags_base = {r["item_id"]: set(r.get("slices") or []) for r in brows}
    moved = sorted({r["item_id"] for r in rows if r["item_id"] in tags_base and set(r.get("slices") or []) != tags_base[r["item_id"]]})
    if moved:
        problems.append(f"slice tags changed vs the baseline for: {', '.join(moved[:5])}")

    # 8. ratchet: on the same eval-set version thresholds may only get stricter
    if base_spec is not None and base_spec.get("eval_set_version") == spec.get("eval_set_version"):
        problems += _ratchet(spec, base_spec)
    return problems


def _loosened(new: dict, old: dict, label: str) -> list[str]:
    """Threshold-level ratchet for one metric or slice. `new` / `old` are the spec entries."""
    out: list[str] = []
    nt, ot = new.get("threshold", new) or {}, old.get("threshold", old) or {}
    for key in ("min",):
        if key in ot and (key not in nt or nt[key] < ot[key]):
            out.append(f"{label}: min {ot[key]} -> {nt.get(key)} (looser)")
    for key in ("max", "max_increase"):
        if key in ot and (key not in nt or nt[key] > ot[key]):
            out.append(f"{label}: {key} {ot[key]} -> {nt.get(key)} (looser)")
    if ot.get("no_significant_drop") and not nt.get("no_significant_drop"):
        out.append(f"{label}: no_significant_drop removed")
    if old.get("blocking") and not new.get("blocking"):
        out.append(f"{label}: blocking -> non-blocking")
    return out


def _ratchet(spec: dict, base_spec: dict) -> list[str]:
    out: list[str] = []
    new_m = {m["id"]: m for m in spec.get("metrics", [])}
    for om in base_spec.get("metrics", []):
        if om["id"] not in new_m:
            out.append(f"metric {om['id']} removed from the spec")
        else:
            out += _loosened(new_m[om["id"]], om, f"metric {om['id']}")
    new_s = {s["name"]: s for s in spec.get("slices") or []}
    for os_ in base_spec.get("slices") or []:
        if os_["name"] not in new_s:
            out.append(f"slice {os_['name']} removed from the spec")
        else:
            ns = new_s[os_["name"]]
            if ns.get("metric") != os_.get("metric"):
                out.append(f"slice {os_['name']}: metric {os_.get('metric')} -> {ns.get('metric')}")
            for key in ("min",):
                if key in os_ and (key not in ns or ns[key] < os_[key]):
                    out.append(f"slice {os_['name']}: min {os_[key]} -> {ns.get(key)} (looser)")
            if os_.get("no_significant_drop") and not ns.get("no_significant_drop"):
                out.append(f"slice {os_['name']}: no_significant_drop removed")
            if os_.get("blocking") and not ns.get("blocking"):
                out.append(f"slice {os_['name']}: blocking -> non-blocking")
    return out


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})
    for sl in spec.get("slices") or []:
        name, metric = sl["name"], sl["metric"]
        a = per_item(pr, metric, slice_name=name)
        b = per_item(base, metric, slice_name=name)
        bid = f"slice:{name}/{metric}"
        verdict, note, val = "ok", "", None
        if not a:
            verdict, note = "fail", "no items in this slice (relabelled or dropped?)"
        else:
            val = round(sum(a.values()) / len(a), 4)
            if "min" in sl and val < sl["min"]:
                verdict = "fail"
            if sl.get("no_significant_drop"):
                keys = sorted(set(a) & set(b))
                if keys:
                    d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                       n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
                    note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}] n={len(keys)}"
                    if hi < 0:
                        verdict = "fail"
        if verdict != "ok" and sl.get("blocking"):
            blocked.append(bid)
        label = "ok" if verdict == "ok" else ("BLOCK" if sl.get("blocking") else "warn")
        th = {k: sl[k] for k in ("min", "no_significant_drop") if k in sl}
        lines.append(f"  {bid:<34} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
