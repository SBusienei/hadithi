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
    assert "Conversational interpretation from oral tradition" in response.text
    assert "Tap to ask about Luanda" in response.text
    assert "Luanda Magere" in response.text
    assert "La Llorona" in response.text
    assert "Anansi" not in response.text
    assert "Sundiata" not in response.text
    assert "El Cadejo" not in response.text
    assert "African Warrior" in response.text
    assert "avenirdesign" in response.text


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
