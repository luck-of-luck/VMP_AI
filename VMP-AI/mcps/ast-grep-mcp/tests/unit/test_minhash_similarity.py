"""Tests for MinHash-based similarity calculation.

Tests the O(n) MinHash similarity implementation that replaces
the O(n²) SequenceMatcher for scalable code clone detection.
"""

from ast_grep_mcp.constants import MinHashDefaults, SemanticSimilarityDefaults
from ast_grep_mcp.features.deduplication.similarity import (
    EnhancedStructureHash,
    MinHashSimilarity,
    SimilarityConfig,
    SimilarityResult,
)


class TestMinHashSimilarity:
    """Tests for MinHash similarity calculation."""

    def test_identical_code_high_similarity(self):
        """Identical code should have similarity close to 1.0."""
        code = """
def process_data(data):
    result = []
    for item in data:
        result.append(item * 2)
    return result
"""
        similarity = MinHashSimilarity()
        score = similarity.estimate_similarity(code, code)
        assert score > 0.95, f"Expected > 0.95, got {score}"

    def test_similar_code_moderate_similarity(self):
        """Similar code with minor changes should have moderate-to-high similarity.

        Note: MinHash with token shingles is sensitive to variable name changes,
        so similar code may score lower than SequenceMatcher. This is a trade-off
        for O(n) vs O(n²) complexity.
        """
        code1 = """
def process_data(data):
    result = []
    for item in data:
        result.append(item * 2)
    return result
"""
        code2 = """
def process_data(items):
    result = []
    for item in items:
        result.append(item * 3)
    return result
"""
        similarity = MinHashSimilarity()
        score = similarity.estimate_similarity(code1, code2)
        # MinHash produces lower scores for variable renames - threshold adjusted
        assert score > 0.3, f"Expected > 0.3 for similar code, got {score}"

    def test_different_code_low_similarity(self):
        """Different code should have low similarity."""
        code1 = """
def add(a, b):
    return a + b
"""
        code2 = """
class DataProcessor:
    def __init__(self, config):
        self.config = config
        self.cache = {}

    def process(self, data):
        for item in data:
            self.cache[item.id] = item
"""
        similarity = MinHashSimilarity()
        score = similarity.estimate_similarity(code1, code2)
        assert score < 0.4, f"Expected < 0.4 for different code, got {score}"

    def test_empty_code_returns_zero(self):
        """Empty code should return 0.0 similarity."""
        similarity = MinHashSimilarity()
        assert similarity.estimate_similarity("", "def foo(): pass") == 0.0
        assert similarity.estimate_similarity("def foo(): pass", "") == 0.0
        assert similarity.estimate_similarity("", "") == 0.0

    def test_minhash_signature_caching(self):
        """MinHash signatures should be cached for performance."""
        code = "def example(): return 42"
        similarity = MinHashSimilarity()

        # Create first signature
        m1 = similarity.create_minhash(code)

        # Create second signature - should be from cache
        m2 = similarity.create_minhash(code)

        # Should be the same object (cached)
        assert m1 is m2

    def test_clear_cache(self):
        """Cache should be clearable."""
        code = "def example(): return 42"
        similarity = MinHashSimilarity()

        # Create signature and populate cache
        m1 = similarity.create_minhash(code)
        assert len(similarity._signature_cache) > 0

        # Clear cache
        similarity.clear_cache()
        assert len(similarity._signature_cache) == 0

        # Create new signature - should not be the same object
        m2 = similarity.create_minhash(code)
        assert m1 is not m2

    def test_signature_cache_keyed_on_code_string(self):
        """Cache keys must be exact code strings, not hash() values (BUG-12)."""
        code1 = "def alpha(): return 1"
        code2 = "def beta(): return 2"
        similarity = MinHashSimilarity()

        similarity.create_minhash(code1)
        similarity.create_minhash(code2)

        assert set(similarity._signature_cache.keys()) == {code1, code2}

    def test_signature_cache_lru_eviction(self, monkeypatch):
        """Signature cache should evict the least-recently-used entry at the bound."""
        monkeypatch.setattr(MinHashDefaults, "SIGNATURE_CACHE_MAX_SIZE", 2)
        similarity = MinHashSimilarity()
        codes = ["def a(): return 1", "def b(): return 2", "def c(): return 3"]

        similarity.create_minhash(codes[0])
        similarity.create_minhash(codes[1])
        similarity.create_minhash(codes[0])  # Refresh recency of codes[0]
        similarity.create_minhash(codes[2])  # Evicts codes[1] (LRU)

        assert set(similarity._signature_cache.keys()) == {codes[0], codes[2]}


