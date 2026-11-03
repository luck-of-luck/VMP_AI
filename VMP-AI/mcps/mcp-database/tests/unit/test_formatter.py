import time
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from mcp_database.errors import QueryValidationError
from mcp_database.formatter import (
    HARD_ROW_CAP,
    MASK,
    build_result,
    effective_row_limit,
    json_default,
    mask_column_stats,
    mask_rows,
    redact_uri_passwords,
    sanitize_error,
    to_jsonable,
    type_placeholder,
)


class TestToJsonable:
    def test_leaves_json_native_types_untouched(self):
        value = {"a": 1, "b": "s", "c": 1.5, "d": True, "e": None, "f": [1, 2]}
        assert to_jsonable(value) == value

    def test_converts_driver_native_scalars(self):
        assert to_jsonable(Decimal("2.5")) == 2.5
        assert to_jsonable(b"xyz") == "<3 bytes>"
        uid = uuid4()
        assert to_jsonable(uid) == str(uid)
        assert to_jsonable(datetime(2026, 7, 11, tzinfo=UTC)).startswith("2026-07-11")

    def test_recurses_into_nested_containers(self):
        class ObjectId:
            def __str__(self):
                return "deadbeef"

        row = {"_id": ObjectId(), "tags": [ObjectId(), "plain"], "meta": {"n": Decimal("3")}}
        assert to_jsonable(row) == {"_id": "deadbeef", "tags": ["deadbeef", "plain"], "meta": {"n": 3.0}}

    def test_converts_bytes_with_invalid_utf8(self):
        # MongoDB $currentOp can surface raw binary; it must not blow up JSON serialization.
        assert to_jsonable({"op": b"\xff\xfe"}) == {"op": "<2 bytes>"}


class TestBuildResult:
    def test_happy_no_truncation(self):
        result = build_result([{"a": 1}, {"a": 2}], row_limit=10)
        assert result == {"rows": [{"a": 1}, {"a": 2}], "row_count": 2, "truncated": False}

    def test_execution_ms_rounded(self):
        assert build_result([], row_limit=10, execution_ms=12.3456)["execution_ms"] == 12.3

    def test_truncates_by_rows(self):
        rows = [{"i": i} for i in range(20)]
        result = build_result(rows, row_limit=5)
        assert result["row_count"] == 5
        assert result["truncated"] is True

    def test_truncates_by_bytes(self):
        rows = [{"blob": "x" * 300_000} for _ in range(10)]
        result = build_result(rows, row_limit=10)
        assert result["truncated"] is True
        assert 1 <= result["row_count"] < 10

    def test_single_huge_row_is_kept(self):
        rows = [{"blob": "x" * 3_000_000}]
        assert build_result(rows, row_limit=10)["row_count"] == 1

    def test_masking_applied(self):
        result = build_result([{"email": "a@b.c", "id": 1}], row_limit=10, redact_fields=("email",))
        assert result["rows"] == [{"email": MASK, "id": 1}]

    def test_absurd_row_limit_clamped(self):
        rows = [{"i": i} for i in range(3)]
        assert build_result(rows, row_limit=-99)["row_count"] == 1
        assert build_result(rows, row_limit=10**9)["row_count"] == 3

    def test_masking_shrinks_rows_before_byte_budget(self):
        """Masking runs before the 1 MiB byte cap, so redacted rows all fit where raw rows would truncate."""
        rows = [{"id": i, "blob": "x" * 300_000} for i in range(6)]
        masked = build_result(rows, row_limit=10, redact_fields=("blob",))
        assert masked["row_count"] == 6
        assert masked["truncated"] is False
        unmasked = build_result(rows, row_limit=10)
        assert unmasked["truncated"] is True
        assert unmasked["row_count"] < 6

    def test_compact_uniform_rows(self):
        result = build_result([{"id": 1, "name": "a"}, {"id": 2, "name": "b"}], row_limit=10, compact=True)
        assert result["columns"] == ["id", "name"]
        assert result["rows"] == [[1, "a"], [2, "b"]]
        assert result["row_count"] == 2 and result["truncated"] is False
        assert "rows" in result and "columns" in result  # no dict-per-row form

    def test_compact_heterogeneous_rows_union_and_nullfill(self):
        result = build_result([{"a": 1}, {"b": 2}, {"a": 3, "b": 4}], row_limit=10, compact=True)
        assert result["columns"] == ["a", "b"]
        assert result["rows"] == [[1, None], [None, 2], [3, 4]]

    def test_compact_empty(self):
        result = build_result([], row_limit=10, compact=True)
        assert result == {"columns": [], "rows": [], "row_count": 0, "truncated": False}

    def test_compact_still_masks(self):
        result = build_result([{"email": "a@b.c", "id": 1}], row_limit=10, redact_fields=("email",), compact=True)
        assert result["columns"] == ["email", "id"]
        assert result["rows"] == [[MASK, 1]]

    def test_compact_preserves_truncation(self):
        rows = [{"i": i} for i in range(20)]
        result = build_result(rows, row_limit=5, compact=True)
        assert result["row_count"] == 5 and result["truncated"] is True
        assert len(result["rows"]) == 5


