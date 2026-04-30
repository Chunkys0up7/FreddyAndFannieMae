from pathlib import Path

from pipeline.store.review_store import ReviewStore
from pipeline.store.state_store import StateStore


def test_state_store_bulletin_lifecycle(tmp_path: Path):
    store = StateStore(tmp_path / "test.db")
    assert not store.has_bulletin("SEL-2026-04")
    store.mark_bulletin("SEL-2026-04", "fannie", "https://example/x", "April Update")
    assert store.has_bulletin("SEL-2026-04")
    bulletins = store.list_recent_bulletins("fannie", days=30)
    assert len(bulletins) == 1
    assert bulletins[0].title == "April Update"


def test_state_store_guide_hash(tmp_path: Path):
    store = StateStore(tmp_path / "test.db")
    assert store.get_guide_hash("fannie") is None
    store.set_guide_hash("fannie", "abc123")
    assert store.get_guide_hash("fannie") == "abc123"
    store.set_guide_hash("fannie", "xyz789")
    assert store.get_guide_hash("fannie") == "xyz789"


def test_review_store_flag_and_status(tmp_path: Path):
    store = ReviewStore(tmp_path / "review.db")
    flag_id = store.flag_section(
        "B3-4.3-04", "fannie", "Bulletin SEL-2026-04 changed gift fund rules", "high"
    )
    assert flag_id > 0
    status = store.get_review_status("B3-4.3-04")
    assert status.status == "flagged"

    store.mark_reviewed("B3-4.3-04", "Verified — no SOP impact", "alice")
    status = store.get_review_status("B3-4.3-04")
    assert status.status == "reviewed"


def test_review_store_gap_note(tmp_path: Path):
    store = ReviewStore(tmp_path / "review.db")
    note_id = store.create_gap_note(
        "B3-4.3-04", "fannie", "Old SOP", "Section now requires X", "Update SOP step 4"
    )
    assert note_id > 0
    notes = store.list_gap_notes("B3-4.3-04")
    assert len(notes) == 1
    assert "X" in notes[0].change


def test_review_store_default_status_is_new(tmp_path: Path):
    store = ReviewStore(tmp_path / "review.db")
    status = store.get_review_status("never-touched")
    assert status.status == "new"
