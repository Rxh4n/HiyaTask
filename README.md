# Hey Cook

A hands-free voice cooking assistant. Ask questions about a recipe, scale it, or swap an ingredient mid-cook - without touching a screen.

**Why voice:** when you're cooking, your hands are covered in oil or marinade and your eyes are on the pan. I watched a flatmate scrolling a recipe on his phone with oily fingers - that's the moment a keyboard or touchscreen fails and voice doesn't.

```
You:      "Hey cook, what's the first step?"
Hey Cook: "Zest and juice the lemon, and crush four cloves of garlic."
You:      "Hey cook, make it for two."
Hey Cook: "Done, I've scaled it for two people."
You:      "Hey cook, how much chicken now?"
Hey Cook: "You'll need 400 grams of chicken thighs."
You:      "Hey cook, I've got no Greek yoghurt."
Hey Cook: "Use plain natural yoghurt instead, the same amount."
```

## Requirements

- **macOS** (speech output uses the built-in `say` command)
- **Python 3.10+** (developed and tested on 3.12)
- A microphone
- A **Gemini API key** - free from [Google AI Studio](https://aistudio.google.com/apikey)

## Setup

```bash
git clone https://github.com/Rxh4n/HiyaTask.git
cd HiyaTask
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and paste your Gemini key after `GEMINI_API_KEY=`.

## Run

```bash
python main.py
```

1. The first run downloads the Whisper speech model (~150 MB) - give it a minute.
2. When it says **"Calibrating"**, stay quiet for a couple of seconds while it measures background noise.
3. When it says **"Hey Cook is ready"**, start every question with **"hey cook"**.
4. `Ctrl+C` to quit.

Things to try: *"what's the first step"*, *"what's next"*, *"go back a step"*, *"how much garlic"*, *"make it for six"*, *"I've run out of lemons"*, *"how long does the chicken go in for"*.

### Typed test mode (no microphone needed)

```bash
python main.py --type
```

Same brain and recipe logic, with typed questions instead of speech. Useful for checking your API key works before testing voice.

### Use a different recipe

```bash
python main.py --recipe recipes/your_recipe.json
```

Recipes are JSON - see `recipes/lemon_garlic_chicken.json` for the format. Keep quantities in the ingredient list only, not in the steps, so scaling stays correct.

## How it works

```
Mic -> utterance splitter -> Whisper (local) -> wake-phrase check -> Gemini -> apply actions to recipe state -> speak
```

| File | Role |
|---|---|
| `audio.py` | Microphone capture on a background thread, splitting speech from silence, and speaking replies with the mic muted so it never hears itself |
| `transcriber.py` | Local speech-to-text with faster-whisper, and detecting the "hey cook" wake phrase |
| `recipe.py` | The recipe and its live state: servings, current step, substitutions. Does all scaling maths |
| `brain.py` | Calls Gemini with the recipe state, the last few exchanges and the question; validates the JSON reply |
| `main.py` | The main loop: listen, wake, think, apply, speak |

**Key design choice - the LLM decides *what*, the code decides *how*.** Gemini never calculates quantities. It returns a structured action like `{"type": "scale", "servings": 2}`, and `recipe.py` does the arithmetic. LLMs make occasional arithmetic slips, and in cooking an occasional slip ruins the dish. Every action is validated before it's applied, and every model reply is validated against a schema - malformed output is retried once, then handled gracefully.

## Troubleshooting

- **It never hears me / only hears silence** - allow microphone access for your terminal or VS Code in System Settings -> Privacy & Security -> Microphone, then restart it.
- **It takes ~15 seconds to respond in a noisy room** - the speech/silence threshold is set during calibration. Stay quiet while it calibrates, and move away from loud fans.
- **`404 NOT_FOUND` for the model** - Google retires model names regularly. Add `GEMINI_MODEL=<a current Flash-Lite model>` to `.env`.
- **`KeyError: 'GEMINI_API_KEY'`** - `.env` is missing or the key line is empty.

## Known limitations

- macOS only, because of `say`. Swapping in a cross-platform text-to-speech library would fix this.
- You can't interrupt it mid-sentence - the mic is muted while it speaks.
- Speech detection is volume-based, so a very loud extractor fan can confuse it.
- English only.
