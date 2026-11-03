from scripts.analysis_output_helpers import count_by_key, log_count_breakdown, print_section_header


def test_count_by_key_counts_missing_and_empty_values() -> None:
    items = [
        {"severity": "high"},
        {"severity": "high"},
        {"severity": "low"},
        {"severity": ""},
        {},
    ]

    counts = count_by_key(items, "severity")

    assert counts["high"] == 2
    assert counts["low"] == 1
    assert counts["unknown"] == 2


def test_log_count_breakdown_respects_preferred_order() -> None:
    lines: list[str] = []

    log_count_breakdown(lines.append, {"medium": 3, "low": 1, "high": 2}, order=["high", "medium", "low"], indent="  ")

    assert lines == [
        "  High: 2",
        "  Medium: 3",
        "  Low: 1",
    ]


def test_print_section_header_with_trailing_newline() -> None:
    lines: list[str] = []

    print_section_header(lines.append, "TITLE", width=8, leading_newline=False, trailing_newline=True)

    assert lines == [
        "========",
        " TITLE",
        "========\n",
    ]