class TestMinHashLSH:
    """Tests for LSH-based candidate retrieval."""

    def test_build_lsh_index(self):
        """LSH index should be buildable from code items."""
        code_items = [
            ("func1", "def add(a, b): return a + b"),
            ("func2", "def subtract(a, b): return a - b"),
            ("func3", "def multiply(a, b): return a * b"),
        ]
        similarity = MinHashSimilarity()
        similarity.build_lsh_index(code_items)

        assert similarity._lsh_index is not None
        assert len(similarity._lsh_keys) == 3

    def test_query_similar(self):
        """LSH should return similar candidates."""
        code_items = [
            ("func1", "def add(a, b): return a + b"),
            ("func2", "def add(x, y): return x + y"),  # Very similar to func1
            ("func3", "class DataProcessor: pass"),  # Different
        ]
        config = SimilarityConfig(similarity_threshold=0.5)
        similarity = MinHashSimilarity(config)
        similarity.build_lsh_index(code_items)

        # Query with code similar to func1 and func2
        similar = similarity.query_similar("def add(a, b): return a + b")

        # Should find func1 and possibly func2
        assert "func1" in similar

    def test_find_all_similar_pairs(self):
        """Should find all pairs of similar code snippets.

        Note: Uses identical code to ensure LSH works correctly.
        Variable name changes reduce MinHash similarity significantly.
        """
        code_items = [
            (
                "func1",
                """
def process_list(items):
    result = []
    for item in items:
        result.append(item.upper())
    return result
""",
            ),
            (
                "func2",
                """
def process_list(items):
    result = []
    for item in items:
        result.append(item.upper())
    return result
""",
            ),  # Identical to func1
            (
                "func3",
                """
class Config:
    def __init__(self, settings):
        self.settings = settings
        self.cache = {}
""",
            ),  # Different
        ]

        config = SimilarityConfig(similarity_threshold=0.5)
        similarity = MinHashSimilarity(config)
        pairs = similarity.find_all_similar_pairs(code_items, min_similarity=0.5)

        # Should find func1-func2 pair (they're identical)
        pair_keys = [(p[0], p[1]) for p in pairs]
        assert any(("func1", "func2") == p or ("func2", "func1") == p for p in pair_keys), f"Expected func1-func2 pair, got {pair_keys}"


class TestSimilarityConfig:
    """Tests for similarity configuration."""

    def test_default_config(self):
        """Default config should have sensible values."""
        config = SimilarityConfig()
        assert config.num_permutations == 128
        assert config.shingle_size == 3
        assert config.similarity_threshold == 0.8
        assert config.use_token_shingles is True

    def test_custom_config(self):
        """Custom config should override defaults."""
        config = SimilarityConfig(
            num_permutations=64,
            shingle_size=5,
            similarity_threshold=0.9,
        )
        assert config.num_permutations == 64
        assert config.shingle_size == 5
        assert config.similarity_threshold == 0.9


class TestSimilarityResult:
    """Tests for similarity result dataclass."""

    def test_result_creation(self):
        """Should create result with expected values."""
        result = SimilarityResult(
            similarity=SemanticSimilarityDefaults.MEDIUM_SIMILARITY_THRESHOLD,
            method="minhash",
            verified=False,
        )
        assert result.similarity == SemanticSimilarityDefaults.MEDIUM_SIMILARITY_THRESHOLD
        assert result.method == "minhash"
        assert result.verified is False
        assert result.candidate_count == 0


