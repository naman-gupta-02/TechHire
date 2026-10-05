"""Citation handling and the answer graph's retry loop, with a fake LLM and
a fake retriever — no Groq, no database."""
import asyncio

import pytest

from ai.answer_graph import (
    ABSTAIN_TOKEN, MAX_ATTEMPTS, NOT_FOUND_MESSAGE,
    build_answer_graph, normalize_citations, parse_citations, validate,
)

SOURCES = [
    {"job_id": 1, "title": "ML Engineer", "company": "Stripe", "section": "Responsibilities", "body": "Fraud models."},
    {"job_id": 2, "title": "Data Scientist", "company": "Coinbase", "section": "Requirements", "body": "SQL, Python."},
]


@pytest.mark.parametrize("raw, expected", [
    ("A [1]. B [2].", [1, 2]),
    ("A [1, 2] and [2][1]", [1, 2]),
    ("A [1, 2]", [1, 2]),          # narrow no-break space, seen from gpt-oss
    ("no citations", []),
])
def test_parse_citations(raw, expected):
    assert parse_citations(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("A【1】【2】", "A[1][2]"),
    ("A【1†L3-L5】", "A[1]"),
    ("A【1, 2】", "A[1, 2]"),
    ("A［1，2］", "A[1, 2]"),
    ("already [1]", "already [1]"),
])
def test_normalize_native_citation_styles(raw, expected):
    assert normalize_citations(raw) == expected


def test_validate():
    assert validate("Fraud work [1].", 2) == ([1], [])
    assert validate(ABSTAIN_TOKEN, 2) == ([], [])
    cited, problems = validate("Made up [3].", 2)
    assert cited == [] and "do not exist" in problems[0]
    _, problems = validate("No sources at all.", 2)
    assert "cites no sources" in problems[0]


def scripted_llm(replies, calls):
    """Returns each reply in turn; raises if a reply is an Exception."""
    async def llm(model, messages, max_tokens, temperature):
        calls.append(messages)
        reply = replies[len(calls) - 1]
        if isinstance(reply, Exception):
            raise reply
        return reply
    return llm


def ask(replies, sources=SOURCES):
    calls = []
    graph = build_answer_graph(scripted_llm(replies, calls), lambda q: sources)
    return asyncio.run(graph.ainvoke({"question": "Who does fraud ML?"})), calls


def test_valid_answer_passes_first_time():
    state, calls = ask(["Stripe's ML Engineer builds fraud models [1]."])
    assert state["status"] == "answered"
    assert state["cited"] == [1]
    assert len(calls) == 1


def test_invalid_citation_triggers_one_retry_with_feedback():
    state, calls = ask(["Fraud at Stripe [7].", "Fraud at Stripe [1]."])
    assert state["status"] == "answered"
    assert state["attempts"] == 2
    feedback = calls[1][-1]["content"]
    assert "[7]" in feedback and "do not exist" in feedback
    assert calls[1][-2] == {"role": "assistant", "content": "Fraud at Stripe [7]."}


def test_still_invalid_after_max_attempts_is_flagged_ungrounded():
    state, calls = ask(["No citations."] * MAX_ATTEMPTS)
    assert state["status"] == "ungrounded"
    assert len(calls) == MAX_ATTEMPTS


def test_native_citations_are_accepted_without_retry():
    state, calls = ask(["Stripe does fraud ML【1】."])
    assert state["status"] == "answered"
    assert state["answer"] == "Stripe does fraud ML[1]."
    assert len(calls) == 1


def test_abstention():
    state, _ = ask([ABSTAIN_TOKEN])
    assert state["status"] == "abstained"
    assert state["answer"] == NOT_FOUND_MESSAGE


def test_nothing_retrieved_skips_the_llm():
    state, calls = ask([], sources=[])
    assert state["status"] == "no_results"
    assert calls == []


def test_llm_error_ends_in_error_status_instead_of_raising():
    state, calls = ask([RuntimeError("429 rate limit")])
    assert state["status"] == "error"
    assert "429" in state["error"]
    assert len(calls) == 1
