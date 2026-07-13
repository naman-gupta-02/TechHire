import re
from typing import Optional
from .base import Job

CS_KEYWORDS = [
    "software engineer", "backend engineer", "frontend engineer",
    "full stack", "fullstack", "data engineer", "ml engineer",
    "machine learning", "devops", "data scientist", "python developer",
    "java developer", "android developer", "ios developer",
    "cloud engineer", "site reliability", "sre", "platform engineer",
    "security engineer", "systems engineer", "infrastructure engineer",
    "backend", "frontend", "mobile engineer",
]

TECH_SKILLS = [
    # Languages
    "python", "java", "javascript", "typescript", "golang", "rust", "c++", "c#",
    "ruby", "swift", "kotlin", "scala", "php", "bash", "r", "matlab",
    # Frontend
    "react", "angular", "vue", "next.js", "svelte", "html", "css", "tailwind", "redux",
    # Backend
    "node.js", "express", "django", "flask", "fastapi", "spring", "rails", "laravel",
    # Cloud & DevOps
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform", "ansible",
    "jenkins", "github actions", "ci/cd", "linux",
    # Databases
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "cassandra",
    "dynamodb", "snowflake", "databricks",
    # Data & ML
    "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy", "spark",
    "kafka", "airflow", "dbt",
    "machine learning", "deep learning", "nlp", "computer vision",
    # General
    "rest", "graphql", "grpc", "microservices", "rabbitmq",
    "git", "agile", "system design", "data structures", "algorithms",
]

_US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

_SECTION_MAP = [
    ("responsibilities", [
        r"key responsibilities", r"responsibilities", r"what you.?ll do",
        r"what you will do", r"what you will", r"you will",
        r"your role", r"job duties", r"duties",
        r"in this role", r"what you.?ll be doing", r"position purpose",
        r"the opportunity", r"your day.to.day", r"about the role",
    ]),
    ("qualifications", [
        r"qualifications", r"requirements", r"what you.?ll need",
        r"what we.?re looking for", r"required skills", r"minimum qualifications",
        r"basic qualifications", r"preferred qualifications",
        r"you have", r"you.?ll have", r"you must have", r"must have",
        r"experience", r"tech stack", r"technical skills", r"skills",
        r"what you bring", r"what we need",
    ]),
    ("benefits", [
        r"benefits", r"what we offer", r"perks", r"what you.?ll get",
        r"we offer", r"compensation and benefits", r"total compensation",
        r"why join", r"our offer", r"what.s in it for you",
    ]),
]

_VISA_POSITIVE = [
    "visa sponsorship", "will sponsor", "we sponsor", "h1b sponsor",
    "h-1b sponsor", "sponsorship available", "open to sponsoring",
    "sponsorship provided",
]
_VISA_NEGATIVE = [
    "no visa", "cannot sponsor", "not able to sponsor", "unable to sponsor",
    "no sponsorship", "sponsorship not available", "must be authorized",
    "must be legally authorized", "not eligible to sponsor",
    "us citizen", "green card only", "no h1b",
]


# ── location ─────────────────────────────────────────────────────────────────

def _city_state_from_text(text: str) -> Optional[tuple[str, str]]:
    """Try every common pattern to pull (city, state_abbr) out of a string."""
    # "in Beavercreek, OH" / "in Austin TX"
    m = re.search(r'\bin\s+([A-Z][a-zA-Z\s\-]+?),?\s+([A-Z]{2})\b', text)
    if m and m.group(2) in _US_STATES:
        return m.group(1).strip(), m.group(2)

    # "- Sunnyvale, CA" / "– Phoenix AZ"
    m = re.search(r'[-–]\s*([A-Z][a-zA-Z\s\-]+?),?\s+([A-Z]{2})\b', text)
    if m and m.group(2) in _US_STATES:
        return m.group(1).strip(), m.group(2)

    # "City, ST" anywhere (catches "Frisco/Dallas area" → skipped by length)
    m = re.search(r'\b([A-Z][a-zA-Z\s\-]{2,30}),\s*([A-Z]{2})\b', text)
    if m and m.group(2) in _US_STATES:
        return m.group(1).strip(), m.group(2)

    return None


