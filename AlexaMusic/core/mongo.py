# Copyright (C) 2025 by Alexa_Help @ Github, < https://github.com/TheTeamAlexa >
# Subscribe On YT < Jankari Ki Duniya >. All rights reserved. © Alexa © Yukki.

"""
Database backend.

MongoDB is preferred when MONGO_DB_URI is configured and reachable.
If MongoDB is unavailable, the bot automatically falls back to a local
JSON database stored at data/database.json.
"""

import asyncio
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

from config import MONGO_DB_URI

from ..logging import LOGGER


JSON_DB_PATH = Path(os.getenv("JSON_DB_PATH", "data/database.json"))


def _matches(document: dict, query: dict) -> bool:
    for key, expected in (query or {}).items():
        actual = document.get(key)

        if isinstance(expected, dict):
            for operator, value in expected.items():
                if operator == "$gt":
                    if actual is None or not actual > value:
                        return False
                elif operator == "$gte":
                    if actual is None or not actual >= value:
                        return False
                elif operator == "$lt":
                    if actual is None or not actual < value:
                        return False
                elif operator == "$lte":
                    if actual is None or not actual <= value:
                        return False
                elif operator == "$ne":
                    if actual == value:
                        return False
                elif operator == "$in":
                    if actual not in value:
                        return False
                elif operator == "$nin":
                    if actual in value:
                        return False
                else:
                    return False
        elif actual != expected:
            return False

    return True


class JsonCursor:
    def __init__(self, documents: list[dict]):
        self._documents = [copy.deepcopy(item) for item in documents]
        self._index = 0

    def __aiter__(self):
        self._index = 0
        return self

    async def __anext__(self):
        if self._index >= len(self._documents):
            raise StopAsyncIteration
        item = self._documents[self._index]
        self._index += 1
        return copy.deepcopy(item)

    async def to_list(self, length: int | None = None):
        docs = self._documents if length is None else self._documents[:length]
        return copy.deepcopy(docs)

    def sort(self, key: str, direction: int = 1):
        reverse = direction < 0
        self._documents.sort(
            key=lambda item: (item.get(key) is None, item.get(key)),
            reverse=reverse,
        )
        return self

    def limit(self, length: int):
        self._documents = self._documents[:length]
        return self


