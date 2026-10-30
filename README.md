# Hadithi

Hadithi is an immersive, source-aware oral traditions portal. Its launch
experiences are:

- **Luanda Magere — Kenya, Africa**
- **La Llorona — Mexico and Latin America**

Visitors enter a legend's landscape, ask questions by text or microphone, and
see the sources and regional tellings behind each answer.

## Current prototype

- Three.js globe journey and Kano Plains scene
- Licensed, rigged warrior character with moving sunlight and shadow
- Grounded Luanda Magere conversation in English and Kiswahili
- Bounded conversation memory for natural follow-up questions
- La Llorona narrative and source registries
- UNAM, Smithsonian, Guatemalan government, folklore scholarship, historical
  association, and explicitly labelled Wikipedia context
- Strict structured-output and citation validation
- Reviewed deterministic answers when generation fails
- faster-whisper voice-question transcription in English, Kiswahili, and Spanish
- Optional ElevenLabs narration
- Procedural Web Audio ambience
- Installable PWA shell

## Model configuration

Hadithi supports OpenAI-compatible chat-completions providers:

```powershell
$env:LLM_API_KEY = "<private-provider-token>"
$env:LLM_API_URL = "https://api.cloudflare.com/client/v4/accounts/<account-id>/ai/v1/chat/completions"
$env:LLM_MODEL = "@cf/meta/llama-3.2-3b-instruct"
```

The public demo uses Cloudflare Workers AI. A local Gemma model can be used
through Ollama:

```powershell
$env:LLM_API_KEY = "ollama"
$env:LLM_API_URL = "http://127.0.0.1:11434/v1/chat/completions"
$env:LLM_MODEL = "gemma3:4b"
```

Generated source IDs are checked against each legend's approved registry before
citations are displayed. Provider failures fall back to reviewed source
responses.

## Voice

Voice questions use the CPU-friendly faster-whisper `base` model with INT8
inference. Natural narration remains optional:

```powershell
$env:ELEVENLABS_API_KEY = "<private-api-key>"
$env:ELEVENLABS_VOICE_ID = "<voice-id>"
```

Without narration configuration, answers remain available as chat and captions.

## Run locally

```powershell
py -3.13 -m pip install -e ".[dev,ai]"
py -3.13 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

## Deploy to Render

`render.yaml` provisions one Frankfurt web service on the `1c-2g` compute plan.
The build installs Hadithi and pre-downloads the faster-whisper `base` model.

When Render creates the Blueprint, provide:

```text
LLM_API_URL=https://api.cloudflare.com/client/v4/accounts/<account-id>/ai/v1/chat/completions
LLM_API_KEY=<private-workers-ai-token>
```

The Cloudflare token is entered only in the Render dashboard and is never
committed to the repository.

## 3D asset credit

["African Warrior"](https://skfb.ly/68YLs) by
[avenirdesign](https://sketchfab.com/avenirdesign) is licensed under
[Creative Commons Attribution 4.0](http://creativecommons.org/licenses/by/4.0/).

## Test

```powershell
py -3.13 -m pytest
```
