FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    zstd \
    procps \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://ollama.com/install.sh | sh

RUN useradd -m -u 1000 user && mkdir -p /home/user/.ollama/models /home/user/app && chown -R user:user /home/user

WORKDIR /home/user/app

COPY requirements.txt /home/user/app/requirements.txt
RUN pip install --no-cache-dir -r /home/user/app/requirements.txt

USER user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_MODELS=/home/user/.ollama/models \
    PYTHONUNBUFFERED=1

RUN ollama serve >/tmp/ollama-build.log 2>&1 & \
    pid=$!; \
    for i in $(seq 1 30); do \
      if curl -sf http://127.0.0.1:11434/api/tags >/dev/null; then break; fi; \
      sleep 1; \
    done; \
    ollama pull qwen2.5:3b && \
    ollama pull nomic-embed-text && \
    kill $pid || true

COPY --chown=user:user . /home/user/app

RUN sed -i 's/\r$//' /home/user/app/start.sh && chmod +x /home/user/app/start.sh

EXPOSE 7860

CMD ["/home/user/app/start.sh"]
