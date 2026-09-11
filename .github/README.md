# higeusic

بوت Telegram لتشغيل الصوت والفيديو داخل المكالمات الصوتية في المجموعات والقنوات.

## التشغيل

يدعم البوت التشغيل في المجموعات، ويدعم أيضاً أمر `/play` و`/vplay` مباشرة من منشور القناة لتشغيل المحتوى في مكالمة القناة نفسها.

### المتغيرات المطلوبة

- `API_ID`
- `API_HASH`
- `BOT_TOKEN`
- `OWNER_ID`
- `LOG_GROUP_ID`
- `MUSIC_BOT_NAME`
- `STRING_SESSION`

### متغيرات اختيارية

- `MONGO_DB_URI`: عند عدم توفره يستخدم البوت قاعدة JSON المحلية.
- `JSON_DB_PATH`: يفضل ضبطه على مسار Railway Volume مثل `/data/database.json`.
- `COOKIES`: محتوى cookies.txt بصيغة Netscape لاستخدامه مع YouTube.
- `SPOTIFY_CLIENT_ID` و`SPOTIFY_CLIENT_SECRET`.
- `START_IMG_URL` وبقية متغيرات صور الواجهة.

## إنشاء جلسة المساعد

استخدم الملف المحلي:

```bash
python genstring.py
```

مولد الجلسة لا ينضم إلى أي قناة ولا يرسل الجلسة إلى أي جهة. بعد إنشائها ضع القيمة في `STRING_SESSION`.

## Railway

المشروع يحتوي `Dockerfile` ويبدأ عبر:

```bash
python3 -m AlexaMusic
```

إذا كنت تستخدم JSON بدلاً من MongoDB وتريد الاحتفاظ بالبيانات بعد إعادة النشر، اربط Railway Volume واضبط:

```text
JSON_DB_PATH=/data/database.json
```

## الأمان

- لا ترفع `BOT_TOKEN` أو `API_HASH` أو `STRING_SESSION` أو Cookies إلى GitHub.
- لا تشارك `STRING_SESSION` أو Cookies في المحادثات العامة.
- الحساب المساعد ينضم فقط إلى المحادثة المطلوبة للتشغيل، ولا توجد اشتراكات إجبارية بقنوات خارجية.
- لا يحتوي المشروع على أوامر remote eval/shell أو تحديث ذاتي وقت التشغيل.
