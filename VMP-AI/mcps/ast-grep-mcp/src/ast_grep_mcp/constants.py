"""Shared constants across the ast-grep-mcp codebase.

This module centralizes magic numbers and configuration values
to improve maintainability and reduce code duplication.
"""

import os


class ConversionFactors:
    """Unit conversion constants."""

    MILLISECONDS_PER_SECOND = 1000
    PERCENT_MULTIPLIER = 100


class ComplexityDefaults:
    """Default thresholds for complexity analysis."""

    CYCLOMATIC_THRESHOLD = 10
    COGNITIVE_THRESHOLD = 15
    NESTING_THRESHOLD = 4
    LENGTH_THRESHOLD = 50


class CriticalComplexityThresholds:
    """Critical complexity thresholds for script-level audit/report tools."""

    CYCLOMATIC = 20
    COGNITIVE = 30
    NESTING = 6
    LINES = 150


class ParallelProcessing:
    """Parallel processing configuration."""

    DEFAULT_WORKERS = 4
    MAX_WORKERS = 16

    # Timeout configuration for parallel operations
    DEFAULT_TIMEOUT_PER_CANDIDATE_SECONDS = 30  # 30 seconds per candidate
    MAX_TIMEOUT_SECONDS = 300  # 5 minutes max total timeout; enforced as shared deadline in _parallel_enrich

    @staticmethod
    def get_optimal_workers(max_threads: int = 0) -> int:
        """Calculate optimal worker count based on CPU cores.

        Args:
            max_threads: Maximum threads to use (0 = auto-detect)

        Returns:
            Optimal number of worker threads (1 to MAX_WORKERS)
        """
        if max_threads > 0:
            return min(max_threads, ParallelProcessing.MAX_WORKERS)

        cpu_count = os.cpu_count() or 4
        # Reserve 1 core for system, cap at MAX_WORKERS
        return max(1, min(cpu_count - 1, ParallelProcessing.MAX_WORKERS))


class BackupDefaults:
    """Defaults for backup retention and lifecycle management."""

    RETENTION_DAYS = 30
    DIR_NAME = ".ast-grep-backups"
    METADATA_FILE = "backup-metadata.json"
    DEDUP_PREFIX = "dedup-backup"
    REWRITE_PREFIX = "backup"


class CacheDefaults:
    """Cache configuration defaults."""

    TTL_SECONDS = 3600  # 1 hour
    MAX_SIZE_MB = 100
    CLEANUP_INTERVAL_SECONDS = 300  # 5 minutes
    DEFAULT_CACHE_SIZE = 100  # Number of cached items
    CACHE_KEY_LENGTH = 16  # Length of truncated SHA256 hash for cache keys
    RULE_ID_HASH_LENGTH = 8  # Length of truncated SHA256 hash for rule IDs


class FilePatterns:
    """Common file patterns for analysis."""

    VENV_EXCLUDE = [
        "**/venv/**",
        "**/.venv/**",
        "**/virtualenv/**",
        "**/site-packages/**",
    ]

    DEFAULT_EXCLUDE = [
        "**/node_modules/**",
        "**/__pycache__/**",
        *VENV_EXCLUDE,
        "**/dist/**",
        "**/build/**",
        "**/.git/**",
        "**/coverage/**",
        "**/.next/**",
        "**/.turbo/**",
        "**/.cache/**",
        "**/output/**",
        "**/generated/**",
        "**/logs/**",
        "**/vendor/**",
        "**/.svelte-kit/**",
        "**/.nuxt/**",
        "**/.ast-grep-backups/**",
    ]

    MINIFIED_EXCLUDE = [
        "**/*.d.ts",
        "**/*.min.js",
        "**/*.min.css",
        "**/*.map",
    ]

    TEST_EXCLUDE = [
        "**/test*/**",
        "**/*test*",
        "**/tests/**",
        "**/*_test.py",
        "**/test_*.py",
    ]

    SKIP_DIR_NAMES: frozenset[str] = frozenset(
        {
            "node_modules",
            ".git",
            "venv",
            ".venv",
            "__pycache__",
            "dist",
            "build",
            "vendor",
            "site-packages",
            "virtualenv",
        }
    )

    @staticmethod
    def merge_with_venv_excludes(exclude_patterns: list[str] | None) -> list[str]:
        """Ensure virtualenv/site-packages paths are always excluded.

        This is intentionally applied even when callers provide custom exclude
        patterns, so environment directories never enter analysis scope.
        """
        merged = list(exclude_patterns or [])
        for pattern in FilePatterns.VENV_EXCLUDE:
            if pattern not in merged:
                merged.append(pattern)
        return merged

    @staticmethod
    def normalize_excludes(
        exclude_patterns: list[str] | None,
        defaults: list[str] = DEFAULT_EXCLUDE,
    ) -> list[str]:
        """Default-if-None then merge venv excludes.

        Args:
            exclude_patterns: Caller-supplied patterns, or None for defaults.
            defaults: Default patterns when exclude_patterns is None.
        """
        if exclude_patterns is None:
            exclude_patterns = list(defaults)
        return FilePatterns.merge_with_venv_excludes(exclude_patterns)


