#!/usr/bin/env bash
set -euo pipefail
CHART_PROJECT_ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
CHART_WORKSPACE_ROOT="${CHART_WORKSPACE_ROOT:-$CHART_PROJECT_ROOT}"
CHART_LLAMA_BIN="${CHART_LLAMA_BIN:-$CHART_WORKSPACE_ROOT/work/llama-cpu/llama-b12000/llama-server}"
CHART_MODEL_FILE="${CHART_MODEL_FILE:-$CHART_WORKSPACE_ROOT/work/models/qwen25-1.5b-gguf/qwen2.5-1.5b-instruct-q4_k_m.gguf}"
exec "$CHART_LLAMA_BIN" -m "$CHART_MODEL_FILE" \
  --host 127.0.0.1 --port "${CHART_PORT:-8018}" \
  --alias "${CHART_MODEL_ALIAS:-Qwen2.5-1.5B-Instruct-Q4_K_M}" -c 16384 \
  -t "${CHART_THREADS:-8}" -tb "${CHART_BATCH_THREADS:-16}" -ngl 0 --parallel 1
