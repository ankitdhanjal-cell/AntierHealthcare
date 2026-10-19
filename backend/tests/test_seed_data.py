import json
from collections import Counter
from pathlib import Path

from sqlalchemy import select

from app.models import Case, FeedbackResponse

TEXTS = json.loads((Path(__file__).parent.parent / "app" / "seed_data" / "feedback_texts.json").read_text(encoding="utf-8"))


def test_text_file_has_no_duplicates():
    texts = [row[1] for rows in TEXTS.values() for row in rows]
    summaries = [row[-1] for rows in TEXTS.values() for row in rows]
    assert len(texts) == len(set(texts))
    assert len(summaries) == len(set(summaries))
    assert len(TEXTS["complaints_en"]) + len(TEXTS["complaints_ar"]) >= 120
    assert len(TEXTS["compliments_en"]) + len(TEXTS["compliments_ar"]) >= 80


def test_seeded_feedback_text_is_unique_and_part_arabic(db):
    rows = [f for f in db.scalars(select(FeedbackResponse)) if f.text]
    assert len(rows) == len({f.text for f in rows})
    arabic = sum(f.language == "ar" for f in rows) / len(rows)
    assert 0.2 <= arabic <= 0.3


def test_case_titles_and_resolutions_are_unique(db):
    cases = list(db.scalars(select(Case)))
    assert len({c.title for c in cases}) == len(cases)
    resolutions = [c.resolution for c in cases if c.resolution]
    assert len(resolutions) == len(set(resolutions))


def test_timestamps_are_unique(db):
    ts = [f.created_at for f in db.scalars(select(FeedbackResponse))]
    assert len(ts) == len(set(ts))


def test_ratings_skew_positive_with_a_tail(db):
    counts = Counter(f.rating for f in db.scalars(select(FeedbackResponse)))
    total = sum(counts.values())
    assert (counts[4] + counts[5]) / total > 0.55
    assert counts[1] + counts[2] > 0
