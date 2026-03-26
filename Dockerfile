FROM vllm/vllm-openai:v0.18.0

# Install git (needed for pip install from GitHub) + vllm-omni TTS support
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir git+https://github.com/vllm-project/vllm-omni.git

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