class TestMasking:
    def test_field_list_case_insensitive_and_nested(self):
        rows = [{"Email": "a@b.c", "profile": {"CPF": "123", "city": "SP"}, "tags": [{"cpf": "9"}]}]
        masked = mask_rows(rows, ("email", "cpf"))
        assert masked == [{"Email": MASK, "profile": {"CPF": MASK, "city": "SP"}, "tags": [{"cpf": MASK}]}]

    def test_mask_all_preserves_structure_with_type_placeholders(self):
        now = datetime.now(UTC)
        rows = [
            {
                "name": "x",
                "age": 3,
                "pi": 1.5,
                "ok": True,
                "none": None,
                "when": now,
                "nested": {"deep": "s"},
                "items": [1, "a"],
            }
        ]
        masked = mask_rows(rows, ("*",))
        assert masked == [
            {
                "name": "<string>",
                "age": "<int>",
                "pi": "<float>",
                "ok": "<bool>",
                "none": "<null>",
                "when": "<datetime>",
                "nested": {"deep": "<string>"},
                "items": ["<int>", "<string>"],
            }
        ]

    def test_no_redact_fields_is_identity(self):
        rows = [{"a": 1}]
        assert mask_rows(rows, ()) is rows

    def test_patterns_mask_by_field_name_regex(self):
        rows = [{"user_email": "a@b.c", "ssn_number": "123", "safe": "ok"}]
        masked = mask_rows(rows, (), (r"email$", r"^ssn"))
        assert masked == [{"user_email": MASK, "ssn_number": MASK, "safe": "ok"}]

    def test_patterns_and_fields_combine_nested(self):
        rows = [{"Email": "a@b.c", "profile": {"cpf_doc": "9"}}]
        masked = mask_rows(rows, ("email",), (r"cpf",))
        assert masked == [{"Email": MASK, "profile": {"cpf_doc": MASK}}]

    def test_patterns_are_case_insensitive(self):
        assert mask_rows([{"SecretToken": "x"}], (), (r"token",)) == [{"SecretToken": MASK}]

    def test_placeholder_for_exotic_types(self):
        assert type_placeholder(b"abc") == "<bytes>"
        assert type_placeholder(Decimal("1.5")) == "<float>"
        assert type_placeholder(object()) == "<object>"


class TestEffectiveRowLimit:
    def test_defaults_and_caps(self):
        assert effective_row_limit(None, 500) == 500
        assert effective_row_limit(None, 10**9) == HARD_ROW_CAP
        assert effective_row_limit(50, 500) == 50
        assert effective_row_limit(10**9, 500) == HARD_ROW_CAP

    @pytest.mark.parametrize("bad", [0, -1, -(10**9), True, "10", 1.5])
    def test_absurd_values_rejected(self, bad):
        with pytest.raises(QueryValidationError):
            effective_row_limit(bad, 500)