class StreamDefaults:
    """Defaults for streaming operations."""

    DEFAULT_TIMEOUT_MS = 120000  # 2 minutes
    MAX_TIMEOUT_MS = 600000  # 10 minutes
    PROGRESS_INTERVAL = 100  # Log progress every N matches
    SIGTERM_RETURN_CODE = -15  # Return code for SIGTERM signal
    PROCESS_TERMINATE_TIMEOUT_SECONDS = 2  # Grace period after SIGTERM before escalating to SIGKILL
    PROCESS_KILL_TIMEOUT_SECONDS = 5  # Timeout for process.wait after SIGKILL / thread.join


class ExecutorDefaults:
    """Defaults for the ast-grep executor."""

    AST_GREP_COMMAND = "ast-grep"


class ValidationDefaults:
    """Defaults for validation operations."""

    MAX_FILE_SIZE_MB = 10  # Skip files larger than this
    SYNTAX_CHECK_TIMEOUT_SECONDS = 5


class FileConstants:
    """Constants for file operations."""

    BYTES_PER_KB = 1024
    BYTES_PER_MB = 1024 * 1024
    BYTES_PER_GB = 1024 * 1024 * 1024
    LINE_PREVIEW_LENGTH = 100  # Maximum characters to show in line preview


class DeduplicationDefaults:
    """Defaults for deduplication analysis."""

    MIN_SIMILARITY = 0.8  # Minimum similarity threshold (0-1)
    MIN_LINES = 5  # Minimum lines to consider for duplication
    MAX_CANDIDATES = 100  # Maximum candidate pairs to analyze

    # Scoring weights (must sum to 1.0)
    SAVINGS_WEIGHT = 0.40
    COMPLEXITY_WEIGHT = 0.20
    RISK_WEIGHT = 0.25
    EFFORT_WEIGHT = 0.15

    # Regression thresholds for performance benchmarks
    REGRESSION_PATTERN_ANALYSIS = 0.15  # 15% slowdown allowed
    REGRESSION_CODE_GENERATION = 0.10  # 10% slowdown allowed
    REGRESSION_FULL_WORKFLOW = 0.20  # 20% slowdown allowed
    REGRESSION_SCORING = 0.05  # 5% slowdown allowed
    REGRESSION_TEST_COVERAGE = 0.15  # 15% slowdown allowed

    # Analysis pipeline progress stages
    PROGRESS_RANKING = 0.25
    PROGRESS_ENRICHING = 0.40
    PROGRESS_SELECTION = 0.50
    PROGRESS_COVERAGE_CHECK = 0.60
    PROGRESS_COVERAGE_COMPLETE = 0.75
    PROGRESS_RECOMMENDATIONS = 0.85
    PROGRESS_STATISTICS = 0.90


class HybridSimilarityDefaults:
    """Defaults for hybrid two-stage similarity pipeline.

    Scientific basis: TACC (Token and AST-based Code Clone detector)
    from ICSE 2023 demonstrates that combining MinHash filtering with
    AST verification yields optimal precision/recall balance.
    """

    # Stage 1: MinHash filter threshold for early exit
    # Code pairs below this threshold skip Stage 2 (AST verification)
    MINHASH_EARLY_EXIT_THRESHOLD = 0.5

    # Stage 2 weights for combining MinHash and AST similarity
    # Must sum to 1.0. AST gets higher weight due to structural precision.
    MINHASH_WEIGHT = 0.4
    AST_WEIGHT = 0.6

    # Weight validation
    WEIGHT_SUM_TARGET = 1.0
    WEIGHT_SUM_TOLERANCE = 0.001

    # LSH threshold floor to prevent overly aggressive filtering
    LSH_THRESHOLD_FLOOR = 0.1

    # Minimum token count to use hybrid approach
    # Very short code snippets may not benefit from AST analysis
    MIN_TOKENS_FOR_AST = 10

    # Maximum code length (lines) for AST analysis
    # Very long code may be too expensive for detailed AST comparison
    MAX_LINES_FOR_FULL_AST = 500

    # AST tree edit distance normalization factor
    # Used to convert raw edit distance to 0-1 similarity score
    TREE_EDIT_DISTANCE_NORMALIZATION = 100


