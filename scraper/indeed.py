import os

from .base import Job
from .utils import fetch_jsearch_pages

API_KEY = os.getenv("RAPIDAPI_KEY", "")


def fetch(query="software engineer", location="remote", max_pages=5, existing_ids=None) -> tuple[list[Job], bool]:
    return fetch_jsearch_pages(
        api_key=API_KEY,
        query=query,
        location=location,
        source="indeed",
        existing_ids=existing_ids,
        max_pages=max_pages,
        employment_types="FULLTIME,INTERN",
    )
