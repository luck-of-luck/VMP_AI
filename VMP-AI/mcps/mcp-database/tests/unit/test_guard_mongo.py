import pytest

from mcp_database import guard
from mcp_database.errors import QueryValidationError

HAPPY_READS = [
    {"collection": "users", "operation": "find"},
    {"collection": "users", "operation": "find", "filter": {"age": {"$gt": 18}}, "sort": {"age": -1}},
    {"collection": "events", "operation": "aggregate", "pipeline": [{"$match": {"a": 1}}, {"$group": {"_id": "$b"}}]},
    {"collection": "users", "operation": "countDocuments", "filter": {}},
    {"collection": "users", "operation": "estimatedDocumentCount"},
    {"collection": "users", "operation": "distinct", "key": "country"},
    {"collection": "users", "operation": "listIndexes"},
    {"collection": "usuários😀", "operation": "find"},
    {"collection": "users", "operation": "find", "database": "analytics"},
]


@pytest.mark.parametrize("query", HAPPY_READS)
def test_validate_read_happy(query):
    assert guard.validate_mongo_read(query) == query


SAD_LOGICAL_READS = [
    {"collection": "users", "operation": "insertMany", "documents": [{}]},
    {"collection": "users", "operation": "deleteMany", "filter": {}},
    {"collection": "users", "operation": "aggregate", "pipeline": [{"$out": "stolen"}]},
    {"collection": "users", "operation": "aggregate", "pipeline": [{"$merge": {"into": "other"}}]},
    {"collection": "users", "operation": "aggregate", "pipeline": [{"$facet": {"x": [{"$out": "nested"}]}}]},
    {"collection": "users", "operation": "aggregate", "pipeline": {"$match": {}}},
    {"collection": "users", "operation": "distinct"},
]


@pytest.mark.parametrize("query", SAD_LOGICAL_READS)
def test_validate_read_sad_logical(query):
    with pytest.raises(QueryValidationError):
        guard.validate_mongo_read(query)


SAD_ABSURD_READS = [
    None,
    "find users",
    42,
    [],
    {},
    {"operation": "find"},
    {"collection": "users"},
    {"collection": "users", "operation": "mapReduce"},
    {"collection": "users", "operation": "eval"},
    {"collection": "", "operation": "find"},
    {"collection": "users", "operation": ""},
    {"collection": "users", "operation": 123},
    {"collection": "users", "operation": "find", "database": ""},
]


@pytest.mark.parametrize("query", SAD_ABSURD_READS)
def test_validate_read_sad_absurd(query):
    with pytest.raises(QueryValidationError):
        guard.validate_mongo_read(query)


@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        ("insertOne", "insert"),
        ("insertMany", "insert"),
        ("updateOne", "update"),
        ("updateMany", "update"),
        ("replaceOne", "update"),
        ("deleteOne", "delete"),
        ("deleteMany", "delete"),
        ("createIndex", "ddl"),
        ("dropIndex", "ddl"),
        ("createCollection", "ddl"),
        ("dropCollection", "ddl"),
        ("renameCollection", "ddl"),
    ],
)
def test_classify_write_happy(operation, expected):
    parsed, op = guard.classify_mongo_write({"collection": "c", "operation": operation})
    assert op == expected
    assert parsed["collection"] == "c"


def test_classify_write_rejects_reads():
    with pytest.raises(QueryValidationError, match="db_read_query"):
        guard.classify_mongo_write({"collection": "c", "operation": "find"})


@pytest.mark.parametrize("query", [None, {}, {"collection": "c", "operation": "dropEverything"}])
def test_classify_write_rejects_absurd(query):
    with pytest.raises(QueryValidationError):
        guard.classify_mongo_write(query)


def test_deeply_nested_out_is_caught():
    pipeline = [{"$lookup": {"pipeline": [{"$unionWith": {"pipeline": [{"$out": "deep"}]}}]}}]
    with pytest.raises(QueryValidationError, match=r"\$out"):
        guard.validate_mongo_read({"collection": "c", "operation": "aggregate", "pipeline": pipeline})


