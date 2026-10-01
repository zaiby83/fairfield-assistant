#!/usr/bin/env bash
# Fairfield Assistant - start the vLLM backends on the DGX Spark (single node, DEV).
#
#   vllm-gptoss : openai/gpt-oss-120b            -> served as "gpt-oss-120b" on 192.168.250.1:8000
#   vllm-gemma  : nvidia/Gemma-4-26B-A4B-NVFP4   -> served as "gemma4-26b"   on 192.168.250.1:8001
#
# gpt-oss is started first and must answer /v1/models before Gemma is started
# (the second engine sizes itself from the memory left after the first).
#
# Flags come from github.com/eugr/spark-vllm-docker recipes
#   recipes/openai-gpt-oss-120b.yaml, recipes/gemma4-26b-a4b-nvfp4.yaml
# and were checked against `vllm serve --help=all` in the vllm-node image
# (vLLM 0.30.1rc1.dev511+gcb6458c5c). See CHANGELOG.md for what was verified.
#
# Opt-in switches (environment variables, default off):
#   GPTOSS_MXFP4_FLAGS=1  add the MXFP4-build-only flags from the upstream recipe
#                         (--mxfp4-backend, --mxfp4-layers, VLLM_USE_FLASHINFER_MOE_MXFP4_MXFP8).
#                         Only valid with a vllm-node-mxfp4 image (set GPTOSS_IMAGE too);
#                         the script refuses if the image does not support them.
#   GEMMA_MTP=1           enable MTP speculative decoding for Gemma using
#                         google/gemma-4-26B-A4B-it-assistant (must be in the HF cache).
#
# The API key is never put on the command line: vLLM reads VLLM_API_KEY from the
# environment (--env-file ~/vllm.env) and enforces it exactly like --api-key.

set -euo pipefail

BIND_HOST="192.168.250.1"            # mac-direct link only. Never 0.0.0.0.
ENV_FILE="${ENV_FILE:-$HOME/vllm.env}"
HF_CACHE="${HF_CACHE:-$HOME/.cache/huggingface}"
READY_TIMEOUT="${READY_TIMEOUT:-1800}" # seconds per model (first load + compile can be slow)

GPTOSS_IMAGE="${GPTOSS_IMAGE:-vllm-node}"
GPTOSS_NAME="vllm-gptoss"
GPTOSS_MODEL="openai/gpt-oss-120b"
GPTOSS_SERVED="gpt-oss-120b"
GPTOSS_PORT=8000
GPTOSS_GPU_UTIL="${GPTOSS_GPU_UTIL:-0.55}"
GPTOSS_MAX_LEN="${GPTOSS_MAX_LEN:-65536}"
GPTOSS_LOAD_FORMAT="${GPTOSS_LOAD_FORMAT:-fastsafetensors}"
GPTOSS_MXFP4_FLAGS="${GPTOSS_MXFP4_FLAGS:-0}"

GEMMA_IMAGE="${GEMMA_IMAGE:-vllm-node}"
GEMMA_NAME="vllm-gemma"
GEMMA_MODEL="nvidia/Gemma-4-26B-A4B-NVFP4"
GEMMA_SERVED="gemma4-26b"
GEMMA_PORT=8001
GEMMA_GPU_UTIL="${GEMMA_GPU_UTIL:-0.25}"
GEMMA_MAX_LEN="${GEMMA_MAX_LEN:-32768}"
GEMMA_LOAD_FORMAT="${GEMMA_LOAD_FORMAT:-instanttensor}"
GEMMA_MTP="${GEMMA_MTP:-0}"
GEMMA_MTP_MODEL="google/gemma-4-26B-A4B-it-assistant"

log() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

# ---------- preflight ----------
command -v docker >/dev/null || die "docker not found"
command -v curl >/dev/null || die "curl not found"
ip -4 addr show | grep -q "inet ${BIND_HOST}/" || die "${BIND_HOST} is not configured on this host (mac-direct down?)"
[[ -r "$ENV_FILE" ]] || die "$ENV_FILE not readable"
[[ "$(stat -c %a "$ENV_FILE")" == "600" ]] || die "$ENV_FILE must be chmod 600"
VLLM_API_KEY="$(sed -n 's/^VLLM_API_KEY=//p' "$ENV_FILE" | tail -n 1)"
[[ -n "$VLLM_API_KEY" ]] || die "VLLM_API_KEY missing from $ENV_FILE"

model_cached() { # repo id -> succeeds if a snapshot exists and no partial downloads remain
  local dir="$HF_CACHE/hub/models--${1//\//--}"
  compgen -G "$dir/snapshots/*/config.json" >/dev/null || return 1
  ! compgen -G "$dir/blobs/*.incomplete" >/dev/null
}
model_cached "$GPTOSS_MODEL" || die "$GPTOSS_MODEL not fully in $HF_CACHE (download still running?)"
model_cached "$GEMMA_MODEL" || die "$GEMMA_MODEL not fully in $HF_CACHE (download still running?)"
if [[ "$GEMMA_MTP" == "1" ]]; then
  model_cached "$GEMMA_MTP_MODEL" || die "GEMMA_MTP=1 but $GEMMA_MTP_MODEL is not fully cached"
fi

for n in "$GPTOSS_NAME" "$GEMMA_NAME"; do
  if docker container inspect "$n" >/dev/null 2>&1; then
    die "container $n already exists; run ./stop-vllm.sh first"
  fi
