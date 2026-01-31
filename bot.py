import os
import logging
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# تحميل المتغيرات البيئية
load_dotenv()

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== إعدادات النظام الإداري ====================
def get_admin_ids():
    """جلب قائمة معرفات المشرفين من متغير البيئة"""
    admin_ids_str = os.getenv("ADMIN_IDS", "")
    if admin_ids_str:
        try:
            return [int(admin_id.strip()) for admin_id in admin_ids_str.split(",")]
        except ValueError:
            logger.error("❌ خطأ في تنسيق ADMIN_IDS في ملف .env")
            return []
    return []

# قائمة المشرفين (سيتم تحميلها عند التشغيل)
ADMIN_IDS = get_admin_ids()

def is_admin(user_id: int) -> bool:
    """التحقق مما إذا كان المستخدم مشرفاً"""
    result = user_id in ADMIN_IDS
    logger.info(f"🔍 التحقق من صلاحيات {user_id}: {result}")
    return result

async def admin_only(func):
    """ديكوراتور للتحقق من صلاحيات المشرف"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not is_admin(user_id):
            await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
            logger.warning(f"محاولة غير مصرح بها: المستخدم {user_id} حاول استخدام أمر المشرفين")
            return
        return await func(update, context)
    return wrapper

# ==================== HTTP Server للـ Healthcheck ====================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
            logger.debug(f"✅ Healthcheck request from {self.client_address[0]}")
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # تقليل السجلات HTTP
        pass

def run_health_server():
    """تشغيل خادم HTTP بسيط للـ healthcheck"""
    try:
        port = int(os.getenv("PORT", 8080))
        server = HTTPServer(('0.0.0.0', port), HealthHandler)
        logger.info(f"🌐 خادم الـ healthcheck يعمل على المنفذ {port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"❌ خطأ في خادم healthcheck: {e}")

# ==================== أوامر البوت الأساسية ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الترحيب بالمستخدم"""
    user = update.effective_user
    await update.message.reply_text(
        f"🚀 مرحباً {user.first_name}!\n"
        f"البوت يعمل على Railway بنجاح!\n\n"
        f"معرفك: {user.id}"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض رسالة المساعدة"""
    help_text = """
🎯 **الأوامر المتاحة:**

👤 **للمستخدمين:**
/start - بدء التشغيل
/help - عرض هذه الرسالة
/status - حالة البوت

👑 **للمشرفين:**
/admin - القائمة الإدارية
/stats - إحصائيات المستخدمين
/broadcast - إرسال رسالة للجميع (رد على رسالة)
/users - عرض عدد المستخدمين
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض حالة البوت"""
    await update.message.reply_text("✅ البوت يعمل بشكل طبيعي!")

# ==================== أوامر المشرفين ====================
@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لوحة تحكم المشرفين"""
    admin_commands = """
👑 **لوحة تحكم المشرفين**

📊 /stats - إحصائيات النظام
📢 /broadcast - إرسال رسالة للجميع (رد على رسالة)
👥 /users - عرض عدد المستخدمين
📝 /logs - عرض سجلات النظام (قريباً)
⚙️ /settings - إعدادات البوت (قريباً)

🔢 **المعلومات الحالية:**
- عدد المشرفين: {}
- نظام الإذاعة: ✅ مفعل
""".format(len(ADMIN_IDS))
    
    await update.message.reply_text(admin_commands, parse_mode='Markdown')

@admin_only
async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال رسالة لجميع المستخدمين"""
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "📝 **كيفية الاستخدام:**\n"
            "1. أرسل الرسالة التي تريد إذاعتها\n"
            "2. رد على تلك الرسالة بالأمر /broadcast"
        )
        return
    
    message_to_broadcast = update.message.reply_to_message
    
    await update.message.reply_text(
        "📢 **تم استلام الرسالة للإذاعة**\n"
        f"📝 النص: {message_to_broadcast.text[:50]}...\n\n"
        "✅ نظام الإذاعة جاهز - سيتم تفعيله مع قاعدة البيانات"
    )

@admin_only
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات النظام"""
    stats_text = """
📊 **إحصائيات النظام**

👥 **المستخدمون:**
- المشرفين: {} مشرف
- المستخدمين الكلي: قريباً مع قاعدة البيانات

⚙️ **النظام:**
- حالة البوت: ✅ يعمل
- حالة الخادم: ✅ نشط
- الإصدار: v1.0

💾 **الذاكرة:**
- الاستخدام: قريباً
""".format(len(ADMIN_IDS))
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

@admin_only
async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض معلومات المستخدمين"""
    await update.message.reply_text(
        "👥 **نظام المستخدمين:**\n\n"
        f"✅ عدد المشرفين: {len(ADMIN_IDS)}\n"
        f"📋 قائمة المشرفين: {ADMIN_IDS}\n\n"
        "🎯 **الخطوة التالية:** إضافة قاعدة بيانات SQLite"
    )

# ==================== الوظائف الرئيسية ====================
def setup_handlers(application):
    """إعداد جميع handlers"""
    
    # الأوامر الأساسية
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    
    # أوامر المشرفين
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("broadcast", broadcast_message))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("users", users_command))

def run_bot():
    """تشغيل بوت تليجرام"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير معين")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة handlers
    setup_handlers(application)
    
    # تسجيل معلومات التشغيل
    logger.info(f"🤖 بدأ تشغيل بوت تليجرام...")
    logger.info(f"👑 عدد المشرفين: {len(ADMIN_IDS)}")
    if ADMIN_IDS:
        logger.info(f"🔑 معرفات المشرفين: {ADMIN_IDS}")
    
    application.run_polling(drop_pending_updates=True)

