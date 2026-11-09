#!/usr/bin/env bash
set -euo pipefail
CHART_PROJECT_ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
CHART_WORKSPACE_ROOT="${CHART_WORKSPACE_ROOT:-$CHART_PROJECT_ROOT}"
mkdir -p "$CHART_WORKSPACE_ROOT/work/llama-cpu" "$CHART_WORKSPACE_ROOT/work/model-trials"
case "${1:-1.5b}" in
  1.5b) CHART_MODEL_SIZE=1.5; CHART_REVISION=91cad51170dc346986eccefdc2dd33a9da36ead9 ;;
  3b) CHART_MODEL_SIZE=3; CHART_REVISION=7dabda4d13d513e3e842b20f0d435c732f172cbe ;;
  *) echo 'Usage: bash scripts/setup_local_cpu.sh [1.5b|3b]' >&2; exit 2 ;;
esac
hf download "Qwen/Qwen2.5-${CHART_MODEL_SIZE}B-Instruct-GGUF" "qwen2.5-${CHART_MODEL_SIZE}b-instruct-q4_k_m.gguf" \
  --revision "$CHART_REVISION" \
  --local-dir "$CHART_WORKSPACE_ROOT/work/models/qwen25-${CHART_MODEL_SIZE}b-gguf"
hf cache verify "Qwen/Qwen2.5-${CHART_MODEL_SIZE}B-Instruct-GGUF" \
  --revision "$CHART_REVISION" \
  --local-dir "$CHART_WORKSPACE_ROOT/work/models/qwen25-${CHART_MODEL_SIZE}b-gguf"
curl -fL --retry 2 \
  https://github.com/ggml-org/llama.cpp/releases/download/b12000/llama-b12000-bin-ubuntu-x64.tar.gz \
  -o "$CHART_WORKSPACE_ROOT/work/model-trials/llama-cpu.tar.gz"
python - "$CHART_WORKSPACE_ROOT/work/model-trials/llama-cpu.tar.gz" <<'PY'
import hashlib,sys
assert hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest()=="c56588b49ed4be846b115188407ea2b601fa3a5c30b8c25ad60e8344dfc7a4fd", "Runtime checksum mismatch"
PY
tar -xzf "$CHART_WORKSPACE_ROOT/work/model-trials/llama-cpu.tar.gz" -C "$CHART_WORKSPACE_ROOT/work/llama-cpu"
