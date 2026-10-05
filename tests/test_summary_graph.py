"""The summary graph's routing, exercised with a fake LLM — no Groq calls."""
import asyncio
import time

from ai.summary_graph import SYNTHESIS_MODEL, VARIANTS, build_summary_graph

MODELS = [m for m, _ in VARIANTS]


def fake_llm(fail=(), synth_fails=False, delay=0.2, calls=None):
    calls = calls if calls is not None else []

    async def llm(model, messages, max_tokens, temperature):
        is_synth = "MODEL SUMMARIES" in messages[-1]["content"]
        calls.append("synth" if is_synth else model)
        await asyncio.sleep(delay)
        if is_synth:
            if synth_fails:
                raise RuntimeError("synthesis model down")
            return "SYNTHESIZED"
        if model in fail:
            raise RuntimeError("404 model_decommissioned")
        return f"draft:{model}"
    return llm


def run(llm):
    return asyncio.run(build_summary_graph(llm).ainvoke({"context": "a job"}))


def test_all_drafts_ok_synthesizes_once():
    calls = []
    out = run(fake_llm(calls=calls))
    assert out["strategy"] == "synthesized"
    assert out["summary"] == "SYNTHESIZED"
    assert sorted(c for c in calls if c != "synth") == sorted(MODELS)
    assert calls.count("synth") == 1  # the fan-in barrier fires once, not per branch


def test_drafts_run_in_parallel():
    t0 = time.perf_counter()
    run(fake_llm(delay=0.3))
    # 3 parallel drafts (0.3s) + synthesis (0.3s) ≈ 0.6s; sequential would be 1.2s.
    assert time.perf_counter() - t0 < 1.0


def test_one_model_down_still_synthesizes_from_the_rest():
    calls = []
    out = run(fake_llm(fail=(MODELS[1],), calls=calls))
    assert out["strategy"] == "synthesized"
    failed = [d for d in out["drafts"] if d["error"]]
    assert [d["model"] for d in failed] == [MODELS[1]]
    assert "404" in failed[0]["error"]


def test_only_one_draft_ok_skips_synthesis():
    calls = []
    out = run(fake_llm(fail=MODELS[1:], calls=calls))
    assert out["strategy"] == "single_draft"
    assert out["summary"] == f"draft:{MODELS[0]}"
    assert "synth" not in calls


def test_all_models_down_fails_with_every_error():
    out = run(fake_llm(fail=MODELS))
    assert out["strategy"] == "failed"
    assert out["summary"] == ""
    for m in MODELS:
        assert m in out["error"]


def test_synthesis_failure_falls_back_to_a_draft():
    out = run(fake_llm(synth_fails=True))
    assert out["strategy"] == "single_draft"
    assert out["summary"].startswith("draft:")


def test_empty_model_output_counts_as_failure():
    async def llm(model, messages, max_tokens, temperature):
        if "MODEL SUMMARIES" in messages[-1]["content"]:
            return "SYNTHESIZED"
        return "" if model == MODELS[0] else f"draft:{model}"
    out = run(llm)
    assert {d["model"]: d["error"] for d in out["drafts"]}[MODELS[0]] == "ValueError: empty response"


def test_synthesis_uses_the_configured_model():
    seen = []

    async def llm(model, messages, max_tokens, temperature):
        if "MODEL SUMMARIES" in messages[-1]["content"]:
            seen.append(model)
        return "ok"
    run(llm)
    assert seen == [SYNTHESIS_MODEL]
