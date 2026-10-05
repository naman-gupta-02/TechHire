"""AI job summary as a LangGraph graph: 3 models in parallel → synthesis.

            ┌─► draft (gpt-oss-120b) ─┐
    START ──┼─► draft (qwen3.8-27b)  ─┼─► collect ─┬─► synthesize ──► END   (≥2 drafts ok)
            └─► draft (gpt-oss-20b)  ─┘            ├─► use_single ──► END   (exactly 1 ok)
                                                   └─► fail ────────► END   (none ok)

What the graph buys over the previous `asyncio.gather` + synthesis call:
  - Partial failure is a routing decision, not an exception. gather() raised
    if any one model failed, so a single retired model (Groq has removed
    models this project depended on before — every call 404'd) took the
    whole endpoint down. Now each draft node records its own error, and
    `route` picks a path based on how many drafts actually succeeded.
  - Fan-out is data: `fan_out` emits one `Send` per entry in VARIANTS,
    so adding a fourth model is a list edit, not new control flow.
  - `drafts` uses an `operator.add` reducer, so the parallel branches
    append to one list instead of overwriting each other's state.
  - The final state is a trace: which models ran, how long each took,
    which failed and why, and which path produced the summary. The API
    returns it alongside the summary.
"""
import operator
import time
from typing import Annotated, Optional, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from ai.llm import LLM

SYSTEM = (
    "You are a concise career advisor helping CS Masters students and new grad "
    "engineers quickly evaluate job postings. Write clearly, avoid filler phrases "
    "like 'this is a great opportunity', and always include concrete details "
    "(tech stack, salary, experience requirements if mentioned). "
    "Output only the requested paragraphs — no headers, no bullet points, no preamble."
)

# Three different models (all free on Groq), each prompted from a different
# angle so their drafts disagree in useful ways.
VARIANTS = [
    (
        "openai/gpt-oss-120b",      # best quality — role & day-to-day
        "Summarize this job in exactly 3 short paragraphs for a CS Masters student:\n"
        "Paragraph 1: What the company does and what this role is about.\n"
        "Paragraph 2: What you will actually build or do day-to-day, and the tech stack.\n"
        "Paragraph 3: What they require — years of experience and must-have skills.\n"
        "Be specific. No filler.",
    ),
    (
        "qwen/qwen3.8-27b",         # different model — fit & growth angle
        "Summarize this job in exactly 3 short paragraphs:\n"
        "Paragraph 1: What makes this company and role interesting — product, scale, or mission.\n"
        "Paragraph 2: What a typical week looks like — responsibilities and tech used.\n"
        "Paragraph 3: Who is the ideal candidate — skills, background, experience level. "
        "Mention salary and visa if available.\n"
        "Keep it tight.",
    ),
    (
        "openai/gpt-oss-20b",       # fastest — practical / student-focused
        "Summarize this job posting in exactly 3 short paragraphs for someone deciding whether to apply:\n"
        "Paragraph 1: One-sentence pitch — role + company + why it matters.\n"
        "Paragraph 2: The core technical work and stack they will use.\n"
        "Paragraph 3: Requirements and what you get — salary, remote/hybrid, visa, perks.\n"
        "Be direct. Students want facts, not marketing.",
    ),
]

SYNTHESIS_MODEL = "openai/gpt-oss-120b"

SYNTHESIS_PROMPT = (
    "Several AI models each summarized the same job posting from a different angle. "
    "Read all the summaries, then write the single best 3-paragraph summary that combines "
    "the strongest, most specific information from each:\n\n"
    "Paragraph 1: Company context and what this role is (2-3 sentences).\n"
    "Paragraph 2: Day-to-day work, tech stack, and what you will build.\n"
    "Paragraph 3: Requirements (skills, experience level) and compensation "
    "(salary, visa sponsorship, work mode).\n\n"
    "Rules: include actual numbers and tech names from the originals. No filler. "
    "Output only the 3 paragraphs separated by blank lines — nothing else."
)