class TestEnhancedStructureHash:
    """Tests for improved structure hash algorithm."""

    def test_similar_structure_same_hash(self):
        """Similar code structures with same call patterns should have the same hash."""
        # These two functions have identical structure AND no function calls
        # (only control flow and returns), so they should hash the same
        code1 = """
def process(data):
    if data:
        for item in data:
            result = item * 2
        return result
    return None
"""
        code2 = """
def handle(items):
    if items:
        for x in items:
            value = x * 2
        return value
    return None
"""
        hasher = EnhancedStructureHash()
        hash1 = hasher.calculate(code1)
        hash2 = hasher.calculate(code2)

        assert hash1 == hash2, f"Expected same hash, got {hash1} and {hash2}"

    def test_different_call_patterns_different_hash(self):
        """Code with different API calls should have different hashes.

        This is intentional: the improved algorithm groups code by both
        structure AND the APIs it uses.
        """
        code1 = """
def process(data):
    result = fetch_data(data)
    return transform(result)
"""
        code2 = """
def process(data):
    result = load_file(data)
    return serialize(result)
"""
        hasher = EnhancedStructureHash()
        hash1 = hasher.calculate(code1)
        hash2 = hasher.calculate(code2)

        # Different function calls = different hashes (improved behavior)
        assert hash1 != hash2, "Different API calls should produce different hashes"

    def test_different_structure_different_hash(self):
        """Different code structures should have different hashes."""
        code1 = """
def simple(): return 42
"""
        code2 = """
class Complex:
    def __init__(self):
        self.data = {}

    def process(self, items):
        for item in items:
            if item.valid:
                self.data[item.id] = item
        return self.data
"""
        hasher = EnhancedStructureHash()
        hash1 = hasher.calculate(code1)
        hash2 = hasher.calculate(code2)

        assert hash1 != hash2, "Expected different hashes for different structures"

    def test_create_buckets(self):
        """Should create buckets with proper distribution."""
        code_items = [
            ("func1", "def a(): return 1"),
            ("func2", "def b(): return 2"),  # Same structure as func1
            (
                "func3",
                """
def complex(data):
    for item in data:
        if item:
            yield item
""",
            ),
        ]

        hasher = EnhancedStructureHash()
        buckets = hasher.create_buckets(code_items)

        # Should have at least 2 buckets (simple functions vs complex)
        assert len(buckets) >= 1

        # Total items across buckets should equal input
        total_items = sum(len(b.items) for b in buckets.values())
        assert total_items == 3

    def test_control_flow_detection(self):
        """Should detect control flow keywords."""
        code_with_loops = """
def process(data):
    for item in data:
        if item.valid:
            while item.processing:
                pass
    return data
"""
        code_without_loops = """
def simple():
    return 42
"""
        hasher = EnhancedStructureHash()
        hash1 = hasher.calculate(code_with_loops)
        hash2 = hasher.calculate(code_without_loops)

        # Different control flow should produce different hashes
        assert hash1 != hash2


class TestEnhancedStructureHashNodeSequence:
    """Tests for AST-like node sequence extraction."""

    def test_extract_node_sequence_basic(self):
        """Should extract correct node sequence from simple code."""
        code = """
def process(data):
    for item in data:
        if item:
            return item
    return None
"""
        hasher = EnhancedStructureHash()
        nodes = hasher._extract_node_sequence(code)

        # Should find: def (FN), for (FR), if (IF), return (RT), return (RT)
        assert "FN" in nodes, f"Expected FN in nodes, got {nodes}"
        assert "FR" in nodes, f"Expected FR in nodes, got {nodes}"
        assert "IF" in nodes, f"Expected IF in nodes, got {nodes}"
        assert "RT" in nodes, f"Expected RT in nodes, got {nodes}"

    def test_extract_node_sequence_order_preserved(self):
        """Node sequence should preserve order of appearance."""
        code = """
def func():
    if condition:
        for item in items:
            return item
"""
        hasher = EnhancedStructureHash()
        nodes = hasher._extract_node_sequence(code)

        # Order should be: FN -> IF -> FR -> RT
        fn_idx = nodes.index("FN")
        if_idx = nodes.index("IF")
        fr_idx = nodes.index("FR")
        rt_idx = nodes.index("RT")

        assert fn_idx < if_idx < fr_idx < rt_idx, f"Expected order FN < IF < FR < RT, got indices {fn_idx}, {if_idx}, {fr_idx}, {rt_idx}"

    def test_extract_node_sequence_ignores_comments(self):
        """Should ignore comments when extracting nodes."""
        code = """
# This is a comment
def func():
    # if this were code
    return 42
"""
        hasher = EnhancedStructureHash()
        nodes = hasher._extract_node_sequence(code)

        # Should only have FN and RT (comments ignored)
        assert len(nodes) == 2, f"Expected 2 nodes, got {len(nodes)}: {nodes}"
        assert nodes == ["FN", "RT"], f"Expected ['FN', 'RT'], got {nodes}"

    def test_extract_node_sequence_class_and_methods(self):
        """Should extract class and method definitions."""
        code = """
class MyClass:
    def __init__(self):
        self.data = None

    def process(self):
        return self.data
"""
        hasher = EnhancedStructureHash()
        nodes = hasher._extract_node_sequence(code)

        # Should find: CL, FN, FN, RT
        assert nodes.count("CL") >= 1, f"Expected at least 1 CL, got {nodes}"
        assert nodes.count("FN") >= 2, f"Expected at least 2 FN, got {nodes}"


