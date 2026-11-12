# AI tools used

## In the product

- **Gemini 3.5 Flash-Lite** (Google AI Studio API) is Hey Cook's "brain". It gets the current recipe state, the last three exchanges and the cook's question, and returns what to say plus structured actions. I chose a Flash-Lite model because in a voice conversation response speed matters more than depth of reasoning.
- **Whisper** (`base.en`, via `faster-whisper`) runs locally for speech-to-text, including spotting the "hey cook" wake phrase. Running it locally means audio isn't streamed to the cloud just to listen for the wake phrase, and it costs nothing.

## In building it

I used **Claude** (Anthropic) as a pair programmer throughout.

**How I used it:**
- **Choosing the idea.** I brainstormed with Claude, but the idea came from something I'd seen: a flatmate scrolling a recipe with oily hands. Claude pressure-tested it - it pointed out that a plain "hands-free recipe reader" is a common idea and pushed me to focus on what command-based assistants handle badly. I picked natural follow-up questions and on-the-fly fixes (substitutions and scaling).
- **Architecture.** We designed the pipeline together (mic -> speech splitter -> Whisper -> wake check -> LLM -> recipe state -> speech). I made the product decisions: local Whisper over a cloud wake-word service, "hey cook" plus the question in one sentence, and sending only recent exchanges to the model rather than the full history, to keep it fast.
- **Code.** Claude wrote the first drafts of the modules. I ran and tested everything on my Mac and fed back what happened, and I can explain each file's role and design choices.
- **Debugging.** Claude helped me fix a Python version issue (type-hint syntax not supported on Python 3.9, so I moved to 3.12), a retired Gemini model name, and an early commit that accidentally included my `.env` file before it was ever pushed.

**Where Claude changed my mind:**
- I initially thought the LLM should calculate scaled quantities. Claude argued that an LLM making occasional arithmetic mistakes is unacceptable for cooking, so the LLM now only returns *intent* (e.g. scale to 2 servings) and Python does the maths.
- Claude tested fuzzy matching for the wake phrase and found "hey look" scored too close to "hey cook", so it uses an allowlist of the spellings Whisper actually produces instead.

**What I verified myself:** the full voice loop end to end on my machine, the brain in typed test mode, and the actions being applied (substitution, step navigation and scaling).
