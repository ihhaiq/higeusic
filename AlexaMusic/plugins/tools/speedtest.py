import asyncio

import speedtest
from pyrogram import filters

from strings import get_command
from AlexaMusic import app
from AlexaMusic.misc import SUDOERS

SPEEDTEST_COMMAND = get_command("SPEEDTEST_COMMAND")


async def testspeed(message):
    try:
        test = speedtest.Speedtest()
        test.get_best_server()

        await message.edit_text("⏳ جاري قياس سرعة التنزيل...")
        download = test.download()

        await message.edit_text("⏳ جاري قياس سرعة الرفع...")
        upload = test.upload()

        result = test.results.dict()
        result["download"] = download
        result["upload"] = upload
        return result
    except Exception as error:
        await message.edit_text(f"تعذر إجراء اختبار السرعة: {error}")
        return None


@app.on_message(filters.command(SPEEDTEST_COMMAND) & SUDOERS)
async def speedtest_function(client, message):
    status = await message.reply_text("⏳ جاري بدء اختبار السرعة...")
    result = await testspeed(status)
    if not result:
        return

    download_mbps = result["download"] / 1_000_000
    upload_mbps = result["upload"] / 1_000_000
    ping = result.get("ping", 0)
    server = result.get("server") or {}
    client_data = result.get("client") or {}

    output = (
        "<b>نتيجة اختبار السرعة</b>\n\n"
        f"<b>التنزيل:</b> {download_mbps:.2f} Mbps\n"
        f"<b>الرفع:</b> {upload_mbps:.2f} Mbps\n"
        f"<b>Ping:</b> {ping:.2f} ms\n"
        f"<b>مزود الخدمة:</b> {client_data.get('isp', 'غير معروف')}\n"
        f"<b>الخادم:</b> {server.get('name', 'غير معروف')} - "
        f"{server.get('country', 'غير معروف')}"
    )
    await asyncio.sleep(0.5)
    await status.edit_text(output)
