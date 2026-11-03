"""Tests for extracted Flask route parser helpers."""

import re

from ast_grep_mcp.features.documentation.api_docs_generator import FlaskRouteParser


class TestParseDecoratorMatch:
    parser = FlaskRouteParser()

    def _match(self, line: str) -> "re.Match[str] | None":
        return self.parser._DECORATOR_RE.search(line)

    def test_simple_route(self):
        m = self._match("@app.route('/users')")
        assert m is not None
        path, methods = self.parser._parse_decorator_match(m)
        assert path == "/users"
        assert methods == ["GET"]

    def test_route_with_methods(self):
        m = self._match("@app.route('/users', methods=['GET', 'POST'])")
        assert m is not None
        path, methods = self.parser._parse_decorator_match(m)
        assert path == "/users"
        assert set(methods) == {"GET", "POST"}

    def test_blueprint_route(self):
        m = self._match("@bp.route('/items')")
        assert m is not None
        path, _ = self.parser._parse_decorator_match(m)
        assert path == "/items"


class TestFindNextHandlerName:
    parser = FlaskRouteParser()

    def test_finds_def_on_next_line(self):
        lines = ["@app.route('/x')", "def get_x():", "    return x"]
        assert self.parser._find_next_handler_name(lines, 0) == "get_x"

    def test_skips_decorators(self):
        lines = ["@app.route('/x')", "@login_required", "def get_x():", "    pass"]
        assert self.parser._find_next_handler_name(lines, 0) == "get_x"

    def test_returns_unknown_when_no_def(self):
        lines = ["@app.route('/x')", "x = 1"]
        assert self.parser._find_next_handler_name(lines, 0) == "unknown"

    def test_returns_unknown_at_eof(self):
        lines = ["@app.route('/x')"]
        assert self.parser._find_next_handler_name(lines, 0) == "unknown"


class TestBuildRoutesForMethods:
    parser = FlaskRouteParser()

    def test_single_method(self):
        routes = self.parser._build_routes_for_methods("/api/users", ["GET"], "list_users", "app.py", 5)
        assert len(routes) == 1
        assert routes[0].method == "GET"
        assert routes[0].handler_name == "list_users"
        assert routes[0].line_number == 6

    def test_multiple_methods(self):
        routes = self.parser._build_routes_for_methods("/api/users", ["GET", "post"], "users", "app.py", 10)
        assert len(routes) == 2
        assert routes[0].method == "GET"
        assert routes[1].method == "POST"

    def test_path_params_extracted(self):
        routes = self.parser._build_routes_for_methods("/users/<int:id>", ["GET"], "get_user", "app.py", 0)
        assert len(routes[0].parameters) == 1
        assert routes[0].parameters[0].name == "id"
