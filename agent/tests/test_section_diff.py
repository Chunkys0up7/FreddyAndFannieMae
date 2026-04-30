from agent.tools.section_diff import section_diff


def test_diff_added_lines():
    result = section_diff("a\nb\nc", "a\nb\nc\nd")
    assert "d" in result["added"]
    assert result["removed"] == []


def test_diff_removed_lines():
    result = section_diff("a\nb\nc", "a\nc")
    assert "b" in result["removed"]


def test_diff_changed_block():
    result = section_diff("foo\nbar", "foo\nbaz")
    assert result["changed"]
    assert result["unified"]
