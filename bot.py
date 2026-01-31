import os
import logging
import asyncio
from threading import Thread
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

# ==================== HTTP Server للـ Healthcheck ====================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # تقليل السجلات HTTP
        pass

def run_health_server():
    """تشغيل خادم HTTP بسيط للـ healthcheck"""
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    logger.info(f"🌐 خادم الـ healthcheck يعمل على المنفذ {port}")
    server.serve_forever()

# ==================== نظام المشرفين ====================
def get_admin_ids():
    """جلب قائمة معرفات المشرفين من متغير البيئة"""
    admin_ids_str = os.getenv("ADMIN_IDS", "")
    if admin_ids_str:
        try:
            return [int(admin_id.strip()) for admin_id in admin_ids_str.split(",")]
        except ValueError:
            logger.error("❌ خطأ في تنسيق ADMIN_IDS")
            return []
    return []

ADMIN_IDS = get_admin_ids()

def is_admin(user_id: int) -> bool:
    """التحقق مما إذا كان المستخدم مشرفاً"""
    return user_id in ADMIN_IDS

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
/help - المساعدة
/status - حالة البوت

👑 **للمشرفين:**
/admin - لوحة التحكم
/stats - إحصائيات النظام
/broadcast - إرسال رسالة للجميع
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض حالة البوت"""
    await update.message.reply_text("✅ البوت يعمل بشكل طبيعي!")

# ==================== أوامر المشرفين ====================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لوحة تحكم المشرفين"""
    user_id = update.effective_user.id
    
    # التحقق من الصلاحيات
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        logger.warning(f"محاولة وصول غير مصرح: المستخدم {user_id} حاول استخدام /admin")
        return
    
    admin_commands = """
👑 **لوحة تحكم المشرفين**

📊 /stats - إحصائيات النظام
📢 /broadcast - إرسال رسالة للجميع (رد على رسالة)
👥 /users - عرض عدد المستخدمين

🔢 **معلومات النظام:**
- عدد المشرفين: {}
- البوت: ✅ نشط
- النظام: جاهز للتطوير
""".format(len(ADMIN_IDS))
    
    await update.message.reply_text(admin_commands, parse_mode='Markdown')
    logger.info(f"المشرف {user_id} فتح لوحة التحكم")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إحصائيات النظام"""
    user_id = update.effective_user.id
    
    # التحقق من الصلاحيات
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        return
    
    stats_text = """
📊 **إحصائيات النظام**

👑 **المشرفون:**
- العدد: {} مشرف
- القائمة: {}

⚙️ **النظام:**
- البوت: ✅ يعمل
- الخادم: ✅ نشط
- Healthcheck: ✅ شغال

🎯 **المرحلة التالية:**
- قاعدة بيانات المستخدمين
- نظام الإذاعة الكامل
- المزيد من الإحصائيات
""".format(len(ADMIN_IDS), ADMIN_IDS)
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال رسالة للجميع"""
    user_id = update.effective_user.id
    
    # التحقق من الصلاحيات
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        return
    
    # التحقق إذا كان الرد على رسالة
    if update.message.reply_to_message:
        message = update.message.reply_to_message.text or "رسالة ميديا"
        await update.message.reply_text(
            f"📢 **رسالة الإذاعة:**\n"
            f"'{message[:50]}...'\n\n"
            f"✅ جاهزة للإرسال عند تفعيل قاعدة البيانات",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "📝 **طريقة استخدام /broadcast:**\n"
            "1. أرسل الرسالة التي تريد إذاعتها\n"
            "2. رد على الرسالة بالأمر /broadcast\n\n"
            "⚠️ **ملاحظة:** نظام الإذاعة الكامل يحتاج قاعدة بيانات لتخزين المستخدمين",
            parse_mode='Markdown'
        )

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض معلومات المستخدمين"""
    user_id = update.effective_user.id
    
    # التحقق من الصلاحيات
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        return
    
    await update.message.reply_text(
        "👥 **نظام المستخدمين:**\n\n"
        "🔧 **الحالة:** قيد التطوير\n\n"
        "📋 **المخطط:**\n"
        "1. قاعدة بيانات SQLite للمستخدمين\n"
        "2. تخزين: المعرف، الاسم، تاريخ الانضمام\n"
        "3. تتبع عدد الرسائل\n"
        "4. إحصائيات مفصلة\n\n"
        "🎯 **جاري العمل عليه...**",
        parse_mode='Markdown'
    )

# ==================== الوظائف الرئيسية ====================
def run_bot():
    """تشغيل بوت تليجرام"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير معين")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة handlers الأساسية
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    
    # إضافة handlers المشرفين
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("users", users_command))
    
    # تسجيل معلومات التشغيل
    logger.info(f"🤖 بدأ تشغيل بوت تليجرام...")
    logger.info(f"👑 عدد المشرفين: {len(ADMIN_IDS)}")
    if ADMIN_IDS:
        logger.info(f"🔑 معرفات المشرفين: {ADMIN_IDS}")
    else:
        logger.warning("⚠️ لا توجد معرفات مشرفين! استخدم ADMIN_IDS في متغيرات Railway")
    
    application.run_polling(drop_pending_updates=True)

def main():
    """الدالة الرئيسية"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        logger.error("❌ يرجى تعيين BOT_TOKEN في متغيرات Railway")
        return
    
    # بدء خادم HTTP للـ healthcheck في thread منفصل
    health_thread = Thread(target=run_health_server, daemon=True)
    health_thread.start()
    logger.info("✅ بدأ خادم الـ healthcheck")
    
    # بدء بوت تليجرام
    run_bot()

if __name__ == "__main__":
    main()