def main():
    """الدالة الرئيسية"""
    # تسجيل معلومات البدء
    logger.info("=" * 50)
    logger.info("🚀 بدء تشغيل البوت...")
    logger.info(f"🔑 BOT_TOKEN موجود: {'✅' if os.getenv('BOT_TOKEN') else '❌'}")
    logger.info(f"👑 ADMIN_IDS: {os.getenv('ADMIN_IDS', 'غير معين')}")
    logger.info(f"✅ تم تحميل {len(ADMIN_IDS)} مشرف: {ADMIN_IDS}")
    logger.info("=" * 50)
    
    # التحقق من إعداد المشرفين
    if not ADMIN_IDS:
        logger.warning("⚠️ لا توجد معرفات مشرفين محددة. استخدم ADMIN_IDS في متغيرات Railway")
    
    # بدء خادم HTTP للـ healthcheck في thread منفصل
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    logger.info("✅ بدأ خادم الـ healthcheck في الخلفية")
    
    # تأكد من بدء الخادم (مهم لـ Railway)
    time.sleep(3)
    
    # التحقق من وجود BOT_TOKEN
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("❌ يرجى تعيين BOT_TOKEN في متغيرات Railway")
        return
    
    # بدء بوت تليجرام
    logger.info("🚀 بدء تشغيل بوت تليجرام الرئيسي...")
    run_bot()

if __name__ == "__main__":
    main()    await update.message.reply_text(
        "📢 **تم استلام الرسالة للإذاعة**\n"
        f"📝 النص: {message_to_broadcast.text[:50]}...\n\n"
        "✅ نظام الإذاعة جاهز - سيتم تفعيله مع قاعدة البيانات"
    )

@admin_only
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات النظام"""
    stats_text = """
📊 **إحصائيات النظام**

👥 **المستخدمون:**
- المشرفين: {} مشرف
- المستخدمين الكلي: قريباً مع قاعدة البيانات

⚙️ **النظام:**
- حالة البوت: ✅ يعمل
- حالة الخادم: ✅ نشط
- الإصدار: v1.0

💾 **الذاكرة:**
- الاستخدام: قريباً
""".format(len(ADMIN_IDS))
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

@admin_only
async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض معلومات المستخدمين"""
    await update.message.reply_text(
        "👥 **نظام المستخدمين:**\n\n"
        f"✅ عدد المشرفين: {len(ADMIN_IDS)}\n"
        f"📋 قائمة المشرفين: {ADMIN_IDS}\n\n"
        "🎯 **الخطوة التالية:** إضافة قاعدة بيانات SQLite"
    )

# ==================== الوظائف الرئيسية ====================
def setup_handlers(application):
    """إعداد جميع handlers"""
    
    # الأوامر الأساسية
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    
    # أوامر المشرفين
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("broadcast", broadcast_message))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("users", users_command))

def run_bot():
    """تشغيل بوت تليجرام"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير معين")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة handlers
    setup_handlers(application)
    
    # تسجيل معلومات التشغيل
    logger.info(f"🤖 بدأ تشغيل بوت تليجرام...")
    logger.info(f"👑 عدد المشرفين: {len(ADMIN_IDS)}")
    if ADMIN_IDS:
        logger.info(f"🔑 معرفات المشرفين: {ADMIN_IDS}")
    
    application.run_polling(drop_pending_updates=True)

def main():
    """الدالة الرئيسية"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        logger.error("❌ يرجى تعيين BOT_TOKEN في متغيرات Railway")
        return
    
    # تسجيل معلومات البدء
    logger.info("=" * 50)
    logger.info("🚀 بدء تشغيل البوت...")
    logger.info(f"🔑 BOT_TOKEN موجود: {'✅' if os.getenv('BOT_TOKEN') else '❌'}")
    logger.info(f"👑 ADMIN_IDS: {os.getenv('ADMIN_IDS', 'غير معين')}")
    logger.info(f"✅ تم تحميل {len(ADMIN_IDS)} مشرف: {ADMIN_IDS}")
    logger.info("=" * 50)
    
    # التحقق من إعداد المشرفين
    if not ADMIN_IDS:
        logger.warning("⚠️ لا توجد معرفات مشرفين محددة. استخدم ADMIN_IDS في متغيرات Railway")
    
    # بدء خادم HTTP للـ healthcheck في thread منفصل
    health_thread = Thread(target=run_health_server, daemon=True)
    health_thread.start()
    logger.info("✅ بدأ خادم الـ healthcheck")
    
    # بدء بوت تليجرام
    run_bot()

