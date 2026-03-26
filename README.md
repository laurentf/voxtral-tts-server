# Voxtral TTS Server

[![Docker Hub](https://img.shields.io/docker/v/naturelbenton/voxtral-tts-server?label=Docker%20Hub)](https://hub.docker.com/r/naturelbenton/voxtral-tts-server)
[![RunPod](https://img.shields.io/badge/RunPod-serverless-blueviolet)](https://runpod.io)

Docker image for self-hosting [Voxtral 4B TTS](https://huggingface.co/mistralai/Voxtral-4B-TTS-2603) (Mistral AI) via [vLLM-omni](https://github.com/vllm-project/vllm-omni).

Exposes an OpenAI-compatible API for text-to-speech with zero-shot voice cloning. Works as a standalone Docker service or as a RunPod serverless worker.

## Features

- **9 languages** — English, French, Spanish, German, Italian, Portuguese, Dutch, Arabic, Hindi
- **20 preset voices** — male/female across all supported languages
- **Zero-shot voice cloning** — 5-25s reference audio, cross-lingual adaptation
- **Up to 8 min audio** per generation (max_new_tokens=8192)
- **Multiple output formats** — WAV, MP3, FLAC, PCM, AAC, Opus
- **Low latency** — 70ms TTFA on H200 (single request)
- **RunPod serverless** — ready-to-deploy with GPU presets and network volume caching
- **License** — CC BY-NC 4.0 (non-commercial)

## Requirements

- NVIDIA GPU — 8GB+ VRAM in BF16, or **~4GB** with INT8 quantization (see [Quantization](#quantization))
- CUDA driver **12.9+** (required by vLLM v0.18.0 / vLLM-omni v0.18.0)
- Docker with [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)

---

## Quick start

### Docker (self-hosted)

Pre-built image available on Docker Hub:

```bash
docker run --gpus all -p 8082:8000 --entrypoint /entrypoint.sh naturelbenton/voxtral-tts-server:latest
```

Or build from source (standalone mode uses the entrypoint script):

```bash
docker build -t voxtral-tts .
docker run --gpus all -p 8082:8000 --entrypoint /entrypoint.sh voxtral-tts
```

Docker Compose:

```yaml
services:
  voxtral-tts:
    image: naturelbenton/voxtral-tts-server:latest
    entrypoint: /entrypoint.sh
    ports:
      - "8082:8000"
    volumes:
      - voxtral-models:/root/.cache/huggingface
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

volumes:
  voxtral-models:
```

The model (~8 GB) is downloaded at first startup from HuggingFace — set `HF_TOKEN` env var if the model requires authentication.

### RunPod (serverless)

Deploy as a serverless endpoint on [RunPod](https://runpod.io):

1. Go to **Serverless** > **New Endpoint**
2. Set image: `naturelbenton/voxtral-tts-server:runpod`
3. Select GPU tier (see [presets](#runpod-presets))
4. Network volume optional (model is pre-baked in the image)
5. Set environment variables as needed (see [Configuration](#configuration))
6. Deploy

**Build the RunPod image yourself:**

```bash
docker build -t naturelbenton/voxtral-tts-server:runpod .
docker push naturelbenton/voxtral-tts-server:runpod
```

#### RunPod input/output

**Input** (sent as `job.input`):

```json
{
  "text": "Bonjour et bienvenue!",
  "voice": "fr_marie_happy",
  "language": "fr",
  "response_format": "wav"
}
```

**Input with voice cloning** (use `ref_audio` instead of `voice`):

```json
{
  "text": "Speaking with a cloned voice.",
  "ref_audio": "data:audio/wav;base64,UklGRi...",
  "ref_text": "Transcript of the reference audio.",
  "response_format": "wav"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `text` | string | (required) | Text to synthesize |
| `voice` | string | `"neutral_male"` | Preset voice (ignored when `ref_audio` is set) |
| `ref_audio` | string | — | Voice cloning: base64 data URL |
| `ref_text` | string | — | Transcript of reference audio |
| `response_format` | string | `"wav"` | wav, mp3, flac, pcm, aac, opus |
| `speed` | float | `1.0` | Playback speed (0.25–4.0) |
| `language` | string | `"Auto"` | en, fr, es, de, it, pt, nl, ar, hi |
| `max_new_tokens` | int | `2048` | Max generation tokens (~2 min audio) |

**Output:**

```json
{
  "audio_base64": "UklGRi...",
  "format": "wav",
  "model": "mistralai/Voxtral-4B-TTS-2603"
}
```

#### RunPod presets

| Preset | GPUs | VRAM | Quantization |
|--------|------|------|--------------|
| BF16 (best quality) | A40 48GB, RTX 4090 24GB, A100 | 8GB+ used | None (native BF16) |
| INT8 (low VRAM) | RTX 4060 16GB, A10 | ~4GB used | `bitsandbytes` |

---

## API (self-hosted)

OpenAI-compatible endpoints served by vLLM-omni on port 8000 (internal).

### `POST /v1/audio/speech`

Synthesize speech from text. Returns binary audio in the requested format.

Two modes — **preset voice** or **voice cloning** (mutually exclusive):

**Preset voice** — use `voice` to select one of the 20 built-in voices:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `input` | string | (required) | Text to synthesize |
| `voice` | string | `"neutral_male"` | Preset voice name (see `GET /v1/audio/voices`) |
| `response_format` | string | `"wav"` | wav, mp3, flac, pcm, aac, opus |
| `speed` | float | `1.0` | Playback speed (0.25–4.0) |
| `language` | string | `"Auto"` | Force language: en, fr, es, de, it, pt, nl, ar, hi |
| `max_new_tokens` | int | `2048` | Max generation tokens (~2 min audio) |
| `model` | string | server default | Model ID override |

```bash
curl http://localhost:8082/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"input": "Bonjour!", "voice": "fr_marie_happy", "language": "fr"}' \
  --output speech.wav
```

**Voice cloning** — use `ref_audio` + `ref_text` instead of `voice` (5-25s reference):

| Field | Type | Description |
|-------|------|-------------|
| `ref_audio` | string | Base64 data URL (`data:audio/wav;base64,...`), HTTP URL, or `file://` URI |
| `ref_text` | string | Transcript of the reference audio |

All other fields (`input`, `response_format`, `speed`, `language`, `max_new_tokens`) apply to both modes.

```bash
curl http://localhost:8082/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Speaking with a cloned voice.",
    "ref_audio": "data:audio/wav;base64,UklGRi...",
    "ref_text": "Transcript of the reference."
  }' --output cloned.wav
```

### `GET /v1/audio/voices`

List available preset voices (20 voices across 9 languages).

```bash
curl http://localhost:8082/v1/audio/voices
```

### `GET /health`

Returns 200 when the server is ready to accept requests.

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `VOXTRAL_MODEL` | `mistralai/Voxtral-4B-TTS-2603` | HuggingFace model ID |
| `VOXTRAL_PORT` | `8000` | Internal server port |
| `VOXTRAL_MAX_MODEL_LEN` | `8192` | Max context length |
| `VOXTRAL_QUANTIZATION` | (none) | Quantization method (see below) |

### Quantization

By default the model loads in BF16 (~8 GB VRAM). This requires a 8GB+ GPU (e.g. RTX 3070, RTX 4070, A100).

For smaller GPUs (6-8 GB), set `VOXTRAL_QUANTIZATION` to compress the model at load time — no pre-quantized weights needed, vLLM handles it automatically:

| Value | VRAM | Quality | GPU requirement |
|-------|------|---------|-----------------|
| (empty) | ~8 GB | Best — native BF16 | 8GB+ (RTX 3070, RTX 4070, A100) |
| `bitsandbytes` | ~4 GB | Good — INT8 runtime quantization | 6GB+ (RTX 3060, RTX 4060) |
| `fp8` | ~4 GB | Good — FP8 hardware quantization | Ada/Hopper only (RTX 4090, H100) |

```bash
docker run --gpus all -p 8082:8000 -e VOXTRAL_QUANTIZATION=bitsandbytes naturelbenton/voxtral-tts-server:latest
```

## References

- [Model card](https://huggingface.co/mistralai/Voxtral-4B-TTS-2603) — weights, benchmarks, preset voice list
- [Blog post](https://mistral.ai/news/voxtral-tts) — architecture overview, capabilities
- [Research paper](https://mistral.ai/static/research/voxtral-tts.pdf) — technical details
- [vLLM-omni](https://github.com/vllm-project/vllm-omni) — inference engine with TTS support
