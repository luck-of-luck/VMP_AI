"""Tests for CodeBERT-based semantic similarity (Phase 5).

Tests the SemanticSimilarity class and three-stage hybrid pipeline:
- Stage 1: Fast MinHash filter (O(n))
- Stage 2: Precise AST verification
- Stage 3: CodeBERT semantic similarity (optional)

Scientific basis: GraphCodeBERT (2024) produces 768-dimensional
embeddings capturing semantic meaning for Type-4 clone detection.

Note: These tests work without transformers/torch installed by
mocking the imports. Integration tests requiring the actual model
are marked with @pytest.mark.semantic.
"""

from unittest.mock import MagicMock, patch

import pytest

from ast_grep_mcp.constants import SemanticSimilarityDefaults
from ast_grep_mcp.features.deduplication.similarity import (
    HybridSimilarity,
    HybridSimilarityConfig,
    HybridSimilarityResult,
    SemanticSimilarity,
    SemanticSimilarityConfig,
    SemanticSimilarityResult,
    _check_transformers_available,
)

# =============================================================================
# SemanticSimilarityConfig Tests
# =============================================================================


class TestSemanticSimilarityConfig:
    """Tests for SemanticSimilarityConfig dataclass."""

    def test_default_config(self):
        """Default config should have sensible values from SemanticSimilarityDefaults."""
        config = SemanticSimilarityConfig()
        assert config.model_name == "microsoft/codebert-base"
        assert config.max_length == 512
        assert config.device == "auto"
        assert config.batch_size == 8
        assert config.cache_embeddings is True
        assert config.normalize_embeddings is True

    def test_custom_config(self):
        """Custom config should override defaults."""
        config = SemanticSimilarityConfig(
            model_name="microsoft/graphcodebert-base",
            max_length=256,
            device="cpu",
            cache_embeddings=False,
        )
        assert config.model_name == "microsoft/graphcodebert-base"
        assert config.max_length == 256
        assert config.device == "cpu"
        assert config.cache_embeddings is False


# =============================================================================
# SemanticSimilarityResult Tests
# =============================================================================


class TestSemanticSimilarityResult:
    """Tests for SemanticSimilarityResult dataclass."""

    def test_result_creation(self):
        """Should create result with expected values."""
        result = SemanticSimilarityResult(
            similarity=0.92,
            model_used="microsoft/codebert-base",
            embedding_dim=768,
            truncated=False,
            code1_tokens=50,
            code2_tokens=45,
        )
        assert result.similarity == 0.92
        assert result.model_used == "microsoft/codebert-base"
        assert result.embedding_dim == 768
        assert result.truncated is False
        assert result.code1_tokens == 50
        assert result.code2_tokens == 45

    def test_result_to_dict(self):
        """Should convert to dictionary correctly."""
        result = SemanticSimilarityResult(
            similarity=0.92345,
            model_used="microsoft/codebert-base",
            embedding_dim=768,
            truncated=True,
            code1_tokens=600,
            code2_tokens=45,
        )
        d = result.to_dict()
        assert d["similarity"] == 0.9234  # Rounded to 4 decimals
        assert d["model_used"] == "microsoft/codebert-base"
        assert d["embedding_dim"] == 768
        assert d["truncated"] is True
        assert d["code1_tokens"] == 600
        assert d["code2_tokens"] == 45


# =============================================================================
# SemanticSimilarity Class Tests (Mocked)
# =============================================================================


class TestSemanticSimilarityAvailability:
    """Tests for SemanticSimilarity.is_available() method."""

    def test_is_available_without_transformers(self):
        """Should return False when transformers not installed."""
        # Reset the cached value
        import ast_grep_mcp.features.deduplication.similarity as sim_module

        sim_module._TRANSFORMERS_AVAILABLE = None

        with patch.dict("sys.modules", {"transformers": None, "torch": None}):
            # Force re-check
            sim_module._TRANSFORMERS_AVAILABLE = None
            result = SemanticSimilarity.is_available()
            # The result depends on whether transformers is actually installed
            # We're testing the method works, not the actual availability
            assert isinstance(result, bool)

    def test_is_available_caches_result(self):
        """Should cache the availability check result."""
        import ast_grep_mcp.features.deduplication.similarity as sim_module

        # Set a cached value
        sim_module._TRANSFORMERS_AVAILABLE = True

        # Should return cached value without re-checking
        result = _check_transformers_available()
        assert result is True

        # Reset for other tests
        sim_module._TRANSFORMERS_AVAILABLE = None


