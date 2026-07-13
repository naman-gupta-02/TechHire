from .base import Job
from .utils import fetch_jsearch_pages

API_KEY = "57daa5cbf3msh1ee5d6df857d805p1c778ejsn9ccbe8f5bc01"


def fetch(query="software engineer", location="remote", max_pages=5, existing_ids=None) -> tuple[list[Job], bool]:
    return fetch_jsearch_pages(
        api_key=API_KEY,
        query=query,
        location=location,
        source="lever",
        existing_ids=existing_ids,
        max_pages=max_pages,
        employment_types="FULLTIME,INTERN",
        query_suffix=" via lever",
    )