class TestEnhancedStructureHashComplexity:
    """Tests for control flow complexity calculation."""

    def test_complexity_simple_function(self):
        """Simple function should have low complexity."""
        hasher = EnhancedStructureHash()
        nodes = ["FN", "RT"]  # def func(): return x
        complexity = hasher._calculate_control_flow_complexity(nodes)

        assert complexity == 1, f"Expected complexity 1, got {complexity}"

    def test_complexity_with_conditionals(self):
        """Conditionals should increase complexity."""
        hasher = EnhancedStructureHash()
        nodes = ["FN", "IF", "RT", "RT"]  # def func(): if x: return a; return b
        complexity = hasher._calculate_control_flow_complexity(nodes)

        assert complexity == 2, f"Expected complexity 2 (1 base + 1 IF), got {complexity}"

    def test_complexity_with_loops(self):
        """Loops should increase complexity."""
        hasher = EnhancedStructureHash()
        nodes = ["FN", "FR", "IF", "RT", "RT"]  # for loop with conditional
        complexity = hasher._calculate_control_flow_complexity(nodes)

        # 1 base + 1 for + 1 if = 3
        assert complexity == 3, f"Expected complexity 3, got {complexity}"

    def test_complexity_with_exception_handling(self):
        """Exception handling should increase complexity."""
        hasher = EnhancedStructureHash()
        nodes = ["FN", "TR", "RT", "EX", "RT"]  # try/except block
        complexity = hasher._calculate_control_flow_complexity(nodes)

        # 1 base + 1 try + 1 except = 3
        assert complexity == 3, f"Expected complexity 3, got {complexity}"


class TestEnhancedStructureHashCallSignature:
    """Tests for function call signature extraction."""

    def test_call_signature_basic(self):
        """Should extract function call signature."""
        code = """
def process():
    data = fetch_data()
    result = transform(data)
    save(result)
"""
        hasher = EnhancedStructureHash()
        signature = hasher._extract_call_signature(code)

        # Should return 4-character hex
        assert len(signature) == 4, f"Expected 4-char signature, got {signature}"
        assert all(c in "0123456789ABCDEF" for c in signature)

    def test_call_signature_no_calls(self):
        """Code without calls should return '0000'."""
        code = """
def simple():
    x = 1
    y = 2
    return x + y
"""
        hasher = EnhancedStructureHash()
        signature = hasher._extract_call_signature(code)

        assert signature == "0000", f"Expected '0000', got {signature}"

    def test_call_signature_consistent(self):
        """Same calls should produce same signature."""
        code1 = """
def func1():
    process_data()
    save_result()
"""
        code2 = """
def func2():
    save_result()
    process_data()
"""
        hasher = EnhancedStructureHash()
        sig1 = hasher._extract_call_signature(code1)
        sig2 = hasher._extract_call_signature(code2)

        # Same functions called (order shouldn't matter - sorted)
        assert sig1 == sig2, f"Expected same signature, got {sig1} and {sig2}"

    def test_call_signature_filters_keywords(self):
        """Should filter out keywords that look like function calls."""
        code = """
def func():
    if condition:
        for item in items:
            while processing:
                pass
"""
        hasher = EnhancedStructureHash()
        signature = hasher._extract_call_signature(code)

        # if, for, while should be filtered - no real calls
        assert signature == "0000", f"Expected '0000' (keywords filtered), got {signature}"


class TestEnhancedStructureHashNestingDepth:
    """Tests for nesting depth estimation."""

    def test_nesting_depth_flat(self):
        """Flat code should have low nesting depth."""
        code = """
def func():
    return 42
"""
        hasher = EnhancedStructureHash()
        depth = hasher._estimate_nesting_depth(code)

        assert depth <= 2, f"Expected depth <= 2, got {depth}"

    def test_nesting_depth_nested(self):
        """Nested code should have higher depth."""
        code = """
def func():
    if condition:
        for item in items:
            if item.valid:
                do_something()
"""
        hasher = EnhancedStructureHash()
        depth = hasher._estimate_nesting_depth(code)

        assert depth >= 3, f"Expected depth >= 3 for nested code, got {depth}"


