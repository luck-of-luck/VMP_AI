import pytest

from mcp_database.errors import QueryValidationError
from mcp_database.helpers import mongo_query


def test_require_str_field_happy():
    assert mongo_query.require_str_field({"collection": "users"}, "collection") == "users"


@pytest.mark.parametrize("value", [None, "", 42, ["users"], {"name": "users"}])
def test_require_str_field_sad(value):
    with pytest.raises(QueryValidationError):
        mongo_query.require_str_field({"collection": value}, "collection")


@pytest.mark.parametrize("operation", ["find", "aggregate", "insertMany", "dropCollection"])
def test_ensure_known_operation_happy(operation):
    mongo_query.ensure_known_operation(operation)


@pytest.mark.parametrize("operation", ["eval", "mapReduce", "", "FIND", "🤯"])
def test_ensure_known_operation_sad(operation):
    with pytest.raises(QueryValidationError, match="Unknown MongoDB operation"):
        mongo_query.ensure_known_operation(operation)


@pytest.mark.parametrize("query", [{}, {"database": "app"}, {"database": "app_🚀"}, {"collection": "c"}])
def test_ensure_optional_database_happy(query):
    mongo_query.ensure_optional_database(query)


@pytest.mark.parametrize("database", ["", 42, ["app"]])
def test_ensure_optional_database_sad(database):
    with pytest.raises(QueryValidationError):
        mongo_query.ensure_optional_database({"database": database})


def test_scan_for_forbidden_operators_happy():
    mongo_query.scan_for_forbidden_operators([{"$match": {"a": 1}}, {"$lookup": {"from": "b"}}])


@pytest.mark.parametrize(
    "pipeline",
    [
        [{"$out": "stolen"}],
        [{"$merge": {"into": "stolen"}}],
        [{"$facet": {"x": [{"$out": "stolen"}]}}],
        [{"$match": {"a": {"$in": [{"$merge": "deep"}]}}}],
    ],
)
def test_scan_for_forbidden_operators_sad_nested(pipeline):
    with pytest.raises(QueryValidationError, match="not allowed"):
        mongo_query.scan_for_forbidden_operators(pipeline)


def test_validate_aggregate_read_requires_pipeline_list():
    with pytest.raises(QueryValidationError, match="'pipeline' list"):
        mongo_query.validate_aggregate_read({"operation": "aggregate", "pipeline": {"$match": {}}})
    with pytest.raises(QueryValidationError, match="'pipeline' list"):
        mongo_query.validate_aggregate_read({"operation": "aggregate"})


def test_validate_distinct_read_requires_key():
    with pytest.raises(QueryValidationError, match="'key'"):
        mongo_query.validate_distinct_read({"operation": "distinct"})


@pytest.mark.parametrize(
    ("parsed", "unbounded"),
    [
        ({"operation": "updateMany"}, True),
        ({"operation": "deleteMany", "filter": {}}, True),
        ({"operation": "updateMany", "filter": {"a": 1}}, False),
        ({"operation": "deleteOne"}, False),
        ({"operation": "insertMany"}, False),
    ],
)
def test_is_unbounded_write(parsed, unbounded):
    assert mongo_query.is_unbounded_write(parsed) is unbounded


def test_audit_shape_redacts_data_keeps_structure():
    shape = mongo_query.audit_shape(
        {
            "collection": "users",
            "operation": "updateMany",
            "filter": {"email": "a@b.c", "tags": ["vip", "😀"]},
            "update": {"$set": {"password": "hunter2"}},
        }
    )
    assert shape["collection"] == "users"
    assert shape["operation"] == "updateMany"
    assert shape["filter"] == {"email": "?", "tags": ["?", "?"]}
    assert shape["update"] == {"$set": {"password": "?"}}


def test_audit_shape_does_not_mutate_input():
    parsed = {"collection": "c", "operation": "insertMany", "documents": [{"secret": "x"}]}
    mongo_query.audit_shape(parsed)
    assert parsed["documents"] == [{"secret": "x"}]
