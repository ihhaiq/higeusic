# Copyright (C) 2025 by Alexa_Help @ Github, < https://github.com/TheTeamAlexa >
# Subscribe On YT < Jankari Ki Duniya >. All rights reserved. © Alexa © Yukki.

"""
TheTeamAlexa is a project of Telegram bots with variety of purposes.
Copyright (c) 2021 ~ Present Team Alexa <https://github.com/TheTeamAlexa>

This program is free software: you can redistribute it and can modify
as you want or you can collabe if you have new ideas.
"""

import asyncio
import sys

from AlexaMusic.core.bot import AlexaBot
from AlexaMusic.core.dir import dirr
from AlexaMusic.core.userbot import Userbot
from AlexaMusic.misc import dbb

from .logging import LOGGER

if sys.platform != "win32":
    try:
        import uvloop

        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        LOGGER(__name__).info("Using Uvloop Event Loop for Enhanced Performance")
    except ImportError:
        LOGGER(__name__).warning("Uvloop not found, using default event loop.")


# Directories
dirr()

# Initialize Memory DB
dbb()

# Bot Client
app = AlexaBot()

# Assistant Client
userbot = Userbot()

from .platforms import *

YouTube = YouTubeAPI()
Spotify = SpotifyAPI()
Apple = AppleAPI()
Resso = RessoAPI()
SoundCloud = SoundAPI()
Telegram = TeleAPI()