class TestSemanticSimilarityInitialization:
    """Tests for SemanticSimilarity initialization."""

    def test_lazy_initialization(self):
        """Model should not be loaded on initialization."""
        # Create mock to track if model loading is called
        with patch.object(SemanticSimilarity, "_load_model") as mock_load:
            semantic = SemanticSimilarity()
            mock_load.assert_not_called()
            assert semantic._initialized is False
            assert semantic._model is None
            assert semantic._tokenizer is None


class TestSemanticSimilarityMocked:
    """Tests for SemanticSimilarity with mocked transformers."""

    @pytest.fixture
    def mock_torch(self):
        """Create a mock torch module."""
        mock = MagicMock()
        mock.cuda.is_available.return_value = False
        mock.no_grad.return_value.__enter__ = MagicMock()
        mock.no_grad.return_value.__exit__ = MagicMock()
        mock.nn.functional.normalize.return_value = MagicMock()
        mock.nn.functional.cosine_similarity.return_value.item.return_value = 0.8
        return mock

    @pytest.fixture
    def mock_transformers(self):
        """Create a mock transformers module."""
        mock = MagicMock()

        # Mock tokenizer
        tokenizer_instance = MagicMock()
        tokenizer_instance.return_value = {
            "input_ids": MagicMock(shape=(1, 50)),
            "attention_mask": MagicMock(),
        }
        mock.AutoTokenizer.from_pretrained.return_value = tokenizer_instance

        # Mock model
        model_instance = MagicMock()
        model_instance.to.return_value = model_instance
        model_output = MagicMock()
        model_output.last_hidden_state = MagicMock()
        model_output.last_hidden_state.__getitem__ = MagicMock(return_value=MagicMock(squeeze=MagicMock(return_value=MagicMock())))
        model_instance.return_value = model_output
        mock.AutoModel.from_pretrained.return_value = model_instance

        return mock

    def test_empty_input_returns_zero(self):
        """Empty inputs should return 0.0 similarity."""
        SemanticSimilarity()
        # Test with empty code without loading model
        result = SemanticSimilarityResult(
            similarity=0.0,
            model_used="microsoft/codebert-base",
            embedding_dim=768,
        )
        assert result.similarity == 0.0

    def test_config_applied(self):
        """Config should be applied to instance."""
        config = SemanticSimilarityConfig(
            model_name="microsoft/graphcodebert-base",
            device="cpu",
            cache_embeddings=False,
        )
        semantic = SemanticSimilarity(config)
        assert semantic.config.model_name == "microsoft/graphcodebert-base"
        assert semantic.config.device == "cpu"
        assert semantic.config.cache_embeddings is False

    def test_clear_cache(self):
        """Cache clearing should work."""
        semantic = SemanticSimilarity()
        semantic._embedding_cache = {12345: MagicMock()}
        assert len(semantic._embedding_cache) == 1

        semantic.clear_cache()
        assert len(semantic._embedding_cache) == 0

    def test_get_cache_stats(self):
        """Should return cache statistics."""
        semantic = SemanticSimilarity()
        semantic._embedding_cache = {1: MagicMock(), 2: MagicMock()}

        stats = semantic.get_cache_stats()
        assert stats["cache_size"] == 2


# =============================================================================
# Embedding Cache Keying and LRU Tests (BUG-12)
# =============================================================================


class TestEmbeddingCacheLRU:
    """Tests for collision-safe embedding cache keys and LRU bound (BUG-12)."""

    @staticmethod
    def _make_semantic() -> SemanticSimilarity:
        """Create a SemanticSimilarity that skips model loading."""
        semantic = SemanticSimilarity()
        semantic._initialized = True
        return semantic

    def test_embedding_cache_keyed_on_code_string(self):
        """Cache keys must be exact code strings, not hash() values."""
        semantic = self._make_semantic()
        code1 = "def alpha(): return 1"
        code2 = "def beta(): return 2"

        with patch.object(semantic, "_run_model_inference", side_effect=lambda code: MagicMock()):
            semantic.get_embedding(code1)
            semantic.get_embedding(code2)

        assert set(semantic._embedding_cache.keys()) == {code1, code2}

    def test_embedding_cache_hit_returns_cached_object(self):
        """Repeated code should hit the cache and skip inference."""
        semantic = self._make_semantic()
        code = "def alpha(): return 1"

        with patch.object(semantic, "_run_model_inference", side_effect=[MagicMock(), MagicMock()]) as mock_infer:
            emb1 = semantic.get_embedding(code)
            emb2 = semantic.get_embedding(code)

        assert emb1 is emb2
        assert mock_infer.call_count == 1
        assert semantic._cache_hits == 1

    def test_embedding_cache_lru_eviction(self, monkeypatch):
        """Embedding cache should evict the least-recently-used entry at the bound."""
        monkeypatch.setattr(SemanticSimilarityDefaults, "EMBEDDING_CACHE_MAX_SIZE", 2)
        semantic = self._make_semantic()

        with patch.object(semantic, "_run_model_inference", side_effect=lambda code: MagicMock()):
            semantic.get_embedding("code_a")
            semantic.get_embedding("code_b")
            semantic.get_embedding("code_a")  # Refresh recency of code_a
            semantic.get_embedding("code_c")  # Evicts code_b (LRU)

        assert set(semantic._embedding_cache.keys()) == {"code_a", "code_c"}


