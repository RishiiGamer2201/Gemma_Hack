# Local model feasibility

Last measured: 2026-07-13 IST (2026-07-12 UTC)

## Decision

Use the pinned `gemma4:e4b-it-q4_K_M` build as the primary text model and
`gemma4:e2b-it-q4_K_M` as the fallback. Both completed all deterministic text,
multilingual, structured-output, 8K-context, and sequential-agent probes without an
out-of-memory error. Set the current production context ceiling to 8,192 tokens and
keep the output ceiling at 1,200 tokens.

The compact Ollama manifests expose `completion`, `tools`, and `thinking`, but do not
advertise `vision` or audio capability. The offline image and audio fallbacks are now
benchmarked in `docs/ocr_feasibility.md` and `docs/asr_feasibility.md`. Native Gemma
multimodal input remains unverified. The upstream Gemma 4 models
do support text, image, and audio, but upstream capability does not prove that these
particular quantized runtime packages expose every modality.

## Reproduction

```powershell
python scripts/model_feasibility.py --benchmark --output .runtime/model_feasibility.json
```

The command inventories only machine/runtime properties, queries only the loopback
Ollama API, unloads each model before its cold-start probe, samples RAM and NVIDIA
VRAM during every call, and writes the full result to an ignored runtime directory.
It sends no user documents and contains no benchmark secrets.

## Machine and runtime

| Property | Measured value |
|---|---|
| OS | Windows 11 Pro, build 26200 (`10.0.26200`) |
| CPU | Intel Core Ultra 7 265K, 20 physical / 20 logical cores |
| RAM | 33,686,286,336 bytes (31.38 GiB) |
| GPU | NVIDIA GeForce RTX 5070 Ti |
| VRAM | 17,094,934,528 bytes (15.92 GiB) |
| NVIDIA driver | 610.74 |
| System disk | 1,999,329,292,288 bytes total; 664,510,484,480 free |
| Runtime | Ollama 0.31.2, loopback `127.0.0.1:11434` |
| Benchmark Python | 3.13.13 |

Ollama was installed from the `Ollama.Ollama` WinGet package. The server is bound to
loopback; production launch must also set `OLLAMA_NO_CLOUD=1` after model acquisition.

## Pinned builds

| Role | Tag | Ollama digest | Size | Quantization | License |
|---|---|---|---:|---|---|
| Primary | `gemma4:e4b-it-q4_K_M` | `c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb` | 9,608,350,718 bytes | Q4_K_M | Apache-2.0 |
| Fallback | `gemma4:e2b-it-q4_K_M` | `7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e` | 7,162,405,886 bytes | Q4_K_M | Apache-2.0 |

The exact tags and digests are enforced in `config/model_builds.json`. The license and
base-model capabilities were checked against Google's official Hugging Face model
cards and Google AI documentation; runtime tag metadata was checked against the
official Ollama registry.

Sources:

- [Google Gemma 4 E4B model card](https://huggingface.co/google/gemma-4-E4B)
- [Google Gemma 4 E2B model card](https://huggingface.co/google/gemma-4-E2B)
- [Google Gemma 4 overview](https://ai.google.dev/gemma/docs/core)
- [Ollama Gemma 4 tags](https://ollama.com/library/gemma4/tags)

## Benchmark results

All calls used temperature 0 and `think=false`. The latter is important: the first
diagnostic pass showed that thinking tokens could consume a deliberately small output
budget and leave the visible response empty.

| Probe | E4B | E2B |
|---|---:|---:|
| Cold load | 8.16 s | 7.27 s |
| 943-token prompt generation rate | 147.88 tok/s | 222.90 tok/s |
| Warm English deterministic call | pass | pass |
| Hindi deterministic call | pass | pass |
| Hinglish deterministic call | pass | pass |
| System instruction + JSON object | pass | pass |
| Advocate → opponent → rebuttal | pass, 7.69 s total | pass, 6.35 s total |

The generation-rate field is Ollama's output-token rate over a 160-token generated
sample. The prompt contained 943 evaluated tokens, close to the requested 1K
benchmark size; prompt processing and model reload are included in total wall time.

### Context and memory

| Model | Requested context | Evaluated prompt | Result | Total time | Peak GPU memory |
|---|---:|---:|---|---:|---:|
| E4B | 2,048 | 1,568 | pass | 0.38 s | 12,379,488,256 B |
| E4B | 4,096 | 3,104 | pass | 6.33 s | 12,417,236,992 B |
| E4B | 8,192 | 6,176 | pass | 6.69 s | 12,629,049,344 B |
| E2B | 2,048 | 1,568 | pass | 0.36 s | 10,838,081,536 B |
| E2B | 4,096 | 3,104 | pass | 5.48 s | 10,852,761,600 B |
| E2B | 8,192 | 6,176 | pass | 5.88 s | 11,024,728,064 B |

GPU memory is the maximum device-wide reading sampled by `nvidia-smi`, not an
isolated per-process allocation. System-RAM delta is also host-wide and can be noisy;
the maximum observed delta was 1,319,116,800 bytes for E4B and 5,621,116,928 bytes
for E2B during cold model loading. Both other pinned models were unloaded before each
model run to avoid cross-model residency.

## Acceptance status and remaining work

- E4B structured output and all tested contexts pass without OOM.
- Warm deterministic responses complete in about 0.3–0.5 seconds; cold loads take
  7–9 seconds and must be hidden by startup preloading.
- The three-stage text workflow completes in about 6–8 seconds. The hardened live
  workflow emitted 271 visible token events across advocate, opponent, and rebuttal;
  a warm single-stage probe produced its first visible token in about 405 ms.
- E2B passes every currently implemented text probe.
- Printed-notice and synthetic phone-style image probes pass through the local OCR
  fallback. A real consented camera photograph remains a pre-release evaluation item.