class JsonStore:
    def __init__(self, path: Path):
        self.path = path
        self.lock = asyncio.Lock()
        self._data: dict[str, dict[str, list[dict]]] | None = None

    def _load_sync(self):
        if self._data is not None:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._data = {}
            return

        try:
            with self.path.open("r", encoding="utf-8") as file:
                loaded = json.load(file)
                self._data = loaded if isinstance(loaded, dict) else {}
        except (OSError, json.JSONDecodeError):
            LOGGER(__name__).warning(
                "JSON database is unreadable; starting with an empty database."
            )
            self._data = {}

    def _save_sync(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(self._data, file, ensure_ascii=False, indent=2)
        os.replace(temp_path, self.path)

    def collection(self, database: str, collection: str) -> list[dict]:
        self._load_sync()
        db = self._data.setdefault(database, {})
        return db.setdefault(collection, [])


class JsonCollection:
    def __init__(self, store: JsonStore, database: str, name: str):
        self.store = store
        self.database = database
        self.name = name

    def _documents(self) -> list[dict]:
        return self.store.collection(self.database, self.name)

    async def find_one(self, query: dict | None = None):
        async with self.store.lock:
            for document in self._documents():
                if _matches(document, query or {}):
                    return copy.deepcopy(document)
        return None

    def find(self, query: dict | None = None):
        documents = [
            document
            for document in self._documents()
            if _matches(document, query or {})
        ]
        return JsonCursor(documents)

    async def insert_one(self, document: dict):
        async with self.store.lock:
            documents = self._documents()
            documents.append(copy.deepcopy(document))
            self.store._save_sync()
            return SimpleNamespace(inserted_id=len(documents) - 1)

    async def update_one(self, query: dict, update: dict, upsert: bool = False):
        async with self.store.lock:
            documents = self._documents()
            target = None
            for document in documents:
                if _matches(document, query):
                    target = document
                    break

            created = False
            if target is None and upsert:
                target = {
                    key: copy.deepcopy(value)
                    for key, value in query.items()
                    if not isinstance(value, dict)
                }
                documents.append(target)
                created = True

            if target is None:
                return SimpleNamespace(
                    matched_count=0, modified_count=0, upserted_id=None
                )

            for operator, values in update.items():
                if operator == "$set":
                    target.update(copy.deepcopy(values))
                elif operator == "$unset":
                    for key in values:
                        target.pop(key, None)
                elif operator == "$inc":
                    for key, value in values.items():
                        target[key] = target.get(key, 0) + value
                elif operator == "$push":
                    for key, value in values.items():
                        target.setdefault(key, []).append(copy.deepcopy(value))
                elif operator == "$addToSet":
                    for key, value in values.items():
                        target.setdefault(key, [])
                        if value not in target[key]:
                            target[key].append(copy.deepcopy(value))
                elif operator == "$pull":
                    for key, value in values.items():
                        if isinstance(target.get(key), list):
                            target[key] = [
                                item for item in target[key] if item != value
                            ]

            self.store._save_sync()
            return SimpleNamespace(
                matched_count=0 if created else 1,
                modified_count=1,
                upserted_id=(len(documents) - 1) if created else None,
            )

    async def delete_one(self, query: dict):
        async with self.store.lock:
            documents = self._documents()
            for index, document in enumerate(documents):
                if _matches(document, query):
                    documents.pop(index)
                    self.store._save_sync()
                    return SimpleNamespace(deleted_count=1)
            return SimpleNamespace(deleted_count=0)

    async def delete_many(self, query: dict):
        async with self.store.lock:
            documents = self._documents()
            original = len(documents)
            documents[:] = [
                document for document in documents if not _matches(document, query)
            ]
            deleted = original - len(documents)
            if deleted:
                self.store._save_sync()
            return SimpleNamespace(deleted_count=deleted)

    async def count_documents(self, query: dict | None = None):
        return sum(1 for document in self._documents() if _matches(document, query or {}))


class JsonDatabase:
    def __init__(self, store: JsonStore, name: str):
        self.store = store
        self.name = name

    def __getattr__(self, collection: str):
        return JsonCollection(self.store, self.name, collection)

    def __getitem__(self, collection: str):
        return JsonCollection(self.store, self.name, collection)


class JsonClient:
    def __init__(self, path: Path):
        self.store = JsonStore(path)

    def __getattr__(self, database: str):
        return JsonDatabase(self.store, database)

    def __getitem__(self, database: str):
        return JsonDatabase(self.store, database)


def _mongo_is_available(uri: str | None) -> bool:
    if not uri:
        return False

    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        client.close()
        return True
    except Exception as error:
        LOGGER(__name__).warning(
            "MongoDB is unavailable (%s). Falling back to JSON storage.", error
        )
        return False


if _mongo_is_available(MONGO_DB_URI):
    LOGGER(__name__).info("Using MongoDB database backend.")
    _mongo_async_ = AsyncIOMotorClient(MONGO_DB_URI)
    mongodb = _mongo_async_.Alexa

    MONGODB_CLI = AsyncIOMotorClient(MONGO_DB_URI)
    db = MONGODB_CLI["subscriptions"]
    DATABASE_BACKEND = "mongo"
else:
    JSON_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _json_client = JsonClient(JSON_DB_PATH)
    mongodb = _json_client.Alexa
    MONGODB_CLI = _json_client
    db = _json_client["subscriptions"]
    DATABASE_BACKEND = "json"
    LOGGER(__name__).warning(
        "MONGO_DB_URI is missing or unavailable. Using JSON database at %s.",
        JSON_DB_PATH,
    )
