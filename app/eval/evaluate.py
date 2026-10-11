"""Evaluation: precision / recall / F1 split by explicit vs implicit + hallucination rate.

Matching: a predicted action counts as TP if its normalized text overlaps a gold
action (token-F1 >= 0.5) AND commitment_type matches (for the split metrics).
Hallucination: predicted item whose evidence is NOT a verbatim transcript substring.
"""
from __future__ import annotations
import json
import re
from pathlib import Path


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def _overlap(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    return 2 * inter / (len(ta) + len(tb))


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3),
            "tp": tp, "fp": fp, "fn": fn}


def evaluate_case(transcript: str, gold: list[dict], pred: list[dict]) -> dict:
    out: dict = {}
    for ctype in ("explicit", "implicit"):
        g = [x for x in gold if x.get("commitment_type") == ctype]
        p = [x for x in pred if x.get("commitment_type") == ctype]
        used = set()
        tp = 0
        for gg in g:
            hit = next((i for i, pp in enumerate(p)
                        if i not in used and _overlap(gg.get("action", ""), pp.get("action", "")) >= 0.5), None)
            if hit is not None:
                used.add(hit)
                tp += 1
        out[ctype] = prf(tp, len(p) - tp, len(g) - tp)
    # micro overall
    tps = sum(v["tp"] for v in out.values())
    fps = sum(v["fp"] for v in out.values())
    fns = sum(v["fn"] for v in out.values())
    out["overall"] = prf(tps, fps, fns)
    # hallucination rate
    t_norm = " ".join(transcript.lower().split())
    hall = sum(1 for pp in pred if " ".join(str(pp.get("evidence", "")).lower().split()) not in t_norm)
    out["hallucination_rate"] = round(hall / len(pred), 3) if pred else 0.0
    out["n_pred"], out["n_gold"] = len(pred), len(gold)
    return out


def evaluate_file(gold_path: str | Path, run_fn) -> dict:
    """run_fn(transcript) -> list[dict] predicted action dicts."""
    items = json.loads(Path(gold_path).read_text(encoding="utf-8"))
    per_case, agg_g, agg_p = {}, [], []
    for case in items:
        pred = run_fn(case["transcript"])
        per_case[case["id"]] = evaluate_case(case["transcript"], case["gold_actions"], pred)
        agg_g += [{**g, "_t": case["transcript"]} for g in case["gold_actions"]]
        agg_p += [{**p, "_t": case["transcript"]} for p in pred]
    # aggregate by pooling per-type matching across all transcripts is complex;
    # report macro average instead (mean of per-case scores).
    def _macro(key, metric):
        vals = [v[key][metric] for v in per_case.values()]
        return round(sum(vals) / len(vals), 3) if vals else 0.0
    macro = {ct: {m: _macro(ct, m) for m in ("precision", "recall", "f1")}
             for ct in ("explicit", "implicit", "overall")}
    macro_hall = round(sum(v["hallucination_rate"] for v in per_case.values()) / len(per_case), 3) if per_case else 0.0
    return {"per_case": per_case, "macro": macro, "macro_hallucination_rate": macro_hall}
