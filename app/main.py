from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
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
    question: str = Field(min_length=1, max_length=500)
    language: str = Field(default="en", pattern="^(en|sw)$")
    history: list[LegendConversationTurn] = Field(default_factory=list, max_length=6)


class LaLloronaQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    language: str = Field(default="en", pattern="^(en|es)$")
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


@app.get("/about", response_class=HTMLResponse)
async def about(request: Request) -> HTMLResponse:
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


@app.get("/", response_class=HTMLResponse)
@app.get("/portal", response_class=HTMLResponse)
async def oral_traditions_portal(request: Request) -> HTMLResponse:
    catalogue = load_json_content("legend_catalog.json")
    return render(
        request,
        "portal.html",
        legends=catalogue["legends"],
    )


@app.get("/portal/la-llorona", response_class=HTMLResponse)
async def la_llorona_environment(request: Request) -> HTMLResponse:
    source_registry = load_json_content("la_llorona_sources.json")
    return render(
        request,
        "la_llorona_environment.html",
        review_status=source_registry["review_status"],
    )


@app.get("/api/legends/luanda-magere")
async def luanda_magere_data() -> dict[str, object]:
    return load_json_content("luanda_magere.json")


@app.get("/api/legends/la-llorona")
async def la_llorona_data() -> dict[str, object]:
    return load_json_content("la_llorona.json")


def normalize_conversation_question(question: str, greetings: set[str]) -> str:
    normalized = re.sub(r"[^\w\s]", "", question.casefold())
    normalized = " ".join(normalized.split())
    if normalized in greetings:
        return normalized
    for greeting in sorted(greetings, key=len, reverse=True):
        prefix = f"{greeting} "
        if normalized.startswith(prefix):
            return normalized[len(prefix):]
    return normalized


