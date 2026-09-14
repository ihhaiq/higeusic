# Copyright (C) 2025 by Alexa_Help @ Github, < https://github.com/TheTeamAlexa >
# Subscribe On YT < Jankari Ki Duniya >. All rights reserved. © Alexa © Yukki.

"""
TheTeamAlexa is a project of Telegram bots with variety of purposes.
Copyright (c) 2021 ~ Present Team Alexa <https://github.com/TheTeamAlexa>

This program is free software: you can redistribute it and can modify
as you want or you can collabe if you have new ideas.
"""

import os
import re
import textwrap

import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from config import YOUTUBE_IMG_URL


def _duration_seconds(metadata):
    value = metadata.get("duration")
    if value not in (None, "", False):
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            pass
    parts = str(metadata.get("duration_min") or "").split(":")
    try:
        total = 0
        for part in parts:
            total = total * 60 + int(part)
        return max(0, total)
    except (TypeError, ValueError):
        return 0


async def _thumbnail_metadata(videoid, metadata=None):
    if metadata is None:
        from AlexaMusic import YouTube

        metadata = await YouTube.info(
            f"https://www.youtube.com/watch?v={videoid}"
        )
    title = re.sub(
        r"\W+", " ", metadata.get("title") or "Unsupported Title"
    ).title()
    duration_seconds = _duration_seconds(metadata)
    duration = (
        f"{duration_seconds // 60}:{duration_seconds % 60:02d}"
        if duration_seconds
        else "Live"
    )
    thumbnail = (
        metadata.get("thumbnail")
        or metadata.get("thumb")
        or YOUTUBE_IMG_URL
    )
    views = f"{int(metadata.get('view_count') or 0):,}"
    return title, duration, thumbnail, views


def changeImageSize(maxWidth, maxHeight, image):
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]
    newWidth = int(widthRatio * image.size[0])
    newHeight = int(heightRatio * image.size[1])
    return image.resize((newWidth, newHeight))


