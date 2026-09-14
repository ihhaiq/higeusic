import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from pyrogram import filters


ROOT = Path(__file__).resolve().parents[1]


def load_source(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class DeveloperPanelTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bot = NS(
            on_message=lambda *_args, **_kwargs: lambda function: function,
            on_callback_query=lambda *_args, **_kwargs: lambda function: function,
        )
        self.database = NS(
            add_private_chat=AsyncMock(),
            get_private_served_chats=AsyncMock(return_value=[]),
            is_served_private_chat=AsyncMock(return_value=False),
            remove_private_chat=AsyncMock(),
        )
        self.chat = NS(id=-1001234567890, title="Allowed channel")
        self.resolve = AsyncMock(return_value=self.chat)
        dependencies = {
            "config": NS(OWNER_ID=42),
            "AlexaMusic": NS(app=self.bot),
            "AlexaMusic.misc": NS(SUDOERS=filters.user([42, 43])),
            "AlexaMusic.utils.database": self.database,
            "AlexaMusic.utils.private_play": NS(resolve_private_chat=self.resolve),
        }
        self.module_patch = patch.dict(sys.modules, dependencies)
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        self.dev = load_source("dev_panel_under_test", "AlexaMusic/plugins/sudo/dev.py")

    async def test_add_uses_private_play_authorization_store(self):
        message = NS(reply_text=AsyncMock())
        await self.dev._change_authorization(message, "add", "@allowed")

        self.resolve.assert_awaited_once_with("@allowed")
        self.database.add_private_chat.assert_awaited_once_with(self.chat.id)
        self.database.remove_private_chat.assert_not_awaited()

    async def test_remove_uses_same_authorization_store(self):
        self.database.is_served_private_chat.return_value = True
        message = NS(reply_text=AsyncMock())
        await self.dev._change_authorization(message, "remove", str(self.chat.id))

        self.database.remove_private_chat.assert_awaited_once_with(self.chat.id)

    async def test_non_developer_cannot_open_panel(self):
        message = NS(
            from_user=NS(id=99),
            text="/dev",
            reply_text=AsyncMock(),
        )
        await self.dev.developer_panel(None, message)

        message.reply_text.assert_awaited_once()
        self.database.get_private_served_chats.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