if __name__ == "__main__":
    main()👑 **لوحة تحكم المشرفين**

📊 /stats - إحصائيات النظام
📢 /broadcast - إرسال رسالة للجميع (رد على رسالة)
👥 /users - عرض عدد المستخدمين
📝 /logs - عرض سجلات النظام (قريباً)
⚙️ /settings - إعدادات البوت (قريباً)

🔢 **المعلومات الحالية:**
- عدد المشرفين: {}
- نظام الإذاعة: ✅ مفعل
""".format(len(ADMIN_IDS))
    
    await update.message.reply_text(admin_commands, parse_mode='Markdown')

@admin_only
async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال رسالة لجميع المستخدمين"""
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "📝 **كيفية الاستخدام:**\n"
            "1. أرسل الرسالة التي تريد إذاعتها\n"
            "2. رد على تلك الرسالة بالأمر /broadcast"
        )
        return
    
    message_to_broadcast = update.message.reply_to_message
    
    # هنا سنخزن معرفات المستخدمين لاحقاً في قاعدة بيانات
    # حالياً سنرسل رسالة تجريبية
    await update.message.reply_text(
        "📢 **وضع الإذاعة:**\n"
        "سيتم إضافة نظام تخزين المستخدمين قريباً.\n"
        "حالياً، الأمر جاهز للتشغيل مع قاعدة البيانات."
    )

@admin_only
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات النظام"""
    stats_text = """
📊 **إحصائيات النظام**

👥 **المستخدمون:**
- المشرفين: {} مشرف
- المستخدمين الكلي: قريباً مع قاعدة البيانات

⚙️ **النظام:**
- حالة البوت: ✅ يعمل
- حالة الخادم: ✅ نشط
- الإصدار: v1.0

💾 **الذاكرة:**
- الاستخدام: قريباً
""".format(len(ADMIN_IDS))
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

@admin_only
async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض معلومات المستخدمين"""
    # هذه وظيفة تجريبية - سنطورها مع قاعدة البيانات
    await update.message.reply_text(
        "👥 **نظام المستخدمين:**\n\n"
        "✅ جاهز للتكامل مع قاعدة البيانات\n"
        "📁 سيتم تخزين:\n"
        "- معرف المستخدم\n"
        "- الاسم\n"
        "- تاريخ الانضمام\n"
        "- عدد الرسائل\n\n"
        "🎯 **الخطوة التالية:** إضافة قاعدة بيانات SQLite"
    )

# ==================== الوظائف الرئيسية ====================
def setup_handlers(application):
    """إعداد جميع handlers"""
    
    # الأوامر الأساسية
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    
    # أوامر المشرفين
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("broadcast", broadcast_message))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("users", users_command))

def run_bot():
    """تشغيل بوت تليجرام"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير معين")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة handlers
    setup_handlers(application)
    
    # تسجيل معلومات التشغيل
    logger.info(f"🤖 بدأ تشغيل بوت تليجرام...")
    logger.info(f"👑 عدد المشرفين: {len(ADMIN_IDS)}")
    if ADMIN_IDS:
        logger.info(f"🔑 معرفات المشرفين: {ADMIN_IDS}")
    
    application.run_polling(drop_pending_updates=True)

def main():
    """الدالة الرئيسية"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        logger.error("❌ يرجى تعيين BOT_TOKEN في متغيرات Railway")
        return
    
    # التحقق من إعداد المشرفين
    if not ADMIN_IDS:
        logger.warning("⚠️ لا توجد معرفات مشرفين محددة. استخدم ADMIN_IDS في ملف .env")
    
    # بدء خادم HTTP للـ healthcheck في thread منفصل
    health_thread = Thread(target=run_health_server, daemon=True)
    health_thread.start()
    logger.info("✅ بدأ خادم الـ healthcheck")
    
    # بدء بوت تليجرام
    run_bot()

if __name__ == "__main__":
    main()
