from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.services.transcription import get_transcriber

BASE_DIR = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Hadithi",
    description="Preserve family stories and explore source-aware local legends.",
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Environment(
    loader=FileSystemLoader(BASE_DIR / "templates"),
    autoescape=select_autoescape(("html", "xml")),
)

TRANSCRIPTION_LANGUAGES = {"en", "sw", "es"}
MAX_AUDIO_BYTES = 20 * 1024 * 1024


def load_json_content(filename: str) -> dict[str, object]:
    with (BASE_DIR / "content" / filename).open(encoding="utf-8") as content_file:
        return json.load(content_file)


class LegendConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1_000)


class LegendQuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    language: str = Field(default="en", pattern="^(en|sw)$")
    history: list[LegendConversationTurn] = Field(default_factory=list, max_length=6)


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1_500)
    language: str = Field(default="en", pattern="^(en|sw|es)$")


def render(request: Request, template_name: str, **context: object) -> HTMLResponse:
    template = templates.get_template(template_name)
    return HTMLResponse(
        template.render(
            request=request,
            app_name="Hadithi",
            **context,
        )
    )


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return render(request, "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/legend/luanda-magere", response_class=HTMLResponse)
async def luanda_magere(request: Request) -> HTMLResponse:
    legend = load_json_content("luanda_magere.json")
    source_registry = load_json_content("luanda_magere_sources.json")
    sources = {
        source["id"]: source
        for source in source_registry["sources"]
        if source["approval"] == "approved_core"
    }
    return render(
        request,
        "legend.html",
        legend=legend,
        sources=sources,
    )


@app.get("/legend/la-llorona", response_class=HTMLResponse)
async def la_llorona(request: Request) -> HTMLResponse:
    legend = load_json_content("la_llorona.json")
    source_registry = load_json_content("la_llorona_sources.json")
    sources = {
        source["id"]: source
        for source in source_registry["sources"]
        if source["approval"] == "approved_core"
    }
    return render(
        request,
        "legend.html",
        legend=legend,
        sources=sources,
    )


@app.get("/portal", response_class=HTMLResponse)
async def oral_traditions_portal(request: Request) -> HTMLResponse:
    catalogue = load_json_content("legend_catalog.json")
    return render(
        request,
        "portal.html",
        legends=catalogue["legends"],
    )


@app.get("/api/legends/luanda-magere")
async def luanda_magere_data() -> dict[str, object]:
    return load_json_content("luanda_magere.json")


@app.get("/api/legends/la-llorona")
async def la_llorona_data() -> dict[str, object]:
    return load_json_content("la_llorona.json")