class SemanticSimilarityDefaults:
    """Defaults for CodeBERT-based semantic similarity (Phase 5).

    Scientific basis: GraphCodeBERT (2024) produces 768-dimensional
    embeddings capturing semantic meaning for Type-4 clone detection.

    Note: Semantic similarity is OPTIONAL and requires:
    - transformers library
    - torch (PyTorch)
    - GPU recommended for performance

    Install with: pip install ast-grep-mcp[semantic]
    """

    # Whether semantic similarity is enabled by default
    # Set to False to require explicit opt-in
    ENABLE_SEMANTIC = False

    # Weight for semantic similarity in three-stage hybrid score
    # When enabled, weights are rebalanced: MinHash (0.2), AST (0.5), Semantic (0.3)
    SEMANTIC_WEIGHT = 0.3

    # Rebalanced weights when semantic is enabled (must sum to 1.0)
    MINHASH_WEIGHT_WITH_SEMANTIC = 0.2
    AST_WEIGHT_WITH_SEMANTIC = 0.5

    # Minimum similarity from Stage 2 (AST) to proceed to Stage 3 (Semantic)
    # This provides a second early-exit point to avoid expensive model inference
    SEMANTIC_STAGE_THRESHOLD = 0.6

    # Medium semantic similarity baseline used for heuristic comparisons/reporting
    MEDIUM_SIMILARITY_THRESHOLD = 0.85

    # Default model for CodeBERT embeddings
    MODEL_NAME = "microsoft/codebert-base"

    # Maximum token length for CodeBERT input
    MAX_TOKEN_LENGTH = 512

    # Device selection: 'auto', 'cpu', 'cuda', or 'mps'
    DEFAULT_DEVICE = "auto"

    # Whether to cache embeddings for repeated comparisons
    CACHE_EMBEDDINGS = True

    # Whether to L2-normalize embeddings (recommended for cosine similarity)
    NORMALIZE_EMBEDDINGS = True

    # Embedding vector dimensionality for CodeBERT
    EMBEDDING_DIM = 768

    # Default batch size for embedding inference
    DEFAULT_BATCH_SIZE = 8

    # LRU bound for the embedding cache; each entry holds a 768-float tensor (BUG-12)
    EMBEDDING_CACHE_MAX_SIZE = 1024


class SecurityScanDefaults:
    """Defaults for security scanning."""

    MAX_ISSUES = 100  # Maximum issues to return
    DEFAULT_SEVERITY_THRESHOLD = "low"  # Minimum severity to report

    # Confidence thresholds
    VERY_HIGH_CONFIDENCE = 0.95
    HIGH_CONFIDENCE = 0.9
    ELEVATED_CONFIDENCE = 0.85  # High confidence with moderate residual uncertainty
    DEFAULT_CONFIDENCE = 0.8
    MEDIUM_CONFIDENCE = 0.7
    LOW_CONFIDENCE = 0.5


class SemanticVolumeDefaults:
    """Shared list-volume limits from high-overlap magic-number clusters."""

    TOP_RESULTS_LIMIT = 5
    DETAIL_RESULTS_LIMIT = 20
    SUMMARY_PREVIEW_LIMIT = 50
    MAGIC_NUMBER_SAMPLE_LIMIT = 50


class CodeQualityDefaults:
    """Defaults for code quality analysis."""

    # Code smell thresholds
    LONG_FUNCTION_LINES = 50
    PARAMETER_COUNT = 5
    NESTING_DEPTH = 4
    CLASS_LINES = 300
    CLASS_METHODS = 20

    # Magic numbers to ignore
    ALLOWED_MAGIC_NUMBERS = {0, 1, -1, 2, 10, 100, 1000}


