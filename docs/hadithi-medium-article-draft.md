# Hadithi: When Legends Speak Back

> Draft for the Hacktoberfest Open-Source AI Challenge: Ghost in the Machine

## The idea

In my community, stories have always been passed through oral narratives.
People would sit together and listen to stories of old, carried from one
generation to another.

The way we gather is changing, but the need to remember where we come from has
not changed.

Hadithi is an immersive portal into oral tradition. Instead of reading a short
summary of a legend, visitors enter its landscape, meet a conversational
interpretation of its central character, and ask questions using text or their
voice.

The first complete experience is **Luanda Magere**, remembered in Luo oral
tradition and associated with the Kano Plains in Kenya. The second destination
will be **La Llorona**, approached through the different tellings found across
Mexico and Latin America.

The "ghost in the machine" is not a claim that these characters are alive or
historically verified in every detail. It is the trace of a story that survives
because people continue to tell, question, reinterpret, and remember it.

## What I built

Hadithi currently includes:

- a full-screen Three.js journey from a cosmic portal to the Kano Plains;
- a licensed 3D warrior representing Luanda Magere;
- a moving sun and physically changing shadow connected to the legend;
- a conversational interface beside the character;
- text questions submitted with a button or the Enter key;
- microphone recording and open-model transcription with faster-whisper;
- English and Kiswahili response modes;
- support for mixed-language questions;
- source-grounded generation through Llama 3.2 on Cloudflare Workers AI;
- strict structured-output and citation validation;
- reviewed deterministic answers when the model or provider fails;
- visible provider and fallback status instead of hidden errors;
- links to the institutional and academic sources behind each answer;
- a lightweight procedural ambient soundscape built with the Web Audio API.

Hadithi labels Luanda as a **conversational interpretation from oral
tradition**. It does not pretend that the 3D character is the historical person
or that every supernatural element is established fact.

## Entering the Kano Plains

The experience begins with a globe floating in a dark portal. The camera moves
toward Kenya before revealing a stylised Kano Plains landscape.

Luanda faces the visitor. The interface invites questions about his strength,
his shadow, the plains, his marriage, the stone and shrine associated with the
story, and the different ways his name and final battle are remembered.

The visual environment is part of the storytelling. Moving the sun changes the
direction of Luanda's shadow, turning an important part of the oral narrative
into something visitors can see and explore.

## A conversation, not a generated biography

Hadithi does not give the language model permission to answer from everything
it may have encountered during training.

For every question, the server sends:

1. the visitor's question;
2. a carefully selected set of approved passages;
3. instructions to preserve differences between tellings;
4. a strict JSON schema for the answer, citations, topic and character gesture.

The returned source IDs are checked against an approved registry before the
answer is shown. A generated answer cannot display an invented citation.

If the model returns invalid JSON, cites an unapproved source, claims grounding
without evidence, times out, or becomes unavailable, Hadithi switches to a
reviewed source response. The interface tells the visitor that this happened.

That failure path is part of the product, not an error I tried to hide.

## Source-aware oral tradition

The Luanda Magere source pack currently includes material associated with:

- National Museums of Kenya and Google Arts & Culture;
- Kisumu County's recognition of the Luanda Magere shrine;
- University of Nairobi scholarship on heroic traditions;
- University of Nairobi research on orature, heroism and gender.

The experience distinguishes:

- oral tradition from verified history;
- `Luanda` and `Lwanda` spelling variants;
- differences in how opponents are named;
- different explanations for the marriage;
- supernatural claims from historical or geological evidence;
- heroic interpretations from critical readings of gender and betrayal.

This matters because AI can easily flatten several living tellings into one
confident but misleading biography.

## Multilingual and voice interaction

Visitors can type a question or record it through the microphone. Audio is sent
to the FastAPI server and transcribed with the open faster-whisper `base` model
using CPU INT8 inference.

During local measurement:

- the first transcription request completed in approximately 8.54 seconds;
- a warm request completed in approximately 4.67 seconds.

The interface currently offers English and Kiswahili response modes. Llama also
understood a mixed-language question such as:

> "Yeah, alikuwa ametoka wapi?"

When English was selected, it understood the Kiswahili portion and answered in
English. Selecting Kiswahili instructs the character to respond in Kiswahili.

The microphone provides voice input. Natural spoken narration is intentionally
disabled until a reliable neural text-to-speech provider is available. I chose
silence and readable chat over quietly falling back to an old robotic browser
voice.

## Architecture

```text
Browser
  |- Three.js: globe, Kano Plains, character and shadow
  |- MediaRecorder: voice questions
  |- Web Audio API: procedural ambience
  `- Chat interface: answers, citations and provider status

FastAPI
  |- approved cultural-source passages
  |- deterministic reviewed responses
  |- strict generation and citation validation
  |- faster-whisper transcription
  `- provider failure handling

Cloudflare Workers AI
  `- @cf/meta/llama-3.2-3b-instruct

Future destination
  `- La Llorona source pack, environment and licensed character
```

## Why Llama and Cloudflare Workers AI

The public experience currently uses the open Llama 3.2 3B Instruct model
through Cloudflare's OpenAI-compatible Workers AI endpoint.

Cloudflare provides a recurring free daily allocation, allowing the demo to run
without loading model weights on the visitor's phone or turning my development
laptop into the production inference server.

The integration is provider-configurable. Hadithi can use another compatible
host or a locally served open model without changing the cultural grounding and
validation rules.

## What went wrong along the way

The working architecture came from several provider failures:

- Hugging Face Inference Providers reached Gemma but returned HTTP 402 because
  credits were required;
- free OpenRouter Gemma providers returned HTTP 429 when capacity was
  unavailable;
- Cloudflare authenticated correctly, but the selected Gemma model was not
  available to the account;
- Llama initially returned conversational prose instead of the required JSON;
- the public Chatterbox narration service returned upstream failures;
- browser speech fallback sounded robotic and weakened the experience.

I switched the Cloudflare model to Llama 3.2 and enabled JSON-schema output. I
also kept provider failures visible and preserved deterministic answers for
core questions.

This made Hadithi more reliable and made the engineering story more honest.

## Responsible design

- The character is clearly labelled as an interpretation.
- Generated answers use only approved passages.
- Citations are validated before display.
- Unsupported questions receive an honest refusal.
- Supernatural events are attributed to oral tradition.
- Different versions of the legend are preserved rather than silently merged.
- The 3D model is credited under its CC BY 4.0 licence.
- Arbitrary live web search is not used during conversations.
- Provider failures never become fabricated success.

Before publication, the experience should also be reviewed by Luo cultural
practitioners or representatives connected to the Sidho and Kano communities.

## The next portal: La Llorona

Hadithi is being narrowed to two legends so that each destination can receive
real attention:

- **Luanda Magere — Kenya, Africa**
- **La Llorona — Mexico and Latin America**

The root experience will become a world portal containing only these two
destinations. Luanda will lead to the Kano Plains. La Llorona will lead to a
separate moonlit river environment.

La Llorona will not be treated as a generic horror character. Her source pack
must preserve regional differences and explore themes such as grief, warning,
motherhood, colonial interpretation and memory without claiming that one
version represents all of Latin America.

The character render must be legally reusable, suitable for web delivery, and
visually distinct from copyrighted film or television interpretations.

## What remains before submission

- separate the world portal from the Luanda experience;
- create dedicated routes for Luanda Magere and La Llorona;
- complete La Llorona source research and cultural review;
- select and optimise a licensed La Llorona character;
- build the moonlit river environment;
- deploy the FastAPI application to Render;
- add privacy-safe Sentry performance monitoring;
- test the full experience on phones;
- capture final screenshots and a short demonstration video;
- document the live deployment and repository.

## Closing

Hadithi is built around a simple idea: oral traditions should not become static
museum labels, and AI should not rewrite them into confident fiction.

The technology should invite people into the story while remaining honest
about where each answer came from, where tellings differ, and what is still
unknown.

The past speaks—but Hadithi makes sure it does not speak without its sources.