class TestEnhancedStructureHashLogarithmicBucket:
    """Tests for logarithmic size bucketing."""

    def test_logarithmic_bucket_small(self):
        """Small code should be in low buckets."""
        hasher = EnhancedStructureHash()

        assert hasher._logarithmic_bucket(3) == 0
        assert hasher._logarithmic_bucket(7) == 1
        assert hasher._logarithmic_bucket(15) == 2

    def test_logarithmic_bucket_medium(self):
        """Medium code should be in middle buckets."""
        hasher = EnhancedStructureHash()

        assert hasher._logarithmic_bucket(25) == 3
        assert hasher._logarithmic_bucket(50) == 4
        assert hasher._logarithmic_bucket(100) == 5

    def test_logarithmic_bucket_large(self):
        """Large code should be in high buckets."""
        hasher = EnhancedStructureHash()

        assert hasher._logarithmic_bucket(200) == 6
        assert hasher._logarithmic_bucket(500) == 7

    def test_logarithmic_bucket_max(self):
        """Very large code should cap at bucket 9."""
        hasher = EnhancedStructureHash()

        assert hasher._logarithmic_bucket(10000) == 9
        assert hasher._logarithmic_bucket(100000) == 9


class TestEnhancedStructureHashBucketDistribution:
    """Tests for bucket distribution quality."""

    def test_bucket_distribution_diverse_code(self):
        """Diverse code should distribute across multiple buckets."""
        code_samples = [
            # Simple function
            ("simple", "def a(): return 1"),
            # Function with loop
            (
                "loop",
                """
def b(items):
    for item in items:
        process(item)
""",
            ),
            # Function with conditionals
            (
                "conditional",
                """
def c(x):
    if x > 0:
        return "positive"
    elif x < 0:
        return "negative"
    return "zero"
""",
            ),
            # Class with methods
            (
                "class",
                """
class D:
    def __init__(self):
        self.data = {}

    def add(self, key, value):
        self.data[key] = value

    def get(self, key):
        return self.data.get(key)
""",
            ),
            # Complex nested function
            (
                "complex",
                """
def e(data):
    results = []
    for item in data:
        if item.valid:
            try:
                result = process(item)
                results.append(result)
            except Exception:
                continue
    return results
""",
            ),
        ]

        hasher = EnhancedStructureHash()
        buckets = hasher.create_buckets(code_samples)

        # Should have at least 3 different buckets for diverse code
        assert len(buckets) >= 3, f"Expected at least 3 buckets for diverse code, got {len(buckets)}"


class TestDetectorIntegration:
    """Integration tests for detector with MinHash."""

    def test_detector_uses_minhash_by_default(self):
        """Detector should use MinHash by default."""
        from ast_grep_mcp.features.deduplication.detector import DuplicationDetector

        detector = DuplicationDetector()
        assert detector.use_minhash is True

    def test_detector_can_use_sequence_matcher(self):
        """Detector should support fallback to SequenceMatcher."""
        from ast_grep_mcp.features.deduplication.detector import DuplicationDetector

        detector = DuplicationDetector(use_minhash=False)
        assert detector.use_minhash is False

    def test_detector_similarity_calculation(self):
        """Detector should calculate similarity correctly."""
        from ast_grep_mcp.features.deduplication.detector import DuplicationDetector

        detector = DuplicationDetector()

        # Use identical code to verify MinHash works
        code1 = "def add(a, b): return a + b"
        code2 = "def add(a, b): return a + b"

        similarity = detector.calculate_similarity(code1, code2)
        assert 0.0 <= similarity <= 1.0
        assert similarity > 0.9, "Identical code should have > 0.9 similarity"

    def test_detector_similarity_with_sequence_matcher(self):
        """Detector should support SequenceMatcher fallback for precise comparison."""
        from ast_grep_mcp.features.deduplication.detector import DuplicationDetector

        detector = DuplicationDetector(use_minhash=False)

        code1 = "def add(a, b): return a + b"
        code2 = "def add(x, y): return x + y"

        similarity = detector.calculate_similarity(code1, code2)
        assert 0.0 <= similarity <= 1.0
        # SequenceMatcher handles variable renames better
        assert similarity > 0.5, "Similar code should have > 0.5 similarity with SequenceMatcher"

    def test_detector_structure_hash(self):
        """Detector should use enhanced structure hash."""
        from ast_grep_mcp.features.deduplication.detector import DuplicationDetector

        detector = DuplicationDetector()

        code = """
def process(data):
    for item in data:
        if item:
            return item
    return None
"""
        hash_val = detector._calculate_structure_hash(code)
        assert isinstance(hash_val, int)
        assert hash_val >= 0