def _parse_location(j: dict) -> tuple[Optional[str], Optional[str], Optional[str]]:
    # 1. Direct API fields (non-null)
    city    = j.get("job_city")
    state   = j.get("job_state")
    country = j.get("job_country")
    if city or state or country:
        return city, state, country

    # 2. job_location when it's not just "Anywhere" / "Remote"
    loc = (j.get("job_location") or "").strip()
    if loc and loc.lower() not in ("anywhere", "remote", ""):
        parts = [p.strip() for p in loc.split(",")]
        if len(parts) >= 2:
            return parts[0], parts[1], None
        return parts[0], None, None

    # 3. Parse from job title
    title = j.get("job_title", "")
    result = _city_state_from_text(title)
    if result:
        return result[0], result[1], "US"

    # 4. Parse from first 600 chars of description
    desc = (j.get("job_description") or "")[:600]

    # "Location: City, ST" or "Location: City ST"
    m = re.search(
        r'location\s*[:\-]\s*([A-Z][a-zA-Z\s\-]+?),?\s*([A-Z]{2})\b',
        desc, re.IGNORECASE
    )
    if m and m.group(2).upper() in _US_STATES:
        return m.group(1).strip(), m.group(2).upper(), "US"

    # Generic "City, ST" pattern in description
    result = _city_state_from_text(desc)
    if result:
        return result[0], result[1], "US"

    return None, None, None


# ── salary ───────────────────────────────────────────────────────────────────

def _parse_salary_from_text(text: str) -> tuple[Optional[float], Optional[float], Optional[str]]:
    """Extract (min, max, period) from a salary string or job description snippet."""
    if not text:
        return None, None, None

    t = text.lower()
    period: Optional[str] = None
    if any(w in t for w in ["year", "annual", "/yr", "per year", "annually"]):
        period = "YEAR"
    elif any(w in t for w in ["hour", "/hr", "/h ", "per hour"]):
        period = "HOUR"
    elif any(w in t for w in ["month", "/mo", "per month"]):
        period = "MONTH"

    def _to_float(raw: str, has_k: bool) -> float:
        val = float(raw.replace(",", "").replace(" ", ""))
        if has_k and val < 1000:
            val *= 1000
        return val

    # Range with $: "$76,500 – $125,000" or "$76.5K to $125K"
    m = re.search(
        r'\$\s*([\d,]+(?:\.\d+)?)\s*([Kk])?\s*[-–to]+\s*\$?\s*([\d,]+(?:\.\d+)?)\s*([Kk])?',
        text
    )
    if m:
        mn = _to_float(m.group(1), bool(m.group(2)))
        mx = _to_float(m.group(3), bool(m.group(4)))
        if 10_000 <= mn <= 1_000_000 and mn <= mx <= 1_000_000:
            return mn, mx, period or ("YEAR" if mn > 10_000 else "HOUR")

    # Range without $: "76.5K – 125K" (salary_string style)
    m = re.search(
        r'([\d]+(?:\.\d+)?)\s*[Kk]\s*[-–to]+\s*([\d]+(?:\.\d+)?)\s*[Kk]',
        text, re.IGNORECASE
    )
    if m:
        mn = float(m.group(1)) * 1000
        mx = float(m.group(2)) * 1000
        if 10_000 <= mn <= mx <= 1_000_000:
            return mn, mx, period or "YEAR"

    # Single value with $: "$120,000" or "$120K"
    m = re.search(r'\$\s*([\d,]+(?:\.\d+)?)\s*([Kk])?\+?', text)
    if m:
        val = _to_float(m.group(1), bool(m.group(2)))
        if 10_000 <= val <= 1_000_000:
            return val, None, period or "YEAR"

    # Single value without $: "80K", "120K+"
    m = re.search(r'\b([\d]+(?:\.\d+)?)\s*[Kk]\+?', text, re.IGNORECASE)
    if m:
        val = float(m.group(1)) * 1000
        if 10_000 <= val <= 1_000_000:
            return val, None, period or "YEAR"

    return None, None, None


# ── sections ─────────────────────────────────────────────────────────────────

def _detect_section(line: str) -> Optional[str]:
    stripped = line.strip()
    if not stripped:
        return None
    # Prose sentences end with . ! ? — skip them
    if re.search(r'[.!?]\s*$', stripped):
        return None

    clean = stripped.lower()
    clean = re.sub(r'[:\-–•*\s]+$', '', clean).strip()
    clean = re.sub(r'^\d+%\s+', '', clean)   # drop "40% " prefix

    for section, patterns in _SECTION_MAP:
        for pattern in patterns:
            if re.search(pattern, clean):
                return section
    return None