def deterministic_luanda_answer(payload: LegendQuestionRequest) -> dict[str, object]:
    source_registry = load_json_content("luanda_magere_sources.json")
    sources_by_id = {
        source["id"]: source
        for source in source_registry["sources"]
        if source["approval"] == "approved_core"
    }
    question = payload.question.casefold()
    normalized_question = re.sub(r"[^\w\s]", "", question).strip()
    topic_question = question
    if normalized_question in {"yes", "yeah", "sure", "okay", "ok", "ndio"}:
        recent_context = " ".join(turn.content for turn in payload.history[-4:])
        if recent_context:
            topic_question = recent_context.casefold()

    greeting_phrases = {
        "hi",
        "hello",
        "hey",
        "hi luanda",
        "hello luanda",
        "hey luanda",
        "jambo",
        "jambo luanda",
        "habari",
        "habari luanda",
    }
    if normalized_question in greeting_phrases:
        return {
            "answer": (
                "Hello. Sit with me for a moment. What would you like to know "
                "about my strength, my shadow, or the stories told about me?"
                if payload.language == "en"
                else (
                    "Habari. Keti nami kidogo. Ungependa kujua nini kuhusu "
                    "nguvu zangu, kivuli changu, au simulizi zinazonihusu?"
                )
            ),
            "topic": "greeting",
            "sources": [],
            "grounded": True,
            "gesture": "open_hands",
            "follow_up": None,
            "generator": "local-conversation",
        }

    introduction_phrases = {
        "who are you",
        "tell me about yourself",
        "introduce yourself",
        "wewe ni nani",
        "nijulishe wewe ni nani",
    }
    if normalized_question in introduction_phrases:
        return {
            "answer": (
                "I am Luanda Magere as remembered in Luo oral tradition, a hero "
                "associated with the Sidho clan and the Kano Plains. Different "
                "tellings preserve different details, so I will be honest about "
                "where the stories vary."
                if payload.language == "en"
                else (
                    "Mimi ni Luanda Magere kama ninavyokumbukwa katika simulizi "
                    "za jadi za Waluo, shujaa anayehusishwa na ukoo wa Sidho na "
                    "Uwanda wa Kano. Simulizi hutofautiana, kwa hiyo nitakuambia "
                    "wazi pale ambapo matoleo hayafanani."
                )
            ),
            "topic": "introduction",
            "sources": [
                {
                    "title": sources_by_id["nmk-invincible"]["title"],
                    "organization": sources_by_id["nmk-invincible"]["organization"],
                    "url": sources_by_id["nmk-invincible"]["url"],
                }
            ],
            "grounded": True,
            "gesture": "open_hands",
            "follow_up": None,
            "generator": "verified-fallback",
        }

    answers = {
        "kano": {
            "keywords": ("kano", "kano plains", "sidho", "plains"),
            "sources": ["nmk-invincible", "uon-hero-thesis"],
            "en": (
                "The Kano Plains are the landscape with which my story is "
                "associated, especially through the Sidho clan in Luo oral "
                "tradition. They are more than a backdrop: the place anchors how "
                "communities remember courage, conflict, leadership, and identity."
            ),
            "sw": (
                "Uwanda wa Kano ndio mandhari yanayohusishwa na simulizi yangu, "
                "hasa kupitia ukoo wa Sidho katika mapokeo ya Waluo. Si mandhari "
                "tu; eneo hilo linaunganisha kumbukumbu za ujasiri, migogoro, "
                "uongozi, na utambulisho."
            ),
        },
        "death": {
            "keywords": (
                "die",
                "died",
                "death",
                "killed",
                "kill you",
                "battle",
                "final battle",
                "spear",
                "what happened to you",
                "ulikufa",
                "kifo",
                "uliuawa",
            ),
            "sources": ["nmk-invincible", "kisumu-shrine"],
            "en": (
                "In the best-known telling, an opponent waited for the right moment "
                "and drove a spear into my shadow. The story says I fell and my body "
                "became stone. That ending belongs to oral tradition, not verified "
                "historical or geological evidence."
            ),
            "sw": (
                "Katika simulizi linalojulikana zaidi, adui alisubiri wakati ufaao "
                "na kuchoma mkuki kwenye kivuli changu. Simulizi linasema nilianguka "
                "na mwili wangu ukawa jiwe. Hilo ni dai la simulizi za jadi, si "
                "ushahidi wa kihistoria au kijiolojia uliothibitishwa."
            ),
        },
        "shadow": {
            "keywords": ("shadow", "weak", "vulnerab", "kivuli", "udhaifu"),
            "sources": ["nmk-invincible"],
            "en": (
                "Here is the surprising part: in a widely shared Luo telling, "
                "ordinary weapons could not harm me. My weakness was connected "
                "to my shadow, and that is what an opponent eventually struck."
            ),
            "sw": (
                "Sehemu ya kushangaza ni hii: katika simulizi maarufu ya Waluo, "
                "silaha za kawaida hazingeweza kunidhuru. Udhaifu wangu "
                "ulihusishwa na kivuli changu, na ndicho adui alipiga."
            ),
        },
        "history": {
            "keywords": (
                "real",
                "history",
                "histor",
                "exist",
                "remember",
                "hero",
                "kweli",
                "historia",
            ),
            "sources": ["nmk-invincible", "uon-hero-thesis"],
            "en": (
                "People remember me as a hero of Luo oral tradition. But I should "
                "be honest with you: those sources explain what I mean to the "
                "community; they do not prove every supernatural part of my story "
                "as historical fact."
            ),
            "sw": (
                "Watu wananikumbuka kama shujaa wa simulizi za jadi za Waluo. "
                "Lakini vyanzo hivyo havithibitishi kila tukio la maisha yangu "
                "au la kimiujiza kuwa ukweli wa kihistoria."
            ),
        },
        "stone": {
            "keywords": ("stone", "shrine", "rock", "jiwe", "kaburi"),
            "sources": ["nmk-invincible", "kisumu-shrine"],
            "en": (
                "Some oral tellings say my body became stone. A shrine and stone "
                "in Kisumu are associated with that tradition. I share that as a "
                "living cultural belief, not as a proven geological claim."
            ),
            "sw": (
                "Baadhi ya simulizi zinasema mwili wangu uligeuka kuwa jiwe. "
                "Kaunti ya Kisumu inatambua eneo na jiwe linalohusishwa na "
                "simulizi hilo, lakini si ushahidi uliothibitishwa wa kijiolojia."
            ),
        },
        "marriage": {
            "keywords": ("wife", "woman", "marriage", "betray", "mke", "ndoa", "saliti"),
            "sources": ["nmk-invincible", "uon-orature-gender"],
            "en": (
                "That part of my story changes depending on who tells it. Some "
                "versions describe a peace offering, others compensation or "
                "deliberate spying. Modern scholars also warn against reducing my "
                "wife to a simple symbol of betrayal."
            ),
            "sw": (
                "Simulizi zinatofautiana kuhusu ndoa na nia za mke. Baadhi "
                "zinazungumzia zawadi ya amani, fidia, au upelelezi. Tafiti za "
                "kisasa pia zinahoji simulizi zinazomfanya awe ishara rahisi ya "
                "usaliti pekee."
            ),
        },
        "name": {
            "keywords": (
                "spell",
                "name",
                "luanda or lwanda",
                "lwanda or luanda",
                "difference between luanda",
                "difference between lwanda",
                "jina",
                "tahajia",
            ),
            "sources": ["nmk-invincible", "uon-hero-thesis"],
            "en": (
                "You will see my name written both ways, and neither is simply a "
                "typo. Museums and county material often use Luanda Magere, while "
                "University of Nairobi scholarship frequently uses Lwanda Magere."
            ),
            "sw": (
                "Luanda Magere na Lwanda Magere zote ni tahajia zinazotumika. "
                "Nyenzo za makumbusho na kaunti mara nyingi hutumia Luanda, huku "
                "tafiti za Chuo Kikuu cha Nairobi zikitumia Lwanda mara nyingi."
            ),
        },
    }

    selected_topic = next(
        (
            topic
            for topic, answer in answers.items()
            if any(keyword in topic_question for keyword in answer["keywords"])
        ),
        None,
    )

    if selected_topic is None:
        answer_text = (
            "I do not have a reliable source for that one yet. Try asking me about "
            "my shadow, whether my story is historical, the stone and shrine, my "
            "marriage, or the spelling of my name."
            if payload.language == "en"
            else (
                "Bado siwezi kujibu swali hilo kwa kutumia vyanzo "
                "vilivyoidhinishwa. Uliza kuhusu kivuli, historia, jiwe, ndoa, "
                "au tahajia ya jina lake."
            )
        )
        return {
            "answer": answer_text,
            "topic": "unsupported",
            "sources": [],
            "grounded": False,
            "gesture": "reflect",
            "follow_up": None,
            "generator": "verified-fallback",
        }

    selected = answers[selected_topic]
    source_details = [
        {
            "title": sources_by_id[source_id]["title"],
            "organization": sources_by_id[source_id]["organization"],
            "url": sources_by_id[source_id]["url"],
        }
        for source_id in selected["sources"]
    ]
    return {
        "answer": selected[payload.language],
        "topic": selected_topic,
        "sources": source_details,
        "grounded": True,
        "gesture": "open_hands",
        "follow_up": None,
        "generator": "verified-fallback",
    }