done

# ---------- helpers ----------
wait_ready() { # name port
  local name="$1" port="$2" start=$SECONDS state
  log "waiting for $name on http://${BIND_HOST}:${port}/v1/models (timeout ${READY_TIMEOUT}s)"
  while (( SECONDS - start < READY_TIMEOUT )); do
    state="$(docker container inspect -f '{{.State.Status}}' "$name" 2>/dev/null || echo missing)"
    if [[ "$state" != "running" ]]; then
      log "$name is '$state'; last log lines:"
      docker logs --tail 80 "$name" 2>&1 || true
      die "$name stopped before becoming ready"
    fi
    # Header comes from a process substitution so the key never appears in `ps`.
    if curl -fsS -m 5 -H @<(printf 'Authorization: Bearer %s\n' "$VLLM_API_KEY") \
        "http://${BIND_HOST}:${port}/v1/models" >/dev/null 2>&1; then
      log "$name ready after $(( SECONDS - start ))s"
      return 0
    fi
    sleep 10
  done
  log "$name not ready after ${READY_TIMEOUT}s; last log lines:"
  docker logs --tail 80 "$name" 2>&1 || true
  die "timeout waiting for $name (container left running for inspection)"
}

common_run_args=(
  -d
  --gpus all
  --ipc host
  --network host
  --restart unless-stopped
  -v "$HF_CACHE:/root/.cache/huggingface"
  --env-file "$ENV_FILE"
  -e HF_HUB_OFFLINE=1
  --entrypoint vllm
)

# ---------- gpt-oss-120b ----------
gptoss_env=()
gptoss_extra=()
if [[ "$GPTOSS_MXFP4_FLAGS" == "1" ]]; then
  # Verify the image actually supports these before using them.
  if ! docker run --rm --gpus all --entrypoint vllm "$GPTOSS_IMAGE" serve --help=all 2>/dev/null \
      | grep -q -- '--mxfp4-backend'; then
    die "GPTOSS_MXFP4_FLAGS=1 but image '$GPTOSS_IMAGE' has no --mxfp4-backend (needs vllm-node-mxfp4)"
  fi
  gptoss_env=(-e VLLM_USE_FLASHINFER_MOE_MXFP4_MXFP8=1)
  gptoss_extra=(--mxfp4-backend CUTLASS --mxfp4-layers "moe,qkv,o,lm_head")
fi

log "starting $GPTOSS_NAME ($GPTOSS_MODEL, image $GPTOSS_IMAGE, mxfp4-build-flags=$GPTOSS_MXFP4_FLAGS)"
docker run "${common_run_args[@]}" --name "$GPTOSS_NAME" ${gptoss_env[@]+"${gptoss_env[@]}"} \
  "$GPTOSS_IMAGE" serve "$GPTOSS_MODEL" \
    --served-model-name "$GPTOSS_SERVED" \
    --host "$BIND_HOST" --port "$GPTOSS_PORT" \
    --gpu-memory-utilization "$GPTOSS_GPU_UTIL" \
    --max-model-len "$GPTOSS_MAX_LEN" \
    --tool-call-parser openai \
    --reasoning-parser openai_gptoss \
    --enable-auto-tool-choice \
    --enable-prefix-caching \
    --load-format "$GPTOSS_LOAD_FORMAT" \
    --quantization mxfp4 \
    --attention-backend FLASHINFER \
    --kv-cache-dtype fp8 \
    --max-num-batched-tokens 8192 \
    ${gptoss_extra[@]+"${gptoss_extra[@]}"} >/dev/null
wait_ready "$GPTOSS_NAME" "$GPTOSS_PORT"

# ---------- Gemma 4 26B-A4B NVFP4 (text + image) ----------
gemma_extra=()
if [[ "$GEMMA_MTP" == "1" ]]; then
  gemma_extra=(--speculative-config
    "{\"method\":\"mtp\",\"model\":\"${GEMMA_MTP_MODEL}\",\"num_speculative_tokens\":4,\"moe_backend\":\"triton\"}")
fi

log "starting $GEMMA_NAME ($GEMMA_MODEL, image $GEMMA_IMAGE, mtp=$GEMMA_MTP)"
docker run "${common_run_args[@]}" --name "$GEMMA_NAME" \
  "$GEMMA_IMAGE" serve "$GEMMA_MODEL" \
    --served-model-name "$GEMMA_SERVED" \
    --host "$BIND_HOST" --port "$GEMMA_PORT" \
    --gpu-memory-utilization "$GEMMA_GPU_UTIL" \
    --max-model-len "$GEMMA_MAX_LEN" \
    --tensor-parallel-size 1 \
    --load-format "$GEMMA_LOAD_FORMAT" \
    --enable-prefix-caching \
    --enable-auto-tool-choice \
    --tool-call-parser gemma4 \
    --reasoning-parser gemma4 \
    --kv-cache-dtype fp8 \
    --max-num-batched-tokens 8192 \
    ${gemma_extra[@]+"${gemma_extra[@]}"} >/dev/null
wait_ready "$GEMMA_NAME" "$GEMMA_PORT"

log "both backends ready: gpt-oss-120b @ :${GPTOSS_PORT}, gemma4-26b @ :${GEMMA_PORT} on ${BIND_HOST}"
