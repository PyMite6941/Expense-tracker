#!/usr/bin/env bash
# uninstall.sh — Remove the Finance Kit virtual environment and optional artifacts.
#
# Usage:
#   ./uninstall.sh                 # interactive: removes .venv, keeps data/logs by default
#   ./uninstall.sh --yes           # non-interactive, same defaults
#   ./uninstall.sh --remove-data   # also delete user finance data (data.json, rules.json, backups/, receipts/)
#   ./uninstall.sh --remove-logs   # also delete logs (streamlit logs, pytest cache, etc.)
#   ./uninstall.sh --remove-all    # delete .venv + data + logs + caches
#   ./uninstall.sh --keep-all      # only remove .venv; keep everything else (default)
#
# Safety: never touches source code, git history, or committed config files.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$REPO_ROOT/.venv"

REMOVE_DATA=false
REMOVE_LOGS=false
NONINTERACTIVE=false

while [ $# -gt 0 ]; do
  case "$1" in
    --remove-data) REMOVE_DATA=true; shift ;;
    --remove-logs) REMOVE_LOGS=true; shift ;;
    --remove-all)  REMOVE_DATA=true; REMOVE_LOGS=true; shift ;;
    --keep-all)    shift ;;
    --yes|-y)      NONINTERACTIVE=true; shift ;;
    -h|--help)
      sed -n '1,20p' "$0"
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

# Default: keep data and logs; only remove the venv and caches.
if [ "$NONINTERACTIVE" = false ] && [ "$REMOVE_DATA" = false ] && [ "$REMOVE_LOGS" = false ]; then
  echo "== Finance Kit uninstall =="
  echo "Venv:     $VENV_DIR  (will be removed)"
  echo "Data:     kept (use --remove-data to delete data.json, rules.json, backups/, receipts/)"
  echo "Logs:     kept (use --remove-logs to delete caches/logs)"
  echo ""
  read -rp "Proceed? [y/N] " ans
  case "$ans" in
    y|Y|yes|YES) ;;
    *) echo "Aborted."; exit 1 ;;
  esac
fi

echo "[1/4] Removing virtual environment: $VENV_DIR"
if [ -d "$VENV_DIR" ]; then
  rm -rf "$VENV_DIR"
  echo "  removed."
else
  echo "  not present, skipping."
fi

echo "[2/4] Removing Python caches (__pycache__, *.pyc, .pytest_cache, .mypy_cache)"
find "$REPO_ROOT" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
find "$REPO_ROOT" -name '*.pyc' -delete 2>/dev/null || true
find "$REPO_ROOT" -name '*.pyo' -delete 2>/dev/null || true
rm -rf "$REPO_ROOT/.pytest_cache" "$REPO_ROOT/.mypy_cache" "$REPO_ROOT/.coverage" 2>/dev/null || true
echo "  done."

if [ "$REMOVE_LOGS" = true ]; then
  echo "[3/4] Removing logs and runtime caches"
  rm -rf "$REPO_ROOT/.streamlit" "$REPO_ROOT/logs" "$REPO_ROOT/*.log" 2>/dev/null || true
  echo "  done."
else
  echo "[3/4] Keeping logs and runtime caches (use --remove-logs to delete)"
fi

if [ "$REMOVE_DATA" = true ]; then
  echo "[4/4] Removing user finance data"
  rm -f "$REPO_ROOT/data.json" "$REPO_ROOT/rules.json" 2>/dev/null || true
  rm -rf "$REPO_ROOT/backups" "$REPO_ROOT/receipts" 2>/dev/null || true
  rm -f "$REPO_ROOT/expenses.csv" "$REPO_ROOT/income.csv" "$REPO_ROOT/subscriptions.csv" "$REPO_ROOT/monthly_summary.pdf" 2>/dev/null || true
  rm -f "$REPO_ROOT/expenses*.pdf" "$REPO_ROOT/income*.pdf" 2>/dev/null || true
  echo "  done."
else
  echo "[4/4] Keeping user finance data (data.json, rules.json, backups/, receipts/, exports)"
fi

echo ""
echo "Uninstall complete. Source code and git history are untouched."
echo "To reinstall: python -m venv .venv && .venv/Scripts/pip install -r requirements.txt"