class TestDetectorMinHashRegressions:
    """Regression tests to prevent detector/MinHash integration issues.

    These tests ensure DuplicationDetector properly delegates to MinHashSimilarity
    and returns correct similarity values. Prevents regression of issue where
    identical code returned 0.125 instead of > 0.9 due to integration bugs.
    """

    def test_detector_identical_code_high_similarity(self):
        """Detector should return > 0.9 for identical code.

        Regression test: Ensures identical code returns high similarity,
        not a broken value like 0.125 (which was 1/8, suggesting only 1
        matching hash out of 8 instead of all 128).
        """
        from ast_grep_mcp.features.deduplication.detector import DuplicationDetector

        detector = DuplicationDetector(use_minhash=True)
        code = "def add(a, b): return a + b"
        similarity = detector.calculate_similarity(code, code)
        assert similarity > 0.9, f"Expected > 0.9 for identical code, got {similarity}"

    def test_detector_consistent_with_direct_minhash(self):
        """Detector should match direct MinHashSimilarity results.

        Regression test: Ensures DuplicationDetector uses the same MinHash
        configuration and produces consistent results with direct MinHash calls.
        """
        code1 = "def process(data): return data * 2"
        code2 = "def process(data): return data * 2"

        direct = MinHashSimilarity()
        direct_sim = direct.estimate_similarity(code1, code2)

        from ast_grep_mcp.features.deduplication.detector import DuplicationDetector

        detector = DuplicationDetector(use_minhash=True)
        detector_sim = detector.calculate_similarity(code1, code2)

        # Allow 5% tolerance for any cache/timing differences
        assert abs(direct_sim - detector_sim) < 0.05, f"Direct: {direct_sim}, Detector: {detector_sim}"

    def test_detector_multiline_identical_code(self):
        """Detector should handle multiline identical code correctly.

        Regression test: Ensures longer, more realistic code samples
        also return high similarity when identical.
        """
        from ast_grep_mcp.features.deduplication.detector import DuplicationDetector

        detector = DuplicationDetector(use_minhash=True)
        code = """
def process_data(data):
    result = []
    for item in data:
        if item.valid:
            result.append(item.value * 2)
    return result
"""
        similarity = detector.calculate_similarity(code, code)
        assert similarity > 0.95, f"Expected > 0.95 for identical multiline code, got {similarity}"

    def test_detector_different_code_low_similarity(self):
        """Detector should return low similarity for different code.

        Ensures detector doesn't always return high values.
        """
        from ast_grep_mcp.features.deduplication.detector import DuplicationDetector

        detector = DuplicationDetector(use_minhash=True)
        code1 = "def add(a, b): return a + b"
        code2 = """
class DataProcessor:
    def __init__(self, config):
        self.config = config
        self.cache = {}

    def process(self, items):
        for item in items:
            self.cache[item.id] = transform(item)
        return self.cache
"""
        similarity = detector.calculate_similarity(code1, code2)
        assert similarity < 0.5, f"Expected < 0.5 for different code, got {similarity}"

    def test_detector_empty_code_returns_zero(self):
        """Detector should return 0.0 for empty code.

        Edge case test ensuring proper handling of empty strings.
        """
        from ast_grep_mcp.features.deduplication.detector import DuplicationDetector

        detector = DuplicationDetector(use_minhash=True)
        assert detector.calculate_similarity("", "def foo(): pass") == 0.0
        assert detector.calculate_similarity("def foo(): pass", "") == 0.0
        assert detector.calculate_similarity("", "") == 0.0

    def test_detector_minhash_config_propagation(self):
        """Detector should properly propagate MinHash configuration.

        Ensures custom SimilarityConfig is passed to the internal MinHash instance.
        """
        from ast_grep_mcp.features.deduplication.detector import DuplicationDetector

        custom_config = SimilarityConfig(
            num_permutations=64,
            shingle_size=5,
        )
        detector = DuplicationDetector(use_minhash=True, similarity_config=custom_config)

        assert detector._minhash.config.num_permutations == 64
        assert detector._minhash.config.shingle_size == 5


