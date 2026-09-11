import asyncio

from pyrogram import Client


async def generate_string_session(api_id: int, api_hash: str) -> None:
    """
    Generate a Pyrogram String Session locally.

    This script does not join channels, send messages, contact support chats,
    or store a persistent .session file. It only logs in to Telegram,
    exports the session string, prints it once, then disconnects.
    """
    app = Client(
        "session_generator",
        api_id=api_id,
        api_hash=api_hash,
        in_memory=True,
    )

    try:
        await app.start()
        string_session = await app.export_session_string()
        print("\nPyrogram String Session:\n")
        print(string_session)
        print("\nCopy the value above into Railway as STRING_SESSION.")
    finally:
        if app.is_connected:
            await app.stop()


def main() -> None:
    api_id_text = input("API ID: ").strip()
    api_hash = input("API Hash: ").strip()

    if not api_id_text.isdigit():
        raise ValueError("API ID must be a number.")
    if not api_hash:
        raise ValueError("API Hash is required.")

    asyncio.run(generate_string_session(int(api_id_text), api_hash))


if __name__ == "__main__":
    main()
