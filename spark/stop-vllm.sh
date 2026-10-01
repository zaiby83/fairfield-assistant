#!/usr/bin/env bash
# Fairfield Assistant - stop and remove the vLLM containers on the DGX Spark.
# Removes only the two containers; the HF cache, image and ~/vllm.env are untouched.
set -euo pipefail

for name in vllm-gemma vllm-gptoss; do
  if docker container inspect "$name" >/dev/null 2>&1; then
    echo "stopping $name"
    docker stop -t 30 "$name" >/dev/null
    docker rm "$name" >/dev/null
  else
    echo "$name not present"
  fi
done
