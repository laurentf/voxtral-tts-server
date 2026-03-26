#!/bin/bash
set -e

MODEL_ID="${VOXTRAL_MODEL:-mistralai/Voxtral-4B-TTS-2603}"
PORT="${VOXTRAL_PORT:-8000}"
MAX_MODEL_LEN="${VOXTRAL_MAX_MODEL_LEN:-8192}"
QUANTIZATION="${VOXTRAL_QUANTIZATION:-}"

echo "=== Voxtral TTS Server ==="
echo "Model: $MODEL_ID"
echo "Port: $PORT"
[ -n "$QUANTIZATION" ] && echo "Quantization: $QUANTIZATION"

EXTRA_ARGS=()
if [ -n "$QUANTIZATION" ]; then
    EXTRA_ARGS+=(--quantization "$QUANTIZATION")
fi

exec vllm serve "$MODEL_ID" \
    --omni \
    --port "$PORT" \
    --max-model-len "$MAX_MODEL_LEN" \
    --dtype bfloat16 \
    --gpu-memory-utilization 0.9 \
    "${EXTRA_ARGS[@]}"