def deterministic_luanda_answer(payload: LegendQuestionRequest) -> dict[str, object]:
    source_registry = load_json_content("luanda_magere_sources.json")
    sources_by_id = {
        source["id"]: source
        for source in source_registry["sources"]
        if source["approval"] == "approved_core"
    }
    question = payload.question.casefold()
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
    normalized_question = normalize_conversation_question(question, greeting_phrases)
    topic_question = question
    if normalized_question in {"yes", "yeah", "sure", "okay", "ok", "ndio"}:
        recent_context = " ".join(turn.content for turn in payload.history[-4:])
        if recent_context:
            topic_question = recent_context.casefold()

    if normalized_question in greeting_phrases:
        return {
            "answer": (
                "Hello. Come sit with me. Want to hear about my shadow, "
                "or is there something else you're curious about?"
                if payload.language == "en"
                else (
                    "Habari! Karibu, keti nami. Unataka kusikia kuhusu kivuli "
                    "changu, au kuna jambo lingine ungependa kujua?"
                )
            ),
            "topic": "greeting",
            "sources": [],
            "grounded": True,
            "gesture": "open_hands",
            "follow_up": None,
            "generator": "local-conversation",
        }

    help_phrases = {
        "help",
        "what can we talk about",
        "what can i ask",
        "what do you know",
        "nisaidie",
        "tunaweza kuzungumza nini",
        "naweza kuuliza nini",
    }
    if normalized_question in help_phrases:
        return {
            "answer": (
                "You can ask me about my strength, my shadow, the Kano Plains, "
                "my battles, the Sidho clan, or how different storytellers remember me."
                if payload.language == "en"
                else (
                    "Unaweza kuniuliza kuhusu nguvu zangu, kivuli changu, Uwanda "
                    "wa Kano, vita vyangu, ukoo wa Sidho, au jinsi wasimulizi "
                    "tofauti wanavyonikumbuka."
                )
            ),
            "topic": "help",
            "sources": [],
            "grounded": True,
            "gesture": "open_hands",
            "follow_up": None,
            "generator": "local-conversation",
        }

    if normalized_question in {"thank you", "thanks", "asante", "asante sana"}:
        return {
            "answer": (
                "You're welcome. Ask me another question whenever you're ready."
                if payload.language == "en"
                else "Karibu! Ukiwa na swali lingine, niulize tu."
            ),
            "topic": "thanks",
            "sources": [],
            "grounded": True,
            "gesture": "open_hands",
            "follow_up": None,
            "generator": "local-conversation",
        }

    if normalized_question in {"goodbye", "bye", "see you", "kwaheri", "tuonane"}:
        return {
            "answer": (
                "Go well, and carry the stories with care."
                if payload.language == "en"
                else "Nenda salama, na uzibebe simulizi kwa uangalifu."
            ),
            "topic": "goodbye",
            "sources": [],
            "grounded": True,
            "gesture": "reflect",
            "follow_up": None,
            "generator": "local-conversation",
        }

    introduction_phrases = {
        "who are you",
        "what is your name",
        "whats your name",
        "your name",
        "tell me about yourself",
        "introduce yourself",
        "wewe ni nani",
        "jina lako ni nani",
        "unaitwa nani",
        "nijulishe wewe ni nani",
    }
    if normalized_question in introduction_phrases:
        return {
            "answer": (
                "I'm Luanda Magere, a hero remembered in Luo oral tradition "
                "and linked to the Sidho clan and the Kano Plains. Not everyone "
                "tells my story the same way, so I'll point out where it changes."
                if payload.language == "en"
                else (
                    "Mimi ni Luanda Magere, shujaa wa simulizi za Waluo "
                    "anayehusishwa na ukoo wa Sidho na Uwanda wa Kano. Watu "
                    "hawasimulii hadithi yangu kwa namna moja, kwa hiyo "
                    "nitakuambia pale matoleo yanapotofautiana."
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
                "My story is tied to the Kano Plains, especially through the "
                "Sidho clan in Luo oral tradition. The place matters: it's part "
                "of how people remember courage, conflict, and who they are."
            ),
            "sw": (
                "Hadithi yangu inahusishwa na Uwanda wa Kano, hasa kupitia "
                "ukoo wa Sidho katika mapokeo ya Waluo. Eneo hilo ni muhimu: "
                "watu hulihusisha na ujasiri, migogoro, na utambulisho wao."
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


def legend_grounding_context(
    legend_filename: str,
    source_registry_filename: str,
) -> str:
    legend = load_json_content(legend_filename)
    source_registry = load_json_content(source_registry_filename)
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
    if "editorial_position" in source_registry:
        passages.append(f"[editorial-policy] {source_registry['editorial_position']}")
    passages.extend(
        f"[variant-to-preserve] {variant}"
        for variant in source_registry.get("variants_to_preserve", [])
    )
    passages.extend(
        f"[reuse-rule] {rule}"
        for rule in source_registry.get("reuse_rules", [])
    )
    return "\n".join(passages)


def gemma_grounding_context() -> str:
    return legend_grounding_context(
        "luanda_magere.json",
        "luanda_magere_sources.json",
    )


@dataclass(frozen=True)
class LegendGenerationConfig:
    character_name: str
    legend_filename: str
    source_registry_filename: str
    language_names: dict[str, str]
    system_instructions: str


LUANDA_GENERATION_CONFIG = LegendGenerationConfig(
    character_name="Luanda",
    legend_filename="luanda_magere.json",
    source_registry_filename="luanda_magere_sources.json",
    language_names={"en": "English", "sw": "Kiswahili"},
    system_instructions=(
        "Speak as Luanda Magere in a warm first-person character voice. Preserve "
        "oral variants, distinguish cultural "
        "belief from verified history, and never invent details or claim "
        "supernatural events are proven."
    ),
)

LA_LLORONA_GENERATION_CONFIG = LegendGenerationConfig(
    character_name="La Llorona",
    legend_filename="la_llorona.json",
    source_registry_filename="la_llorona_sources.json",
    language_names={"en": "English", "es": "Spanish"},
    system_instructions=(
        "Speak as La Llorona in a careful, compassionate first-person character "
        "voice. Make clear that there is no single universal biography. Preserve "
        "Mexican, Otomí, Guatemalan, U.S. Latino, and Chicano variants without "
        "flattening them together. Attribute origin theories and supernatural "
        "claims, avoid generic-horror or jump-scare framing, and never present "
        "infanticide, suicide, a named partner, or one colonial identity as "
        "universal fact. When citing Wikipedia, call it a community-edited overview."
    ),
)


def approved_sources(source_registry_filename: str) -> dict[str, dict[str, object]]:
    source_registry = load_json_content(source_registry_filename)
    return {
        source["id"]: source
        for source in source_registry["sources"]
        if source["approval"] == "approved_core"
    }


def source_details(
    source_ids: list[str],
    sources_by_id: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    return [
        {
            "id": source_id,
            "title": sources_by_id[source_id]["title"],
            "organization": sources_by_id[source_id]["organization"],
            "url": sources_by_id[source_id]["url"],
            "role": sources_by_id[source_id]["role"],
        }
        for source_id in source_ids
    ]


def generate_structured_legend_answer(
    payload: LegendQuestionRequest | LaLloronaQuestionRequest,
    config: LegendGenerationConfig,
) -> dict[str, object]:
    api_key = os.getenv("LLM_API_KEY") or os.getenv("GEMMA_API_KEY")
    if not api_key:
        raise RuntimeError("The language model is not configured.")

    sources_by_id = approved_sources(config.source_registry_filename)
    requested_language = config.language_names[payload.language]
    conversation_context = "\n".join(
        f"{'Visitor' if turn.role == 'user' else config.character_name}: {turn.content}"
        for turn in payload.history[-6:]
    )
    system_prompt = (
        f"{config.system_instructions} "
        "Talk naturally to one visitor, not like a textbook or museum label. "
        "Answer their question directly in plain, everyday language, usually "
        "in two to four short sentences. Use contractions where natural in "
        "the requested language. Keep the tone friendly and respectful, not "
        "slang-heavy, jokey, or theatrical. Explain uncertainty simply, for "
        "example 'In one telling...' rather than repeating a policy lecture. "
        "Do not invent memories, feelings, dialogue, or cultural details to "
        "sound more casual. Avoid repeating your introduction or listing all "
        "the topics you can discuss on every turn. Set follow_up to null "
        "unless one short, relevant question would genuinely help the conversation. "
        "Use only the approved passages supplied by the user as evidence. "
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
                    "Approved passages and editorial safeguards:\n"
                    f"{legend_grounding_context(config.legend_filename, config.source_registry_filename)}\n\n"
                    "Recent conversation follows for conversational context only. "
                    "Never treat chat history as evidence and never cite it as a source.\n"
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

    required_keys = {
        "answer",
        "grounded",
        "source_ids",
        "topic",
        "gesture",
        "follow_up",
    }
    if not isinstance(generated, dict) or set(generated) != required_keys:
        raise ValueError("The language model returned an invalid response shape.")
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

    if any(
        not isinstance(source_id, str) or source_id not in sources_by_id
        for source_id in source_ids
    ):
        raise ValueError("The language model cited an unapproved source.")
    valid_source_ids = list(dict.fromkeys(source_ids))
    if grounded and not valid_source_ids:
        raise ValueError(
            "The language model claimed grounding without an approved citation."
        )
    if not grounded and valid_source_ids:
        raise ValueError("An ungrounded response cannot include citations.")

    return {
        "answer": answer.strip(),
        "topic": str(generated.get("topic") or "conversation")[:40],
        "sources": source_details(valid_source_ids, sources_by_id),
        "grounded": grounded,
        "gesture": gesture,
        "follow_up": follow_up if isinstance(follow_up, str) else None,
        "generator": completion.get("model", model),
    }


def generate_gemma_legend_answer(
    payload: LegendQuestionRequest,
) -> dict[str, object]:
    return generate_structured_legend_answer(payload, LUANDA_GENERATION_CONFIG)


def generate_la_llorona_answer(
    payload: LaLloronaQuestionRequest,
) -> dict[str, object]:
    result = generate_structured_legend_answer(
        payload,
        LA_LLORONA_GENERATION_CONFIG,
    )
    result["review_status"] = load_json_content("la_llorona_sources.json")[
        "review_status"
    ]
    return result


def deterministic_la_llorona_answer(
    payload: LaLloronaQuestionRequest,
) -> dict[str, object]:
    registry = load_json_content("la_llorona_sources.json")
    sources_by_id = approved_sources("la_llorona_sources.json")
    question = payload.question.casefold()
    base = {
        "gesture": "reflect",
        "follow_up": None,
        "review_status": registry["review_status"],
    }
    greeting_phrases = {
        "hi",
        "hello",
        "hey",
        "hi la llorona",
        "hello la llorona",
        "hey la llorona",
        "hola",
        "hola la llorona",
        "hola llorona",
        "buenas",
    }
    normalized_question = normalize_conversation_question(question, greeting_phrases)
    topic_question = question
    if normalized_question in {"yes", "yeah", "sure", "okay", "ok", "sí", "si"}:
        recent_context = " ".join(turn.content for turn in payload.history[-4:])
        if recent_context:
            topic_question = recent_context.casefold()

    if normalized_question in greeting_phrases:
        return {
            **base,
            "answer": (
                "Hello. I am La Llorona, the Weeping Woman. What are you curious "
                "about: the river, the children, or a particular telling?"
                if payload.language == "en"
                else (
                    "Hola. Soy La Llorona, la Mujer que Llora. ¿Qué te da "
                    "curiosidad: el río, los niños o alguna versión de mi historia?"
                )
            ),
            "topic": "greeting",
            "sources": [],
            "grounded": True,
            "generator": "local-conversation",
        }

    identity_phrases = {
        "who are you",
        "what is your name",
        "whats your name",
        "your name",
        "tell me about yourself",
        "introduce yourself",
        "quién eres",
        "quien eres",
        "cómo te llamas",
        "como te llamas",
        "cuál es tu nombre",
        "cual es tu nombre",
    }
    if normalized_question in identity_phrases:
        return {
            **base,
            "answer": (
                "I am La Llorona, the Weeping Woman. People tell my story "
                "differently from place to place, so I'll let you know "
                "which telling we're talking about."
                if payload.language == "en"
                else (
                    "Soy La Llorona, la Mujer que Llora. Mi historia cambia "
                    "de un lugar a otro, así que te diré de qué versión "
                    "estamos hablando."
                )
            ),
            "topic": "identity",
            "sources": [],
            "grounded": True,
            "generator": "local-conversation",
        }

    help_phrases = {
        "help",
        "what can we talk about",
        "what can i ask",
        "what do you know",
        "ayuda",
        "de qué podemos hablar",
        "de que podemos hablar",
        "qué puedo preguntar",
        "que puedo preguntar",
    }
    if normalized_question in help_phrases:
        return {
            **base,
            "answer": (
                "Ask me about the river, the children, the Otomí telling in which "
                "I bring water, Guatemala, Chicano retellings, or the different "
                "ideas about where my story began."
                if payload.language == "en"
                else (
                    "Pregúntame por el río, los niños, la versión otomí en la que "
                    "llevo agua, Guatemala, las reinterpretaciones chicanas o las "
                    "distintas ideas sobre el origen de mi historia."
                )
            ),
            "topic": "help",
            "sources": [],
            "grounded": True,
            "generator": "local-conversation",
        }

    if normalized_question in {
        "thank you",
        "thanks",
        "gracias",
        "muchas gracias",
    }:
        return {
            **base,
            "answer": (
                "You're welcome. We can keep talking if you'd like."
                if payload.language == "en"
                else "De nada. Podemos seguir hablando si quieres."
            ),
            "topic": "thanks",
            "sources": [],
            "grounded": True,
            "generator": "local-conversation",
        }

    if normalized_question in {
        "goodbye",
        "bye",
        "see you",
        "adiós",
        "adios",
        "hasta luego",
    }:
        return {
            **base,
            "answer": (
                "Go carefully. Remember that every river carries a different telling."
                if payload.language == "en"
                else "Ve con cuidado. Recuerda que cada río lleva una historia distinta."
            ),
            "topic": "goodbye",
            "sources": [],
            "grounded": True,
            "generator": "local-conversation",
        }

    answers = {
        "variants": {
            "keywords": (
                "one true",
                "true version",
                "real version",
                "same story",
                "single story",
                "una versión",
                "version verdadera",
                "historia verdadera",
                "una sola",
            ),
            "sources": [
                "unam-tlalocan-variants",
                "smithsonian-ay-mis-hijos",
                "jfr-perez-review",
            ],
            "en": (
                "There isn't just one true version of my story. Mexican, "
                "Guatemalan, U.S. Latino, and Chicano tellings don't all say "
                "the same thing. I'll tell you which version a detail comes "
                "from rather than mix them together."
            ),
            "es": (
                "No hay una sola versión verdadera de mi historia. Las "
                "versiones mexicanas, guatemaltecas, latinas de Estados Unidos "
                "y chicanas no cuentan lo mismo. Te diré de dónde viene cada "
                "detalle en lugar de mezclarlas."
            ),
        },
        "water": {
            "keywords": (
                "water",
                "river",
                "lake",
                "canal",
                "cry",
                "weeping",
                "agua",
                "río",
                "rio",
                "lago",
                "canal",
                "llanto",
                "llorar",
            ),
            "sources": [
                "unam-memory-water",
                "smithsonian-ay-mis-hijos",
                "wikipedia-la-llorona",
            ],
            "en": (
                "My cry is often placed near a river, canal, or lake. But water "
                "doesn't mean the same thing in every telling: it can be about "
                "grief, a warning, or even care. UNAM explores those meanings; "
                "Wikipedia is a community-edited overview, not the final word."
            ),
            "es": (
                "Mi llanto suele aparecer junto a un río, canal o lago. Pero el "
                "agua no significa lo mismo en cada versión: puede hablar del "
                "duelo, de una advertencia o incluso del cuidado. La UNAM "
                "explora esos sentidos; Wikipedia es un resumen editado por "
                "la comunidad, no la última palabra."
            ),
        },
        "children": {
            "keywords": (
                "children",
                "child",
                "drown",
                "kids",
                "hijos",
                "hijas",
                "niños",
                "ninos",
                "ahog",
            ),
            "sources": [
                "smithsonian-ay-mis-hijos",
                "unam-tlalocan-variants",
            ],
            "en": (
                "That depends on the telling. Some modern versions say I "
                "deliberately drowned my children; others say they were lost "
                "or disappeared, or describe a different encounter. I wouldn't "
                "give you one version's motive or punishment as if everyone "
                "told it that way."
            ),
            "es": (
                "Depende de la versión. Algunas versiones modernas dicen que "
                "ahogué deliberadamente a mis hijos; otras cuentan que se "
                "perdieron, desaparecieron o hubo un encuentro distinto. "
                "El motivo y el castigo de una versión no valen para todas."
            ),
        },
        "otomi": {
            "keywords": (
                "otomí",
                "otomi",
                "generosity",
                "brought water",
                "gave water",
                "generosidad",
                "trajo agua",
                "dio agua",
                "mezquital",
            ),
            "sources": ["unam-memory-water"],
            "en": (
                "Here's a different side of my story. In an Otomí telling from "
                "the Valle del Mezquital that UNAM records, young shepherds "
                "share their food with me, and I give them water in return. "
                "That version is about generosity and care when water is scarce, "
                "not just fear."
            ),
            "es": (
                "Esta historia muestra otro lado de mí. En una versión otomí "
                "del Valle del Mezquital que recoge la UNAM, unos niños "
                "pastores comparten su comida conmigo y yo les doy agua. "
                "Ahí se habla de generosidad y cuidado cuando el agua escasea, "
                "no solo de miedo."
            ),
        },
        "guatemala": {
            "keywords": ("guatemala", "semetabaj", "sololá", "solola"),
            "sources": ["guatemala-semetabaj"],
            "en": (
                "In San Andrés Semetabaj, elders and young people gathered to "
                "share local stories about me, as Guatemala's Ministry of "
                "Culture records. Those are living Guatemalan traditions, "
                "not just copies of a Mexican version."
            ),
            "es": (
                "En San Andrés Semetabaj, personas mayores y jóvenes se "
                "reunieron para compartir historias locales sobre mí, según "
                "el Ministerio de Cultura de Guatemala. Son tradiciones "
                "guatemaltecas vivas, no simples copias de una versión mexicana."
            ),
        },
        "chicano": {
            "keywords": (
                "chicano",
                "chicana",
                "latino",
                "united states",
                "u.s.",
                "resistance",
                "resistencia",
                "estados unidos",
            ),
            "sources": [
                "smithsonian-ay-mis-hijos",
                "jfr-perez-review",
            ],
            "en": (
                "Writers and artists in U.S. Latino and Chicano communities "
                "sometimes tell my story in a new way. It can move between "
                "English, Spanish, Spanglish, and Indigenous-language contexts. "
                "Some explore grief or migration; others use my story to "
                "question gender roles or talk about resistance and the environment."
            ),
            "es": (
                "Escritores y artistas de comunidades latinas y chicanas en "
                "Estados Unidos a veces cuentan mi historia de otra manera. "
                "Usan inglés, español, spanglish y contextos de lenguas "
                "indígenas para explorar el duelo, la migración, el género, "
                "la resistencia o la memoria del entorno."
            ),
        },
        "origins": {
            "keywords": (
                "origin",
                "aztec",
                "pre-hispanic",
                "prehispanic",
                "colonial",
                "malinche",
                "cihuacoatl",
                "tonantzin",
                "origen",
                "prehispán",
                "prehispan",
                "colonial",
            ),
            "sources": [
                "unam-memory-water",
                "jfr-perez-review",
                "wikipedia-la-llorona",
            ],
            "en": (
                "There's no proven single starting point for my story. People "
                "have linked me to Cihuacoatl, Tonantzin, La Malinche, colonial "
                "guilt, or a historical woman, but those are interpretations. "
                "UNAM discusses some of those connections; Wikipedia offers "
                "a community-edited overview of other theories."
            ),
            "es": (
                "No hay un único origen comprobado para mi historia. Hay "
                "quienes me relacionan con Cihuacóatl, Tonantzin, La Malinche, "
                "la culpa colonial o una mujer histórica, pero son "
                "interpretaciones. La UNAM analiza algunas conexiones; "
                "Wikipedia ofrece un resumen de otras teorías editado "
                "por la comunidad."
            ),
        },
        "fear": {
            "keywords": (
                "scary",
                "fright",
                "horror",
                "monster",
                "warning",
                "miedo",
                "terror",
                "monstruo",
                "advertencia",
            ),
            "sources": [
                "unam-memory-water",
                "smithsonian-ay-mis-hijos",
                "jfr-perez-review",
            ],
            "en": (
                "Some versions are meant to frighten people, or warn children "
                "away from dangerous water. But that's not my whole story. "
                "Other tellings are about grief, generosity, migration, or "
                "resistance, so calling me just a monster misses a lot."
            ),
            "es": (
                "Algunas versiones buscan dar miedo o alejar a los niños "
                "del agua peligrosa. Pero mi historia no se queda ahí. "
                "Otras hablan del duelo, la generosidad, la migración o "
                "la resistencia; llamarme solo monstruo deja mucho fuera."
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
        return {
            **base,
            "answer": (
                "I'm not sure about that, and I don't have a reliable source "
                "to answer it. We could talk about the river or a regional "
                "telling instead."
                if payload.language == "en"
                else (
                    "No estoy segura y no tengo una fuente fiable para "
                    "responderte. Podemos hablar del río o de alguna "
                    "versión regional."
                )
            ),
            "topic": "unsupported",
            "sources": [],
            "grounded": False,
            "generator": "verified-fallback",
        }

    selected = answers[selected_topic]
    return {
        **base,
        "answer": selected[payload.language],
        "topic": selected_topic,
        "sources": source_details(selected["sources"], sources_by_id),
        "grounded": True,
        "generator": "verified-fallback",
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


@app.post("/api/legends/la-llorona/ask")
async def ask_la_llorona(
    payload: LaLloronaQuestionRequest,
) -> dict[str, object]:
    fallback = deterministic_la_llorona_answer(payload)
    if fallback["topic"] == "greeting":
        return fallback
    if not (os.getenv("LLM_API_KEY") or os.getenv("GEMMA_API_KEY")):
        return fallback
    try:
        return await run_in_threadpool(generate_la_llorona_answer, payload)
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
            "La Llorona generation failed; using verified fallback: %s",
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
