import itertools
import json
import re
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


_STOP = set("a an the of in on at to and for with by no not was were is are my i we our after before from over up out it its that this had has have been when while than then they them their there here as but or so very too did do does done into only just".split())


def _tokens(text):
    return {w[:5] for w in re.findall(r"[a-z]+", text.lower()) if w not in _STOP and len(w) > 2}


def _overlap(a, b):
    a, b = _tokens(a), _tokens(b)
    return len(a & b) / max(1, min(len(a), len(b)))


def test_no_two_texts_describe_the_same_event():
    """Exact-match checks miss a reworded repeat (father vs family with a sick child), so compare by shared meaning words."""
    rows = [(k.split("_")[0], x[-1], x[1] if not k.endswith("_ar") else x[2]) for k, v in TEXTS.items() for x in v]
    close = [(a[1], b[1]) for a, b in itertools.combinations(rows, 2)
             if a[0] == b[0] and max(_overlap(a[1], b[1]), 0.9 * _overlap(a[2], b[2])) >= 0.55]
    assert not close, close


def test_open_and_recent_cases_never_repeat_a_story(db):
    titles = [c.title for c in db.scalars(select(Case))]
    close = [(a, b) for a, b in itertools.combinations(titles, 2) if _overlap(a, b) >= 0.6]
    assert not close, close
