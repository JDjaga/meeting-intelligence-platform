"""Smoke tests: structured outputs, evidence grounding, review routing, eval."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.llm.extractor import extract_meeting

T = open(Path(__file__).parent.parent / "data" / "sample_transcripts" / "sprint_planning.txt").read()

def test_structured_and_grounded():
    ext, _ = extract_meeting(T, title="t", meeting_date="2026-10-03", provider="rules")
    assert ext.action_items, "should extract actions"
    assert any(a.commitment_type == "explicit" for a in ext.action_items)
    assert any(a.commitment_type == "implicit" for a in ext.action_items)
    t = " ".join(T.lower().split())
    for a in ext.action_items:
        assert " ".join(a.evidence.lower().split()) in t, f"evidence not grounded: {a.evidence}"
        assert 0.0 <= a.confidence <= 1.0

def test_review_routing():
    ext, _ = extract_meeting(T, provider="rules")
    low = [a for a in ext.action_items if a.confidence < 0.60]
    assert low and all(a.needs_review for a in low)

def test_eval_runs():
    from app.eval.evaluate import evaluate_case
    ext, _ = extract_meeting(T, provider="rules")
    pred = [a.model_dump() for a in ext.action_items]
    gold = [{"action": "finish the schema migration", "commitment_type": "explicit"}]
    r = evaluate_case(T, gold, pred)
    assert r["explicit"]["f1"] > 0 and r["hallucination_rate"] == 0.0