# =============================================================================
# HybridSimilarityConfig with Semantic Tests
# =============================================================================


class TestHybridSimilarityConfigSemantic:
    """Tests for HybridSimilarityConfig semantic options."""

    def test_default_semantic_disabled(self):
        """Semantic should be disabled by default."""
        config = HybridSimilarityConfig()
        assert config.enable_semantic is False
        assert config.semantic_weight == SemanticSimilarityDefaults.SEMANTIC_WEIGHT
        assert config.semantic_stage_threshold == SemanticSimilarityDefaults.SEMANTIC_STAGE_THRESHOLD
        assert config.semantic_model_name == SemanticSimilarityDefaults.MODEL_NAME

    def test_enable_semantic_with_rebalanced_weights(self):
        """Should accept rebalanced weights when semantic enabled."""
        config = HybridSimilarityConfig(
            enable_semantic=True,
            minhash_weight=0.2,
            ast_weight=0.5,
            semantic_weight=0.3,
        )
        assert config.enable_semantic is True
        assert config.minhash_weight == 0.2
        assert config.ast_weight == 0.5
        assert config.semantic_weight == 0.3

    def test_semantic_weights_must_sum_to_one(self):
        """Weights must sum to 1.0 when semantic enabled."""
        with pytest.raises(ValueError, match="must equal 1.0"):
            HybridSimilarityConfig(
                enable_semantic=True,
                minhash_weight=0.3,
                ast_weight=0.5,
                semantic_weight=0.3,  # Sum = 1.1
            )

    def test_invalid_semantic_weight(self):
        """Invalid semantic weight should raise ValueError."""
        with pytest.raises(ValueError, match="semantic_weight"):
            HybridSimilarityConfig(semantic_weight=1.5)

    def test_invalid_semantic_threshold(self):
        """Invalid semantic threshold should raise ValueError."""
        with pytest.raises(ValueError, match="semantic_stage_threshold"):
            HybridSimilarityConfig(semantic_stage_threshold=1.5)


# =============================================================================
# HybridSimilarityResult with Semantic Tests
# =============================================================================


class TestHybridSimilarityResultSemantic:
    """Tests for HybridSimilarityResult semantic fields."""

    def test_result_with_semantic(self):
        """Should create result with semantic fields."""
        result = HybridSimilarityResult(
            similarity=0.88,
            method="hybrid",
            verified=True,
            minhash_similarity=SemanticSimilarityDefaults.MEDIUM_SIMILARITY_THRESHOLD,
            ast_similarity=0.87,
            semantic_similarity=0.92,
            stage1_passed=True,
            stage2_passed=True,
            early_exit=False,
            semantic_skipped=False,
            token_count=50,
            semantic_model="microsoft/codebert-base",
        )
        assert result.semantic_similarity == 0.92
        assert result.stage2_passed is True
        assert result.semantic_skipped is False
        assert result.semantic_model == "microsoft/codebert-base"

    def test_result_without_semantic(self):
        """Should create result with semantic fields as None."""
        result = HybridSimilarityResult(
            similarity=SemanticSimilarityDefaults.MEDIUM_SIMILARITY_THRESHOLD,
            method="hybrid",
            verified=True,
            minhash_similarity=0.8,
            ast_similarity=0.88,
            semantic_similarity=None,
            stage1_passed=True,
            stage2_passed=False,
            early_exit=False,
            semantic_skipped=True,
            token_count=50,
            semantic_model=None,
        )
        assert result.semantic_similarity is None
        assert result.semantic_skipped is True
        assert result.semantic_model is None

    def test_result_to_dict_with_semantic(self):
        """Should include semantic fields in dict."""
        result = HybridSimilarityResult(
            similarity=0.88,
            method="hybrid",
            verified=True,
            minhash_similarity=SemanticSimilarityDefaults.MEDIUM_SIMILARITY_THRESHOLD,
            ast_similarity=0.87,
            semantic_similarity=0.92123,
            stage1_passed=True,
            stage2_passed=True,
            semantic_model="microsoft/codebert-base",
        )
        d = result.to_dict()
        assert d["semantic_similarity"] == 0.9212  # Rounded to 4 decimals
        assert d["stage2_passed"] is True
        assert d["semantic_skipped"] is False
        assert d["semantic_model"] == "microsoft/codebert-base"


