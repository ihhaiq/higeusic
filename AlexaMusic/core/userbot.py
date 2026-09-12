"""Telegram assistant clients used for voice/video playback."""

from contextlib import suppress

from pyrogram import Client

import config
from ..logging import LOGGER

assistants = []
assistantids = []


class Userbot:
    def __init__(self):
        self.one = self._build_client("AlexaOne", config.STRING1)
        self.two = self._build_client("AlexaTwo", config.STRING2)
        self.three = self._build_client("AlexaThree", config.STRING3)
        self.four = self._build_client("AlexaFour", config.STRING4)
        self.five = self._build_client("AlexaFive", config.STRING5)

    @staticmethod
    def _build_client(name, session_string):
        if not session_string:
            return None
        return Client(
            name=name,
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=session_string,
            no_updates=True,
        )

    def _configured_clients(self):
        return (
            (1, self.one),
            (2, self.two),
            (3, self.three),
            (4, self.four),
            (5, self.five),
        )

    async def start(self):
        LOGGER(__name__).info("جاري تشغيل حسابات المساعد...")
        assistants.clear()
        assistantids.clear()

        for index, client in self._configured_clients():
            if client is None:
                continue
            try:
                await client.start()
                get_me = await client.get_me()
            except Exception as error:
                LOGGER(__name__).error(
                    "فشل تشغيل الحساب المساعد %s: %s",
                    index,
                    error,
                )
                with suppress(Exception):
                    if client.is_connected:
                        await client.stop()
                continue

            client.username = get_me.username
            client.id = get_me.id
            client.name = (
                f"{get_me.first_name} {get_me.last_name}"
                if get_me.last_name
                else get_me.first_name
            )
            assistants.append(index)
            assistantids.append(get_me.id)
            LOGGER(__name__).info(
                "تم تشغيل الحساب المساعد %s باسم %s",
                index,
                client.name,
            )

        if not assistants:
            raise RuntimeError("لم يتم تشغيل أي حساب مساعد صالح.")

        return len(assistants)

    async def stop(self):
        for _, client in self._configured_clients():
            if client is None:
                continue
            with suppress(Exception):
                if client.is_connected:
                    await client.stop()
