from types import SimpleNamespace

from rag.chunking import (
    MAX_WORDS, OVERLAP_WORDS, TARGET_WORDS, SHORT_DESCRIPTION_WORDS,
    chunk_job, find_template_paragraphs, pack_paragraphs, split_sections,
)


def job(**overrides):
    defaults = dict(
        title="Backend Engineer", company="Acme", description="", responsibilities=None,
        qualifications=None, benefits=None, required_skills=["python", "postgres"],
        experience_level="mid", job_type="FULLTIME", work_mode="remote", city="Austin",
        state="TX", country="US", salary_min=150000, salary_max=190000, salary_period="YEAR",
        visa_sponsorship=True, start_date_text=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def sentence(n, word="lorem"):
    return " ".join([word] * (n - 1)) + " end."


DESCRIPTION = f"""About the team

{sentence(90, "platform")}

What you'll do:

- Build APIs in Go and Python for {sentence(20, "billing")}
- Own the ingestion pipeline {sentence(20, "ingest")}

MINIMUM REQUIREMENTS

- 3+ years building distributed systems {sentence(20, "systems")}

We are an equal opportunity employer and do not discriminate on the basis of race or religion.
"""


def test_fixture_description_counts_as_long():
    assert len(DESCRIPTION.split()) > SHORT_DESCRIPTION_WORDS


def test_splits_on_headings_in_document_order():
    heads = [h for h, _ in split_sections(DESCRIPTION)]
    assert heads == ["About the team", "What you'll do", "MINIMUM REQUIREMENTS"]


def test_bullets_are_not_mistaken_for_headings():
    # "- Python" is short and has no full stop, but it's a list item.
    sections = split_sections("Skills\n\n- Python\n\n- Go\n\n" + sentence(30))
    assert [h for h, _ in sections] == ["Skills"]
    assert "- Python" in sections[0][1]


def test_drops_legal_boilerplate_paragraphs():
    text = " ".join(p for _, ps in split_sections(DESCRIPTION) for p in ps)
    assert "equal opportunity" not in text


def test_drops_everything_under_a_boilerplate_heading():
    desc = f"The role\n\n{sentence(40)}\n\nApplicant Privacy Policy\n\n{sentence(40, 'gdpr')}"
    text = " ".join(p for _, ps in split_sections(desc) for p in ps)
    assert "gdpr" not in text and "lorem" in text


def test_tiny_sections_merge_forward():
    desc = f"Intro\n\nShort blurb here.\n\nThe role\n\n{sentence(60)}"
    sections = split_sections(desc)
    assert len(sections) == 1
    assert sections[0][1][0] == "Short blurb here."


def test_template_paragraphs_found_by_frequency():
    shared = sentence(30, "culture")
    descs = [f"{shared}\n\n{sentence(30, f'unique{i}')}" for i in range(12)]
    template = find_template_paragraphs(descs, min_postings=10)
    text = " ".join(p for _, ps in split_sections(descs[0], template) for p in ps)
    assert "culture" not in text and "unique0" in text


def test_paragraph_below_template_threshold_is_kept():
    shared = sentence(30, "culture")
    descs = [f"{shared}\n\n{sentence(30, f'unique{i}')}" for i in range(3)]
    template = find_template_paragraphs(descs, min_postings=10)
    assert "culture" in " ".join(p for _, ps in split_sections(descs[0], template) for p in ps)


def test_pack_respects_size_and_overlaps():
    paras = [sentence(60, f"p{i}") for i in range(10)]  # 600 words
    chunks = pack_paragraphs(paras)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.split()) <= TARGET_WORDS + OVERLAP_WORDS + 1
    # each chunk after the first opens with "…" + the tail of the previous one
    tail = chunks[0].split()[-OVERLAP_WORDS:]
    assert chunks[1].split()[0] == "…"
    assert chunks[1].split()[1:OVERLAP_WORDS + 1] == tail


def test_oversized_paragraph_is_split():
    chunks = pack_paragraphs([" ".join(["word"] * (MAX_WORDS * 3))])  # no sentence breaks
    assert len(chunks) >= 3
    assert all(len(c.split()) <= MAX_WORDS + OVERLAP_WORDS + 1 for c in chunks)


def test_profile_chunk_carries_structured_facts():
    profile = chunk_job(job(description=DESCRIPTION))[0]
    assert profile.section == "Profile"
    for fact in ["Backend Engineer at Acme", "remote", "Austin", "$150,000", "Visa sponsorship: yes", "postgres"]:
        assert fact in profile.content


def test_contextual_header_on_every_content_chunk():
    for c in chunk_job(job(description=DESCRIPTION))[1:]:
        assert c.content.startswith(f"Backend Engineer at Acme — {c.section}\n")
        assert c.content.endswith(c.body)


def test_html_entities_are_decoded():
    chunks = chunk_job(job(description=f"The role\n\n{sentence(40)} AT&amp;T&nbsp;scale."))
    assert "AT&T scale." in chunks[1].body


def test_short_description_falls_back_to_list_columns():
    chunks = chunk_job(job(description="Join us.", qualifications=["5 years of Rust"]))
    assert any(c.section == "Qualifications" and "Rust" in c.body for c in chunks)


def test_long_description_does_not_duplicate_list_columns():
    # For long descriptions the lists were parsed *out of* the description.
    chunks = chunk_job(job(description=DESCRIPTION, qualifications=["UNIQUE-LIST-ITEM"]))
    assert not any("UNIQUE-LIST-ITEM" in c.body for c in chunks)
