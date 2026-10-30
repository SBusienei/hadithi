import json

from fastapi.testclient import TestClient

import app.main as main
from app.main import app
from app.services.transcription import TranscriptionResult

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_home_page_uses_hadithi_brand() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Hadithi" in response.text
    assert "stories that refuse to disappear" in response.text
    assert "Luanda Magere" in response.text
    assert "La Llorona" in response.text


def test_removed_family_story_routes_are_not_available() -> None:
    for path in ("/interview", "/family", "/story/sample", "/api/story/draft"):
        response = client.get(path)
        assert response.status_code in {404, 405}


def test_la_llorona_content_uses_only_registered_core_sources() -> None:
    legend = main.load_json_content("la_llorona.json")
    registry = main.load_json_content("la_llorona_sources.json")
    approved_ids = {
        source["id"]
        for source in registry["sources"]
        if source["approval"] == "approved_core"
    }

    assert legend["chapters"]
    assert approved_ids
    for chapter in legend["chapters"]:
        assert chapter["source_ids"]
        assert set(chapter["source_ids"]).issubset(approved_ids)


def test_portal_lists_only_the_two_hadithi_legends() -> None:
    response = client.get("/portal")

    assert response.status_code == 200
    assert 'id="legendScene"' in response.text
    assert 'id="enterPortal"' in response.text
    assert 'id="voiceQuestion"' in response.text
    assert 'id="voiceInvitation"' in response.text
    assert 'id="toggleKeyboard"' in response.text
    assert 'id="legendChat"' in response.text
    assert "Luanda Magere" in response.text
    assert "Source-grounded character conversation" in response.text
    assert "Tap to ask about Luanda" in response.text
    assert "Luanda Magere" in response.text
    assert "La Llorona" in response.text
    assert "Anansi" not in response.text
    assert "Sundiata" not in response.text
    assert "El Cadejo" not in response.text
    assert "African Warrior" in response.text
    assert "avenirdesign" in response.text
    assert "Choose a destination" in response.text
    assert "Kenya (Africa)" in response.text
    assert "Mexico (Latin America)" in response.text
    assert 'data-legend="luanda-magere"' in response.text
    assert 'data-legend="la-llorona"' in response.text
    assert "preview unavailable" not in response.text


def test_world_destinations_and_airship_audio_are_wired() -> None:
    script = (main.BASE_DIR / "static" / "portal.js").read_text(encoding="utf-8")

    assert "playAirshipJourneySound" in script
    assert "await context.resume()" in script
    assert 'context.state !== "running"' in script
    assert "startKenyaJourney" in script
    assert 'window.location.assign("/portal/la-llorona")' in script
    assert "getJourneyAudioState" in script


def test_la_llorona_environment_is_separate_from_sourced_reading() -> None:
    response = client.get("/portal/la-llorona")

    assert response.status_code == 200
    assert 'id="laLloronaScene"' in response.text
    assert 'id="toggleLloronaAmbience"' in response.text
    assert 'id="lloronaAudioStatus"' in response.text
    assert 'href="/portal"' in response.text
    assert 'href="/legend/la-llorona"' in response.text
    assert "/static/la-llorona-environment.js" in response.text
    assert 'id="lloronaChat"' in response.text
    assert 'id="lloronaLanguage"' in response.text
    assert "research_draft_requires_cultural_review" in response.text
    assert (
        'This work is based on "ghost_lady_wipppookgtygv" by Blakosad, '
        "licensed under CC BY 4.0."
    ) in response.text
    assert "https://skfb.ly/oQvKF" in response.text
    assert "https://creativecommons.org/licenses/by/4.0/" in response.text


def test_la_llorona_ambience_requires_a_click_and_confirms_context_state() -> None:
    script = (main.BASE_DIR / "static" / "la-llorona-environment.js").read_text(
        encoding="utf-8"
    )

    click_handler = script.index('ambienceButton.addEventListener("click"')
    context_creation = script.index("new AudioContextClass")
    assert click_handler > context_creation
    assert "await context.resume()" in script
    assert 'context.state !== "running"' in script
    assert 'setAmbienceUi(true, "Quiet the river"' in script
    assert "riverLowpass.frequency.value = 2400" in script