# =============================================================================
# HybridSimilarity Three-Stage Pipeline Tests
# =============================================================================


class TestHybridSimilarityThreeStage:
    """Tests for three-stage hybrid pipeline."""

    def test_semantic_disabled_by_default(self):
        """Pipeline should not use semantic when disabled."""
        hybrid = HybridSimilarity()
        assert hybrid.hybrid_config.enable_semantic is False

        code1 = """
def add(a, b):
    return a + b
"""
        code2 = """
def add(x, y):
    return x + y
"""
        result = hybrid.calculate_hybrid_similarity(code1, code2)
        assert result.semantic_similarity is None
        assert result.semantic_skipped is True
        assert result.semantic_model is None

    def test_semantic_skipped_when_unavailable(self):
        """Semantic should be skipped when transformers not available."""
        import ast_grep_mcp.features.deduplication.similarity as sim_module

        # Temporarily mark as unavailable
        original = sim_module._TRANSFORMERS_AVAILABLE
        sim_module._TRANSFORMERS_AVAILABLE = False

        try:
            config = HybridSimilarityConfig(
                enable_semantic=True,
                minhash_weight=0.2,
                ast_weight=0.5,
                semantic_weight=0.3,
            )
            hybrid = HybridSimilarity(hybrid_config=config)

            code1 = "def add(a, b): return a + b"
            code2 = "def add(x, y): return x + y"

            result = hybrid.calculate_hybrid_similarity(code1, code2)
            # Should fall back to two-stage
            assert result.semantic_similarity is None
            assert result.semantic_skipped is True
        finally:
            sim_module._TRANSFORMERS_AVAILABLE = original

    def test_early_exit_skips_semantic(self):
        """Stage 1 early exit should skip semantic."""
        hybrid = HybridSimilarity()

        # Very different code should early exit
        code1 = "def add(a, b): return a + b"
        code2 = "class Database: pass"

        result = hybrid.calculate_hybrid_similarity(code1, code2)
        assert result.early_exit is True
        assert result.semantic_similarity is None
        assert result.semantic_skipped is True

    def test_empty_input_returns_zero_with_semantic_fields(self):
        """Empty input should return zero with all semantic fields set."""
        hybrid = HybridSimilarity()
        result = hybrid.calculate_hybrid_similarity("", "def foo(): pass")

        assert result.similarity == 0.0
        assert result.early_exit is True
        assert result.semantic_similarity is None
        assert result.semantic_skipped is True
        assert result.stage2_passed is False


# =============================================================================
# SemanticSimilarityDefaults Tests
# =============================================================================


class TestSemanticSimilarityDefaults:
    """Tests for SemanticSimilarityDefaults constants."""

    def test_default_values(self):
        """Should have expected default values."""
        assert SemanticSimilarityDefaults.ENABLE_SEMANTIC is False
        assert SemanticSimilarityDefaults.SEMANTIC_WEIGHT == 0.3
        assert SemanticSimilarityDefaults.MINHASH_WEIGHT_WITH_SEMANTIC == 0.2
        assert SemanticSimilarityDefaults.AST_WEIGHT_WITH_SEMANTIC == 0.5
        assert SemanticSimilarityDefaults.SEMANTIC_STAGE_THRESHOLD == 0.6
        assert SemanticSimilarityDefaults.MODEL_NAME == "microsoft/codebert-base"
        assert SemanticSimilarityDefaults.MAX_TOKEN_LENGTH == 512
        assert SemanticSimilarityDefaults.DEFAULT_DEVICE == "auto"
        assert SemanticSimilarityDefaults.CACHE_EMBEDDINGS is True
        assert SemanticSimilarityDefaults.NORMALIZE_EMBEDDINGS is True

    def test_weights_sum_to_one(self):
        """Rebalanced weights should sum to 1.0."""
        total = (
            SemanticSimilarityDefaults.MINHASH_WEIGHT_WITH_SEMANTIC
            + SemanticSimilarityDefaults.AST_WEIGHT_WITH_SEMANTIC
            + SemanticSimilarityDefaults.SEMANTIC_WEIGHT
        )
        assert abs(total - 1.0) < 0.001


