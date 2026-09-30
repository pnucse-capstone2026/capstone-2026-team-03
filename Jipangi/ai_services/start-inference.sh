#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/yejun/Desktop/graduate_proj"
JIPANGI_ROOT="$PROJECT_ROOT/Jipangi"

case "${1:-}" in
  allosaurus)
    exec /home/yejun/yes/envs/allosaurus-ft/bin/python \
      "$JIPANGI_ROOT/ai_services/allosaurus_server.py" --host 127.0.0.1 --port 8101
    ;;
  qwen)
    export PATH="/home/yejun/yes/envs/qwen-infer/bin:$PATH"
    exec /home/yejun/yes/envs/qwen-infer/bin/vllm serve \
      "$PROJECT_ROOT/qwen/Qwen3-8B-AWQ" \
      --host 127.0.0.1 --port 8102 \
      --served-model-name jipangi-qwen3-8b-awq \
      --max-model-len 8192 --gpu-memory-utilization 0.78 \
      --enforce-eager \
      --generation-config vllm
    ;;
  celery)
    cd "$JIPANGI_ROOT/backend"
    exec /home/yejun/yes/envs/grad/bin/celery -A config worker --loglevel=INFO
    ;;
  *)
    echo "Usage: $0 {allosaurus|qwen|celery}" >&2
    exit 2
    ;;
esac