class TestServerSideJavaScriptIsRejected:
    """$where/$function/$accumulator run server-side JS — an injection/DoS surface barred from reads.

    Coverage includes the find filter, which the per-operation validators do not otherwise inspect.
    """

    @pytest.mark.parametrize(
        "query",
        [
            {"collection": "u", "operation": "find", "filter": {"$where": "sleep(9000)"}},
            {"collection": "u", "operation": "countDocuments", "filter": {"$where": "1 == 1"}},
            {"collection": "u", "operation": "distinct", "key": "x", "filter": {"$where": "true"}},
            {
                "collection": "u",
                "operation": "aggregate",
                "pipeline": [{"$addFields": {"x": {"$function": {"body": "f", "args": [], "lang": "js"}}}}],
            },
            {
                "collection": "u",
                "operation": "aggregate",
                "pipeline": [
                    {"$group": {"_id": 1, "v": {"$accumulator": {"init": "f", "accumulate": "f", "lang": "js"}}}}
                ],
            },
            {"collection": "u", "operation": "find", "filter": {"a": {"$elemMatch": {"$where": "deep"}}}},
        ],
    )
    def test_rejected(self, query):
        with pytest.raises(QueryValidationError, match="server-side JavaScript"):
            guard.validate_mongo_read(query)

    @pytest.mark.parametrize(
        "query",
        [
            {"collection": "u", "operation": "find", "filter": {"age": {"$gt": 18}}},
            {"collection": "u", "operation": "aggregate", "pipeline": [{"$match": {"$expr": {"$gt": ["$a", "$b"]}}}]},
            {"collection": "u", "operation": "find", "filter": {"name": {"$regex": "^a"}}},
        ],
    )
    def test_legitimate_operators_still_pass(self, query):
        """$expr (field comparison) and $regex (time-bounded) are not JS execution and stay allowed."""
        assert guard.validate_mongo_read(query) == query


class TestMongoAuditShape:
    def test_redacts_filter_and_update_values_keeps_structure(self):
        shape = guard.mongo_audit_shape(
            {
                "collection": "users",
                "operation": "updateMany",
                "filter": {"ssn": "123-45-6789", "age": {"$gt": 30}},
                "update": {"$set": {"plan": "pro"}},
            }
        )
        assert shape["collection"] == "users"  # structural metadata kept
        assert shape["operation"] == "updateMany"
        assert shape["filter"] == {"ssn": "?", "age": {"$gt": "?"}}  # keys/operators kept, values hidden
        assert shape["update"] == {"$set": {"plan": "?"}}

    def test_redacts_inserted_documents(self):
        shape = guard.mongo_audit_shape(
            {"collection": "u", "operation": "insertMany", "documents": [{"name": "Alice", "ssn": "111"}]}
        )
        assert shape["documents"] == [{"name": "?", "ssn": "?"}]

    def test_does_not_mutate_the_original(self):
        query = {"collection": "u", "operation": "deleteMany", "filter": {"id": 7}}
        guard.mongo_audit_shape(query)
        assert query["filter"] == {"id": 7}


class TestBoundedMongoWrite:
    @pytest.mark.parametrize("operation", ["updateMany", "deleteMany"])
    @pytest.mark.parametrize("query_extra", [{}, {"filter": {}}, {"filter": None}])
    def test_rejects_empty_or_missing_filter(self, operation, query_extra):
        parsed, _ = guard.classify_mongo_write({"collection": "c", "operation": operation, **query_extra})
        with pytest.raises(QueryValidationError, match="every document"):
            guard.ensure_bounded_mongo_write(parsed)

    @pytest.mark.parametrize("operation", ["updateMany", "deleteMany"])
    @pytest.mark.parametrize("flt", [{"id": 1}, {"$or": [{"a": 1}, {"b": 2}]}, {"nested.path": {"$exists": True}}])
    def test_allows_non_empty_filter(self, operation, flt):
        parsed, _ = guard.classify_mongo_write({"collection": "c", "operation": operation, "filter": flt})
        guard.ensure_bounded_mongo_write(parsed)

    @pytest.mark.parametrize("operation", ["updateOne", "deleteOne", "insertMany", "dropCollection"])
    def test_ignores_naturally_bounded_ops(self, operation):
        parsed, _ = guard.classify_mongo_write({"collection": "c", "operation": operation})
        guard.ensure_bounded_mongo_write(parsed)
