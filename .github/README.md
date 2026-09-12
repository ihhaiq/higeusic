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
- `COOKIES`: محتوى cookies.txt بصيغة Netscape كخيار احتياطي لـ YouTube.
- `YOUTUBE_POT_ENABLED`: مفعّل افتراضياً لتشغيل مزود PO Token المحلي تلقائياً.
- `YOUTUBE_POT_PROVIDER_URL`: عنوان المزود، افتراضياً `http://127.0.0.1:4416`.
- `YOUTUBE_EXTRACT_TIMEOUT`: مهلة كل محاولة استخراج بالثواني، افتراضياً `45`.
- `LONG_VIDEO_THRESHOLD_MIN` و`LONG_VIDEO_MAX_QUALITY`: حد مدة الفيديو وجودة الفيديوهات الطويلة، افتراضياً 30 دقيقة و480p.
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
bash start
```

تثبت صورة Docker مزود `bgutil-ytdlp-pot-provider` وتشغله محلياً مع البوت بلا خدمة إضافية أو إعداد يدوي. ترتيب محاولات YouTube هو PO Token ثم Cookies عند توفرها ثم Anonymous. يمكن إبقاء `COOKIES` فارغاً ما لم تحتج فيديوهات تتطلب حساباً، مثل بعض المقاطع المقيدة بالعمر.

إذا كنت تستخدم JSON بدلاً من MongoDB وتريد الاحتفاظ بالبيانات بعد إعادة النشر، اربط Railway Volume واضبط:

```text
JSON_DB_PATH=/data/database.json
```

## الأمان

- لا ترفع `BOT_TOKEN` أو `API_HASH` أو `STRING_SESSION` أو Cookies إلى GitHub.
- لا تشارك `STRING_SESSION` أو Cookies في المحادثات العامة.
- الحساب المساعد ينضم فقط إلى المحادثة المطلوبة للتشغيل، ولا توجد اشتراكات إجبارية بقنوات خارجية.
- لا يحتوي المشروع على أوامر remote eval/shell أو تحديث ذاتي وقت التشغيل.
