from pipeline.config import ChunkConfig
from pipeline.models import DocMeta, SectionMeta
from pipeline.processing.chunker import chunk_section


def _meta():
    return SectionMeta(
        section_number="B3-4.3-04",
        section_title="Personal Gifts",
        agency="fannie",
        source_url="https://selling-guide.fanniemae.com/sel/b3-4.3-04/personal-gifts",
    )


def _doc():
    return DocMeta(
        agency="fannie",
        doc_type="guide",
        source_url="https://selling-guide.fanniemae.com/sel/b3-4.3-04/personal-gifts",
    )


def test_chunker_produces_chunks():
    text = "Lorem ipsum " * 800
    cfg = ChunkConfig(chunk_size=512, chunk_overlap=64)
    chunks = chunk_section(text, _meta(), _doc(), cfg)
    assert len(chunks) >= 2
    for c in chunks:
        assert c.section_number == "B3-4.3-04"
        assert c.agency == "fannie"
        assert c.doc_type == "guide"


def test_chunker_deterministic_ids():
    cfg = ChunkConfig(chunk_size=512, chunk_overlap=64)
    text = "deterministic " * 600
    a = chunk_section(text, _meta(), _doc(), cfg)
    b = chunk_section(text, _meta(), _doc(), cfg)
    assert [c.id for c in a] == [c.id for c in b]


def test_chunker_empty_text():
    cfg = ChunkConfig()
    assert chunk_section("", _meta(), _doc(), cfg) == []
    assert chunk_section("   \n\n  ", _meta(), _doc(), cfg) == []


def test_chunker_metadata_inheritance():
    cfg = ChunkConfig(chunk_size=128, chunk_overlap=16)
    text = " ".join(f"word{i}" for i in range(500))
    chunks = chunk_section(text, _meta(), _doc(), cfg)
    assert len(chunks) > 1
    for idx, c in enumerate(chunks):
        assert c.chunk_index == idx
        assert c.section_title == "Personal Gifts"
