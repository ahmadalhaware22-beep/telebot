from telegram import Update, ReplyKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import json, os
import io
from pathlib import Path

# مسار ملف الإعدادات
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "content.json"
USERS_PATH = BASE_DIR / "users.json"

# الصفوف
GRADES = ["الصف السابع", "الصف الثامن", "الصف التاسع", "الصف العاشر", "الصف الحادي عشر", "البكالوريا"]

# الخيارات الرئيسية
MAIN_OPTIONS = ["📘 شرح المنهاج", "📝 أوراق عمل", "📚 كتب + دليل", "❓ أسئلة الدورات"]

# الأقسام
SECTIONS = ["الجبر", "الهندسة"]

# عدد الوحدات والدروس الافتراضي
UNITS_RANGE = range(1, 6)
LESSONS_RANGE = range(1, 6)

# تحميل/حفظ المستخدمين
def load_users():
    if USERS_PATH.exists():
        with open(USERS_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_users(users):
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

# تحميل المحتوى من ملف json
def load_content():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

# حفظ المحتوى
def save_content(data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ✅ التحقق إذا الصف مفعل (فيه محتوى) – تعديل مهم
def is_grade_enabled(grade: str) -> bool:
    content = load_content()
    grade = grade.strip()
    # نتحقق من أول جزء من المفتاح ونسمح بأي اختلاف بعده
    for k in content.keys():
        if k.strip().startswith(grade):
            return True
    return False

# إرسال المحتوى مع تخزين file_id (يدعم أكثر من ملف)
async def send_payload(update: Update, payload: dict):
    txt = payload.get("text")
    if txt:
        await update.message.reply_text(str(txt))

    lnk = payload.get("link")
    if lnk:
        await update.message.reply_text(str(lnk))

    # استخراج أول file_id إذا كان مخزن كقائمة
    video_id = payload.get("video_id")
    if isinstance(video_id, list):
        video_id = video_id[0]

    document_id = payload.get("document_id")
    if isinstance(document_id, list):
        document_id = document_id[0]

    file_id = payload.get("file_id")
    if isinstance(file_id, list):
        file_id = file_id[0]

    try:
        if video_id:
            await update.message.reply_video(video_id)
            return None
        elif document_id:
            await update.message.reply_document(document_id)
            return None
        elif file_id:
            await update.message.reply_document(file_id)
            return None
        else:
            local = payload.get("file")
            if local:
                files = local if isinstance(local, list) else [local]
                for idx, path in enumerate(files, start=1):
                    if os.path.exists(path):
                        ext = os.path.splitext(path)[1].lower()
                        filename = os.path.basename(path)

                        if files.count(path) > 1:
                            filename = f"{os.path.splitext(filename)[0]}({idx}){ext}"

                        if ext in [".mp4", ".mov", ".mkv"]:
                            with open(path, "rb") as f:
                                msg = await update.message.reply_video(f)
                                fid = msg.video.file_id if msg and msg.video else None
                                if fid:
                                    return ("video_id", fid)
                        elif ext in [".jpg", ".jpeg", ".png", ".gif"]:
                            with open(path, "rb") as f:
                                msg = await update.message.reply_photo(f)
                                fid = msg.photo[-1].file_id if msg and msg.photo else None
                                if fid:
                                    return ("file_id", fid)
                        else:
                            with open(path, "rb") as f:
                                msg = await update.message.reply_document(InputFile(f, filename=filename))
                                fid = msg.document.file_id if msg and msg.document else None
                                if fid:
                                    return ("document_id", fid)
                    else:
                        await update.message.reply_text(f"⚠️ الملف غير موجود: {path}")
    except Exception as e:
        await update.message.reply_text(f"⚠️ تعذر إرسال الملف. السبب: {e}")

    return None

async def deliver_content(update: Update, key: str):
    content = load_content()
    payload = content.get(key)
    if not payload:
        await update.message.reply_text("⚠️ لا يوجد محتوى لهذا الخيار حالياً.")
        return

    result = await send_payload(update, payload)
    if result:
        id_kind, fid = result
        if id_kind in payload:
            if isinstance(payload[id_kind], list):
                if fid not in payload[id_kind]:
                    payload[id_kind].append(fid)
            else:
                if payload[id_kind] != fid:
                    payload[id_kind] = [payload[id_kind], fid]
        else:
            payload[id_kind] = fid

        content[key] = payload
        save_content(content)

    hist = update.message.chat_data.get("history", [])
    if hist and len(hist) >= 4 and hist[1] == "📘 شرح المنهاج":
        unit = hist[3]
        await update.message.reply_text(
            f"📖 اختر درس من {unit}:",
            reply_markup=kb_lessons(unit)
        )

#ثابت هنا

# بدء البوت مع تخزين المستخدمين
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    users = load_users()
    if user_id not in users:
        users.append(user_id)
        save_users(users)

    context.user_data.clear()
    reply_markup = ReplyKeyboardMarkup([[x] for x in GRADES], resize_keyboard=True)
    await update.message.reply_text("اختر الصف:", reply_markup=reply_markup)

# الرجوع خطوة
async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hist = context.user_data.get("history", [])
    if hist:
        hist.pop()
    context.user_data["history"] = hist

    if not hist:
        return await start(update, context)

    if len(hist) == 1:
        return await start(update, context)

    if len(hist) == 2:
        parent = hist[1]
        if parent == "❓ أسئلة الدورات":
            await update.message.reply_text("🗓 اختر سنة الدورة:", reply_markup=kb_years())
        else:
            await update.message.reply_text("📂 اختر نوع المحتوى:", reply_markup=kb(MAIN_OPTIONS))
        return

    parent = hist[1]
    if len(hist) == 3:
        if parent in ["📘 شرح المنهاج", "📝 أوراق عمل", "📚 كتب + دليل"]:
            await update.message.reply_text("🏫 اختر القسم:", reply_markup=kb(SECTIONS))
        elif parent == "❓ أسئلة الدورات":
            await update.message.reply_text("🗓 اختر سنة الدورة:", reply_markup=kb_years())
        return

    if len(hist) == 4:
        if parent == "📘 شرح المنهاج":
            unit = hist[3]
            await update.message.reply_text(f"📖 اختر درس من {unit}:", reply_markup=kb_lessons(unit))
        elif parent == "📝 أوراق عمل":
            key = ".".join(hist)
            return await deliver_content(update, key)
        elif parent == "📚 كتب + دليل":
            await update.message.reply_text("📚 اختر: الكتاب أو الدليل", reply_markup=kb(["الكتاب", "الدليل"]))
        return

    if len(hist) == 5:
        key = ".".join(hist)
        return await deliver_content(update, key)

# التعامل مع الرسائل
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    hist = context.user_data.get("history", [])

    if text == "⏮ العودة للبداية":
        return await start(update, context)
    if text == "🔙 رجوع":
        return await go_back(update, context)

    if text in GRADES:
        context.user_data["history"] = [text]
        if not is_grade_enabled(text):
            return await update.message.reply_text("🚫 المحتوى غير متاح لهذا الصف حالياً.")
        await update.message.reply_text("📂 اختر نوع المحتوى:", reply_markup=kb(MAIN_OPTIONS))
        return

    if hist and len(hist) == 1 and text in MAIN_OPTIONS:
        hist.append(text)
        context.user_data["history"] = hist
        parent = text
        if parent in ["📘 شرح المنهاج", "📝 أوراق عمل", "📚 كتب + دليل"]:
            await update.message.reply_text("🏫 اختر القسم:", reply_markup=kb(SECTIONS))
        elif parent == "❓ أسئلة الدورات":
            await update.message.reply_text("🗓 اختر سنة الدورة:", reply_markup=kb_years())
        return

    if hist and len(hist) == 2:
        parent = hist[1]
        if parent in ["📘 شرح المنهاج", "📝 أوراق عمل", "📚 كتب + دليل"] and text in SECTIONS:
            hist.append(text)
            context.user_data["history"] = hist
            if parent == "📘 شرح المنهاج":
                await update.message.reply_text(f"📚 اختر وحدة من قسم {text}:", reply_markup=kb_units())
            elif parent == "📝 أوراق عمل":
                await update.message.reply_text(f"📚 اختر وحدة من قسم {text}:", reply_markup=kb_units())
            elif parent == "📚 كتب + دليل":
                await update.message.reply_text(f"📚 اختر من قسم {text}:", reply_markup=kb(["الكتاب", "الدليل"]))
            return

    if hist and len(hist) == 3:
        parent = hist[1]
        if parent in ["📘 شرح المنهاج", "📝 أوراق عمل"] and text.startswith("الوحدة"):
            hist.append(text)
            context.user_data["history"] = hist
            if parent == "📘 شرح المنهاج":
                await update.message.reply_text(f"📖 اختر درس من {text}:", reply_markup=kb_lessons(text))
            elif parent == "📝 أوراق عمل":
                key = ".".join(hist)
                return await deliver_content(update, key)
            return
        elif parent == "📚 كتب + دليل" and text in ["الكتاب", "الدليل"]:
            hist.append(text)
            context.user_data["history"] = hist
            key = ".".join(hist)
            return await deliver_content(update, key)

    if hist and len(hist) == 4 and hist[1] == "📘 شرح المنهاج" and text.startswith("الدرس"):
        hist.append(text)
        context.user_data["history"] = hist
        key = ".".join(hist)
        return await deliver_content(update, key)

    # التحقق النهائي: إذا فيه محتوى أو لا
    tentative_key = ".".join(hist + [text]) if hist else text
    payload = load_content().get(tentative_key)

    if payload:
        context.user_data["history"] = hist + [text] if hist else [text]
        return await deliver_content(update, tentative_key)
    else:
        return await update.message.reply_text("⚠️ لا يوجد محتوى لهذا الخيار حالياً.")
# أمر إداري لعرض محتوى content.json

async def debug_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    content = load_content()
    text = json.dumps(content, ensure_ascii=False, indent=2)
    file_obj = io.BytesIO(text.encode("utf-8"))
    file_obj.name = "content.json"
    await update.message.reply_document(file_obj)

# تشغيل البوت
def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("❌ BOT_TOKEN غير موجود في Environment Variables")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_handler(CommandHandler("debug_content", debug_content))
    app.run_polling()

if __name__ == "__main__":
    main()












