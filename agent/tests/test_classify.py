from agent.nodes.classify_heuristic import heuristic_classify


def test_heuristic_compare_keyword():
    assert heuristic_classify("Compare Fannie and Freddie on gift funds", False) == "compare"
    assert heuristic_classify("How does Fannie differ from Freddie?", False) == "compare"


def test_heuristic_bulletin_keyword():
    assert heuristic_classify("What changed in SEL-2026-04?", False) == "bulletin_impact"
    assert heuristic_classify("Show me the latest bulletin", False) == "bulletin_impact"


def test_heuristic_qa_default():
    assert heuristic_classify("What are the gift fund requirements?", False) == "qa"


def test_heuristic_bulletin_when_selected():
    assert heuristic_classify("Tell me more", True) == "bulletin_impact"
