"""Test script for hybrid BM25 + semantic skill matching.

Tests the SkillLoader's get_relevant_context() API directly
instead of reimplementing the scoring logic.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from skills.loader import SkillLoader, Skill

QUERIES = [
    ("fix the bug in the login function", "coding"),
    ("create a React app with Tailwind", "coding"),
    ("read the config file", "coding"),  # file-operations deleted, coding is closest
    ("I want to build a task management app", "coding"),
    ("challenge my approach to this architecture", "challenger"),
    ("what's the weather today", None),  # should not match
]

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "..", "skills")


def test_bm25_only():
    """Test with BM25 only (no encoder)."""
    loader = SkillLoader(skills_dir=SKILLS_DIR)
    loader.load_all()

    print(f"\nLoaded skills: {loader.list_skills()}")
    print(f"\n{'=' * 70}")
    print(f"  BM25-ONLY TEST (through get_relevant_context API)")
    print(f"{'=' * 70}")

    for query, expected in QUERIES:
        result = loader.get_relevant_context(query, max_skills=1)
        matched = None
        if result:
            # Extract skill name from "## skill_name\n..."
            matched = result.split("\n")[0].replace("## ", "").strip()

        if expected is None:
            ok = "PASS" if not result else "FAIL"
        else:
            ok = "PASS" if matched == expected else "FAIL"

        print(f"  [{ok}] {query[:50]:<50} => {matched or 'NO MATCH'}")


def test_hybrid():
    """Test with hybrid BM25 + semantic matching."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("\nsentence-transformers not available — skipping hybrid test.")
        return

    print(f"\n{'=' * 70}")
    print(f"  HYBRID TEST (through get_relevant_context API)")
    print(f"{'=' * 70}")

    print("\nLoading sentence-transformers model (all-MiniLM-L6-v2)...")
    encoder = SentenceTransformer("all-MiniLM-L6-v2")

    loader = SkillLoader(skills_dir=SKILLS_DIR)
    loader.load_all()
    loader.set_encoder(encoder)
    loader.build_index()

    for query, expected in QUERIES:
        result = loader.get_relevant_context(query, max_skills=1)
        matched = None
        if result:
            matched = result.split("\n")[0].replace("## ", "").strip()

        if expected is None:
            ok = "PASS" if not result else "FAIL"
        else:
            ok = "PASS" if matched == expected else "FAIL"

        print(f"  [{ok}] {query[:50]:<50} => {matched or 'NO MATCH'}")


if __name__ == "__main__":
    print("=" * 70)
    print("  SKILL MATCHING TEST (API-level)")
    print("=" * 70)

    test_bm25_only()
    test_hybrid()

    print(f"\n{'=' * 70}")
    print("  TEST COMPLETE")
    print(f"{'=' * 70}")
