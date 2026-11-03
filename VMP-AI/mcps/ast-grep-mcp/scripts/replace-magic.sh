#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/replace-magic.sh --from <pattern> --to <replacement> [options] [path...]

Description:
  Preview-first helper for rg + sed replacements.
  Designed for replacing magic values with constants.

Required:
  --from <pattern>        Search pattern (literal unless --regex is set)
  --to <replacement>      Replacement text

Options:
  --apply                 Apply changes in-place (default: preview only)
  --regex                 Treat --from as regex (default: literal)
  --word                  Match token boundaries for --from (good for numbers)
  --glob <pattern>        Include only matching files (repeatable)
  --context <n>           Context lines for preview (default: 2)
  --help                  Show this help

Examples:
  # Preview: replace standalone 1000 with TIME_MS.SECOND in TS files
  scripts/replace-magic.sh --from 1000 --to TIME_MS.SECOND --word --glob '*.ts' sidequest api

  # Apply same replacement
  scripts/replace-magic.sh --from 1000 --to TIME_MS.SECOND --word --glob '*.ts' --apply sidequest api

  # Regex mode
  scripts/replace-magic.sh --from '30\\s*\\*\\s*24\\s*\\*\\s*60\\s*\\*\\s*60' \
    --to 'GIT_ACTIVITY.MONTHLY_WINDOW_DAYS * (TIME_MS.DAY / TIME_MS.SECOND)' \
    --regex --glob '*.ts' sidequest
EOF
}

escape_ere_literal() {
  printf '%s' "$1" | sed -e 's/[][\.^$*+?(){}|/\\]/\\&/g'
}

escape_replacement() {
  # Escape chars that are special in sed replacement strings.
  printf '%s' "$1" | sed -e 's/[&|\\]/\\&/g'
}

run_sed_in_place() {
  local expr="$1"
  shift
  if sed --version >/dev/null 2>&1; then
    sed -E -i -e "$expr" "$@"
  else
    sed -E -i '' -e "$expr" "$@"
  fi
}

from=""
to=""
apply=0
is_regex=0
word_mode=0
context=2
declare -a globs=()
declare -a paths=()

while (($#)); do
  case "$1" in
    --from)
      from="${2-}"
      shift 2
      ;;
    --to)
      to="${2-}"
      shift 2
      ;;
    --apply)
      apply=1
      shift
      ;;
    --regex)
      is_regex=1
      shift
      ;;
    --word)
      word_mode=1
      shift
      ;;
    --glob)
      globs+=("${2-}")
      shift 2
      ;;
    --context)
      context="${2-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      while (($#)); do
        paths+=("$1")
        shift
      done
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
    *)
      paths+=("$1")
      shift
      ;;
  esac
done

if [[ -z "$from" || -z "$to" ]]; then
  echo "Both --from and --to are required." >&2
  usage
  exit 1
fi

if [[ ! "$context" =~ ^[0-9]+$ ]]; then
  echo "--context must be a non-negative integer." >&2
  exit 1
fi

if ((${#paths[@]} == 0)); then
  paths=(.)
fi

if ((is_regex)); then
  rg_pattern="$from"
  sed_search="$from"
else
  escaped="$(escape_ere_literal "$from")"
  rg_pattern="$escaped"
  sed_search="$escaped"
fi

if ((word_mode)); then
  rg_pattern="(^|[^[:alnum:]_])(${rg_pattern})([^[:alnum:]_]|$)"
  sed_search="(^|[^[:alnum:]_])(${sed_search})([^[:alnum:]_]|$)"
  sed_repl="\\1$(escape_replacement "$to")\\3"
else
  sed_repl="$(escape_replacement "$to")"
fi

declare -a rg_args=("--pcre2" "-n" "-C" "$context")
declare -a rg_files_args=("--pcre2" "-l")
for g in "${globs[@]}"; do
  rg_args+=("-g" "$g")
  rg_files_args+=("-g" "$g")
done

echo "Pattern: $from"
echo "Replacement: $to"
echo "Mode: $([[ $apply -eq 1 ]] && echo apply || echo preview)"
echo "Word boundary mode: $([[ $word_mode -eq 1 ]] && echo on || echo off)"
echo

set +e
rg "${rg_args[@]}" "$rg_pattern" "${paths[@]}"
preview_rc=$?
set -e

if ((preview_rc > 1)); then
  echo "rg failed while previewing matches." >&2
  exit "$preview_rc"
fi

if ((preview_rc == 1)); then
  echo "No matches found."
  exit 0
fi

if ((apply == 0)); then
  echo
  echo "Preview only. Re-run with --apply to modify files."
  exit 0
fi

mapfile -t matched_files < <(rg "${rg_files_args[@]}" "$rg_pattern" "${paths[@]}")
if ((${#matched_files[@]} == 0)); then
  echo "No files to update."
  exit 0
fi

sed_expr="s|${sed_search}|${sed_repl}|g"
run_sed_in_place "$sed_expr" "${matched_files[@]}"

echo
echo "Updated ${#matched_files[@]} file(s)."
echo "Remaining matches after replacement:"
set +e
rg "${rg_args[@]}" "$rg_pattern" "${paths[@]}"
after_rc=$?
set -e
if ((after_rc == 1)); then
  echo "None."
elif ((after_rc > 1)); then
  echo "rg failed during post-check." >&2
  exit "$after_rc"
fi
