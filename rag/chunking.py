"""Turn one job posting into retrievable chunks.

Strategy — structure-aware, not fixed-size:

1. A "profile" chunk built from the structured columns (title, company,
   level, location, salary, visa, skills). Queries like "remote senior Rust
   roles with visa sponsorship" match facts that often never appear in the
   prose at all.
2. The description is split on its own section headings ("About the team",
   "What you'll do", "Minimum requirements", ...), so a chunk never
   straddles two unrelated sections.
3. Each section is packed paragraph-by-paragraph into ~TARGET_WORDS chunks,
   falling back to sentence and then word splits only for paragraphs too
   long to fit. Consecutive chunks of the same section overlap by
   OVERLAP_WORDS so a requirement split across the boundary is still
   retrievable from either side.
4. Boilerplate is dropped, two ways:
   - legal text (EEO, accommodations, background checks, ...) by regex, on
     both headings and paragraphs;
   - company template text by frequency: any paragraph that appears
     verbatim in >= TEMPLATE_MIN_POSTINGS postings (e.g. the same 650-word
     "Life at Palantir" section on ~190 Palantir jobs). It says nothing
     about the specific role, and left in, a culture-ish query returns 190
     copies of one paragraph as its top-k. See find_template_paragraphs().
5. Every chunk gets a contextual header ("<title> at <company> — <section>")
   prepended before embedding, so a passage like "you'll own the ingestion
   pipeline" still carries which job and which part of the job it's from.

Pure functions only — no DB, no model — so it's unit-testable and the
eval script can re-run it with different parameters.
"""
import html
import re
from dataclasses import dataclass

# Bump when chunking logic changes: it's part of each job's content hash,
# so the indexer knows to re-chunk and re-embed everything.
CHUNKER_VERSION = "sections-v1"

TARGET_WORDS = 180   # bge-small truncates at 512 tokens; 180 words + header
MAX_WORDS = 250      # is ~300 tokens, well clear of that limit.
OVERLAP_WORDS = 40
TEMPLATE_MIN_POSTINGS = 10
MIN_SECTION_WORDS = 25   # smaller sections merge into the next one

# Short descriptions (e.g. Lever/JSearch rows) often carry the substance in
# the parsed list columns instead. For long ones the lists were extracted
# *from* the description, so appending them would index the same sentences
# twice and double their weight in retrieval.
SHORT_DESCRIPTION_WORDS = 150

_BOILERPLATE = re.compile(
    r"equal (employment )?opportunity|affirmative action|do(es)? not discriminate|"
    r"without regard to (race|sex|age|religion)|reasonable accommodation|"
    r"accommodations? (for|to) (applicants|individuals|candidates) with disabilit|"
    r"background checks?|arrest (and|or) conviction|export[- ]control|e-verify|"
    r"(applicant|candidate) privacy|privacy (notice|policy)|non-compliant|"
    r"malicious actors|recruit(ment|ing) (fraud|scams?)",
    re.IGNORECASE,
)
_BULLET = re.compile(r"^\s*(?:[-*•·◦▪]|\d+[.)])\s*")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


@dataclass(frozen=True)
class Chunk:
    index: int
    section: str
    body: str      # the passage itself — shown to users as a citation
    content: str   # header + body — what gets embedded / full-text indexed


def _words(text: str) -> int:
    return len(text.split())


def _clean(text: str) -> str:
    text = html.unescape(text or "").replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n\s*", "\n\n", text).strip()


def _para_key(para: str) -> str:
    return re.sub(r"\W+", " ", para).strip().lower()


def _paragraphs(description: str) -> list[str]:
    return [p.strip() for p in _clean(description).split("\n\n") if p.strip()]


def find_template_paragraphs(descriptions, min_postings: int = TEMPLATE_MIN_POSTINGS) -> frozenset[str]:
    """Keys of paragraphs that occur in >= min_postings distinct postings.
    Short lines (headings, one-word bullets) are exempt — "Responsibilities"
    appearing everywhere is structure, not template text."""
    from collections import Counter
    counts: Counter = Counter()
    for desc in descriptions:
        counts.update({_para_key(p) for p in _paragraphs(desc or "") if _words(p) >= 12})
    return frozenset(k for k, n in counts.items() if n >= min_postings)


def _is_heading(para: str) -> bool:
    """A heading is a short standalone line that isn't a bullet and doesn't
    end like a sentence — e.g. "What you'll do", "MINIMUM REQUIREMENTS:"."""
    if "\n" in para or _BULLET.match(para):
        return False
    stripped = para.rstrip(":").strip()
    return 0 < _words(stripped) <= 8 and not re.search(r"[.!?,;]$", stripped)


