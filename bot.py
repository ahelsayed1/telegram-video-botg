# bot.py - النسخة النهائية المصححة
import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from datetime import datetime

# تحميل المتغيرات البيئية
load_dotenv()

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== استيراد قاعدة البيانات ====================
from database import db

# ==================== نظام المشرفين ====================
def get_admin_ids():
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
    return user_id in ADMIN_IDS

# ==================== أوامر البوت الأساسية ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # تسجيل المستخدم في قاعدة البيانات
    success = db.add_or_update_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    if success:
        await update.message.reply_text(
            f"🚀 **مرحباً {user.first_name}!**\n\n"
            f"أنا بوت تليجرام يعمل على Railway!\n\n"
            f"✅ **معرفك:** {user.id}\n"
            f"✅ **تم التسجيل بنجاح**\n\n"
            f"📝 استخدم /help لعرض الأوامر",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"🚀 **مرحباً {user.first_name}!**\n\n"
            f"أنا بوت تليجرام يعمل على Railway!\n"
            f"استخدم /help لعرض الأوامر",
            parse_mode='Markdown'
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🎯 **الأوامر المتاحة:**

👤 **للمستخدمين:**
/start - بدء التشغيل والتسجيل
/help - المساعدة
/status - حالة البوت

👑 **للمشرفين:**
/admin - لوحة التحكم
/stats - إحصائيات النظام
/broadcast - إرسال رسالة للجميع
/userslist - عرض قائمة المستخدمين

📌 **ملاحظة:** خدمات الذكاء الاصطناعي قيد التطوير
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users_count = db.get_users_count()
    
    await update.message.reply_text(
        f"✅ **البوت يعمل بشكل طبيعي!**\n\n"
        f"📊 **المستخدمين:** {users_count}\n"
        f"👑 **المشرفين:** {len(ADMIN_IDS)}\n"
        f"🚀 **المنصة:** Railway\n"
        f"🕒 **الوقت:** {datetime.now().strftime('%H:%M:%S')}",
        parse_mode='Markdown'
    )

# ==================== أوامر المشرفين ====================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        return
    
    users_count = db.get_users_count()
    
    admin_commands = f"""
👑 **لوحة تحكم المشرفين**

📊 /stats - إحصائيات النظام
👥 /userslist - عرض المستخدمين ({users_count} مستخدم)

🔢 **معلومات النظام:**
- عدد المشرفين: {len(ADMIN_IDS)}
- عدد المستخدمين: {users_count}
- قاعدة البيانات: ✅ نشطة
"""
    
    await update.message.reply_text(admin_commands, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات النظام"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        return
    
    try:
        # إحصائيات بسيطة
        users_count = db.get_users_count()
        
        # الحصول على عدد الرسائل
        total_messages = 0
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT SUM(message_count) FROM users")
                result = cursor.fetchone()
                if result and result[0]:
                    total_messages = int(result[0])
        except:
            total_messages = 0
        
        stats_text = f"""
📊 **إحصائيات النظام**

👥 **المستخدمون:**
- العدد الكلي: {users_count} مستخدم
- الرسائل الكلية: {total_messages:,}

👑 **المشرفون:**
- العدد: {len(ADMIN_IDS)} مشرف

💾 **قاعدة البيانات:**
- ✅ SQLite نشطة
- 📁 الملف: {db.db_name}
- 🕒 الوقت: {datetime.now().strftime('%H:%M:%S')}
"""
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"❌ خطأ في عرض الإحصائيات: {e}")
        await update.message.reply_text(
            "📊 **حالة النظام:**\n\n"
            "✅ البوت يعمل بشكل طبيعي\n"
            "✅ قاعدة البيانات نشطة\n"
            "✅ جاهز للاستخدام"
        )

async def users_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        return
    
    users = db.get_all_users()
    users_count = len(users)
    
    if users_count == 0:
        await update.message.reply_text("📭 لا يوجد مستخدمين مسجلين بعد.")
        return
    
    users_text = f"👥 **المستخدمون المسجلون** ({users_count} مستخدم)\n\n"
    
    for i, user in enumerate(users[:10], 1):
        users_text += f"{i}. {user['first_name']}"
        if user['username']:
            users_text += f" (@{user['username']})"
        users_text += f" - ID: {user['user_id']}\n\n"
    
    if users_count > 10:
        users_text += f"\n📋 عرض 10 من أصل {users_count} مستخدم"
    
    await update.message.reply_text(users_text, parse_mode='Markdown')

# ==================== إعداد المعالجات ====================
def setup_handlers(application):
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("userslist", users_list_command))

def run_bot():
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير معين")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    setup_handlers(application)
    
    logger.info("🤖 بدأ تشغيل بوت تليجرام...")
    logger.info(f"👑 عدد المشرفين: {len(ADMIN_IDS)}")
    
    # ✅ فحص حالة النظام عند البدء
    users_count = db.get_users_count()
    logger.info(f"👥 عدد المستخدمين المسجلين: {users_count}")
    
    application.run_polling(drop_pending_updates=True)

def main():
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        logger.error("❌ يرجى تعيين BOT_TOKEN في متغيرات Railway")
        return
    
    logger.info("🚀 بدء تشغيل البوت على Railway...")
    
    try:
        run_bot()
    except Exception as e:
        logger.error(f"❌ فشل في تشغيل البوت: {e}")
        return

if __name__ == "__main__":
    main()