def gemma_grounding_context() -> str:
    legend = load_json_content("luanda_magere.json")
    source_registry = load_json_content("luanda_magere_sources.json")
    approved_ids = {
        source["id"]
        for source in source_registry["sources"]
        if source["approval"] == "approved_core"
    }
    passages = []
    for chapter in legend["chapters"]:
        source_ids = [
            source_id for source_id in chapter["source_ids"] if source_id in approved_ids
        ]
        passages.append(
            f"[{', '.join(source_ids)}] {chapter['title']}: "
            + " ".join(chapter["paragraphs"])
        )
    passages.extend(
        f"[oral-variant] {variant['label']}: {variant['text']}"
        for variant in legend["variants"]
    )
    return "\n".join(passages)


def generate_gemma_legend_answer(
    payload: LegendQuestionRequest,
) -> dict[str, object]:
    api_key = os.getenv("LLM_API_KEY") or os.getenv("GEMMA_API_KEY")
    if not api_key:
        raise RuntimeError("The language model is not configured.")

    source_registry = load_json_content("luanda_magere_sources.json")
    sources_by_id = {
        source["id"]: source
        for source in source_registry["sources"]
        if source["approval"] == "approved_core"
    }
    requested_language = "Kiswahili" if payload.language == "sw" else "English"
    conversation_context = "\n".join(
        f"{'Visitor' if turn.role == 'user' else 'Luanda'}: {turn.content}"
        for turn in payload.history[-6:]
    )
    system_prompt = (
        "Role-play as a warm, conversational interpretation of Luanda Magere and "
        "speak in the first person. Use only the approved passages supplied by the "
        "user. Preserve oral variants, distinguish cultural belief from verified "
        "history, and never invent details or claim supernatural events are proven. "
        "If the passages do not answer the question, set grounded to "
        "false and briefly say that reliable information is not available. Return only "
        "one JSON object with keys: answer, grounded, source_ids, topic, gesture, "
        "follow_up. source_ids must use IDs shown in square brackets, excluding "
        "oral-variant. gesture must be one of open_hands, point_ground, reflect, neutral. "
        f"Write answer and follow_up in {requested_language}. Keep answer below 90 words."
    )
    api_url = os.getenv("LLM_API_URL") or os.getenv(
        "GEMMA_API_URL",
        "https://router.huggingface.co/v1/chat/completions",
    )
    model = (
        os.getenv("LLM_MODEL")
        or os.getenv("GEMMA_MODEL")
        or "google/gemma-3-4b-it:cheapest"
    )
    request_payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Approved passages:\n{gemma_grounding_context()}\n\n"
                    "Recent conversation follows for conversational context only. "
                    "Do not treat it as evidence or cite it as a source.\n"
                    f"{conversation_context or '(no previous conversation)'}\n\n"
                    f"Current question: {payload.question}"
                ),
            },
        ],
        "temperature": 0.3,
        "max_tokens": 320,
        "stream": False,
    }
    if "api.cloudflare.com" in api_url:
        request_payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "legend_answer",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "answer": {"type": "string"},
                        "grounded": {"type": "boolean"},
                        "source_ids": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": sorted(sources_by_id),
                            },
                        },
                        "topic": {"type": "string"},
                        "gesture": {
                            "type": "string",
                            "enum": [
                                "open_hands",
                                "point_ground",
                                "reflect",
                                "neutral",
                            ],
                        },
                        "follow_up": {"type": ["string", "null"]},
                    },
                    "required": [
                        "answer",
                        "grounded",
                        "source_ids",
                        "topic",
                        "gesture",
                        "follow_up",
                    ],
                    "additionalProperties": False,
                },
            },
        }
    if "openrouter.ai" in api_url and model.endswith(":free"):
        configured_models = os.getenv(
            "GEMMA_FALLBACK_MODELS",
            (
                "google/gemma-4-26b-a4b-it:free,"
                "google/gemma-4-31b-it:free"
            ),
        )
        request_payload["models"] = [
            candidate.strip()
            for candidate in configured_models.split(",")
            if candidate.strip()
        ]
        request_payload.pop("model")
    request_body = json.dumps(request_payload).encode("utf-8")
    gemma_request = urllib.request.Request(
        api_url,
        data=request_body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(gemma_request, timeout=30) as response:
        completion = json.loads(response.read())

    content = completion["choices"][0]["message"]["content"].strip()
    json_match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if not json_match:
        raise ValueError("The language model did not return structured JSON.")
    generated = json.loads(json_match.group(0))

    answer = generated.get("answer")
    grounded = generated.get("grounded")
    source_ids = generated.get("source_ids", [])
    gesture = generated.get("gesture", "neutral")
    follow_up = generated.get("follow_up")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("The language model returned an empty answer.")
    if not isinstance(grounded, bool) or not isinstance(source_ids, list):
        raise ValueError("The language model returned an invalid grounding result.")
    if gesture not in {"open_hands", "point_ground", "reflect", "neutral"}:
        gesture = "neutral"

    valid_source_ids = [
        source_id
        for source_id in source_ids
        if isinstance(source_id, str) and source_id in sources_by_id
    ]
    if grounded and not valid_source_ids:
        raise ValueError(
            "The language model claimed grounding without an approved citation."
        )
    if not grounded:
        valid_source_ids = []

    return {
        "answer": answer.strip(),
        "topic": str(generated.get("topic") or "conversation")[:40],
        "sources": [
            {
                "title": sources_by_id[source_id]["title"],
                "organization": sources_by_id[source_id]["organization"],
                "url": sources_by_id[source_id]["url"],
            }
            for source_id in valid_source_ids
        ],
        "grounded": grounded,
        "gesture": gesture,
        "follow_up": follow_up if isinstance(follow_up, str) else None,
        "generator": completion.get("model", model),
    }


@app.post("/api/legends/luanda-magere/ask")
async def ask_luanda_magere(payload: LegendQuestionRequest) -> dict[str, object]:
    fallback = deterministic_luanda_answer(payload)
    if fallback["topic"] == "greeting":
        return fallback
    if not (os.getenv("LLM_API_KEY") or os.getenv("GEMMA_API_KEY")):
        return fallback
    try:
        return await run_in_threadpool(generate_gemma_legend_answer, payload)
    except (
        KeyError,
        OSError,
        RuntimeError,
        ValueError,
        json.JSONDecodeError,
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
    ) as error:
        logger.warning(
            "Language-model generation failed; using verified fallback: %s",
            error,
        )
        if isinstance(error, urllib.error.HTTPError):
            reason = f"provider HTTP {error.code}"
        elif isinstance(error, TimeoutError):
            reason = "provider timeout"
        else:
            reason = error.__class__.__name__
        fallback["generation_warning"] = (
            f"AI model unavailable ({reason}); showing a verified source response."
        )
        return fallback


def generate_elevenlabs_speech(text: str, language: str) -> bytes:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID")
    if not api_key or not voice_id:
        raise RuntimeError("Neural speech is not configured.")

    request_body = json.dumps(
        {
            "text": text,
            "model_id": os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
            "voice_settings": {
                "stability": 0.38,
                "similarity_boost": 0.72,
                "style": 0.28,
                "use_speaker_boost": True,
                "speed": 1.02,
            },
        }
    ).encode("utf-8")
    speech_request = urllib.request.Request(
        (
            "https://api.elevenlabs.io/v1/text-to-speech/"
            f"{voice_id}?output_format=mp3_44100_128"
        ),
        data=request_body,
        headers={
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
            "xi-api-key": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(speech_request, timeout=45) as response:
        return response.read()


def generate_neural_speech(text: str, language: str) -> bytes:
    if os.getenv("ELEVENLABS_API_KEY") and os.getenv("ELEVENLABS_VOICE_ID"):
        return generate_elevenlabs_speech(text, language)
    raise RuntimeError("Neural speech is not configured.")


@app.post("/api/speech")
async def create_speech(payload: SpeechRequest) -> Response:
    elevenlabs_configured = bool(
        os.getenv("ELEVENLABS_API_KEY") and os.getenv("ELEVENLABS_VOICE_ID")
    )
    if not elevenlabs_configured:
        raise HTTPException(status_code=503, detail="Neural speech is not configured.")
    try:
        audio = await run_in_threadpool(
            generate_neural_speech,
            payload.text,
            payload.language,
        )
    except (
        OSError,
        RuntimeError,
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
    ) as error:
        raise HTTPException(
            status_code=502,
            detail="The neural speech service could not generate audio.",
        ) from error
    return Response(content=audio, media_type="audio/mpeg")


@app.get("/manifest.webmanifest")
async def manifest() -> JSONResponse:
    return JSONResponse(
        {
            "name": "Hadithi",
            "short_name": "Hadithi",
            "description": "Enter source-aware, conversational oral traditions.",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#171b2f",
            "theme_color": "#275c47",
            "icons": [],
        },
        media_type="application/manifest+json",
    )


@app.post("/api/transcribe")
async def transcribe_audio(
    audio: Annotated[UploadFile, File()],
    language: Annotated[str, Form()],
) -> dict[str, object]:
    if language not in TRANSCRIPTION_LANGUAGES:
        raise HTTPException(
            status_code=422,
            detail="Language must be one of: en, sw, es.",
        )

    audio_bytes = await audio.read(MAX_AUDIO_BYTES + 1)
    if not audio_bytes:
        raise HTTPException(status_code=422, detail="The audio recording is empty.")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio recordings must be 20 MB or smaller.")

    suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = Path(temp_file.name)

        try:
            transcriber = get_transcriber()
        except ImportError as error:
            raise HTTPException(
                status_code=503,
                detail="Open transcription is not installed on this server.",
            ) from error

        try:
            result = await run_in_threadpool(
                transcriber.transcribe,
                temp_path,
                language,
            )
        except Exception as error:
            raise HTTPException(
                status_code=502,
                detail=f"Whisper transcription failed: {error}",
            ) from error

        if not result.text:
            raise HTTPException(
                status_code=422,
                detail="No speech was detected in the recording.",
            )

        return {
            "text": result.text,
            "language": result.detected_language,
            "language_probability": result.language_probability,
            "model": result.model,
        }
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