def test_la_llorona_model_and_animation_are_wired_to_the_anchor() -> None:
    script = (main.BASE_DIR / "static" / "la-llorona-environment.js").read_text(
        encoding="utf-8"
    )
    model_path = main.BASE_DIR / "static" / "models" / "la-llorona-character-study.glb"
    metadata = json.loads(
        (main.BASE_DIR / "static" / "models" / "la-llorona-model.json").read_text(
            encoding="utf-8"
        )
    )

    assert model_path.stat().st_size > 10_000_000
    assert "GLTFLoader" in script
    assert "/static/models/la-llorona-character-study.glb" in script
    assert '"LaLloronaCharacterAnchor"' in script
    assert '"Mournful_Idle"' in script
    assert "characterAnchor.remove(placeholder)" in script
    assert "showModelFallback" in script
    assert metadata["animation"] == "Mournful_Idle"
    assert metadata["attribution"] == (
        'This work is based on "ghost_lady_wipppookgtygv" by Blakosad, '
        "licensed under CC BY 4.0."
    )


def test_la_llorona_chat_wiring_is_text_only_and_bounded() -> None:
    script = (main.BASE_DIR / "static" / "la-llorona-environment.js").read_text(
        encoding="utf-8"
    )

    assert 'fetch("/api/legends/la-llorona/ask"' in script
    assert "conversationHistory.slice(-6)" in script
    assert "conversationHistory.length > 6" in script
    assert 'event.key === "Enter" && !event.shiftKey' in script
    assert "llorona-citations" in script
    assert "/api/speech" not in script
    assert "ElevenLabs" not in script


def test_la_llorona_fallback_answers_in_english_and_spanish() -> None:
    english = client.post(
        "/api/legends/la-llorona/ask",
        json={"question": "Why are you remembered near water?", "language": "en"},
    )
    spanish = client.post(
        "/api/legends/la-llorona/ask",
        json={"question": "¿Qué dice la versión otomí?", "language": "es"},
    )

    assert english.status_code == 200
    assert english.json()["topic"] == "water"
    assert "community-edited" in english.json()["answer"]
    wikipedia = next(
        source
        for source in english.json()["sources"]
        if source["id"] == "wikipedia-la-llorona"
    )
    assert wikipedia["organization"] == "Wikipedia contributors"
    assert "Community-edited" in wikipedia["role"]
    assert spanish.status_code == 200
    assert spanish.json()["topic"] == "otomi"
    assert "versión otomí" in spanish.json()["answer"]
    assert (
        spanish.json()["review_status"]
        == "research_draft_requires_cultural_review"
    )


def test_characters_handle_short_greetings_and_identity_in_first_person() -> None:
    luanda_greeting = client.post(
        "/api/legends/luanda-magere/ask",
        json={"question": "Hi", "language": "en"},
    )
    llorona_greeting = client.post(
        "/api/legends/la-llorona/ask",
        json={"question": "Hi", "language": "en"},
    )
    llorona_identity = client.post(
        "/api/legends/la-llorona/ask",
        json={"question": "What is your name?", "language": "en"},
    )

    assert luanda_greeting.status_code == 200
    assert luanda_greeting.json()["topic"] == "greeting"
    assert llorona_greeting.status_code == 200
    assert llorona_greeting.json()["topic"] == "greeting"
    assert "I am La Llorona" in llorona_greeting.json()["answer"]
    assert llorona_identity.status_code == 200
    assert llorona_identity.json()["topic"] == "identity"
    assert llorona_identity.json()["answer"].startswith("I am La Llorona")


def test_la_llorona_endpoint_rejects_unbounded_or_wrong_language_history() -> None:
    excessive_history = [
        {"role": "user", "content": f"Question {index}"}
        for index in range(7)
    ]
    too_long = client.post(
        "/api/legends/la-llorona/ask",
        json={
            "question": "What changes across regions?",
            "language": "en",
            "history": excessive_history,
        },
    )
    wrong_language = client.post(
        "/api/legends/la-llorona/ask",
        json={"question": "Tell me about water", "language": "sw"},
    )

    assert too_long.status_code == 422
    assert wrong_language.status_code == 422


