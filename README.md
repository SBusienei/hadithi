# Hadithi

**Immersive, source-grounded conversations with cultural legends.**

[Try Hadithi in production](https://hadithi-zciw.onrender.com/portal) ·
[Read the DEV article](https://dev.to/sbusienei/hadithi-speak-with-your-cultural-legends-eg-la-llorona-and-luanda-magere-50ad) ·
[View the source on GitHub](https://github.com/SBusienei/hadithi)

Hadithi is an open-source storytelling prototype for exploring oral traditions
through interactive landscapes and conversations. Instead of presenting a
legend as one fixed summary, it places visitors inside a visual environment,
lets them speak with a first-person interpretation of the character, and shows
the sources used for factual answers.

The current experience includes:

- **Luanda Magere — Kenya (Africa):** an English/Kiswahili conversation in an
  interactive Kano Plains landscape.
- **La Llorona — Mexico (Latin America):** an English/Spanish conversation in
  a moonlit river environment that preserves differences between regional
  tellings.

Hadithi is an experimental cultural storytelling project, not an authoritative
historical record. Generated wording may vary, while source validation,
citations and reviewed fallbacks constrain factual answers.

## Try it in production

Open the public Render deployment:

### [https://hadithi-zciw.onrender.com/portal](https://hadithi-zciw.onrender.com/portal)

To explore the complete experience:

1. Select **Enter portal**.
2. Choose **Kenya (Africa)** to visit Luanda Magere or
   **Mexico (Latin America)** to visit La Llorona.
3. Ask a question in the chat panel. Try a greeting, ask the character's name,
   or ask about a part of the legend.
4. For Luanda Magere, allow microphone access to test a spoken question.
5. Open the sources shown with a factual answer.
6. Use the landscape controls to enable ambience or interact with the scene.

Useful production links:

- [World portal](https://hadithi-zciw.onrender.com/portal)
- [La Llorona environment](https://hadithi-zciw.onrender.com/portal/la-llorona)
- [Project introduction](https://hadithi-zciw.onrender.com/about)
- [Health check](https://hadithi-zciw.onrender.com/health)

The service runs on Render and may take a short time to wake after inactivity.
Browser audio begins only after a click because of autoplay restrictions.

## Experience preview

![Luanda Magere in the Kano Plains beside the source-grounded conversation panel](docs/assets/luanda-magere-character-conversation.png)

*Luanda Magere in the Kano Plains, with text, microphone and destination
controls.*

![La Llorona at the moonlit river beside the bilingual source-grounded conversation panel](docs/assets/la-llorona-character-conversation.png)

*La Llorona beside the English/Spanish conversation panel. The interface keeps
the research and cultural-review status visible.*

## How it works

1. **The visitor chooses a destination.** Three.js renders a world gateway and
   the legend's environment. User-triggered Web Audio creates the airship,
   plains and river soundscapes without downloaded audio tracks.
2. **The visitor asks a question.** Questions can be typed. Luanda Magere also
   supports recorded voice questions through the browser's `MediaRecorder`
   API.
3. **Speech is transcribed when needed.** The FastAPI backend uses
   faster-whisper with CPU/INT8 inference.
4. **Hadithi selects the relevant source pack.** Luanda Magere and La Llorona
   have separate narrative passages, source registries and editorial
   safeguards.
5. **The language model drafts a structured answer.** The backend supports
   OpenAI-compatible chat-completions providers. The Render configuration uses
   Cloudflare Workers AI.
6. **The backend validates the result.** Returned source IDs must exist in the
   approved registry. Invalid or unavailable model output is replaced with a
   reviewed deterministic response.
7. **The browser displays the answer and citations.** Recent chat provides
   limited conversational context, but it is never treated as evidence.

Simple conversational intents such as greetings, identity questions, thanks
and goodbyes can use reviewed local responses instead of requiring a model
call.

```text
Browser
  |- Three.js environments and animated characters
  |- Text chat and microphone recording
  `- Procedural Web Audio
            |
            v
FastAPI
  |- Legend-specific source selection
  |- faster-whisper transcription
  |- OpenAI-compatible model provider
  |- structured-answer and citation validation
  `- reviewed deterministic fallbacks
```

## Cultural and AI safeguards

- Characters speak in the first person, but the interface does not claim they
  are the historical or supernatural beings themselves.
- Each legend has its own approved source registry.
- Generated citations are checked before being returned to the browser.
- Conversation history is context, not evidence.
- Regional variants are kept visible instead of being combined into one
  universal biography.
- La Llorona remains labelled
  `research_draft_requires_cultural_review`.
- Wikipedia is explicitly identified as community-edited context when used.
- Text chat and captions remain available when speech features are unavailable.

## Technology

- **Backend:** Python, FastAPI, Pydantic and Jinja
- **Frontend:** JavaScript, Three.js, HTML and CSS
- **Generation:** OpenAI-compatible chat-completions API
- **Production model configuration:** Cloudflare Workers AI,
  `@cf/meta/llama-3.2-3b-instruct`
- **Speech recognition:** faster-whisper `base`, CPU/INT8
- **Audio:** browser Web Audio API
- **Deployment:** Render
- **Testing:** pytest
- **Progressive web app:** web manifest and service worker

## Run locally

Hadithi requires Python 3.11 or newer.

```powershell
py -3.13 -m pip install -e ".[dev,ai]"
py -3.13 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000/portal](http://127.0.0.1:8000/portal).

Without model credentials, the application remains usable through reviewed
local conversation and source-grounded fallback responses.

### Configure an LLM provider

Hadithi accepts an OpenAI-compatible chat-completions endpoint:

```powershell
$env:LLM_API_KEY = "<private-provider-token>"
$env:LLM_API_URL = "https://api.cloudflare.com/client/v4/accounts/<account-id>/ai/v1/chat/completions"
$env:LLM_MODEL = "@cf/meta/llama-3.2-3b-instruct"
```

A local Gemma model can also be connected through Ollama:

```powershell
$env:LLM_API_KEY = "ollama"
$env:LLM_API_URL = "http://127.0.0.1:11434/v1/chat/completions"
$env:LLM_MODEL = "gemma3:4b"
```

Never commit provider credentials to the repository.

## Test

```powershell
python -m pytest -q
```

The tests cover routes, source isolation, grounding rules, fallback responses,
conversation behavior, transcription wiring, model attribution and frontend
integration.

## Deployment

[`render.yaml`](render.yaml) defines the Render service, health check, Python
runtime, faster-whisper model download and production start command. The
following secrets must be configured in the Render dashboard:

```text
LLM_API_URL=<OpenAI-compatible chat-completions URL>
LLM_API_KEY=<private provider token>
```

## Project structure

```text
app/
  content/       Legend narratives, source registries and safeguards
  services/      Speech transcription
  static/        Three.js scenes, styles, models and service worker
  templates/     Portal, legend and information pages
  main.py        FastAPI routes and grounded conversation pipeline
docs/            Article drafts and screenshots
scripts/         Reproducible La Llorona model adaptation
tests/           Application and grounding tests
render.yaml      Production deployment configuration
```

## 3D asset credits

### Luanda Magere character

["African Warrior"](https://skfb.ly/68YLs) by
[avenirdesign](https://sketchfab.com/avenirdesign) is licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

### La Llorona character

This work is based on
["ghost_lady_wipppookgtygv"](https://sketchfab.com/3d-models/ghost-lady-wipppookgtygv-7cab2c0c6f1541fb8354dc08b5b868f4)
by Blakosad, licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

The repository includes the displayed licence and model metadata. Uploader
authorship has not been independently verified.

## Read the story behind Hadithi

The DEV article explains the motivation, design decisions, grounding approach
and development process:

### [Hadithi: Speak with your cultural legends — La Llorona and Luanda Magere](https://dev.to/sbusienei/hadithi-speak-with-your-cultural-legends-eg-la-llorona-and-luanda-magere-50ad)

## Next steps

- Complete community cultural review of the La Llorona research draft.
- Evaluate a hosted Gemma endpoint as the primary production model.
- Add optional character speech only after voice quality, pronunciation,
  consent and cultural appropriateness have been reviewed.
- Optimize the 3D assets for slower mobile connections.
- Expand mobile and accessibility testing.
- Add more legends through reviewed, community-informed source packs.