class LoggingDefaults:
    """Logging configuration defaults."""

    DEFAULT_LEVEL = "INFO"
    MAX_LOG_SIZE_MB = 10
    BACKUP_COUNT = 5  # Number of log files to keep
    MAX_BREADCRUMBS = 50  # Maximum Sentry breadcrumbs to keep


# Language-specific extensions mapping (canonical — primary extension first).
# Single source of truth; feature modules and scripts import this map (DRY-06).
LANGUAGE_EXTENSIONS: dict[str, list[str]] = {
    "python": [".py", ".pyi"],
    "typescript": [".ts", ".tsx"],
    "javascript": [".js", ".jsx", ".mjs", ".cjs"],
    "java": [".java"],
    "kotlin": [".kt", ".kts"],
    "go": [".go"],
    "rust": [".rs"],
    "ruby": [".rb"],
    "php": [".php"],
    "c": [".c", ".h"],
    "cpp": [".cpp", ".cc", ".cxx", ".hpp", ".hxx", ".hh"],
    "csharp": [".cs"],
    "swift": [".swift"],
}

# Schema.org constants
SCHEMA_ORG_BASE_URL = "https://schema.org"
SCHEMA_ORG_CONTEXT = "https://schema.org"


class FormattingDefaults:
    """Defaults for code formatting."""

    ROUNDING_PRECISION = 3  # Decimal places for execution times, hit rates
    TIMESTAMP_MS_TRIM = 3  # Trim last 3 digits of microseconds for millisecond precision
    ISO_DATE_LENGTH = 10  # Length of YYYY-MM-DD date string
    SIMILARITY_PRECISION = 4  # Decimal places for similarity scores
    BENCHMARK_PRECISION = 6  # Decimal places for benchmark timing
    DEFAULT_DIFF_CONTEXT_LINES = 3  # Context lines in unified diffs
    BLACK_LINE_LENGTH = 88  # Black formatter default
    PRETTIER_LINE_LENGTH = 80  # Prettier formatter default
    SEPARATOR_LENGTH = 70  # Default CLI separator line length
    USAGE_REPORT_WIDTH = 50  # Separator width for usage summary reports
    SECTION_DIVIDER_WIDTH = 30  # Subsection divider width in reports
    WIDE_SECTION_WIDTH = 80  # Wide separator for enforcement/audit reports
    TABLE_SEPARATOR_WIDTH = 40  # Table row separator width


class UnifiedDiffRegexGroups:
    """Capture group indices for unified diff hunk header parsing."""

    OLD_START = 1
    OLD_COUNT = 2
    NEW_START = 3
    NEW_COUNT = 4
    CONTEXT = 5


class RegexCaptureGroups:
    """Generic regex capture group indices for parser helpers."""

    FIRST = 1
    SECOND = 2
    THIRD = 3
    FOURTH = 4
    FIFTH = 5


class SeverityRankingDefaults:
    """Shared severity ranking maps and fallback rank values."""

    FALLBACK_RANK = 3
    SECURITY_SCAN_ORDER = {"critical": 3, "high": 2, "medium": 1, "low": 0}
    SMELL_SORT_ORDER = {"high": 0, "medium": 1, "low": 2}
    DOC_SYNC_SORT_ORDER = {"error": 0, "warning": 1, "info": 2}
    ENFORCER_THRESHOLD_ORDER = {"info": 0, "warning": 1, "error": 2}


class DisplayDefaults:
    """Constants for display and UI elements."""

    VISUALIZATION_BAR_LENGTH = 10  # Length of ASCII score bars
    LOW_SCORE_THRESHOLD = 3  # Score <= this is "low"
    MEDIUM_SCORE_THRESHOLD = 6  # Score <= this is "medium"
    COMPLEXITY_SCORE_MIN = 1  # Minimum complexity score
    COMPLEXITY_SCORE_MAX = 10  # Maximum complexity score
    CONTENT_PREVIEW_LENGTH = 50  # Characters in content previews
    ERROR_OUTPUT_PREVIEW_LENGTH = 200  # Characters in error output previews
    ERROR_MESSAGE_MAX_LENGTH = 500  # Max characters for stored error messages
    AST_TRUNCATION_LENGTH = 500  # Characters for AST structure previews
    AST_PREVIEW_MAX_LINES = 15  # Lines in AST preview output
    MAX_CHILD_KINDS = 10  # Max child kinds to return in analysis
    MAX_LITERALS = 5  # Max literals to return in analysis
    MAX_IDENTIFIERS = 10  # Max identifiers to return in analysis
    MAX_PATTERN_REPLACEMENTS = 3  # Max literal replacements in patterns
    MAX_PATTERN_IDENTIFIERS = 5  # Max identifier replacements in patterns
    SHORT_IDENTIFIER_THRESHOLD = 4  # Length threshold for short identifiers


