from __future__ import annotations

from typing import Any

STORAGE_KEY = "review_session"


def save_review_state(
    storage: dict[str, Any],
    srs_app: Any,
    *,
    item_dict: dict[int, list[int]],
) -> None:

    # no reviews
    if not srs_app.current_reviews:

        return None

    storage[STORAGE_KEY] = {
        "current_reviews": list(srs_app.current_reviews),
        "current_index": srs_app.current_index,
        "current_completed": srs_app.current_completed,
        "len_review_ids": srs_app.len_review_ids,
        "due_review_ids": list(srs_app.due_review_ids),
        "stop_updating_review": srs_app.stop_updating_review,
        "item_dict": {k: list(v) for k, v in item_dict.items()},
    }

    return None


def load_review_state(
    storage: dict[str, Any],
    srs_app: Any,
    item_dict: dict[int, list[int]],
) -> dict[str, Any] | None:
    state = storage.get(STORAGE_KEY)

    if state is None:

        return None

    srs_app.current_reviews = list(state["current_reviews"])
    srs_app.current_index = int(state["current_index"])
    srs_app.current_completed = int(state["current_completed"])
    srs_app.len_review_ids = int(state["len_review_ids"])
    srs_app.due_review_ids = list(state["due_review_ids"])
    srs_app.stop_updating_review = bool(state["stop_updating_review"])

    # nicegui serialises storage as json, which converts int dict keys to strings
    # convert them back to ints.
    raw_item_dict = state["item_dict"]
    item_dict.clear()
    for k, v in raw_item_dict.items():
        item_dict[int(k)] = list(v)

    return state


def clear_review_state(storage: dict[str, Any]) -> None:
    storage.pop(STORAGE_KEY, None)


def has_review_state(storage: dict[str, Any]) -> bool:
    state = storage.get(STORAGE_KEY)
    if not isinstance(state, dict):

        return False

    reviews = state.get("current_reviews", [])

    return bool(reviews)
