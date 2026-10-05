"""Build / refresh the RAG index (job_chunks + job_vectors).

Incremental — only new or changed postings are re-embedded, so it's safe
to re-run any time. `python main.py` also runs it after every scrape.

Usage:
    python scripts/build_rag_index.py
    python scripts/build_rag_index.py --force               # re-embed everything
    python scripts/build_rag_index.py --include-synthetic   # also index load-test rows
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import init_db, SessionLocal  # noqa: E402
from rag.indexer import index_jobs  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="re-embed every job, even if unchanged")
    parser.add_argument("--include-synthetic", action="store_true",
                        help="also index synthetic load-test rows (slow, and pollutes results)")
    args = parser.parse_args()

    init_db()
    with SessionLocal() as session:
        result = index_jobs(session, include_synthetic=args.include_synthetic, force=args.force)
    print(f"Done: {result}")


if __name__ == "__main__":
    main()
