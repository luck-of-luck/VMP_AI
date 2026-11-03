# ast_grep_mcp

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareSourceCode",
  "name": "ast_grep_mcp",
  "description": "Directory containing 1 code files with 59 classes and 0 functions",
  "programmingLanguage": [
    {
      "@type": "ComputerLanguage",
      "name": "Python"
    }
  ],
  "featureList": [
    "59 class definitions"
  ]
}
</script>

## Overview

This directory contains 1 code file(s) with extracted schemas.

## Files and Schemas

### `constants.py` (python)

**Classes:**
- `ConversionFactors` - Line 10
  - Unit conversion constants.
- `ComplexityDefaults` - Line 17
  - Default thresholds for complexity analysis.
- `CriticalComplexityThresholds` - Line 26
  - Critical complexity thresholds for script-level audit/report tools.
- `ParallelProcessing` - Line 35
  - Parallel processing configuration.
  - Methods: get_optimal_workers
- `BackupDefaults` - Line 63
  - Defaults for backup retention and lifecycle management.
- `CacheDefaults` - Line 73
  - Cache configuration defaults.
- `FilePatterns` - Line 84
  - Common file patterns for analysis.
  - Methods: merge_with_venv_excludes, normalize_excludes
- `StreamDefaults` - Line 158
  - Defaults for streaming operations.
- `ExecutorDefaults` - Line 169
  - Defaults for the ast-grep executor.
- `ValidationDefaults` - Line 175
  - Defaults for validation operations.
- `FileConstants` - Line 182
  - Constants for file operations.
- `DeduplicationDefaults` - Line 191
  - Defaults for deduplication analysis.
- `HybridSimilarityDefaults` - Line 221
  - Defaults for hybrid two-stage similarity pipeline.
- `SemanticSimilarityDefaults` - Line 258
  - Defaults for CodeBERT-based semantic similarity (Phase 5).
- `SecurityScanDefaults` - Line 313
  - Defaults for security scanning.
- `SemanticVolumeDefaults` - Line 328
  - Shared list-volume limits from high-overlap magic-number clusters.
- `CodeQualityDefaults` - Line 337
  - Defaults for code quality analysis.
- `LoggingDefaults` - Line 351
  - Logging configuration defaults.
- `FormattingDefaults` - Line 382
  - Defaults for code formatting.
- `UnifiedDiffRegexGroups` - Line 400
  - Capture group indices for unified diff hunk header parsing.
- `RegexCaptureGroups` - Line 410
  - Generic regex capture group indices for parser helpers.
- `SeverityRankingDefaults` - Line 420
  - Shared severity ranking maps and fallback rank values.
- `DisplayDefaults` - Line 430
  - Constants for display and UI elements.
- `PerformanceDefaults` - Line 451
  - Defaults for performance monitoring.
- `BenchmarkExpectationDefaults` - Line 457
  - Expected performance-improvement thresholds for benchmark scripts.
- `CodeAnalysisDefaults` - Line 470
  - Defaults for code structure analysis.
- `ComplexityLevelDefaults` - Line 480
  - Thresholds for classifying complexity into low/medium/high.
- `SmellSeverityDefaults` - Line 487
  - Thresholds for code smell severity classification.
- `UsageTrackingDefaults` - Line 494
  - Defaults for usage tracking and alerting.
- `ReportingDefaults` - Line 512
  - Defaults for deduplication reporting.
- `SEODefaults` - Line 519
  - Defaults for SEO scoring in schema enhancement.
- `SentryDefaults` - Line 540
  - Defaults for Sentry monitoring configuration.
- `DocstringDefaults` - Line 547
  - Defaults for docstring generation.
- `IndentationDefaults` - Line 557
  - Indentation analysis defaults.
- `MinHashDefaults` - Line 565
  - MinHash algorithm configuration.
- `ASTFingerprintDefaults` - Line 576
  - AST structural fingerprinting configuration.
- `PriorityClassifierThresholds` - Line 589
  - Thresholds for classifying deduplication candidate priority.
- `RankerDefaults` - Line 598
  - Deduplication ranker scoring configuration.
- `RiskMultipliers` - Line 610
  - Risk score multipliers for deduplication.
- `RecommendationDefaults` - Line 618
  - Deduplication recommendation configuration.
- `ChangelogDefaults` - Line 671
  - Changelog generator configuration.
- `ReadmeSectionOrder` - Line 677
  - Section ordering for README generation.
- `ReadmeDefaults` - Line 689
  - README generation defaults.
- `SyntaxValidationDefaults` - Line 695
  - Syntax validation timeouts and limits.
- `SubprocessDefaults` - Line 706
  - Default timeouts for subprocess operations.
- `LogBucketThresholds` - Line 715
  - Logarithmic bucket boundaries for code size classification.
- `DifficultyThresholds` - Line 729
  - Complexity-based difficulty classification thresholds.
- `PriorityWeights` - Line 737
  - Weights for priority calculation in deduplication reporting.
- `CrossLanguageDefaults` - Line 745
  - Defaults for cross-language analysis.
- `EquivalenceDefaults` - Line 751
  - Cross-language pattern equivalence defaults.
- `ExampleDataDefaults` - Line 758
  - Shared sample data values used in cross-language examples.
- `DetectorDefaults` - Line 765
  - Deduplication detector defaults.
- `ComplexityStorageDefaults` - Line 778
  - Defaults for complexity trend storage and queries.
- `RuleSetPriority` - Line 784
  - Execution priority ordering for rule sets (higher = runs first).
- `PatternSuggestionConfidence` - Line 794
  - Confidence scores for pattern suggestion types.
- `CondenseDefaults` - Line 805
  - Defaults for code condensation pipeline.
- `CondenseDictionaryDefaults` - Line 834
  - Defaults for zstd dictionary training.
- `CondenseParsing` - Line 843
  - Constants for structural code parsing in condense feature.
- `CondenseFileRouting` - Line 850
  - File-type routing for polyglot condensation.

**Key Imports:** `os`

---
*Generated by Enhanced Schema Generator with schema.org markup*