from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from recipe import Recipe, RecipeState

DEFAULT_RECIPE = Path(__file__).parent / "recipes" / "lemon_garlic_chicken.json"


def handle(question: str, state: RecipeState, brain) -> str:
    print(f"[THINKING] {question!r}")
    try:
        reply = brain.ask(state, question)
    except Exception as error:
        print(f"[brain error] {error}")
        return "Sorry, I couldn't reach my brain just then. Try asking again."
    for action in reply.actions:
        try:
            print(f"[STATE] {state.apply(action.model_dump())}")
        except ValueError as error:
            print(f"[STATE] ignored {action.model_dump(exclude_none=True)}: {error}")
    return reply.say


def run_voice(state: RecipeState, brain):
    from audio import Microphone, UtteranceSplitter, speak
    from transcriber import split_wake, transcribe

    mic = Microphone()
    mic.start()
    splitter = UtteranceSplitter(mic)
    splitter.calibrate()
    speak(f"Hey Cook is ready. We're making {state.recipe.title}. Say hey cook, then ask me anything.", mic)

    try:
        while True:
            print("\n[LISTENING]")
            heard = transcribe(splitter.next_utterance())
            print(f"[HEARD] {heard!r}")
            question = split_wake(heard)
            if question is None:
                continue
            if question == "":
                speak("Yes?", mic)
                print("[RECORDING]")
                question = transcribe(splitter.next_utterance())
                print(f"[HEARD] {question!r}")
                if not question:
                    continue
            answer = handle(question, state, brain)
            print(f"[SPEAKING] {answer}")
            speak(answer, mic)
    except KeyboardInterrupt:
        mic.stop()


def run_typed(state: RecipeState, brain):
    print("Typed test mode. Type a question, or 'quit'.")
    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if question.lower() in ("quit", "exit"):
            break
        if question:
            print(handle(question, state, brain))


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Hey Cook - a hands-free voice cooking assistant")
    parser.add_argument("--recipe", default=str(DEFAULT_RECIPE), help="path to a recipe JSON file")
    parser.add_argument("--type", action="store_true", help="type questions instead of speaking (for testing)")
    args = parser.parse_args()

    from brain import Brain

    state = RecipeState(Recipe.load(args.recipe))
    brain = Brain()
    print(f"Loaded: {state.recipe.title} (serves {state.servings})")
    (run_typed if args.type else run_voice)(state, brain)


if __name__ == "__main__":
    main()