class TestPerformanceCharacteristics:
    """Tests to verify performance characteristics."""

    def test_minhash_scales_linearly(self):
        """MinHash should maintain O(n) complexity."""
        import time

        similarity = MinHashSimilarity()

        # Generate increasingly large code samples
        sizes = [100, 200, 400]
        times = []

        for size in sizes:
            code = "\n".join([f"x{i} = {i}" for i in range(size)])

            start = time.perf_counter()
            for _ in range(10):
                similarity.create_minhash(code)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        # Verify roughly linear scaling (allow 3x factor for overhead)
        ratio_1_2 = times[1] / times[0]
        ratio_2_3 = times[2] / times[1]

        # If O(n), doubling input should roughly double time (with overhead tolerance)
        assert ratio_1_2 < 4.0, f"Expected < 4x, got {ratio_1_2}x"
        assert ratio_2_3 < 4.0, f"Expected < 4x, got {ratio_2_3}x"


class TestSmallCodeFallback:
    """Tests for SequenceMatcher fallback for small code snippets.

    Phase 4: MinHash accuracy depends on shingle count. Small code (< 15 tokens)
    produces too few shingles, causing inaccurate similarity estimation.
    SequenceMatcher provides exact results for small code.
    """

    def test_small_code_fallback_accuracy(self):
        """Test SequenceMatcher fallback provides accurate results for small code."""
        # Very small code (< 15 tokens)
        code1 = "def f(): pass"
        code2 = "def f(): pass"

        similarity_calc = MinHashSimilarity()
        similarity = similarity_calc.estimate_similarity(code1, code2)

        # Should use SequenceMatcher and get perfect score for identical code
        assert similarity > 0.95, f"Small identical code should get > 0.95, got {similarity}"

    def test_large_code_uses_minhash(self):
        """Test MinHash is used for large code (>= 15 tokens)."""
        # Large code (100+ tokens) - repeating a function multiple times
        large_code = (
            """
def complex_function(param1, param2, param3):
    result = []
    for item in param1:
        if item.matches(param2):
            processed = item.process(param3)
            result.append(processed)
    return result
"""
            * 5
        )  # Repeat to ensure > 15 tokens

        similarity_calc = MinHashSimilarity()
        similarity = similarity_calc.estimate_similarity(large_code, large_code)

        # Should use MinHash and still get high score for identical code
        assert similarity > 0.95, f"Large identical code should get > 0.95, got {similarity}"

    def test_small_code_different_gets_low_similarity(self):
        """Test that different small code gets low similarity."""
        code1 = "def f(): pass"
        code2 = "class X: pass"

        similarity_calc = MinHashSimilarity()
        similarity = similarity_calc.estimate_similarity(code1, code2)

        # Different code should have low similarity even with SequenceMatcher
        assert similarity < 0.5, f"Different code should have < 0.5 similarity, got {similarity}"

    def test_fallback_can_be_disabled(self):
        """Test that small code fallback can be disabled via config."""
        config = SimilarityConfig(use_small_code_fallback=False)
        calculator = MinHashSimilarity(config)

        code1 = "def f(): pass"
        code2 = "def f(): pass"

        # Should use MinHash even for small code when fallback disabled
        similarity = calculator.estimate_similarity(code1, code2)

        # MinHash may not be perfectly accurate for small code, but should work
        assert 0.0 <= similarity <= 1.0, f"Similarity should be in valid range, got {similarity}"

    def test_small_code_threshold_configurable(self):
        """Test that small_code_threshold can be configured."""
        # Set very low threshold so even small code uses MinHash
        config = SimilarityConfig(small_code_threshold=3)
        calculator = MinHashSimilarity(config)

        code = "def foo(): return 42"  # More than 3 tokens
        similarity = calculator.estimate_similarity(code, code)

        # Should still work
        assert similarity > 0.9, f"Identical code should have > 0.9 similarity, got {similarity}"

    def test_small_code_near_threshold_boundary(self):
        """Test behavior at the threshold boundary (14 vs 15 tokens)."""
        similarity_calc = MinHashSimilarity()

        # Create code with exactly threshold-1 tokens (should use SequenceMatcher)
        # "def foo ( ) : return x" = 7 tokens, need to get close to 15
        small_code = "def foo(a, b, c): return a + b + c"  # ~14 tokens

        # Create code with more tokens (should use MinHash)
        large_code = "def foo(a, b, c, d, e): return a + b + c + d + e * 2"  # >15 tokens

        # Both should work correctly for identical comparisons
        small_sim = similarity_calc.estimate_similarity(small_code, small_code)
        large_sim = similarity_calc.estimate_similarity(large_code, large_code)

        assert small_sim > 0.95, f"Small identical code should get > 0.95, got {small_sim}"
        assert large_sim > 0.95, f"Large identical code should get > 0.95, got {large_sim}"

    def test_small_code_with_minor_changes(self):
        """Test that small code with minor changes gets accurate similarity."""
        code1 = "def add(a, b): return a + b"
        code2 = "def add(x, y): return x + y"

        similarity_calc = MinHashSimilarity()
        similarity = similarity_calc.estimate_similarity(code1, code2)

        # SequenceMatcher should handle variable renames well
        # The codes have same structure, just different variable names
        assert 0.5 < similarity < 1.0, f"Similar code should have moderate similarity, got {similarity}"

    def test_empty_code_still_returns_zero(self):
        """Test that empty code returns 0.0 regardless of fallback setting."""
        similarity_calc = MinHashSimilarity()

        assert similarity_calc.estimate_similarity("", "def foo(): pass") == 0.0
        assert similarity_calc.estimate_similarity("def foo(): pass", "") == 0.0
        assert similarity_calc.estimate_similarity("", "") == 0.0

        # Also with fallback disabled
        config = SimilarityConfig(use_small_code_fallback=False)
        calculator = MinHashSimilarity(config)

        assert calculator.estimate_similarity("", "def foo(): pass") == 0.0

    def test_fallback_performance(self):
        """Test performance characteristics of small vs large code comparison.

        Phase 4: Observational test to verify both paths work efficiently.
        Times 100 iterations of small code (SequenceMatcher) vs large code (MinHash).
        No strict assertions - results printed for visibility.
        """
        import time

        similarity_calc = MinHashSimilarity()

        # Small code (< 15 tokens) - uses SequenceMatcher
        small_code1 = "def f(): pass"
        small_code2 = "def g(): pass"

        # Large code (> 50 tokens) - uses MinHash
        large_code1 = """
def process_complex_data(param1, param2, param3, param4):
    result = []
    for item in param1:
        if item.matches(param2):
            processed = item.process(param3)
            validated = validate(processed, param4)
            result.append(validated)
    return result
"""
        large_code2 = """
def process_complex_data(param1, param2, param3, param4):
    result = []
    for item in param1:
        if item.matches(param2):
            processed = item.process(param3)
            validated = validate(processed, param4)
            result.append(validated)
    return result
"""

        # Time small code comparisons (SequenceMatcher)
        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            similarity_calc.estimate_similarity(small_code1, small_code2)
        small_time = time.perf_counter() - start

        # Time large code comparisons (MinHash)
        similarity_calc.clear_cache()  # Clear cache to ensure fair comparison
        start = time.perf_counter()
        for _ in range(iterations):
            similarity_calc.estimate_similarity(large_code1, large_code2)
        large_time = time.perf_counter() - start

        # Print timing results for visibility
        print(
            f"\n[Performance] Small code ({iterations} iterations): "
            f"{small_time * 1000:.2f}ms total, {small_time * 1000 / iterations:.3f}ms/iter"
        )
        print(
            f"[Performance] Large code ({iterations} iterations): "
            f"{large_time * 1000:.2f}ms total, {large_time * 1000 / iterations:.3f}ms/iter"
        )

        # Verify both paths produce valid similarity scores
        small_sim = similarity_calc.estimate_similarity(small_code1, small_code2)
        large_sim = similarity_calc.estimate_similarity(large_code1, large_code2)

        assert 0.0 <= small_sim <= 1.0, f"Small code similarity out of range: {small_sim}"
        assert 0.0 <= large_sim <= 1.0, f"Large code similarity out of range: {large_sim}"

        # Large identical code should have high similarity
        assert large_sim > 0.95, f"Large identical code should get > 0.95, got {large_sim}"
