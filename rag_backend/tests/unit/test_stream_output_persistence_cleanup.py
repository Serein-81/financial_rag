from app.utils.output_formatter import OutputFormatter


def test_output_formatter_exposes_completed_stream_cleanup():
    raw = "## Thought\ninternal\n\n## Final Answer\nvisible answer"

    cleaned = OutputFormatter.clean_stream_content(raw)

    assert "Thought" not in cleaned
    assert cleaned == "visible answer"
