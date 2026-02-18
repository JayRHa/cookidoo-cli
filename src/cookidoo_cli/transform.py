"""Transform Cookidoo API dataclasses into normalized CLI payloads."""

from __future__ import annotations

from typing import Any

from .const import SUBSCRIPTION_TYPES


def _seconds_to_minutes(seconds: int | None) -> int | None:
    """Convert seconds to minutes, rounding up."""
    if seconds is None:
        return None
    return (seconds + 59) // 60


def transform_user_info(
    info: Any,
    subscription: Any | None,
) -> dict[str, Any]:
    """Transform user info and subscription into a combined payload."""
    result: dict[str, Any] = {
        "username": info.username,
        "description": info.description,
        "picture": info.picture,
    }
    if subscription is not None:
        result["subscription"] = {
            "active": subscription.active,
            "type": SUBSCRIPTION_TYPES.get(subscription.type, subscription.type),
            "level": subscription.subscription_level,
            "status": subscription.status,
            "expires": subscription.expires,
            "start_date": subscription.start_date,
        }
    else:
        result["subscription"] = None
    return result


def transform_ingredient_items(items: list[Any]) -> list[dict[str, Any]]:
    """Transform ingredient items from the shopping list."""
    return [
        {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "is_owned": item.is_owned,
        }
        for item in items
    ]


def transform_additional_items(items: list[Any]) -> list[dict[str, Any]]:
    """Transform additional (custom) items from the shopping list."""
    return [
        {
            "id": item.id,
            "name": item.name,
            "is_owned": item.is_owned,
        }
        for item in items
    ]


def transform_shopping_recipes(recipes: list[Any]) -> list[dict[str, Any]]:
    """Transform shopping list recipes."""
    return [
        {
            "id": recipe.id,
            "name": recipe.name,
            "ingredient_count": len(recipe.ingredients),
            "url": recipe.url,
        }
        for recipe in recipes
    ]


def transform_recipe_details(details: Any) -> dict[str, Any]:
    """Transform detailed recipe information."""
    return {
        "id": details.id,
        "name": details.name,
        "difficulty": details.difficulty,
        "serving_size": details.serving_size,
        "active_time_min": _seconds_to_minutes(details.active_time),
        "total_time_min": _seconds_to_minutes(details.total_time),
        "url": details.url,
        "utensils": details.utensils,
        "categories": [
            {"id": cat.id, "name": cat.name} for cat in details.categories
        ],
        "ingredients": [
            {
                "id": ing.id,
                "name": ing.name,
                "description": ing.description,
            }
            for ing in details.ingredients
        ],
        "notes": details.notes,
    }


def transform_calendar(days: list[Any]) -> list[dict[str, Any]]:
    """Transform calendar days with recipes."""
    return [
        {
            "date": day.id,
            "title": day.title,
            "recipes": [
                {
                    "id": recipe.id,
                    "name": recipe.name,
                    "total_time_min": _seconds_to_minutes(recipe.total_time),
                    "url": recipe.url,
                }
                for recipe in day.recipes
            ],
        }
        for day in days
    ]


def transform_collections(collections: list[Any]) -> list[dict[str, Any]]:
    """Transform collections with chapters and recipes."""
    return [
        {
            "id": col.id,
            "name": col.name,
            "description": col.description,
            "chapters": [
                {
                    "name": chapter.name,
                    "recipes": [
                        {
                            "id": recipe.id,
                            "name": recipe.name,
                            "total_time_min": _seconds_to_minutes(recipe.total_time),
                        }
                        for recipe in chapter.recipes
                    ],
                }
                for chapter in col.chapters
            ],
        }
        for col in collections
    ]
