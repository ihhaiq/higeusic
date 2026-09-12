"""Load commands and localization files."""

from pathlib import Path
from typing import Any

import yaml

BASE_DIR = Path(__file__).resolve().parent
LANG_DIR = BASE_DIR / "langs"

languages: dict[str, dict[str, Any]] = {}
commands: dict[str, dict[str, Any]] = {}
languages_present: dict[str, str] = {}


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML mapping in {path}")
    return data


commands["command"] = _load_yaml(BASE_DIR / "command.yml")

english = _load_yaml(LANG_DIR / "en.yml")
languages["en"] = english
languages_present["en"] = str(english.get("name", "English"))

for path in sorted(LANG_DIR.glob("*.yml")):
    language_name = path.stem
    if language_name == "en":
        continue

    localized = _load_yaml(path)
    merged = {**english, **localized}
    languages[language_name] = merged
    languages_present[language_name] = str(merged.get("name", language_name))


def get_command(value: str) -> list[str]:
    return commands["command"][value]


def get_string(lang: str) -> dict[str, Any]:
    return languages.get(lang) or languages.get("ar") or languages["en"]
