from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

METRIC_UNITS = ("g", "ml")


@dataclass
class Ingredient:
    name: str
    quantity: float | None
    unit: str = ""


@dataclass
class Recipe:
    title: str
    servings: int
    ingredients: list[Ingredient]
    steps: list[str]

    @classmethod
    def load(cls, path: str | Path) -> Recipe:
        data = json.loads(Path(path).read_text())
        ingredients = [Ingredient(**item) for item in data["ingredients"]]
        return cls(data["title"], data["servings"], ingredients, data["steps"])


def format_quantity(raw: float, unit: str) -> str:
    if unit in METRIC_UNITS:
        value = round(raw / 5) * 5 if raw >= 20 else round(raw)
    else:
        value = round(raw * 4) / 4
    if value == 0:
        value = round(raw, 2)
    text = f"{value:g}"
    return f"{text}{unit}" if unit in METRIC_UNITS else f"{text} {unit}".strip()


@dataclass
class RecipeState:
    recipe: Recipe
    servings: int = 0
    current_step: int = -1
    substitutions: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.servings:
            self.servings = self.recipe.servings

    @property
    def scale(self) -> float:
        return self.servings / self.recipe.servings

    def ingredient_lines(self) -> list[str]:
        lines = []
        for ingredient in self.recipe.ingredients:
            name = self.substitutions.get(ingredient.name, ingredient.name)
            note = f" (instead of {ingredient.name})" if ingredient.name in self.substitutions else ""
            if ingredient.quantity is None:
                lines.append(f"{name}{note}")
            else:
                amount = format_quantity(ingredient.quantity * self.scale, ingredient.unit)
                lines.append(f"{amount} {name}{note}")
        return lines

    def apply(self, action: dict) -> str:
        kind = action.get("type")

        if kind == "scale":
            servings = int(action.get("servings") or 0)
            if not 1 <= servings <= 50:
                raise ValueError(f"servings out of range: {servings}")
            self.servings = servings
            return f"scaled to {servings} servings (x{self.scale:.2f})"

        if kind == "substitute":
            original = self._match_ingredient(action.get("original") or "")
            replacement = (action.get("replacement") or "").strip()
            if not original or not replacement:
                raise ValueError(f"can't substitute {action.get('original')!r}")
            self.substitutions[original] = replacement
            return f"substituted {original} -> {replacement}"

        if kind in ("next_step", "previous_step", "goto_step"):
            if kind == "next_step":
                target = self.current_step + 1
            elif kind == "previous_step":
                target = self.current_step - 1
            else:
                target = int(action.get("step") or 0) - 1
            if not 0 <= target < len(self.recipe.steps):
                raise ValueError(f"no step {target + 1}")
            self.current_step = target
            return f"now on step {target + 1}"

        raise ValueError(f"unknown action {kind!r}")

    def _match_ingredient(self, name: str) -> str | None:
        name = name.lower().strip()
        if not name:
            return None
        for ingredient in self.recipe.ingredients:
            if ingredient.name.lower() == name:
                return ingredient.name
        for ingredient in self.recipe.ingredients:
            if name in ingredient.name.lower() or ingredient.name.lower() in name:
                return ingredient.name
        return None

    def to_prompt(self) -> str:
        lines = [
            f"RECIPE: {self.recipe.title}",
            f"SERVINGS: {self.servings} (original recipe serves {self.recipe.servings})",
            "",
            "INGREDIENTS (already scaled and with substitutions applied):",
            *[f"- {line}" for line in self.ingredient_lines()],
        ]
        if self.substitutions:
            swaps = ", ".join(f"{old} -> {new}" for old, new in self.substitutions.items())
            lines += ["", f"SUBSTITUTIONS IN EFFECT: {swaps}. The steps still use the original names; use the replacement."]
        lines += ["", "STEPS:"]
        for number, step in enumerate(self.recipe.steps, start=1):
            marker = "   <-- CURRENT STEP" if number - 1 == self.current_step else ""
            lines.append(f"{number}. {step}{marker}")
        if self.current_step == -1:
            lines.append("(The cook hasn't started step 1 yet.)")
        return "\n".join(lines)