class TestRedaction:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("postgresql://app:s3cr3t@h:5432/db", "postgresql://app:***@h:5432/db"),
            ("mongodb://u:pw@h1:1,h2:2/db", "mongodb://u:***@h1:1,h2:2/db"),
            ("error at mysql://root:root@localhost/x and more", "error at mysql://root:***@localhost/x and more"),
            ("no uris here", "no uris here"),
            ("postgresql://nopassword@h/db", "postgresql://nopassword@h/db"),
            ("postgresql://u:p%40ss%21@h/db", "postgresql://u:***@h/db"),  # percent-encoded @ and !
            ("mysql://u:pa$$w0rd.-_@h/db", "mysql://u:***@h/db"),  # special chars in password
            ("mongodb+srv://u:s3cret@cluster.mongodb.net/db", "mongodb+srv://u:***@cluster.mongodb.net/db"),
        ],
    )
    def test_redact(self, text, expected):
        assert redact_uri_passwords(text) == expected

    @pytest.mark.parametrize(
        "payload",
        [
            "://" + "a" * 200_000,  # scheme, credentials never terminated
            "://" + "a:" * 100_000,  # many colons, no closing '@'
            "://" + "a" * 100_000 + ":" + "b" * 100_000,  # long user:pass, no '@'
            "://" + "a:b" * 100_000 + " ",  # repeated user:pass fragments, no '@'
        ],
    )
    def test_redact_is_redos_safe(self, payload):
        # The pattern has no nested quantifiers, so pathological near-misses stay linear.
        start = time.perf_counter()
        result = redact_uri_passwords(payload)
        assert time.perf_counter() - start < 0.5
        assert result == payload  # no complete user:pass@ match, nothing redacted

    def test_redact_still_works_after_long_prefix(self):
        text = "x" * 100_000 + " postgresql://u:secret@h/db"
        assert redact_uri_passwords(text).endswith("postgresql://u:***@h/db")
        assert "secret" not in redact_uri_passwords(text)


class TestSanitizeError:
    """sanitize_error strips both URI passwords and the row/column values drivers echo in error text."""

    @pytest.mark.parametrize(
        ("text", "leaked"),
        [
            ("unique constraint\nDETAIL:  Key (ssn)=(123-45-6789) already exists.", "123-45-6789"),
            ("not null\nDETAIL:  Failing row contains (1, alice@secret.com, 42).", "alice@secret.com"),
            ('invalid input syntax for type integer: "not-a-number-4242"', "4242"),
            ("Duplicate entry 'user@private.io' for key 'users.email'", "user@private.io"),
            ("Incorrect integer value: 'secret-9999' for column 'age' at row 1", "secret-9999"),
        ],
    )
    def test_strips_leaked_values(self, text, leaked):
        cleaned = sanitize_error(text)
        assert leaked not in cleaned

    def test_keeps_structural_context(self):
        cleaned = sanitize_error("DETAIL:  Key (ssn)=(123) already exists.")
        assert "Key (ssn)=" in cleaned
        assert "already exists" in cleaned
        assert "123" not in cleaned

    def test_also_redacts_uri_passwords(self):
        assert "hunter2" not in sanitize_error("connect failed: postgresql://app:hunter2@db/x")

    def test_absurd_and_empty_inputs(self):
        assert sanitize_error("") == ""
        assert sanitize_error("a plain message with no values") == "a plain message with no values"
        assert "🔥" in sanitize_error("weird 🔥 error")


class TestJsonDefault:
    def test_known_types(self):
        assert json_default(datetime(2026, 7, 11, tzinfo=UTC)).startswith("2026-07-11")
        assert json_default(Decimal("2.5")) == 2.5
        assert json_default(b"xyz") == "<3 bytes>"
        uid = uuid4()
        assert json_default(uid) == str(uid)

    def test_fallback_is_str(self):
        class Weird:
            def __str__(self):
                return "weird!"

        assert json_default(Weird()) == "weird!"


class TestTruncationNote:
    def test_note_present_when_truncated(self):
        result = build_result([{"i": i} for i in range(10)], row_limit=3)
        assert "db_read_export" in result["note"]

    def test_no_note_when_complete(self):
        assert "note" not in build_result([{"i": 1}], row_limit=10)


def stats_rows():
    return [
        {"column": "id", "n_distinct": -1, "most_common_vals": None},
        {"column": "Email", "n_distinct": 2, "most_common_vals": "{a@b.c,d@e.f}", "histogram": "{...}"},
    ]


class TestMaskColumnStats:
    """mask_column_stats hides MCV lists and histograms — the parts of planner stats that carry real data."""

    def test_no_redact_is_passthrough(self):
        assert mask_column_stats(stats_rows(), ()) == stats_rows()

    def test_named_column_masked_case_insensitive(self):
        masked = mask_column_stats(stats_rows(), ("email",))
        assert masked[1]["most_common_vals"] == MASK
        assert masked[1]["histogram"] == MASK
        assert masked[1]["n_distinct"] == 2
        assert masked[0] == stats_rows()[0]

    def test_star_masks_every_column_with_values(self):
        masked = mask_column_stats(stats_rows(), ("*",))
        assert masked[1]["most_common_vals"] == MASK
        assert masked[0]["most_common_vals"] is None

    def test_absurd_row_without_column_key_survives(self):
        assert mask_column_stats([{"weird": True}], ("email",)) == [{"weird": True}]