def _extract_items(lines: list[str]) -> list[str]:
    bulleted: list[str] = []
    plain:    list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        m = re.match(r'^[•\-–*·▪▸►]\s+(.+)', stripped)
        if m:
            text = m.group(1).strip()
            if len(text) > 10:
                bulleted.append(text)
            continue
        m2 = re.match(r'^\d+[.)]\s+(.+)', stripped)
        if m2:
            text = m2.group(1).strip()
            if len(text) > 10:
                bulleted.append(text)
            continue
        if 20 <= len(stripped) <= 350 and not stripped.endswith(':'):
            plain.append(stripped)

    return bulleted if bulleted else plain


def _parse_sections(description: str) -> dict:
    result: dict[str, list[str]] = {
        "responsibilities": [], "qualifications": [], "benefits": []
    }
    if not description:
        return result

    current_section: Optional[str] = None
    current_lines:   list[str]     = []

    for line in description.split('\n'):
        section = _detect_section(line)
        if section:
            if current_section:
                result[current_section].extend(_extract_items(current_lines))
            current_section = section
            current_lines   = []
        elif current_section:
            current_lines.append(line)

    if current_section:
        result[current_section].extend(_extract_items(current_lines))

    return result


# ── other helpers ─────────────────────────────────────────────────────────────

def _extract_skills(description: str) -> list[str]:
    if not description:
        return []
    desc_lower = description.lower()
    return [s for s in TECH_SKILLS if re.search(r'\b' + re.escape(s) + r'\b', desc_lower)]


_INTERN_RE  = re.compile(r'\bintern(ship)?\b|\bco-?op\b', re.IGNORECASE)
_SENIOR_RE  = re.compile(r'\b(senior|sr\.?|staff|principal|lead|manager|director|vp|head of)\b', re.IGNORECASE)
_ENTRY_RE   = re.compile(r'\b(junior|jr\.?|entry.level|associate|new.?grad|graduate)\b', re.IGNORECASE)


def _experience_level(j: dict) -> str:
    title = j.get("job_title") or ""
    types = j.get("job_employment_types") or []
    # Intern: use API type flag first (most reliable), then title
    if "INTERN" in types or _INTERN_RE.search(title):
        return "intern"
    if _SENIOR_RE.search(title):
        return "senior"
    if _ENTRY_RE.search(title):
        return "entry"
    return "mid"


def _job_type(j: dict) -> str:
    types = j.get("job_employment_types") or []
    title = j.get("job_title") or ""
    if "INTERN" in types or _INTERN_RE.search(title):
        return "INTERN"
    if "CONTRACTOR" in types:
        return "CONTRACT"
    if "PARTTIME" in types:
        return "PARTTIME"
    return "FULLTIME"


def _start_date_text(title: str, description: str) -> Optional[str]:
    """Extract employment start info (e.g. 'Summer 2026', 'January 2026') from title + description."""
    text = title + " " + (description or "")[:800]

    # "Summer 2026" / "Fall 2025" / "Winter 2026 Internship"
    m = re.search(r'\b(summer|fall|spring|winter|autumn)\s+(?:of\s+)?(20\d\d)\b', text, re.IGNORECASE)
    if m:
        season = "Fall" if m.group(1).lower() == "autumn" else m.group(1).capitalize()
        return f"{season} {m.group(2)}"

    # "2026 Summer" / "(BS/MS) 2026 Fall"
    m = re.search(r'\b(20\d\d)\s+(summer|fall|spring|winter|autumn)\b', text, re.IGNORECASE)
    if m:
        season = "Fall" if m.group(2).lower() == "autumn" else m.group(2).capitalize()
        return f"{season} {m.group(1)}"

    # "Summer/Fall 2026"
    m = re.search(
        r'\b(summer|fall|spring|winter)[\s/]+(summer|fall|spring|winter)\s+(20\d\d)\b',
        text, re.IGNORECASE
    )
    if m:
        return f"{m.group(1).capitalize()}/{m.group(2).capitalize()} {m.group(3)}"

    # "January 2026" / "June 2025"
    months = r'(january|february|march|april|may|june|july|august|september|october|november|december)'
    m = re.search(rf'\b{months}\s+(20\d\d)\b', text, re.IGNORECASE)
    if m:
        return f"{m.group(1).capitalize()} {m.group(2)}"

    # Bare season without year: "Summer Internship", "Spring Cohort"
    m = re.search(
        r'\b(summer|fall|spring|winter)\s+(?:internship|position|semester|cohort|program|co-op|batch)\b',
        text, re.IGNORECASE
    )
    if m:
        return m.group(1).capitalize()

    return None