class PerformanceDefaults:
    """Defaults for performance monitoring."""

    DATABASE_TIMEOUT_SECONDS = 30.0  # SQLite/HTTP connection timeout


class BenchmarkExpectationDefaults:
    """Expected performance-improvement thresholds for benchmark scripts."""

    BATCH_SEQUENTIAL_IMPROVEMENT_MIN_PERCENT = 40
    BATCH_SEQUENTIAL_IMPROVEMENT_MAX_PERCENT = 50
    BATCH_PARALLEL_IMPROVEMENT_MIN_PERCENT = 60
    BATCH_PARALLEL_IMPROVEMENT_MAX_PERCENT = 80

    # Classification thresholds for reporting benchmark outcomes
    BATCH_PARALLEL_PARTIAL_MIN_PERCENT = 40
    BATCH_PARALLEL_PASS_MIN_PERCENT = 60


class CodeAnalysisDefaults:
    """Defaults for code structure analysis."""

    SIMPLE_CODE_DEPTH_THRESHOLD = 3
    SIMPLE_CODE_LINES_THRESHOLD = 3
    MEDIUM_CODE_DEPTH_THRESHOLD = 6
    MEDIUM_CODE_LINES_THRESHOLD = 10
    DEFAULT_COMPLEXITY_SCORE = 5  # Default complexity when unknown


class ComplexityLevelDefaults:
    """Thresholds for classifying complexity into low/medium/high."""

    LOW_THRESHOLD = 5  # Score below this is "low"
    MEDIUM_THRESHOLD = 10  # Score below this is "medium"


class SmellSeverityDefaults:
    """Thresholds for code smell severity classification."""

    HIGH_RATIO_THRESHOLD = 2.0  # metric/threshold ratio above this is "high"
    MEDIUM_RATIO_THRESHOLD = 1.5  # metric/threshold ratio above this is "medium"


class UsageTrackingDefaults:
    """Defaults for usage tracking and alerting."""

    DAILY_CALLS_WARNING = 1000
    DAILY_CALLS_CRITICAL = 5000
    DAILY_COST_WARNING = 1.0
    DAILY_COST_CRITICAL = 5.0
    HOURLY_FAILURES_WARNING = 10
    HOURLY_FAILURES_CRITICAL = 50
    FAILURE_RATE_WARNING = 0.1  # 10%
    FAILURE_RATE_CRITICAL = 0.25  # 25%
    USAGE_ID_HASH_LENGTH = 16
    AVG_RESPONSE_TIME_WARNING_MS = 5000
    AVG_RESPONSE_TIME_CRITICAL_MS = 30000
    DEFAULT_PAGINATION_LIMIT = 100
    DEFAULT_STATS_LOOKBACK_DAYS = 7


class ReportingDefaults:
    """Defaults for deduplication reporting."""

    SIGNIFICANT_LINES_SAVED_THRESHOLD = 50
    MANY_DUPLICATES_THRESHOLD = 5


class SEODefaults:
    """Defaults for SEO scoring in schema enhancement."""

    BASE_SCORE = 100.0
    BONUS_INCREMENT = 5.0
    FALLBACK_AVG_ENTITY_SCORE = 50.0
    DEFAULT_PRIORITY_ORDER = 4

    # Priority penalty weights for entity SEO scoring
    ENTITY_PENALTY_CRITICAL = -20
    ENTITY_PENALTY_HIGH = -10
    ENTITY_PENALTY_MEDIUM = -5
    ENTITY_PENALTY_LOW = -2

    # Priority penalty weights for missing entity scoring
    MISSING_PENALTY_CRITICAL = -15
    MISSING_PENALTY_HIGH = -10
    MISSING_PENALTY_MEDIUM = -5
    MISSING_PENALTY_LOW = -2


class SentryDefaults:
    """Defaults for Sentry monitoring configuration."""

    PRODUCTION_TRACES_SAMPLE_RATE = 0.1
    PRODUCTION_PROFILES_SAMPLE_RATE = 0.1


