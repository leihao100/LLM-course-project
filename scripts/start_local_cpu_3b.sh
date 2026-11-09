#!/usr/bin/env bash
set -euo pipefail
CHART_PROJECT_ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
CHART_WORKSPACE_ROOT="${CHART_WORKSPACE_ROOT:-$CHART_PROJECT_ROOT}"
export CHART_MODEL_FILE="${CHART_MODEL_FILE:-$CHART_WORKSPACE_ROOT/work/models/qwen25-3b-gguf/qwen2.5-3b-instruct-q4_k_m.gguf}"
export CHART_MODEL_ALIAS="Qwen2.5-3B-Instruct-Q4_K_M"
export CHART_PORT="${CHART_PORT:-8019}"
exec bash "$CHART_PROJECT_ROOT/scripts/start_local_cpu.sh"
