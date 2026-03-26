FROM vllm/vllm-openai:v0.18.0

# Install git (pip needs it for GitHub installs) + vllm-omni + RunPod SDK
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir \
        git+https://github.com/vllm-project/vllm-omni.git \
        runpod \
        httpx

# Copy handler (RunPod serverless) + entrypoint (standalone Docker)
COPY handler.py /handler.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV HF_HOME=/root/.cache/huggingface
ENV VOXTRAL_MODEL=mistralai/Voxtral-4B-TTS-2603

EXPOSE 8000

# Default: RunPod serverless handler
# Override with --entrypoint /entrypoint.sh for standalone mode
CMD ["python3", "-u", "/handler.py"]