async def gen_thumb(videoid, metadata=None):
    if os.path.isfile(f"cache/{videoid}.png"):
        return f"cache/{videoid}.png"

    try:
        title, duration, thumbnail, views = await _thumbnail_metadata(
            videoid,
            metadata,
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    f = await aiofiles.open(f"cache/thumb{videoid}.png", mode="wb")
                    await f.write(await resp.read())
                    await f.close()

        youtube = Image.open(f"cache/thumb{videoid}.png")
        image1 = changeImageSize(1280, 720, youtube)
        image2 = image1.convert("RGBA")
        background = image2.filter(filter=ImageFilter.GaussianBlur(15))
        enhancer = ImageEnhance.Brightness(background)
        background = enhancer.enhance(0.6)
        Xcenter = youtube.width / 2
        Ycenter = youtube.height / 2
        x1 = Xcenter - 250
        y1 = Ycenter - 250
        x2 = Xcenter + 250
        y2 = Ycenter + 250
        logo = youtube.crop((x1, y1, x2, y2))
        logo.thumbnail((520, 520), Image.LANCZOS)
        logo = ImageOps.expand(logo, border=15, fill="white")
        background.paste(logo, (50, 100))
        draw = ImageDraw.Draw(background)
        font = ImageFont.truetype("assets/font2.ttf", 40)
        font2 = ImageFont.truetype("assets/font2.ttf", 70)
        arial = ImageFont.truetype("assets/font2.ttf", 30)
        name_font = ImageFont.truetype("assets/font.ttf", 30)
        para = textwrap.wrap(title, width=30)
        j = 0
        draw.text((5, 5), "Alexa MusicBot", fill="white", font=name_font)
        draw.text(
            (600, 150),
            "NOW PLAYING",
            fill="white",
            stroke_width=3,
            stroke_fill="black",
            font=font2,
        )
        for line in para:
            if j == 1:
                j += 1
                draw.text(
                    (600, 340),
                    f"{line}",
                    fill="white",
                    stroke_width=1,
                    stroke_fill="black",
                    font=font,
                )
            if j == 0:
                j += 1
                draw.text(
                    (600, 280),
                    f"{line}",
                    fill="white",
                    stroke_width=1,
                    stroke_fill="black",
                    font=font,
                )
        draw.text(
            (600, 450),
            f"Views : {views[:23]}",
            (255, 255, 255),
            font=arial,
        )
        draw.text(
            (600, 500),
            f"Duration : {duration[:23]} Mins",
            (255, 255, 255),
            font=arial,
        )
        draw.text((600, 550), "Owner : Jankari Ki Duniya", (255, 255, 255), font=arial)
        try:
            os.remove(f"cache/thumb{videoid}.png")
        except Exception:
            pass
        background.save(f"cache/{videoid}.png")
        return f"cache/{videoid}.png"
    except Exception:
        return YOUTUBE_IMG_URL


async def gen_qthumb(videoid, metadata=None):
    if os.path.isfile(f"cache/{videoid}.png"):
        return f"cache/{videoid}.png"

    try:
        title, duration, thumbnail, views = await _thumbnail_metadata(
            videoid,
            metadata,
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    f = await aiofiles.open(f"cache/thumb{videoid}.png", mode="wb")
                    await f.write(await resp.read())
                    await f.close()

        youtube = Image.open(f"cache/thumb{videoid}.png")
        image1 = changeImageSize(1280, 720, youtube)
        image2 = image1.convert("RGBA")
        background = image2.filter(filter=ImageFilter.GaussianBlur(15))
        enhancer = ImageEnhance.Brightness(background)
        background = enhancer.enhance(0.6)
        Xcenter = youtube.width / 2
        Ycenter = youtube.height / 2
        x1 = Xcenter - 250
        y1 = Ycenter - 250
        x2 = Xcenter + 250
        y2 = Ycenter + 250
        logo = youtube.crop((x1, y1, x2, y2))
        logo.thumbnail((520, 520), Image.LANCZOS)
        logo = ImageOps.expand(logo, border=15, fill="white")
        background.paste(logo, (50, 100))
        draw = ImageDraw.Draw(background)
        font = ImageFont.truetype("assets/font2.ttf", 40)
        font2 = ImageFont.truetype("assets/font2.ttf", 70)
        arial = ImageFont.truetype("assets/font2.ttf", 30)
        name_font = ImageFont.truetype("assets/font.ttf", 30)
        para = textwrap.wrap(title, width=30)
        j = 0
        draw.text((5, 5), "Alexa MusicBot", fill="white", font=name_font)
        draw.text(
            (600, 150),
            "ADDED THIS SONG IN QUEUE",
            fill="white",
            stroke_width=3,
            stroke_fill="black",
            font=font2,
        )
        for line in para:
            if j == 1:
                j += 1
                draw.text(
                    (600, 340),
                    f"{line}",
                    fill="white",
                    stroke_width=1,
                    stroke_fill="black",
                    font=font,
                )
            if j == 0:
                j += 1
                draw.text(
                    (600, 280),
                    f"{line}",
                    fill="white",
                    stroke_width=1,
                    stroke_fill="black",
                    font=font,
                )
        draw.text(
            (600, 450),
            f"Views : {views[:23]}",
            (255, 255, 255),
            font=arial,
        )
        draw.text(
            (600, 500),
            f"Duration : {duration[:23]} Mins",
            (255, 255, 255),
            font=arial,
        )
        draw.text((600, 550), "Owner : Jankari Ki Duniya", (255, 255, 255), font=arial)
        try:
            os.remove(f"cache/thumb{videoid}.png")
        except Exception:
            pass
        background.save(f"cache/{videoid}.png")
        return f"cache/{videoid}.png"
    except Exception:
        return YOUTUBE_IMG_URL