def split_sections(description: str, template: frozenset[str] = frozenset()) -> list[tuple[str, list[str]]]:
    """[(heading, [paragraph, ...]), ...] in document order. Paragraphs
    under no heading go into an "Overview" section; everything under a
    boilerplate heading ("Applicant privacy policy") is dropped."""
    sections: list[tuple[str, list[str]]] = []
    heading, paras, skipping = "Overview", [], False
    for para in _paragraphs(description):
        if _BULLET.sub("", para).strip() == "":
            continue  # empty bullets ("- ") are common in scraped HTML
        if _is_heading(para):
            if paras and not skipping:
                sections.append((heading, paras))
            heading, paras = para.rstrip(":").strip(), []
            skipping = bool(_BOILERPLATE.search(heading))
            continue
        if _BOILERPLATE.search(para) or _para_key(para) in template:
            continue
        paras.append(para)
    if paras and not skipping:
        sections.append((heading, paras))

    # Merge tiny sections forward: a 10-word "About the team" blurb carries
    # too little signal to be its own vector.
    merged: list[tuple[str, list[str]]] = []
    carry: list[str] = []
    for i, (head, ps) in enumerate(sections):
        ps = carry + ps
        if _words(" ".join(ps)) < MIN_SECTION_WORDS and i < len(sections) - 1:
            carry = ps
            continue
        carry = []
        merged.append((head, ps))
    return merged


def _split_long(para: str) -> list[str]:
    """Break a paragraph over MAX_WORDS into sentence groups, then hard
    word windows if a single "sentence" is still too long (e.g. a giant
    comma-separated tech list with no full stops)."""
    if _words(para) <= MAX_WORDS:
        return [para]
    out, cur = [], []
    for sent in _SENTENCE_END.split(para):
        if cur and _words(" ".join(cur + [sent])) > TARGET_WORDS:
            out.append(" ".join(cur))
            cur = []
        cur.append(sent)
    if cur:
        out.append(" ".join(cur))
    final = []
    for piece in out:
        w = piece.split()
        final.extend(" ".join(w[i:i + MAX_WORDS]) for i in range(0, len(w), MAX_WORDS))
    return final


def pack_paragraphs(paras: list[str]) -> list[str]:
    """Greedy-pack paragraphs into chunks of ~TARGET_WORDS, overlapping
    consecutive chunks by the last OVERLAP_WORDS words of the previous one."""
    pieces = [p for para in paras for p in _split_long(para)]
    chunks: list[str] = []
    cur: list[str] = []
    for piece in pieces:
        if cur and _words("\n".join(cur + [piece])) > TARGET_WORDS:
            chunks.append("\n".join(cur))
            tail = " ".join(chunks[-1].split()[-OVERLAP_WORDS:])
            cur = [f"… {tail}"]
        cur.append(piece)
    if cur:
        chunks.append("\n".join(cur))
    return chunks


def _profile_text(job) -> str:
    parts = [f"{job.title} at {job.company}."]
    facts = []
    if job.experience_level:
        facts.append(f"Level: {job.experience_level}")
    if job.job_type:
        facts.append(f"Type: {job.job_type}")
    if job.work_mode:
        facts.append(f"Work mode: {job.work_mode}")
    loc = ", ".join(x for x in [job.city, job.state, job.country] if x)
    if loc:
        facts.append(f"Location: {loc}")
    if job.salary_min or job.salary_max:
        lo = f"${int(job.salary_min):,}" if job.salary_min else "?"
        hi = f"${int(job.salary_max):,}" if job.salary_max else "?"
        facts.append(f"Salary: {lo}–{hi} per {(job.salary_period or 'year').lower()}")
    if job.visa_sponsorship is True:
        facts.append("Visa sponsorship: yes")
    elif job.visa_sponsorship is False:
        facts.append("Visa sponsorship: no")
    if job.start_date_text:
        facts.append(f"Start: {job.start_date_text}")
    if facts:
        parts.append(". ".join(facts) + ".")
    if job.required_skills:
        parts.append("Skills: " + ", ".join(job.required_skills[:25]) + ".")
    return " ".join(parts)


def chunk_job(job, template: frozenset[str] = frozenset()) -> list[Chunk]:
    """`job` is anything with JobListing's attributes (ORM row or a stub);
    `template` comes from find_template_paragraphs() over the corpus."""
    sections = split_sections(job.description or "", template)

    if _words(job.description or "") < SHORT_DESCRIPTION_WORDS:
        for heading, items in (
            ("Responsibilities", job.responsibilities),
            ("Qualifications", job.qualifications),
            ("Benefits", job.benefits),
        ):
            items = [i for i in (items or []) if i and i.strip()]
            if items:
                sections.append((heading, [f"- {i.strip()}" for i in items]))

    header = f"{job.title} at {job.company}"
    chunks = [Chunk(0, "Profile", _profile_text(job), _profile_text(job))]
    for heading, paras in sections:
        for body in pack_paragraphs(paras):
            chunks.append(Chunk(
                index=len(chunks),
                section=heading[:120],
                body=body,
                content=f"{header} — {heading}\n{body}",
            ))
    return chunks
