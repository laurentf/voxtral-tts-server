# Voxtral TTS Server

Docker image for self-hosting [Voxtral 4B TTS](https://huggingface.co/mistralai/Voxtral-4B-TTS-2603) (Mistral AI) via [vLLM-omni](https://github.com/vllm-project/vllm-omni).

Exposes an OpenAI-compatible API for text-to-speech with zero-shot voice cloning.

## Features

- **9 languages** — English, French, Spanish, German, Italian, Portuguese, Dutch, Arabic, Hindi
- **20 preset voices** — male/female across all supported languages
- **Zero-shot voice cloning** — 5-25s reference audio, cross-lingual adaptation
- **Up to 2 min audio** per generation (max_new_tokens=2048)
- **Multiple output formats** — WAV, MP3, FLAC, PCM, AAC, Opus
- **Low latency** — 70ms TTFA on H200 (single request)
- **License** — CC BY-NC 4.0 (non-commercial)

## Requirements

- NVIDIA GPU — 8GB+ VRAM in BF16, or **~4GB** with INT8 quantization (see [Quantization](#quantization))
- Docker with [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)

## Quick start

Pre-built image available on Docker Hub:

```bash
docker run --gpus all -p 8082:8000 naturelbenton/voxtral-tts-server:latest
```

Or build from source:

```bash
docker build -t voxtral-tts .
docker run --gpus all -p 8082:8000 voxtral-tts
```

Docker Compose:

```yaml
services:
  voxtral-tts:
    build: .
    ports:
      - "8082:8000"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

The model (~8GB) is downloaded on first start and cached in the container.
Use a volume on `/root/.cache/huggingface` to persist it across restarts.

## API

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

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `VOXTRAL_MODEL` | `mistralai/Voxtral-4B-TTS-2603` | HuggingFace model ID |
| `VOXTRAL_PORT` | `8000` | Internal server port |
| `VOXTRAL_MAX_MODEL_LEN` | `8192` | Max context length |
| `VOXTRAL_QUANTIZATION` | (none) | Quantization method (see below) |

### Quantization

By default the model loads in BF16 (~8 GB VRAM). This requires a 16GB+ GPU (e.g. RTX 4080, A100, H100).

For smaller GPUs (6–8 GB), set `VOXTRAL_QUANTIZATION` to compress the model at load time — no pre-quantized weights needed, vLLM handles it automatically:

| Value | VRAM | Quality | GPU requirement |
|-------|------|---------|-----------------|
| (empty) | ~8 GB | Best — native BF16 | 8GB+ (RTX 3070, RTX 4070, A100) |
| `bitsandbytes` | ~4 GB | Good — INT8 runtime quantization | 6GB+ (RTX 3060, RTX 4060) |
| `fp8` | ~4 GB | Good — FP8 hardware quantization | Ada/Hopper only (RTX 4090, H100) |

```bash
docker run --gpus all -p 8082:8000 -e VOXTRAL_QUANTIZATION=bitsandbytes voxtral-tts
```

## References

- [Model card](https://huggingface.co/mistralai/Voxtral-4B-TTS-2603) — weights, benchmarks, preset voice list
- [Blog post](https://mistral.ai/news/voxtral-tts) — architecture overview, capabilities
- [Research paper](https://mistral.ai/static/research/voxtral-tts.pdf) — technical details
- [vLLM-omni](https://github.com/vllm-project/vllm-omni) — inference engine with TTS support