class DocstringDefaults:
    """Defaults for docstring generation."""

    BASIC_INFERENCE_CONFIDENCE = 0.8
    QUOTE_LENGTH = 3  # Length of """ or '''
    REGULAR_FUNCTION_GROUP_COUNT = 5  # Regex capture groups for regular functions
    ARROW_FUNCTION_GROUP_COUNT = 6  # Regex capture groups for arrow functions
    MIN_ONELINER_LENGTH = 6  # Minimum length for a single-line docstring (quote + content + quote)


class IndentationDefaults:
    """Indentation analysis defaults."""

    SPACES_PER_LEVEL = 4
    ALT_SPACES_PER_LEVEL = 2
    NORMALIZATION_DIVISOR = 2


class MinHashDefaults:
    """MinHash algorithm configuration."""

    NUM_PERMUTATIONS = 128
    SHINGLE_SIZE = 3
    SMALL_CODE_TOKEN_THRESHOLD = 20
    SEQUENCEMATCHER_TOKEN_THRESHOLD = 15  # Below this, use SequenceMatcher instead of MinHash
    LSH_RECALL_MARGIN = 0.2  # LSH threshold margin below min_similarity for recall
    MAX_FALLBACK_ITEMS = 100  # Max items before all-pairs O(n²) becomes too expensive
    SIGNATURE_CACHE_MAX_SIZE = 1024  # LRU bound for MinHash signature cache (BUG-12)


class ASTFingerprintDefaults:
    """AST structural fingerprinting configuration."""

    MAX_NODE_SEQUENCE_LENGTH = 20
    MAX_COMPLEXITY_HEX_VALUE = 15
    MAX_NESTING_DEPTH_DIGIT = 9
    HASH_MODULO = 10000
    HASH_BUCKET_MULTIPLIER = 100
    MAX_UNIQUE_CALLS = 10
    CALL_SIGNATURE_BITMASK = 0xFFFF
    CALL_SIGNATURE_HEX_WIDTH = 4


class PriorityClassifierThresholds:
    """Thresholds for classifying deduplication candidate priority."""

    CRITICAL = 80
    HIGH = 60
    MEDIUM = 40
    LOW = 20


class RankerDefaults:
    """Deduplication ranker scoring configuration."""

    SAVINGS_NORMALIZATION_DIVISOR = 5
    MAX_NORMALIZED_SCORE = 100
    COMPLEXITY_INVERSION_FACTOR = 16.67
    DEFAULT_MIDDLE_SCORE = 50.0
    EFFORT_INSTANCE_PENALTY = 5
    EFFORT_FILE_PENALTY = 10
    MIN_SAVINGS_SCORE_FOR_FULL_CALC = 5  # Skip risk/effort if savings < this
    SCORE_CACHE_MAX_SIZE = 1024  # LRU bound for candidate score cache (BUG-12)


class RiskMultipliers:
    """Risk score multipliers for deduplication."""

    LOW = 1.0
    MEDIUM = 0.7
    HIGH = 0.3


class RecommendationDefaults:
    """Deduplication recommendation configuration."""

    EXTRACT_FUNCTION_BASE_SCORE = 70.0
    EXTRACT_CLASS_BASE_SCORE = 50.0
    INLINE_BASE_SCORE = 30.0
    EFFORT_COMPLEXITY_WEIGHT = 0.3
    EFFORT_FILES_WEIGHT = 0.5
    NO_TESTS_EFFORT_MULTIPLIER = 1.5
    VALUE_LINES_WEIGHT = 0.4
    VALUE_FILES_BONUS = 10
    HIGH_PRIORITY_SCORE_THRESHOLD = 80
    MEDIUM_PRIORITY_SCORE_THRESHOLD = 50
    HIGH_SIMILARITY_THRESHOLD = 0.85
    DEFAULT_SIMILARITY = 0.9
    MODULE_EXTRACTION_DUPLICATE_THRESHOLD = 3
    CLASS_EXTRACTION_LINE_THRESHOLD = 20

    # Extract function scoring thresholds
    EXTRACT_FN_LOW_COMPLEXITY = 5
    EXTRACT_FN_LOW_COMPLEXITY_BONUS = 20
    EXTRACT_FN_HIGH_COMPLEXITY = 10
    EXTRACT_FN_HIGH_COMPLEXITY_PENALTY = -20
    EXTRACT_FN_LINES_BONUS_THRESHOLD = 10
    EXTRACT_FN_LINES_BONUS = 10
    EXTRACT_FN_FILES_THRESHOLD = 3
    EXTRACT_FN_FILES_BONUS = 10

    # Extract class scoring thresholds
    EXTRACT_CLS_HIGH_COMPLEXITY = 10
    EXTRACT_CLS_HIGH_COMPLEXITY_BONUS = 30
    EXTRACT_CLS_MID_COMPLEXITY_LOWER = 5
    EXTRACT_CLS_MID_COMPLEXITY_BONUS = 15
    EXTRACT_CLS_LINES_THRESHOLD = 20
    EXTRACT_CLS_LINES_BONUS = 15
    EXTRACT_CLS_FILES_THRESHOLD = 2
    EXTRACT_CLS_FILES_BONUS = 10
    EXTRACT_CLS_LOW_COMPLEXITY = 3
    EXTRACT_CLS_LOW_LINES = 10
    EXTRACT_CLS_LOW_EFFORT_PENALTY = -20

    # Inline scoring thresholds
    INLINE_LOW_SIMILARITY = 40
    INLINE_LOW_SIMILARITY_BONUS = 40
    INLINE_MID_SIMILARITY_UPPER = 60
    INLINE_MID_SIMILARITY_BONUS = 20
    INLINE_SINGLE_FILE_BONUS = 20
    INLINE_SMALL_LINES_THRESHOLD = 5
    INLINE_SMALL_LINES_BONUS = 20
    INLINE_HIGH_SIMILARITY = 80
    INLINE_HIGH_SIMILARITY_PENALTY = -30


