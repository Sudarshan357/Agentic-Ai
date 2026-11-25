#!/usr/bin/env bash
set -euo pipefail

mkdir -p /home/user/app/memory_data

ollama serve >/tmp/ollama.log 2>&1 &

for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:11434/api/tags >/dev/null; then
    break
  fi
  sleep 1
done

if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null; then
  echo "Ollama failed to start:"
  cat /tmp/ollama.log || true
  exit 1
fi

ollama list | grep -q "qwen2.5:3b" || ollama pull qwen2.5:3b
ollama list | grep -q "nomic-embed-text" || ollama pull nomic-embed-text

exec streamlit run app.py \
  --server.port="${PORT:-7860}" \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --browser.gatherUsageStats=false