class Draft(TypedDict):
    model: str
    text: Optional[str]
    error: Optional[str]
    seconds: float


class SummaryState(TypedDict, total=False):
    context: str
    drafts: Annotated[list[Draft], operator.add]
    summary: str
    strategy: str   # "synthesized" | "single_draft" | "failed"
    error: str


class DraftTask(TypedDict):
    """Payload each `Send` hands to one draft branch."""
    context: str
    model: str
    prompt: str


def _ok(drafts: list[Draft]) -> list[Draft]:
    return [d for d in drafts if d["text"]]


def build_summary_graph(llm: LLM, variants=VARIANTS, synthesis_model: str = SYNTHESIS_MODEL):
    def fan_out(state: SummaryState) -> list[Send]:
        return [Send("draft", DraftTask(context=state["context"], model=m, prompt=p))
                for m, p in variants]

    async def draft(task: DraftTask) -> dict:
        t0 = time.perf_counter()
        try:
            text = await llm(task["model"], [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"{task['prompt']}\n\n---JOB---\n{task['context']}"},
            ], 600, 0.4)
            if not text:
                raise ValueError("empty response")
            result = Draft(model=task["model"], text=text, error=None, seconds=0.0)
        except Exception as e:  # recorded, not raised — `route` decides what happens next
            result = Draft(model=task["model"], text=None, error=f"{type(e).__name__}: {e}"[:300], seconds=0.0)
        result["seconds"] = round(time.perf_counter() - t0, 2)
        return {"drafts": [result]}

    def collect(state: SummaryState) -> dict:
        return {}

    def route(state: SummaryState) -> str:
        n = len(_ok(state.get("drafts", [])))
        return "synthesize" if n >= 2 else "use_single" if n == 1 else "fail"

    async def synthesize(state: SummaryState) -> dict:
        ok = _ok(state["drafts"])
        numbered = "\n\n".join(f"[Model {i + 1} — {d['model']}]\n{d['text']}" for i, d in enumerate(ok))
        try:
            text = await llm(synthesis_model, [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": (
                    f"{SYNTHESIS_PROMPT}\n\n"
                    f"--- MODEL SUMMARIES ---\n{numbered}\n\n"
                    f"--- ORIGINAL JOB (reference) ---\n{state['context'][:1500]}"
                )},
            ], 800, 0.3)
        except Exception:
            text = ""
        if not text:
            # Synthesis failing shouldn't throw away good drafts: fall back
            # to the first successful one (VARIANTS order = preference order).
            return {"summary": ok[0]["text"], "strategy": "single_draft"}
        return {"summary": text, "strategy": "synthesized"}

    def use_single(state: SummaryState) -> dict:
        return {"summary": _ok(state["drafts"])[0]["text"], "strategy": "single_draft"}

    def fail(state: SummaryState) -> dict:
        errors = "; ".join(f"{d['model']}: {d['error']}" for d in state.get("drafts", []))
        return {"summary": "", "strategy": "failed", "error": errors}

    g = StateGraph(SummaryState)
    g.add_node("draft", draft)
    g.add_node("collect", collect)
    g.add_node("synthesize", synthesize)
    g.add_node("use_single", use_single)
    g.add_node("fail", fail)
    g.add_conditional_edges(START, fan_out, ["draft"])
    # Fan-in barrier. A conditional edge straight off "draft" would be
    # evaluated once *per branch*, each seeing only its own draft — the
    # first branch to finish would route to use_single with 1 of 3 drafts.
    # A plain edge into a no-op node instead fires once, in the next
    # superstep, after every parallel draft has written to state.
    g.add_edge("draft", "collect")
    g.add_conditional_edges("collect", route, ["synthesize", "use_single", "fail"])
    g.add_edge("synthesize", END)
    g.add_edge("use_single", END)
    g.add_edge("fail", END)
    return g.compile()