class ChangelogDefaults:
    """Changelog generator configuration."""

    COMMIT_PARTS_COUNT = 6


class ReadmeSectionOrder:
    """Section ordering for README generation."""

    FEATURES = 5
    INSTALLATION = 10
    USAGE = 20
    API_REFERENCE = 30
    PROJECT_STRUCTURE = 40
    CONTRIBUTING = 50
    LICENSE = 60


class ReadmeDefaults:
    """README generation defaults."""

    MAX_DEPENDENCIES = 10


class SyntaxValidationDefaults:
    """Syntax validation timeouts and limits."""

    NODE_TIMEOUT_SECONDS = 5
    TSC_TIMEOUT_SECONDS = 10
    JAVAC_TIMEOUT_SECONDS = 10
    JAVAC_ERROR_PREVIEW_LENGTH = 500
    TSC_SYNTAX_ERROR_PATTERN = r"error TS1\d{3}:"
    ERROR_SUGGESTION_PREVIEW_LENGTH = 100  # Characters in error suggestion messages


class SubprocessDefaults:
    """Default timeouts for subprocess operations."""

    GREP_TIMEOUT_SECONDS = 10
    AST_GREP_TIMEOUT_SECONDS = 30
    ZSTD_TRAIN_TIMEOUT_SECONDS = 60  # Timeout for zstd dictionary training
    TSC_NOEMIT_TIMEOUT_SECONDS = 120  # Full project type-check compile


class LogBucketThresholds:
    """Logarithmic bucket boundaries for code size classification."""

    TINY = 5
    SMALL = 10
    MEDIUM = 20
    LARGE = 40
    VERY_LARGE = 80
    HUGE = 160
    MASSIVE = 320
    OVERFLOW_BASE_BUCKET = 7
    MAX_BUCKET = 9


class DifficultyThresholds:
    """Complexity-based difficulty classification thresholds."""

    SIMPLE = 3
    MODERATE = 4
    COMPLEX = 5


class PriorityWeights:
    """Weights for priority calculation in deduplication reporting."""

    OCCURRENCE_WEIGHT = 10
    LINE_WEIGHT = 2
    COMPLEXITY_PENALTY = 3


class CrossLanguageDefaults:
    """Defaults for cross-language analysis."""

    MAX_RESULTS_PER_LANGUAGE = 100  # Maximum results returned per language in multi-language search


class EquivalenceDefaults:
    """Cross-language pattern equivalence defaults."""

    SIMPLE_LINE_THRESHOLD = 2
    MODERATE_LINE_THRESHOLD = 5


class ExampleDataDefaults:
    """Shared sample data values used in cross-language examples."""

    PERSON_AGE = 30
    NUMERIC_EXAMPLE = 42