def test_la_llorona_generation_uses_only_its_registry_and_validates_sources(
    monkeypatch,
) -> None:
    captured_payload: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            return None

        def read(self) -> bytes:
            completion = {
                "model": "test-model",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "answer": "An invalid citation.",
                                    "grounded": True,
                                    "source_ids": ["nmk-invincible"],
                                    "topic": "water",
                                    "gesture": "reflect",
                                    "follow_up": None,
                                }
                            )
                        }
                    }
                ],
            }
            return json.dumps(completion).encode()

    def fake_urlopen(request, timeout):
        captured_payload.update(json.loads(request.data))
        return FakeResponse()

    monkeypatch.setenv("GEMMA_API_KEY", "test-key")
    monkeypatch.setattr(main.urllib.request, "urlopen", fake_urlopen)

    try:
        main.generate_la_llorona_answer(
            main.LaLloronaQuestionRequest(
                question="What does water mean?",
                language="en",
                history=[
                    {
                        "role": "assistant",
                        "content": "This history is context, not evidence.",
                    }
                ],
            )
        )
    except ValueError as error:
        assert "unapproved source" in str(error)
    else:
        raise AssertionError("An unapproved Luanda source ID should be rejected.")

    prompt = captured_payload["messages"][1]["content"]
    assert "Never treat chat history as evidence" in prompt
    assert "nmk-invincible" not in prompt
    assert "Luanda Magere" not in prompt
    assert "research_draft_requires_cultural_review" not in prompt
    assert "Otomí" in prompt


