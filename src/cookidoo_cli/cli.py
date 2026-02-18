"""Command line interface for Cookidoo."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from datetime import date
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout
from cookidoo_api import (
    Cookidoo,
    CookidooAuthException,
    CookidooConfigException,
    CookidooException,
    CookidooRequestException,
    CookidooUnavailableException,
)
from cookidoo_api.helpers import get_localization_options
from cookidoo_api.types import CookidooConfig

from .const import DEFAULT_COUNTRY, DEFAULT_LANGUAGE
from .transform import (
    transform_additional_items,
    transform_calendar,
    transform_collections,
    transform_ingredient_items,
    transform_recipe_details,
    transform_shopping_recipes,
    transform_user_info,
)


class CliInputError(ValueError):
    """Raised for invalid CLI argument combinations."""


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="cookidoo",
        description="High-signal CLI for Cookidoo recipes, shopping lists, and meal planning",
    )
    parser.add_argument(
        "--email",
        default=os.getenv("COOKIDOO_EMAIL"),
        help="Cookidoo account email (or env COOKIDOO_EMAIL)",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("COOKIDOO_PASSWORD"),
        help="Cookidoo account password (or env COOKIDOO_PASSWORD)",
    )
    parser.add_argument(
        "--country",
        default=os.getenv("COOKIDOO_COUNTRY", DEFAULT_COUNTRY),
        help=f"Country code (default: {DEFAULT_COUNTRY}, or env COOKIDOO_COUNTRY)",
    )
    parser.add_argument(
        "--language",
        default=os.getenv("COOKIDOO_LANGUAGE", DEFAULT_LANGUAGE),
        help=f"Language code (default: {DEFAULT_LANGUAGE}, or env COOKIDOO_LANGUAGE)",
    )
    parser.add_argument(
        "--json", dest="json_output", action="store_true", help="Output as JSON"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("user", help="Show user info and subscription status")
    subparsers.add_parser("shopping", help="Show shopping list (ingredients + additional items)")
    subparsers.add_parser("shopping-recipes", help="Show recipes on the shopping list")

    shopping_add = subparsers.add_parser("shopping-add", help="Add items to the shopping list")
    shopping_add_group = shopping_add.add_mutually_exclusive_group(required=True)
    shopping_add_group.add_argument("--items", nargs="+", help="Custom item names to add")
    shopping_add_group.add_argument("--recipe-ids", nargs="+", help="Recipe IDs to add ingredients from")

    shopping_remove = subparsers.add_parser("shopping-remove", help="Remove items from the shopping list")
    shopping_remove_group = shopping_remove.add_mutually_exclusive_group(required=True)
    shopping_remove_group.add_argument("--ids", nargs="+", help="Additional item IDs to remove")
    shopping_remove_group.add_argument("--recipe-ids", nargs="+", help="Recipe IDs to remove ingredients for")

    shopping_check = subparsers.add_parser("shopping-check", help="Check/uncheck items on the shopping list")
    shopping_check.add_argument("--ids", nargs="+", required=True, help="Item IDs to toggle")
    shopping_check.add_argument("--uncheck", action="store_true", help="Uncheck instead of check")
    shopping_check.add_argument(
        "--type",
        choices=["ingredient", "additional"],
        default="ingredient",
        help="Item type (default: ingredient)",
    )

    subparsers.add_parser("shopping-clear", help="Clear the entire shopping list")

    recipe_parser = subparsers.add_parser("recipe", help="Get recipe details")
    recipe_parser.add_argument("--id", required=True, help="Recipe ID")

    calendar_parser = subparsers.add_parser("calendar", help="Show weekly meal plan")
    calendar_parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=None,
        help="Date in the target week (YYYY-MM-DD, default: today)",
    )

    collections_parser = subparsers.add_parser("collections", help="List recipe collections")
    collections_parser.add_argument(
        "--type",
        dest="collection_type",
        choices=["managed", "custom"],
        default="managed",
        help="Collection type (default: managed)",
    )
    collections_parser.add_argument("--page", type=int, default=0, help="Page number (default: 0)")

    return parser


def validate_args(args: argparse.Namespace) -> None:
    """Validate argument combinations."""
    if not args.email:
        raise CliInputError("Email missing. Use --email or COOKIDOO_EMAIL.")
    if not args.password:
        raise CliInputError("Password missing. Use --password or COOKIDOO_PASSWORD.")


def _render_table(headers: list[str], rows: list[list[Any]]) -> str:
    """Render rows as a plain text table."""
    normalized_rows = [
        ["-" if value is None else str(value) for value in row] for row in rows
    ]
    widths = [len(h) for h in headers]

    for row in normalized_rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    header_line = " | ".join(
        header.ljust(widths[i]) for i, header in enumerate(headers)
    )
    separator = "-+-".join("-" * width for width in widths)
    body = [
        " | ".join(value.ljust(widths[i]) for i, value in enumerate(row))
        for row in normalized_rows
    ]

    return "\n".join([header_line, separator, *body])


def _check_mark(is_owned: bool) -> str:
    return "[x]" if is_owned else "[ ]"


def print_human(command: str, payload: dict[str, Any]) -> None:
    """Print result in human-readable format."""
    if command == "user":
        user = payload["user"]
        print(f"Username: {user['username']}")
        print(f"Description: {user.get('description') or '-'}")
        sub = user.get("subscription")
        if sub:
            print(f"\nSubscription: {sub['type']} ({sub['status']})")
            print(f"Active: {sub['active']}")
            print(f"Level: {sub['level']}")
            print(f"Expires: {sub['expires']}")
        else:
            print("\nSubscription: none")
        return

    if command == "shopping":
        ingredients = payload.get("ingredients", [])
        additional = payload.get("additional_items", [])

        if ingredients:
            print("Ingredients:")
            for item in ingredients:
                desc = f" ({item['description']})" if item.get("description") else ""
                print(f"  {_check_mark(item['is_owned'])} {item['name']}{desc}")
        else:
            print("Ingredients: (empty)")

        if additional:
            print("\nAdditional items:")
            for item in additional:
                print(f"  {_check_mark(item['is_owned'])} {item['name']}")
        else:
            print("\nAdditional items: (empty)")

        total = len(ingredients) + len(additional)
        owned = sum(1 for i in ingredients if i["is_owned"]) + sum(
            1 for i in additional if i["is_owned"]
        )
        print(f"\nTotal: {total} items ({owned} checked)")
        return

    if command == "shopping-recipes":
        recipes = payload.get("recipes", [])
        if not recipes:
            print("No recipes on the shopping list.")
            return
        rows = [
            [r["id"], r["name"], r["ingredient_count"]]
            for r in recipes
        ]
        print(_render_table(["id", "name", "ingredients"], rows))
        return

    if command in ("shopping-add", "shopping-remove", "shopping-check", "shopping-clear"):
        print(payload.get("message", "Done."))
        return

    if command == "recipe":
        r = payload["recipe"]
        print(f"Name: {r['name']}")
        print(f"ID: {r['id']}")
        print(f"Difficulty: {r.get('difficulty') or '-'}")
        print(f"Servings: {r.get('serving_size') or '-'}")
        print(f"Active time: {r.get('active_time_min') or '-'} min")
        print(f"Total time: {r.get('total_time_min') or '-'} min")
        print(f"URL: {r.get('url') or '-'}")

        if r.get("utensils"):
            print(f"\nUtensils: {', '.join(r['utensils'])}")

        if r.get("categories"):
            cats = ", ".join(c["name"] for c in r["categories"])
            print(f"Categories: {cats}")

        if r.get("ingredients"):
            print("\nIngredients:")
            for ing in r["ingredients"]:
                desc = f" - {ing['description']}" if ing.get("description") else ""
                print(f"  {ing['name']}{desc}")

        if r.get("notes"):
            print("\nNotes:")
            for note in r["notes"]:
                print(f"  {note}")
        return

    if command == "calendar":
        days = payload.get("calendar", [])
        if not days:
            print("No recipes planned this week.")
            return
        for day in days:
            print(f"\n{day['date']} - {day['title']}")
            if day["recipes"]:
                for recipe in day["recipes"]:
                    time_str = f" ({recipe['total_time_min']} min)" if recipe.get("total_time_min") else ""
                    print(f"  {recipe['name']}{time_str}")
            else:
                print("  (no recipes)")
        return

    if command == "collections":
        collections = payload.get("collections", [])
        if not collections:
            print("No collections found.")
            return
        for col in collections:
            desc = f" - {col['description']}" if col.get("description") else ""
            print(f"\n{col['name']}{desc}")
            print(f"  ID: {col['id']}")
            for chapter in col.get("chapters", []):
                print(f"  {chapter['name']}:")
                for recipe in chapter.get("recipes", []):
                    time_str = f" ({recipe['total_time_min']} min)" if recipe.get("total_time_min") else ""
                    print(f"    {recipe['name']}{time_str}")
        return


async def _get_client(args: argparse.Namespace, session: ClientSession) -> Cookidoo:
    """Create and authenticate a Cookidoo client."""
    localizations = await get_localization_options(
        country=args.country, language=args.language
    )
    if not localizations:
        raise CliInputError(
            f"No localization found for country={args.country}, language={args.language}."
        )

    cfg = CookidooConfig(
        email=args.email,
        password=args.password,
        localization=localizations[0],
    )
    client = Cookidoo(session, cfg=cfg)
    await client.login()
    return client


async def run_command(args: argparse.Namespace) -> dict[str, Any]:
    """Execute the selected command."""
    timeout = ClientTimeout(total=30)

    async with ClientSession(timeout=timeout) as session:
        client = await _get_client(args, session)

        if args.command == "user":
            info = await client.get_user_info()
            subscription = await client.get_active_subscription()
            return {
                "command": args.command,
                "user": transform_user_info(info, subscription),
            }

        if args.command == "shopping":
            ingredients = await client.get_ingredient_items()
            additional = await client.get_additional_items()
            return {
                "command": args.command,
                "ingredients": transform_ingredient_items(ingredients),
                "additional_items": transform_additional_items(additional),
            }

        if args.command == "shopping-recipes":
            recipes = await client.get_shopping_list_recipes()
            return {
                "command": args.command,
                "recipes": transform_shopping_recipes(recipes),
            }

        if args.command == "shopping-add":
            if args.items:
                added = await client.add_additional_items(args.items)
                return {
                    "command": args.command,
                    "message": f"Added {len(added)} item(s).",
                    "items": transform_additional_items(added),
                }
            added = await client.add_ingredient_items_for_recipes(args.recipe_ids)
            return {
                "command": args.command,
                "message": f"Added ingredients from {len(args.recipe_ids)} recipe(s).",
                "items": transform_ingredient_items(added),
            }

        if args.command == "shopping-remove":
            if args.ids:
                await client.remove_additional_items(args.ids)
                return {
                    "command": args.command,
                    "message": f"Removed {len(args.ids)} item(s).",
                }
            await client.remove_ingredient_items_for_recipes(args.recipe_ids)
            return {
                "command": args.command,
                "message": f"Removed ingredients for {len(args.recipe_ids)} recipe(s).",
            }

        if args.command == "shopping-check":
            # Build item objects with toggled ownership
            from cookidoo_api import CookidooIngredientItem, CookidooAdditionalItem

            target_owned = not args.uncheck
            if args.type == "ingredient":
                items_to_edit = [
                    CookidooIngredientItem(
                        id=uid, name="", is_owned=target_owned, description=""
                    )
                    for uid in args.ids
                ]
                await client.edit_ingredient_items_ownership(items_to_edit)
            else:
                items_to_edit = [
                    CookidooAdditionalItem(id=uid, name="", is_owned=target_owned)
                    for uid in args.ids
                ]
                await client.edit_additional_items_ownership(items_to_edit)

            action = "Unchecked" if args.uncheck else "Checked"
            return {
                "command": args.command,
                "message": f"{action} {len(args.ids)} {args.type} item(s).",
            }

        if args.command == "shopping-clear":
            await client.clear_shopping_list()
            return {
                "command": args.command,
                "message": "Shopping list cleared.",
            }

        if args.command == "recipe":
            details = await client.get_recipe_details(args.id)
            return {
                "command": args.command,
                "recipe": transform_recipe_details(details),
            }

        if args.command == "calendar":
            target_date = args.date or date.today()
            days = await client.get_recipes_in_calendar_week(target_date)
            return {
                "command": args.command,
                "calendar": transform_calendar(days),
            }

        # collections
        if args.collection_type == "custom":
            collections = await client.get_custom_collections(page=args.page)
        else:
            collections = await client.get_managed_collections(page=args.page)
        return {
            "command": args.command,
            "collection_type": args.collection_type,
            "page": args.page,
            "collections": transform_collections(collections),
        }


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        validate_args(args)
        payload = asyncio.run(run_command(args))
    except CliInputError as error:
        print(f"Input error: {error}", file=sys.stderr)
        return 2
    except CookidooAuthException as error:
        print(f"Error: Authentication failed: {error}", file=sys.stderr)
        return 2
    except CookidooConfigException as error:
        print(f"Error: Invalid configuration: {error}", file=sys.stderr)
        return 2
    except (
        CookidooRequestException,
        CookidooUnavailableException,
        CookidooException,
        ClientError,
        TimeoutError,
    ) as error:
        print(f"Error while calling Cookidoo API: {error}", file=sys.stderr)
        return 1

    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_human(args.command, payload)

    return 0
