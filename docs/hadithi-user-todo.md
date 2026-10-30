# Hadithi: Your Python and AI To-Do List

## Goal

Own the Python AI Story Engine that converts a storyteller-approved transcript
into a validated, grounded family-story structure. Do not train a model for the
hackathon MVP.

## Definition of done

Given a title, storyteller name, language, and approved transcript, your service
returns valid structured data containing:

- the storyteller's unchanged title;
- a concise summary;
- two to four chapters;
- exact quotations copied from the transcript;
- people and places found in the transcript;
- an optional timeline;
- useful follow-up questions;
- no invented people, places, dates, or quotations.

## Tonight: foundations (60-90 minutes)

### 1. Learn the existing Python flow

Read:

- `app/main.py`
- `app/services/transcription.py`
- `tests/test_app.py`

Run:

```powershell
py -3.13 -m pytest -q
py -3.13 -m uvicorn app.main:app --reload
```

Open:

- `http://127.0.0.1:8000/docs`

Resource:

- FastAPI tutorial: https://fastapi.tiangolo.com/tutorial/

Focus on request bodies, response models, dependencies, errors, and testing.

### 2. Define Pydantic story models

Create:

```text
app/models/__init__.py
app/models/story.py
tests/test_story_models.py
```

Suggested models:

```python
class Chapter(BaseModel):
    heading: str
    text: str


class TimelineEvent(BaseModel):
    date_or_period: str | None
    description: str


class FamilyStory(BaseModel):
    title: str
    summary: str
    chapters: list[Chapter]
    quotations: list[str]
    people: list[str]
    places: list[str]
    timeline: list[TimelineEvent]
    follow_up_questions: list[str]
```

Add sensible length constraints and tests for invalid data.

Resources:

- Pydantic models: https://pydantic.dev/docs/validation/latest/concepts/models/
- Pydantic fields: https://docs.pydantic.dev/latest/concepts/fields/

## Tomorrow morning: Gemma integration (2-3 hours)

### 3. Run Gemma from Python

Recommended MVP route: use Ollama locally so model operations stay simple.

Resources:

- Gemma documentation: https://ai.google.dev/gemma/docs
- Gemma getting started: https://ai.google.dev/gemma/docs/get_started
- Ollama API: https://docs.ollama.com/api
- Ollama Python library: https://github.com/ollama/ollama-python

Optional deeper route:

- Hugging Face Gemma documentation:
  https://huggingface.co/docs/transformers/model_doc/gemma3

Create:

```text
app/services/gemma.py
```

Expose one small interface:

```python
class GemmaClient:
    def generate(self, prompt: str) -> str:
        ...
```

Keep the model name and endpoint configurable through environment variables.

### 4. Produce structured output

Create:

```text
app/services/story_structurer.py
app/prompts/family_story.py
tests/test_story_structurer.py
```

The prompt must say:

- use only facts in the transcript;
- preserve the supplied title exactly;
- copy quotations exactly;
- use `null` or an empty list when information is absent;
- never infer dates, relationships, names, or locations;
- return JSON matching the provided schema.

Useful optional library:

- Instructor structured outputs: https://python.useinstructor.com/

Start with plain JSON plus `FamilyStory.model_validate_json()`. Add Instructor
only if plain validation and retry logic becomes cumbersome.

## Tomorrow midday: grounding and evaluation (90 minutes)

### 5. Add deterministic grounding checks

Implement Python checks after model generation:

- every quotation must be a substring of the transcript;
- every extracted person and place must appear in the transcript;
- the returned title must equal the user title;
- chapters must not be empty;
- invalid output must raise a visible error rather than silently falling back.

### 6. Build a five-example evaluation set

Create:

```text
tests/fixtures/story_cases.json
scripts/evaluate_story_generation.py
```

Include:

1. English childhood story
2. Kiswahili story
3. English-Kiswahili code-switched story
4. Spanish or French story
5. Story with names, places, and no dates

Record:

- schema validity;
- exact-title preservation;
- quotation accuracy;
- unsupported people, places, and dates;
- latency;
- model name.

For later transcription evaluation:

- JiWER documentation: https://jitsi.github.io/jiwer/

For later Luanda Magere RAG evaluation:

- Hugging Face RAG evaluation cookbook:
  https://huggingface.co/learn/cookbook/en/rag_evaluation

## Optional video

- freeCodeCamp Python API/FastAPI course:
  https://www.youtube.com/watch?v=0sOvCWFmrtA

Do not watch the entire course before coding. Use chapters only when the
corresponding FastAPI concept blocks you.

## Handoff to Copilot

When your work is ready, provide:

- the files changed;
- the Gemma model and runtime used;
- the command needed to run it;
- evaluation results for the five cases;
- known failures or hallucination patterns.

Copilot will integrate the story engine into the mobile flow, add persistence
and tracing, deploy it, and incorporate the results into the submission.