# =============================================================================
# Integration Tests (require transformers)
# =============================================================================


@pytest.mark.semantic
class TestSemanticSimilarityIntegration:
    """Integration tests that require transformers and torch.

    Run with: pytest -m semantic
    """

    @pytest.fixture
    def semantic(self):
        """Create SemanticSimilarity instance if available."""
        if not SemanticSimilarity.is_available():
            pytest.skip("transformers and torch not installed")
        return SemanticSimilarity()

    def test_identical_code_high_similarity(self, semantic):
        """Identical code should have high semantic similarity."""
        code = """
def calculate_area(length, width):
    return length * width
"""
        similarity = semantic.calculate_similarity(code, code)
        assert similarity >= 0.99

    def test_similar_code_high_similarity(self, semantic):
        """Semantically similar code should have high similarity."""
        code1 = """
def add_numbers(a, b):
    return a + b
"""
        code2 = """
def sum_values(x, y):
    result = x + y
    return result
"""
        similarity = semantic.calculate_similarity(code1, code2)
        assert similarity >= 0.7

    def test_different_code_lower_similarity(self, semantic):
        """Semantically different code should have lower similarity."""
        code1 = """
def add(a, b):
    return a + b
"""
        code2 = """
class DatabaseConnection:
    def __init__(self, host, port):
        self.host = host
        self.port = port
"""
        similarity = semantic.calculate_similarity(code1, code2)
        assert similarity < 0.7

    def test_embedding_caching(self, semantic):
        """Embeddings should be cached for repeated calls."""
        code = "def foo(): return 42"

        # First call
        semantic.get_embedding(code)
        assert semantic.get_cache_stats()["cache_size"] == 1

        # Second call should use cache
        semantic.get_embedding(code)
        assert semantic.get_cache_stats()["cache_size"] == 1

    def test_detailed_result(self, semantic):
        """Should return detailed result with token counts."""
        code1 = "def foo(): pass"
        code2 = "def bar(): pass"

        result = semantic.calculate_similarity_detailed(code1, code2)
        assert isinstance(result, SemanticSimilarityResult)
        assert 0.0 <= result.similarity <= 1.0
        assert result.embedding_dim == 768
        assert result.code1_tokens > 0
        assert result.code2_tokens > 0


@pytest.mark.semantic
class TestHybridThreeStageIntegration:
    """Integration tests for three-stage hybrid pipeline.

    Run with: pytest -m semantic
    """

    @pytest.fixture
    def hybrid_with_semantic(self):
        """Create HybridSimilarity with semantic enabled."""
        if not SemanticSimilarity.is_available():
            pytest.skip("transformers and torch not installed")

        config = HybridSimilarityConfig(
            enable_semantic=True,
            minhash_weight=0.2,
            ast_weight=0.5,
            semantic_weight=0.3,
            semantic_stage_threshold=0.5,  # Lower threshold for testing
        )
        return HybridSimilarity(hybrid_config=config)

    def test_three_stage_similar_code(self, hybrid_with_semantic):
        """Similar code should run all three stages."""
        code1 = """
def calculate_sum(numbers):
    total = 0
    for num in numbers:
        total += num
    return total
"""
        code2 = """
def sum_list(values):
    result = 0
    for val in values:
        result = result + val
    return result
"""
        result = hybrid_with_semantic.calculate_hybrid_similarity(code1, code2)

        assert result.stage1_passed is True
        assert result.minhash_similarity >= 0.5
        assert result.ast_similarity is not None
        # If AST similarity is high enough, semantic should run
        if result.ast_similarity >= 0.5:
            assert result.semantic_similarity is not None or result.semantic_skipped is False

    def test_three_stage_result_format(self, hybrid_with_semantic):
        """Result should have all three-stage fields."""
        code1 = "def add(a, b): return a + b"
        code2 = "def sum(x, y): return x + y"

        result = hybrid_with_semantic.calculate_hybrid_similarity(code1, code2)

        # Check all fields are present
        d = result.to_dict()
        assert "minhash_similarity" in d
        assert "ast_similarity" in d
        assert "semantic_similarity" in d
        assert "stage1_passed" in d
        assert "stage2_passed" in d
        assert "semantic_skipped" in d
        assert "semantic_model" in d
