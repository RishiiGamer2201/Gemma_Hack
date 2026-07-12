# Offline ASR feasibility

Last measured: 2026-07-13 IST

## Decision

Use pinned `faster-whisper-small` as the local Hindi/English ASR fallback because the
compact Ollama Gemma 4 manifests do not expose audio input. Audio is copied into a
bounded in-memory buffer after validation, transcription runs with Hugging Face forced
offline, and neither audio nor transcript is written by the application.

The transcript must always pass through the editable confirmation loop. The English
sample was exact, while the Hindi sample preserved the meaning but contained several
spelling/word errors.

## Pinned runtime and model

| Item | Pinned value |
|---|---|
| Backend | `faster-whisper==1.2.1` |
| Model | `Systran/faster-whisper-small` |
| Revision | `536b0662742c02347bc0e980a01041f333bce120` |
| License | MIT |
| Local mode | `local_files_only=True`, `HF_HUB_OFFLINE=1` |
| Model size | 486,132,372 bytes across four required files |

Every model asset is size- and SHA-256-verified before the backend is imported. The
receipt is committed at `config/asr_model.json`; weights remain in the ignored
`models/asr/faster-whisper-small/` directory.

Sources:

- [faster-whisper project](https://github.com/SYSTRAN/faster-whisper)
- [Pinned multilingual small model](https://huggingface.co/Systran/faster-whisper-small)

## Measured probes

Both probes ran on CPU with int8 compute from the project `.venv`, with network access
disabled.

| Probe | Duration | Processing | Result |
|---|---:|---:|---|
| Synthetic English wage sentence | 3.80 s | 1.16 s | Exact transcript |
| FLEURS `hi_in` validation sample | 10.62 s | 6.52 s | Hindi detected; meaning retained with transcription errors |

English output:

> My employer has not paid my salary for two months.

Hindi reference:

> इतालवी भाषा में उच्चारण करना तुलनात्मक रूप से आसान है क्योंकि ज़्यादातर शब्दों का उच्चारण वैसे ही किया जाता है जैसे उन्हें लिखा जाता है।

Hindi ASR output:

> इताल्वी पासा में उच्चारन करना तुलनात्मक रुब से असान हैं योंकि जादा तो शब्टो का उच्टार वैसे ही किया जाता है जैसे उने लिखा जाता है

This is adequate as an intake draft, not as confirmed legal facts.

## Evaluation sample provenance

IndicVoices remains gated and cannot be downloaded without the user's Hugging Face
terms acceptance. A bounded FLEURS Hindi validation archive was used as a temporary
CC-BY-4.0 fallback:

- Dataset revision: `70bb2e84b976b7e960aa89f1c648e09c59f894dd`
- Archive SHA-256: `9adbca6d6fc70e40c121910941bcd7c8906eee60b402b6d21b4bd160e20030c7`
- Transcript table SHA-256: `cea87c57a37a0d38ed0afce30e68a35ad7b3945414648430fee09a54ca7b72ba`
- Sample: `14584887621258891555.wav`
- Sample SHA-256: `147ee2f524f05b425f4150fb7c86c8754d4f0660957516c81d9a38134dc261f2`
- [Google FLEURS dataset](https://huggingface.co/datasets/google/fleurs)

The archive and sample are evaluation-only and never enter the production legal index.
