from __future__ import annotations

import os
from collections import deque
from typing import Literal, Optional

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from recipe import RecipeState

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
HISTORY_TURNS = 3

SYSTEM_PROMPT = """You are Hey Cook, a hands-free voice assistant helping someone while they cook.
Their hands are messy and they can't look at a screen. Everything you write in "say" is read aloud.

How to reply:
- One to three short spoken sentences. No markdown, lists, emojis or headings.
- Say quantities naturally, e.g. "about 200 grams", "one and a half teaspoons".
- Use the recipe below for every amount and step. For anything it doesn't cover, use general cooking knowledge, briefly.
- Never do scaling maths yourself. If the cook changes the number of servings, emit a scale action and just confirm the new serving count; the app recalculates every quantity.
- If the cook is missing an ingredient or wants a swap, suggest one sensible substitute, say briefly how to use it, and emit a substitute action. "original" must be the ingredient name as it appears in the ingredient list.
- If the cook asks what's next, emit next_step and read out the step after the current one, including amounts from the ingredient list. Use previous_step or goto_step (numbered from 1) when they ask to go back or jump.
- Food safety comes first: never suggest undercooking chicken or meat, and be clear about the safe option.
- If the question is unclear, ask a short clarifying question and emit no actions.

Respond with JSON only, in exactly this shape:
{"say": "<what to say aloud>", "actions": [<zero or more actions>]}

Each action is one of:
{"type": "scale", "servings": <integer>}
{"type": "substitute", "original": "<ingredient name>", "replacement": "<what to use instead>"}
{"type": "next_step"}
{"type": "previous_step"}
{"type": "goto_step", "step": <integer, 1-based>}

Use an empty actions list when nothing about the recipe changes."""


class Action(BaseModel):
    type: Literal["scale", "substitute", "next_step", "previous_step", "goto_step"]
    servings: Optional[int] = None
    original: Optional[str] = None
    replacement: Optional[str] = None
    step: Optional[int] = None


class BrainReply(BaseModel):
    say: str
    actions: list[Action] = []


def build_prompt(state: RecipeState, history: deque, question: str) -> str:
    parts = [state.to_prompt(), ""]
    if history:
        parts.append("RECENT CONVERSATION:")
        for asked, answered in history:
            parts += [f"Cook: {asked}", f"Hey Cook: {answered}"]
        parts.append("")
    parts.append(f"COOK'S QUESTION: {question}")
    return "\n".join(parts)


class Brain:
    def __init__(self, api_key: str | None = None):
        self.client = genai.Client(api_key=api_key or os.environ["GEMINI_API_KEY"])
        self.history: deque = deque(maxlen=HISTORY_TURNS)

    def ask(self, state: RecipeState, question: str) -> BrainReply:
        prompt = build_prompt(state, self.history, question)
        reply = None
        for _ in range(2):
            raw = self._generate(prompt)
            try:
                reply = BrainReply.model_validate_json(raw)
                break
            except ValidationError as error:
                print(f"[brain] invalid JSON from model, retrying: {error.errors()[0]['msg']}")
        if reply is None:
            reply = BrainReply(say="Sorry, I got muddled. Could you ask that again?", actions=[])
        self.history.append((question, reply.say))
        return reply

    def _generate(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.3,
            ),
        )
        return response.text or ""
