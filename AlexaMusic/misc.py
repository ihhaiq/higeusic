import time

from pyrogram import filters

import config
from AlexaMusic.core.mongo import mongodb

from .logging import LOGGER

SUDOERS = filters.user()
_boot_ = time.time()


def dbb():
    global db
    db = {}
    LOGGER(__name__).info("Database Initialized.")


async def sudo():
    global SUDOERS
    SUDOERS.add(config.OWNER_ID)
    sudoersdb = mongodb.sudoers
    sudoers = await sudoersdb.find_one({"sudo": "sudo"})
    sudoers = sudoers["sudoers"] if sudoers else []
    if config.OWNER_ID not in sudoers:
        sudoers.append(config.OWNER_ID)
        await sudoersdb.update_one(
            {"sudo": "sudo"},
            {"$set": {"sudoers": sudoers}},
            upsert=True,
        )
    for user_id in sudoers:
        SUDOERS.add(user_id)
    LOGGER(__name__).info("Sudoers Loaded.")
