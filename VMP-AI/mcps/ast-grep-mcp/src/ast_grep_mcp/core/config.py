"""Configuration management for ast-grep MCP server."""

import argparse
import os
import sys
from typing import Any, Optional

import yaml
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ast_grep_mcp.constants import CacheDefaults
from ast_grep_mcp.core.exceptions import ConfigurationError
from ast_grep_mcp.core.logging import configure_logging, get_logger
from ast_grep_mcp.models.config import AstGrepConfig


class ServerSettings(BaseSettings):
    """Server configuration using pydantic-settings for automatic env var loading."""

    model_config = SettingsConfigDict(case_sensitive=False, populate_by_name=True)

    config_path: Optional[str] = Field(
        default=None,
        alias="AST_GREP_CONFIG",
        description="Path to sgconfig.yaml file"
    )
    log_level: str = Field(
        default="INFO",
        alias="LOG_LEVEL",
        description="Logging level: DEBUG, INFO, WARNING, ERROR"
    )
    log_file: Optional[str] = Field(
        default=None,
        alias="LOG_FILE",
        description="Path to log file (logs to stderr by default)"
    )
    cache_enabled: bool = Field(
        default=True,
        description="Whether to enable result caching"
    )
    cache_size: int = Field(
        default=CacheDefaults.DEFAULT_CACHE_SIZE,
        alias="CACHE_SIZE",
        description="Maximum cached query results"
    )
    cache_ttl: int = Field(
        default=CacheDefaults.TTL_SECONDS,
        alias="CACHE_TTL",
        description="Cache TTL in seconds"
    )

    @model_validator(mode="after")
    def handle_cache_disabled_flag(self) -> "ServerSettings":
        """Handle CACHE_DISABLED env var (sets cache_enabled to False)."""
        if os.environ.get("CACHE_DISABLED"):
            self.cache_enabled = False
        return self


# Global settings instance
_settings: Optional[ServerSettings] = None

# Backward-compatible globals (set by parse_args_and_get_config)
CONFIG_PATH: Optional[str] = None
CACHE_ENABLED: bool = True
CACHE_SIZE: int = CacheDefaults.DEFAULT_CACHE_SIZE
CACHE_TTL: int = CacheDefaults.TTL_SECONDS

# Global cache instance (will be set after cache.py is extracted)
_query_cache: Optional[Any] = None


def _load_yaml_config(config_path: str) -> dict[str, Any]:
    if not os.path.exists(config_path):
        raise ConfigurationError(config_path, "File does not exist")
    if not os.path.isfile(config_path):
        raise ConfigurationError(config_path, "Path is not a file")
    try:
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigurationError(config_path, f"YAML parsing failed: {e}") from e
    except OSError as e:
        raise ConfigurationError(config_path, f"Failed to read file: {e}") from e
    if config_data is None:
        raise ConfigurationError(config_path, "Config file is empty")
    if not isinstance(config_data, dict):
        raise ConfigurationError(config_path, "Config must be a YAML dictionary")
    return config_data


def validate_config_file(config_path: str) -> AstGrepConfig:
    """Validate sgconfig.yaml file structure.

    Args:
        config_path: Path to sgconfig.yaml file

    Returns:
        Validated AstGrepConfig model

    Raises:
        ConfigurationError: If config file is invalid
    """
    config_data = _load_yaml_config(config_path)
    try:
        return AstGrepConfig(**config_data)
    except Exception as e:
        raise ConfigurationError(config_path, f"Validation failed: {e}") from e


def _add_cache_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--no-cache", action="store_true", help="Disable result caching for queries. Can also be set via CACHE_DISABLED=1 env var."
    )
    parser.add_argument(
        "--cache-size",
        type=int,
        metavar="N",
        default=None,
        help=(f"Maximum cached query results (default: {CacheDefaults.DEFAULT_CACHE_SIZE}). Also settable via CACHE_SIZE env var."),
    )
    parser.add_argument(
        "--cache-ttl",
        type=int,
        metavar="SECONDS",
        default=None,
        help=(f"Cache TTL in seconds (default: {CacheDefaults.TTL_SECONDS}). Also settable via CACHE_TTL env var."),
    )


def _create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    prog = "python main.py" if sys.argv[0].endswith("main.py") else None
    parser = argparse.ArgumentParser(
        prog=prog,
        description="ast-grep MCP Server - Provides structural code search capabilities via Model Context Protocol",
        epilog="""
environment variables:
  AST_GREP_CONFIG    Path to sgconfig.yaml file (overridden by --config flag)
  LOG_LEVEL          Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)
  LOG_FILE           Path to log file (logs to stderr by default)

For more information, see: https://github.com/ast-grep/ast-grep-mcp
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        type=str,
        metavar="PATH",
        help="Path to sgconfig.yaml file for customizing ast-grep behavior (language mappings, rule directories, etc.)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        metavar="LEVEL",
        help="Logging level (DEBUG, INFO, WARNING, ERROR). Can also be set via LOG_LEVEL env var. Default: INFO",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        metavar="PATH",
        default=None,
        help="Path to log file (logs to stderr by default). Can also be set via LOG_FILE env var.",
    )
    _add_cache_arguments(parser)
    return parser


def _try_validate_config(config_path: str) -> None:
    try:
        validate_config_file(config_path)
    except ConfigurationError as e:
        get_logger("config").error("config_validation_failed", config_path=config_path, error=str(e))
        sys.exit(1)


def parse_args_and_get_config() -> None:
    """Parse command-line arguments and determine config path using pydantic-settings."""
    global CONFIG_PATH, CACHE_ENABLED, CACHE_SIZE, CACHE_TTL, _settings

    # Parse CLI arguments
    parser = _create_argument_parser()
    args = parser.parse_args()

    # Create settings from environment + CLI args (CLI takes precedence)
    settings_dict: dict[str, Any] = {}

    # Apply CLI overrides (they take precedence over env vars)
    if args.config:
        settings_dict["config_path"] = args.config
    if args.log_level:
        settings_dict["log_level"] = args.log_level
    if args.log_file:
        settings_dict["log_file"] = args.log_file
    if args.no_cache:
        settings_dict["cache_enabled"] = False
    if args.cache_size is not None:
        settings_dict["cache_size"] = args.cache_size
    if args.cache_ttl is not None:
        settings_dict["cache_ttl"] = args.cache_ttl

    # Create settings instance (merges CLI args with env vars)
    _settings = ServerSettings(**settings_dict)

    # Validate config file if provided
    if _settings.config_path:
        _try_validate_config(_settings.config_path)
    CONFIG_PATH = _settings.config_path

    # Configure logging
    configure_logging(log_level=_settings.log_level, log_file=_settings.log_file)

    # Update globals for backward compatibility
    CACHE_ENABLED = _settings.cache_enabled
    CACHE_SIZE = _settings.cache_size
    CACHE_TTL = _settings.cache_ttl

    # Log cache configuration
    get_logger("cache.init").info(
        "cache_config",
        cache_enabled=CACHE_ENABLED,
        cache_size=CACHE_SIZE,
        cache_ttl=CACHE_TTL
    )
