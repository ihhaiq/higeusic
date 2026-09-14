"""Resolve private playback destinations using assistant accounts, not the bot."""

from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.errors import FloodWait, RPCError

from AlexaMusic.core.userbot import assistants
from AlexaMusic.utils.database import (
    bind_assistant,
    get_assistant,
    get_client,
    is_active_chat,
)
from AlexaMusic.utils.exceptions import AssistantErr


async def resolve_private_chat(target):
    if not assistants:
        raise AssistantErr("لا يوجد حساب مساعد فعّال. تحقق من STRING_SESSION.")
    for number in assistants:
        client = await get_client(number)
        try:
            chat = await client.get_chat(target)
        except FloodWait:
            raise
        except RPCError:
            continue
        if chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL}:
            raise AssistantErr("الوجهة يجب أن تكون مجموعة أو قناة، وليست حساب مستخدم.")
        return chat
    raise AssistantErr(
        "تعذر الوصول إلى المجموعة/القناة. تحقق من اليوزر أو الآيدي "
        "وأضف الحساب المساعد إليها أولاً."
    )


async def prepare_private_assistant(chat) -> int:
    """Prefer the assigned account; never replace an account with an active call.

    The caller serializes requests for this chat while selecting and starting
    playback. No bot membership lookup or automatic join is needed here.
    """
    assigned = await get_assistant(chat.id)
    clients = [(number, await get_client(number)) for number in assistants]
    clients.sort(key=lambda entry: entry[1] is not assigned)
    active = await is_active_chat(chat.id)
    for number, client in clients:
        if active and client is not assigned:
            continue
        try:
            await client.get_chat(chat.username or chat.id)
            member = await client.get_chat_member(chat.id, "me")
        except FloodWait:
            raise
        except RPCError:
            continue
        if member.status not in {
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.MEMBER,
        }:
            continue
        if client is not assigned:
            await bind_assistant(chat.id, number)
        return number
    raise AssistantErr(
        "الحساب المساعد غير موجود في المجموعة/القناة أو مقيّد فيها. "
        "يكفي إضافته كعضو عادي والتأكد أنه غير محظور؛ لا يحتاج أن يكون مشرفاً."
    )
