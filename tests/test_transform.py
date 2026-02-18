"""Tests for transformation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cookidoo_cli.transform import (
    transform_additional_items,
    transform_calendar,
    transform_collections,
    transform_ingredient_items,
    transform_recipe_details,
    transform_shopping_recipes,
    transform_user_info,
)


# Minimal stub dataclasses to avoid importing cookidoo_api in tests.


@dataclass
class _UserInfo:
    username: str
    description: str | None
    picture: str | None


@dataclass
class _Subscription:
    active: bool
    expires: str
    start_date: str
    status: str
    subscription_level: str
    subscription_source: str
    type: str
    extended_type: str


@dataclass
class _IngredientItem:
    id: str
    name: str
    is_owned: bool
    description: str


@dataclass
class _AdditionalItem:
    id: str
    name: str
    is_owned: bool


@dataclass
class _Ingredient:
    id: str
    name: str
    description: str


@dataclass
class _ShoppingRecipe:
    id: str
    name: str
    ingredients: list[Any]
    thumbnail: str | None
    image: str | None
    url: str


@dataclass
class _Category:
    id: str
    name: str
    notes: str


@dataclass
class _RecipeDetails:
    id: str
    name: str
    difficulty: str
    serving_size: int
    active_time: int
    total_time: int
    url: str
    utensils: list[str]
    categories: list[Any]
    ingredients: list[Any]
    notes: list[str]
    thumbnail: str | None = None
    image: str | None = None
    collections: list[Any] | None = None
    nutrition_groups: list[Any] | None = None


@dataclass
class _CalendarDayRecipe:
    id: str
    name: str
    total_time: int
    thumbnail: str | None
    image: str | None
    url: str


@dataclass
class _CalendarDay:
    id: str
    title: str
    recipes: list[Any]


@dataclass
class _ChapterRecipe:
    id: str
    name: str
    total_time: int


@dataclass
class _Chapter:
    name: str
    recipes: list[Any]


@dataclass
class _Collection:
    id: str
    name: str
    description: str | None
    chapters: list[Any]


# --- Tests ---


def test_transform_user_info_with_subscription() -> None:
    info = _UserInfo(username="alice", description="Cook", picture="http://pic.jpg")
    sub = _Subscription(
        active=True,
        expires="2025-12-31",
        start_date="2024-01-01",
        status="active",
        subscription_level="premium",
        subscription_source="web",
        type="REGULAR",
        extended_type="full",
    )
    result = transform_user_info(info, sub)
    assert result["username"] == "alice"
    assert result["subscription"]["type"] == "premium"
    assert result["subscription"]["active"] is True


def test_transform_user_info_without_subscription() -> None:
    info = _UserInfo(username="bob", description=None, picture=None)
    result = transform_user_info(info, None)
    assert result["username"] == "bob"
    assert result["subscription"] is None


def test_transform_ingredient_items() -> None:
    items = [
        _IngredientItem(id="i1", name="Mehl", is_owned=False, description="200g"),
        _IngredientItem(id="i2", name="Zucker", is_owned=True, description="100g"),
    ]
    result = transform_ingredient_items(items)
    assert len(result) == 2
    assert result[0]["name"] == "Mehl"
    assert result[0]["description"] == "200g"
    assert result[0]["is_owned"] is False
    assert result[1]["is_owned"] is True


def test_transform_additional_items() -> None:
    items = [_AdditionalItem(id="a1", name="Servietten", is_owned=False)]
    result = transform_additional_items(items)
    assert result[0]["name"] == "Servietten"
    assert "description" not in result[0]


def test_transform_shopping_recipes() -> None:
    recipes = [
        _ShoppingRecipe(
            id="r1",
            name="Pasta",
            ingredients=[_Ingredient("x", "Nudeln", "500g"), _Ingredient("y", "Sauce", "1 Glas")],
            thumbnail=None,
            image=None,
            url="https://cookidoo.ch/r1",
        )
    ]
    result = transform_shopping_recipes(recipes)
    assert result[0]["ingredient_count"] == 2
    assert result[0]["url"] == "https://cookidoo.ch/r1"


def test_transform_recipe_details() -> None:
    details = _RecipeDetails(
        id="r42",
        name="Risotto",
        difficulty="medium",
        serving_size=4,
        active_time=1200,
        total_time=2400,
        url="https://cookidoo.ch/r42",
        utensils=["Thermomix"],
        categories=[_Category("c1", "Hauptgericht", "")],
        ingredients=[_Ingredient("i1", "Reis", "300g")],
        notes=["Gut umruehren"],
    )
    result = transform_recipe_details(details)
    assert result["name"] == "Risotto"
    assert result["active_time_min"] == 20
    assert result["total_time_min"] == 40
    assert result["ingredients"][0]["name"] == "Reis"
    assert result["categories"][0]["name"] == "Hauptgericht"


def test_transform_recipe_details_time_rounding() -> None:
    details = _RecipeDetails(
        id="r1", name="X", difficulty="easy", serving_size=2,
        active_time=61, total_time=119, url="", utensils=[], categories=[],
        ingredients=[], notes=[],
    )
    result = transform_recipe_details(details)
    assert result["active_time_min"] == 2  # 61s -> 2 min (ceil)
    assert result["total_time_min"] == 2  # 119s -> 2 min (ceil)


def test_transform_calendar() -> None:
    days = [
        _CalendarDay(
            id="2025-03-10",
            title="Montag",
            recipes=[
                _CalendarDayRecipe(
                    id="r1", name="Suppe", total_time=1800,
                    thumbnail=None, image=None, url="https://cookidoo.ch/r1",
                ),
            ],
        ),
        _CalendarDay(id="2025-03-11", title="Dienstag", recipes=[]),
    ]
    result = transform_calendar(days)
    assert len(result) == 2
    assert result[0]["date"] == "2025-03-10"
    assert result[0]["recipes"][0]["total_time_min"] == 30
    assert result[1]["recipes"] == []


def test_transform_collections() -> None:
    collections = [
        _Collection(
            id="col1",
            name="Favoriten",
            description="Meine Lieblingsrezepte",
            chapters=[
                _Chapter(
                    name="Vorspeisen",
                    recipes=[_ChapterRecipe(id="r1", name="Bruschetta", total_time=900)],
                )
            ],
        )
    ]
    result = transform_collections(collections)
    assert result[0]["name"] == "Favoriten"
    assert result[0]["chapters"][0]["recipes"][0]["total_time_min"] == 15
