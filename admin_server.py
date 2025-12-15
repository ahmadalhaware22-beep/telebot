# ======================= نقطة البداية: admin_server.py =======================

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

import os, json
from pathlib import Path

app = Flask(__name__)
CORS(app, origins=["http://127.0.0.1:5500"])

# مسارات الملفات
BASE_DIR = Path(__file__).parent
CONTENT_PATH = BASE_DIR / "content.json"
UPLOAD_DIR = BASE_DIR / "uploads"
USERS_PATH = BASE_DIR / "users.json"   # ملف لتخزين المستخدمين

# إنشاء مجلد رفع الملفات إذا غير موجود
UPLOAD_DIR.mkdir(exist_ok=True)

# تحميل المحتوى من ملف json
def load_content():
    if CONTENT_PATH.exists():
        with open(CONTENT_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

# حفظ المحتوى في ملف json
def save_content(data):
    with open(CONTENT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# تحميل المستخدمين
def load_users():
    if USERS_PATH.exists():
        with open(USERS_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

# حفظ المستخدمين
def save_users(users):
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

# إضافة أو تعديل محتوى
@app.route("/manage", methods=["POST"])
def manage_content():
    key = request.form.get("key")
    text = request.form.get("text")
    link = request.form.get("link")
    file = request.files.get("file")

    if not key:
        return jsonify({"message": "❌ المفتاح غير محدد"}), 400

    content = load_content()
    payload = content.get(key, {})

    if text:
        payload["text"] = text
    if link:
        payload["link"] = link
    if file:
        filename = file.filename
        save_path = UPLOAD_DIR / filename

        # إذا الملف موجود مسبقًا، ضيف ترقيم تلقائي بدل ما يكتب فوقه
        counter = 1
        while save_path.exists():
            name, ext = os.path.splitext(filename)
            new_name = f"{name}({counter}){ext}"
            save_path = UPLOAD_DIR / new_name
            counter += 1

        file.save(save_path)

        # إذا فيه ملفات سابقة، ضيف الجديد للقائمة
        if "file" in payload:
            if isinstance(payload["file"], list):
                payload["file"].append(str(save_path))
            else:
                payload["file"] = [payload["file"], str(save_path)]
        else:
            payload["file"] = [str(save_path)]

    content[key] = payload
    save_content(content)
    return jsonify({"message": f"✅ تم حفظ المحتوى للمفتاح: {key}"}), 200

# حذف محتوى + الملفات المرتبطة به
@app.route("/manage", methods=["DELETE"])
def delete_content():
    data = request.get_json()
    key = data.get("key") if data else None

    if not key:
        return jsonify({"message": "❌ المفتاح غير محدد"}), 400

    content = load_content()
    if key in content:
        # حذف الملفات من السيرفر إذا موجودة
        files = content[key].get("file")
        if files:
            if not isinstance(files, list):
                files = [files]
            for f in files:
                try:
                    os.remove(f)
                except FileNotFoundError:
                    pass
        # حذف المفتاح من content.json
        del content[key]
        save_content(content)
        return jsonify({"message": f"🗑 تم حذف المحتوى والملفات للمفتاح: {key}"}), 200
    else:
        return jsonify({"message": "⚠️ لا يوجد محتوى لهذا المفتاح"}), 404

# إعادة ضبط البوت (تفريغ الملف + حذف الملفات)
@app.route("/reset", methods=["POST"])
def reset_bot():
    # حذف كل الملفات من مجلد uploads
    for f in UPLOAD_DIR.glob("*"):
        try:
            os.remove(f)
        except FileNotFoundError:
            pass
    # تفريغ ملف المحتوى
    save_content({})
    return jsonify({"message": "🔄 تم إعادة ضبط البوت وحذف كل المحتويات والملفات"}), 200

# API تعرض عدد المستخدمين
@app.route("/stats", methods=["GET"])
def stats():
    users = load_users()
    return jsonify({"count": len(users)})

# خدمة صفحة الإدارة مباشرة
@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "manage.html")
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)


# ======================= نقطة النهاية: admin_server.py =======================