_ONSITE_PATTERNS = [
    r'this is an?\s+on.?site role',
    r'on.?site role\s+based in',
    r'required to (?:work |be )?on.?site',
    r'must (?:work |be )?(?:in.?office|on.?site)',
]

_HYBRID_PATTERNS = [
    r'hybrid work (?:environment|schedule|model|arrangement|options?)\b',
    r'hybrid working (?:environment|schedule|model|arrangement)',
    r'considered hybrid',
    r'hybrid remote telecommut',
    r'hybrid (?:position|role)\b',
    r'(?:remote or hybrid|hybrid or remote) role',
    r'this position can be (?:set up as )?(?:either\s+)?(?:a\s+)?(?:remote or )?hybrid',
    # "X days in office/on-site" = part-time in person = hybrid
    r'\d+[\s\-–]+\d+\s+days?\s+(?:per week\s+)?in\s+(?:the\s+)?office',
    r'\d+\s+days?\s+(?:per week\s+)?(?:in\s+(?:the\s+)?office|on.?site)',
]

def _work_mode(is_remote: bool, description: str) -> str:
    desc = (description or "").lower()

    # Strong override: explicit full-remote signals
    if re.search(r'100\s*%\s*remote|fully remote|entirely remote|work from anywhere', desc):
        return "remote"

    # Onsite: specific phrases that clearly describe the work location requirement
    if any(re.search(p, desc) for p in _ONSITE_PATTERNS):
        return "onsite"

    # Hybrid: phrases specifically describing the work arrangement
    # (deliberately excludes "hybrid cloud", "hybrid search", "hybrid physical/virtual")
    if any(re.search(p, desc) for p in _HYBRID_PATTERNS):
        return "hybrid"

    # Default: trust the API's is_remote flag (we scrape with remote_jobs_only=true)
    return "remote" if (is_remote or "remote" in desc) else "onsite"


def _visa_sponsorship(description: str) -> Optional[bool]:
    if not description:
        return None
    desc = description.lower()
    if any(phrase in desc for phrase in _VISA_NEGATIVE):
        return False
    if any(phrase in desc for phrase in _VISA_POSITIVE):
        return True
    return None


# ── main entry point ──────────────────────────────────────────────────────────

def extract_job(j: dict, source: str) -> Job:
    description = j.get("job_description") or ""
    is_remote   = bool(j.get("job_is_remote", False))
    city, state, country = _parse_location(j)
    sections    = _parse_sections(description)

    # Salary: prefer structured API fields, fall back to salary_string, then description
    sal_min  = j.get("job_min_salary")
    sal_max  = j.get("job_max_salary")
    sal_period   = j.get("job_salary_period")
    sal_currency = j.get("job_salary_currency") or "USD"

    if sal_min is None:
        sal_str = j.get("job_salary_string") or ""
        parsed_min, parsed_max, parsed_period = _parse_salary_from_text(sal_str or description[:800])
        if parsed_min:
            sal_min, sal_max, sal_period = parsed_min, parsed_max, parsed_period

    title = j.get("job_title", "N/A")

    return Job(
        source_job_id    = j.get("job_id", ""),
        title            = title,
        company          = j.get("employer_name", "N/A"),
        source           = source,
        url              = j.get("job_apply_link", ""),
        posted_at        = j.get("job_posted_at_datetime_utc"),
        expires_at       = j.get("job_offer_expiration_datetime_utc"),
        city             = city,
        state            = state,
        country          = country,
        is_remote        = is_remote,
        work_mode        = _work_mode(is_remote, description),
        job_type         = _job_type(j),
        experience_level = _experience_level(j),
        description      = description or None,
        responsibilities = sections["responsibilities"],
        qualifications   = sections["qualifications"],
        benefits         = sections["benefits"],
        salary_min       = sal_min,
        salary_max       = sal_max,
        salary_currency  = sal_currency,
        salary_period    = sal_period,
        required_skills  = _extract_skills(description),
        visa_sponsorship = _visa_sponsorship(description),
        start_date_text  = _start_date_text(title, description),
    )


def is_cs_job(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in CS_KEYWORDS)