class DetectorDefaults:
    """Deduplication detector defaults."""

    UTILITY_FUNCTION_LINE_THRESHOLD = 10

    # Precision filter thresholds (reduce false positives)
    TRIVIAL_INIT_MAX_LINES = 10
    MIN_LINE_SAVINGS = 20
    DELEGATION_MAX_BODY_STATEMENTS = 2
    CONSTRUCTOR_NAMES = frozenset({"__init__", "constructor", "__new__", "init"})
    PARALLEL_FORMATTER_PREFIXES = ("to_", "from_", "as_", "into_")


class ComplexityStorageDefaults:
    """Defaults for complexity trend storage and queries."""

    TRENDS_LOOKBACK_DAYS = 30  # Default lookback period for trend queries


class RuleSetPriority:
    """Execution priority ordering for rule sets (higher = runs first)."""

    SECURITY = 200  # Security rules run first
    CUSTOM = 150  # Custom rules after security
    RECOMMENDED = 100  # Recommended/all rules
    PERFORMANCE = 50  # Performance rules
    STYLE = 10  # Style rules run last


class PatternSuggestionConfidence:
    """Confidence scores for pattern suggestion types."""

    EXACT_SIMPLE = 0.9  # Exact match for simple code
    EXACT_COMPLEX = 0.7  # Exact match for complex code
    GENERALIZED = 0.8  # Generalized pattern with metavariables
    STRUCTURAL = 0.6  # Structural (kind-based) pattern
    PATTERN_MATCH = SecurityScanDefaults.ELEVATED_CONFIDENCE  # Security pattern match confidence
    UNKNOWN_FIX = 0.5  # Unknown fix pattern (conservative)


class CondenseDefaults:
    """Defaults for code condensation pipeline."""

    DEFAULT_STRATEGY = "ai_analysis"

    # Extraction
    INCLUDE_DOCSTRINGS = True

    # Normalization
    NORMALIZE_STRING_QUOTES = True
    NORMALIZE_TRAILING_COMMAS = True

    # Strip targets
    STRIP_CONSOLE_LOG = True
    STRIP_DEBUG_STATEMENTS = True
    STRIP_EMPTY_LINES = True

    # Limits
    MAX_FILE_SIZE_BYTES = 1_048_576  # 1 MB; skip larger files
    MAX_FILES_PER_RUN = 500

    # Estimation
    AVG_TOKENS_PER_BYTE = 0.25  # Rough approximation for token counting

    # Complexity-guided extraction thresholds (cyclomatic)
    COMPLEXITY_STRIP_THRESHOLD = 10  # ≤10 cyclomatic → signature + docstring only
    # >10 cyclomatic → keep full body


class CondenseDictionaryDefaults:
    """Defaults for zstd dictionary training."""

    SAMPLE_COUNT = 200
    MAX_SAMPLE_SIZE_BYTES = 102_400  # 100 KB per sample
    DICT_SIZE_BYTES = 112_640  # 110 KB (zstd default)
    DICT_OUTPUT_DIR = ".condense/dictionaries"


class CondenseParsing:
    """Constants for structural code parsing in condense feature."""

    QUOTE_CHARS: frozenset[str] = frozenset(('"', "'", "`"))
    BRACE_DELTA: dict[str, int] = {"{": 1, "}": -1}


class CondenseFileRouting:
    """File-type routing for polyglot condensation."""

    CODE_EXTENSIONS = frozenset(
        {
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".py",
            ".rs",
            ".go",
            ".java",
            ".rb",
            ".php",
            ".swift",
            ".kt",
            ".cs",
            ".cpp",
            ".c",
            ".h",
        }
    )
    CONFIG_EXTENSIONS = frozenset(
        {
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".xml",
            ".ini",
        }
    )
    TEXT_EXTENSIONS = frozenset({".md", ".txt", ".rst", ".adoc"})
    IMAGE_EXTENSIONS = frozenset(
        {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".ico",
            ".bmp",
        }
    )
    EXCLUDE_PATTERNS = [
        "dist/**",
        "build/**",
        "*.lock",
        "package-lock.json",
        "yarn.lock",
        "*.gen.*",
        "*.min.js",
        "*.min.css",
        "**/__pycache__/**",
        "**/.git/**",
        "**/node_modules/**",
        "**/.venv/**",
        "**/venv/**",
    ]
    TEST_PATTERNS = [
        "**/test_*",
        "**/test/**",
        "**/*_test.*",
        "**/*.spec.*",
        "**/*.test.*",
    ]


# HTTP constants
DEFAULT_USER_AGENT = "ast-grep-mcp/1.0"
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 1