def test_la_llorona_generation_failure_uses_safe_isolated_fallback(
    monkeypatch,
) -> None:
    monkeypatch.setenv("GEMMA_API_KEY", "test-key")

    def fail_generation(payload) -> dict[str, object]:
        raise ValueError("bad source id")

    monkeypatch.setattr(main, "generate_la_llorona_answer", fail_generation)
    response = client.post(
        "/api/legends/la-llorona/ask",
        json={"question": "What happened to the children?", "language": "en"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["generator"] == "verified-fallback"
    assert payload["topic"] == "children"
    assert "generation_warning" in payload
    source_ids = {source["id"] for source in payload["sources"]}
    assert source_ids <= {
        "smithsonian-ay-mis-hijos",
        "unam-tlalocan-variants",
    }


def test_legend_guide_returns_grounded_shadow_answer() -> None:
    response = client.post(
        "/api/legends/luanda-magere/ask",
        json={"question": "Why was his shadow important?", "language": "en"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["grounded"] is True
    assert payload["topic"] == "shadow"
    assert payload["sources"]


def test_legend_guide_uses_configured_gemma(monkeypatch) -> None:
    monkeypatch.setenv("GEMMA_API_KEY", "test-key")
    monkeypatch.setattr(
        main,
        "generate_gemma_legend_answer",
        lambda payload: {
            "answer": "A grounded conversational answer.",
            "topic": "shadow",
            "sources": [{"organization": "National Museums of Kenya"}],
            "grounded": True,
            "gesture": "open_hands",
            "follow_up": "Would you like to hear the ending?",
            "generator": "google/gemma-test",
        },
    )

    response = client.post(
        "/api/legends/luanda-magere/ask",
        json={"question": "Why was his shadow important?", "language": "en"},
    )

    assert response.status_code == 200
    assert response.json()["generator"] == "google/gemma-test"
    assert response.json()["grounded"] is True


def test_cloudflare_legend_request_enables_json_mode(monkeypatch) -> None:
    captured_payload: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            return None

        def read(self) -> bytes:
            completion = {
                "model": "@cf/meta/llama-3.2-3b-instruct",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "answer": "My shadow is central to one telling.",
                                    "grounded": True,
                                    "source_ids": ["nmk-invincible"],
                                    "topic": "shadow",
                                    "gesture": "reflect",
                                    "follow_up": "Would you like to hear more?",
                                }
                            )
                        }
                    }
                ],
            }
            return json.dumps(completion).encode()

    def fake_urlopen(request, timeout):
        captured_payload.update(json.loads(request.data))
        return FakeResponse()

    monkeypatch.setenv("GEMMA_API_KEY", "test-key")
    monkeypatch.setenv(
        "GEMMA_API_URL",
        "https://api.cloudflare.com/client/v4/accounts/account/ai/v1/chat/completions",
    )
    monkeypatch.setenv("GEMMA_MODEL", "@cf/meta/llama-3.2-3b-instruct")
    monkeypatch.setattr(main.urllib.request, "urlopen", fake_urlopen)

    result = main.generate_gemma_legend_answer(
        main.LegendQuestionRequest(
            question="Why was your shadow important?",
            language="en",
        )
    )

    response_format = captured_payload["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert result["generator"] == "@cf/meta/llama-3.2-3b-instruct"
    assert result["grounded"] is True


def test_legend_guide_falls_back_when_gemma_is_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("GEMMA_API_KEY", "test-key")

    def fail_generation(payload) -> dict[str, object]:
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(main, "generate_gemma_legend_answer", fail_generation)

    response = client.post(
        "/api/legends/luanda-magere/ask",
        json={"question": "Why was his shadow important?", "language": "en"},
    )

    assert response.status_code == 200
    assert response.json()["generator"] == "verified-fallback"
    assert "generation_warning" in response.json()


def test_legend_name_does_not_override_the_question_topic() -> None:
    response = client.post(
        "/api/legends/luanda-magere/ask",
        json={"question": "Why is Luanda remembered as a hero?", "language": "en"},
    )

    assert response.status_code == 200
    assert response.json()["topic"] == "history"


def test_legend_guide_handles_a_greeting_conversationally() -> None:
    response = client.post(
        "/api/legends/luanda-magere/ask",
        json={"question": "Hi Luanda", "language": "en"},
    )

    assert response.status_code == 200
    assert response.json()["topic"] == "greeting"
    assert response.json()["answer"].startswith("Hello.")
    assert response.json()["generator"] == "local-conversation"


def test_legend_guide_answers_how_luanda_died() -> None:
    response = client.post(
        "/api/legends/luanda-magere/ask",
        json={"question": "How did you die?", "language": "en"},
    )

    assert response.status_code == 200
    assert response.json()["topic"] == "death"
    assert "spear into my shadow" in response.json()["answer"]


def test_legend_guide_answers_about_the_kano_plains() -> None:
    response = client.post(
        "/api/legends/luanda-magere/ask",
        json={"question": "Tell me about Kano", "language": "en"},
    )

    assert response.status_code == 200
    assert response.json()["topic"] == "kano"
    assert "Kano Plains" in response.json()["answer"]
    assert response.json()["sources"]


def test_legend_guide_uses_recent_context_for_short_confirmation() -> None:
    response = client.post(
        "/api/legends/luanda-magere/ask",
        json={
            "question": "Yeah",
            "language": "en",
            "history": [
                {
                    "role": "assistant",
                    "content": "Would you like to hear more about my shadow?",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["topic"] == "shadow"
    assert response.json()["grounded"] is True


def test_legend_guide_answers_about_the_final_battle() -> None:
    response = client.post(
        "/api/legends/luanda-magere/ask",
        json={
            "question": "What do different tellings say about your final battle?",
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert response.json()["topic"] == "death"


def test_legend_guide_refuses_unsupported_questions() -> None:
    response = client.post(
        "/api/legends/luanda-magere/ask",
        json={"question": "What was his favourite colour?", "language": "en"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["grounded"] is False
    assert payload["sources"] == []


def test_speech_requires_neural_voice_configuration(monkeypatch) -> None:
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)

    response = client.post(
        "/api/speech",
        json={"text": "Welcome to the portal.", "language": "en"},
    )

    assert response.status_code == 503


def test_speech_returns_generated_audio(monkeypatch) -> None:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "test-voice")
    monkeypatch.setattr(
        main,
        "generate_neural_speech",
        lambda text, language: b"fake-mp3",
    )

    response = client.post(
        "/api/speech",
        json={"text": "Welcome to the portal.", "language": "en"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"fake-mp3"


def test_legend_page_attributes_oral_tradition_and_shows_sources() -> None:
    response = client.get("/legend/luanda-magere")

    assert response.status_code == 200
    assert "Hadithi presents this as a living oral tradition" in response.text
    assert "National Museums of Kenya" in response.text
    assert "Tellings differ" in response.text
    assert "optional_retelling" not in response.text


def test_la_llorona_page_shows_mixed_source_types() -> None:
    response = client.get("/legend/la-llorona")

    assert response.status_code == 200
    assert "changing family of oral traditions" in response.text
    assert "Wikipedia contributors" in response.text
    assert "Universidad Nacional Autónoma de México" in response.text


def test_transcribe_accepts_kiswahili(monkeypatch) -> None:
    class FakeTranscriber:
        def transcribe(self, audio_path, language):
            assert audio_path.exists()
            assert language == "sw"
            return TranscriptionResult(
                text="Nilikulia karibu na ziwa.",
                detected_language="sw",
                language_probability=0.98,
                model="test-model",
            )

    monkeypatch.setattr(main, "get_transcriber", lambda: FakeTranscriber())

    response = client.post(
        "/api/transcribe",
        data={"language": "sw"},
        files={"audio": ("answer.webm", b"not-real-audio", "audio/webm")},
    )

    assert response.status_code == 200
    assert response.json()["text"] == "Nilikulia karibu na ziwa."
    assert response.json()["language"] == "sw"


def test_transcribe_rejects_unknown_language() -> None:
    response = client.post(
        "/api/transcribe",
        data={"language": "xx"},
        files={"audio": ("answer.webm", b"not-real-audio", "audio/webm")},
    )

    assert response.status_code == 422
