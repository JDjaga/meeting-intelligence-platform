"""Run evaluation: P/R/F1 explicit vs implicit + hallucination rate. Saves JSON + prints table."""
from __future__ import annotations
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.eval.evaluate import evaluate_file
from app.llm.extractor import extract_meeting

def run_fn(transcript: str) -> list[dict]:
    ext, _ = extract_meeting(transcript, provider="rules")
    return [a.model_dump() for a in ext.action_items]

def main():
    base = Path(__file__).resolve().parent.parent
    res = evaluate_file(base / "data" / "eval_gold.json", run_fn)
    out = base / "data" / "eval_results.json"
    out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"{'case':<18}{'type':<10}{'P':>7}{'R':>7}{'F1':>7}   hall")
    for cid, v in res["per_case"].items():
        for ct in ("explicit", "implicit", "overall"):
            m = v[ct]
            print(f"{cid:<18}{ct:<10}{m['precision']:>7.3f}{m['recall']:>7.3f}{m['f1']:>7.3f}   {v['hallucination_rate']:.3f}")
    print("\nMACRO:", json.dumps(res["macro"], indent=2))
    print("macro hallucination:", res["macro_hallucination_rate"])
    print(f"saved -> {out}")

if __name__ == "__main__":
    main()
