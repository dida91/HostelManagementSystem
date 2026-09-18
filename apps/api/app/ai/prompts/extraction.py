"""Mess feedback extraction prompts."""

from __future__ import annotations

VERSION = "mess.feedback.v1"

SYSTEM = """You analyse mess (canteen) feedback from students at a hostel in Nepal.

Rules:
- Extract only what the student actually said.
- `topics` are the food items or aspects mentioned, lowercase and singular
  where natural (e.g. "rice", "dal", "hygiene", "portion size").
- `issues` are concrete problems only. If the feedback is purely positive,
  return an empty list.
- Use MIXED sentiment when the student both praises and criticises.
- Students may write in English, Nepali, or a mix. Write your output in English.
"""

USER_TEMPLATE = """Meal: {meal_type} on {meal_date}
Student rating: {rating} out of 5

<feedback>
{comment}
</feedback>

Return the structured analysis."""


def build_user_prompt(*, meal_type: str, meal_date: str, rating: int, comment: str) -> str:
    return USER_TEMPLATE.format(
        meal_type=meal_type, meal_date=meal_date, rating=rating, comment=comment.strip()
    )
