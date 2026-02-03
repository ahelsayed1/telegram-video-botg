# bot.py - النسخة النهائية مع دعم المحادثة الذكية
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

# ==================== استيراد مدير المحادثة ====================
from ai_chat_only import ChatManager

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

# إنشاء كائن المحادثة
chat_manager = ChatManager(db)

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
    
    welcome_msg = f"""
🚀 **مرحباً {user.first_name}!**

أنا بوت تليجرام مع **محادثة ذكية**! 🤖

✨ **المميزات:**
💬 محادثة ذكية مع `/chat`
📊 إحصائيات استخدام مع `/mystats`
👑 نظام إدارة متكامل

🔍 **معرفك:** `{user.id}`
✅ **الحالة:** مسجل في النظام

📝 استخدم `/help` لعرض جميع الأوامر
"""
    
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🎯 **أوامر البوت المتاحة:**

🤖 **المحادثة الذكية:**
`/chat <رسالتك>` - محادثة مع المساعد الذكي
`/mystats` - إحصائيات استخدامك

👤 **الأوامر العامة:**
`/start` - بدء استخدام البوت
`/help` - عرض هذه الرسالة
`/status` - حالة البوت والخدمات

👑 **للمشرفين:**
`/admin` - لوحة التحكم
`/stats` - إحصائيات النظام
`/userslist` - قائمة المستخدمين

💡 **نصائح:**
- استخدم `/chat` لبدء محادثة
- يمكنك الرد على رسائل البوت
- النظام يدعم العربية بطلاقة
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض حالة البوت"""
    users_count = db.get_users_count()
    chat_status = chat_manager.get_status()
    
    status_text = f"""
✅ **حالة البوت والخدمات**

🤖 **المحادثة الذكية:**
💬 الحالة: {chat_status['status']}
🔄 الإصدار: {chat_status['version']}

📊 **المعلومات:**
👥 المستخدمين: {users_count}
👑 المشرفين: {len(ADMIN_IDS)}
🕒 الوقت: {datetime.now().strftime('%H:%M:%S')}

🚀 **جميع الخدمات تعمل بشكل طبيعي**
"""
    
    await update.message.reply_text(status_text, parse_mode='Markdown')

# ==================== أوامر المحادثة الذكية ====================
async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """محادثة مع المساعد الذكي"""
    user_id = update.effective_user.id
    user_message = ' '.join(context.args) if context.args else ""
    
    if not user_message:
        await update.message.reply_text(
            "💬 **المحادثة الذكية**\n\n"
            "اكتب رسالتك بعد الأمر:\n"
            "`/chat مرحباً، كيف حالك؟`\n\n"
            "💡 **أمثلة:**\n"
            "• `/chat ما اسمك؟`\n"
            "• `/chat كيف حالك؟`\n"
            "• `/chat أخبرني نكتة`\n"
            "• `/chat ساعدني في...`",
            parse_mode='Markdown'
        )
        return
    
    # إظهار رسالة الانتظار
    wait_msg = await update.message.reply_text("🤔 **جاري التفكير...**")
    
    try:
        # استخدام المحادثة الذكية
        response = await chat_manager.chat(user_id, user_message)
        
        # إرسال الرد
        await update.message.reply_text(
            f"🤖 **المساعد الذكي:**\n\n{response}",
            parse_mode='Markdown'
        )
        
        # حذف رسالة الانتظار
        await wait_msg.delete()
        
    except Exception as e:
        logger.error(f"❌ Chat error: {e}")
        await update.message.reply_text(
            "⚠️ **حدث خطأ أثناء المحادثة**\n"
            "حاول مرة أخرى أو جرب سؤالاً مختلفاً."
        )

async def my_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إحصائيات استخدامي"""
    user_id = update.effective_user.id
    
    stats = chat_manager.get_user_stats(user_id)
    user_info = db.get_user(user_id)
    username = user_info['first_name'] if user_info else "مستخدم"
    
    stats_text = f"""
📊 **إحصائيات {username}**

💬 **المحادثات:**
📈 المستخدمة: {stats['chats_used']}
🎯 المتبقية: {stats['chats_remaining']}
📊 الإجمالي: {stats['daily_limit']}

🔧 **الحالة:** {stats['status']}
🆔 **المعرف:** {user_id}

🔄 **التجديد:** يومياً
"""
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

# ==================== أوامر المشرفين ====================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        return
    
    users_count = db.get_users_count()
    
    admin_text = f"""
👑 **لوحة تحكم المشرفين**

🤖 **المحادثة الذكية:**
💬 الحالة: ✅ نشطة
✨ المميزات: جاهزة

📊 **الإحصائيات:**
👥 المستخدمين: {users_count}
👑 المشرفين: {len(ADMIN_IDS)}

🔧 **الأوامر:**
`/stats` - إحصائيات النظام
`/userslist` - قائمة المستخدمين
"""
    
    await update.message.reply_text(admin_text, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إحصائيات النظام"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        return
    
    users_count = db.get_users_count()
    
    stats_text = f"""
📊 **إحصائيات النظام**

👥 **المستخدمون:**
👤 العدد: {users_count} مستخدم

🤖 **المحادثة الذكية:**
💬 الحالة: ✅ نشطة
✨ الإصدار: 1.0

👑 **المشرفون:**
👑 العدد: {len(ADMIN_IDS)} مشرف

🕒 **آخر تحديث:** {datetime.now().strftime('%H:%M:%S')}
"""
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

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
    
    for i, user in enumerate(users[:5], 1):
        users_text += f"{i}. **{user['first_name']}**"
        if user['username']:
            users_text += f" (@{user['username']})"
        users_text += f"\n🆔 المعرف: `{user['user_id']}`\n"
        users_text += f"📅 انضم: {user.get('join_date', '')[:10] if user.get('join_date') else 'غير معروف'}\n\n"
    
    if users_count > 5:
        users_text += f"📋 ... وعرض {users_count - 5} مستخدم آخر"
    
    await update.message.reply_text(users_text, parse_mode='Markdown')

# ==================== معالجة الردود ====================
async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الردود على رسائل البوت"""
    user_message = update.message.text
    
    # تجاهل الأوامر
    if user_message.startswith('/'):
        return
    
    # إذا كان رداً على رسالة البوت
    if update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id:
        wait_msg = await update.message.reply_text("💭 **جاري الرد...**")
        
        try:
            user_id = update.effective_user.id
            response = await chat_manager.chat(user_id, user_message)
            
            await update.message.reply_text(
                f"🤖 **المساعد الذكي:**\n\n{response}",
                parse_mode='Markdown'
            )
            
            await wait_msg.delete()
            
        except Exception as e:
            logger.error(f"❌ Reply error: {e}")
            await update.message.reply_text("⚠️ حدث خطأ في الرد. حاول استخدام `/chat` مباشرة.")

# ==================== إعداد المعالجات ====================
def setup_handlers(application):
    """إعداد معالجات الأوامر"""
    
    # الأوامر الأساسية
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    
    # أوامر المحادثة
    application.add_handler(CommandHandler("chat", chat_command))
    application.add_handler(CommandHandler("mystats", my_stats_command))
    
    # أوامر المشرفين
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("userslist", users_list_command))
    
    # معالجة الردود
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_reply
    ), group=1)

def run_bot():
    """تشغيل البوت"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير معين")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    setup_handlers(application)
    
    logger.info("🤖 بدأ تشغيل بوت تليجرام...")
    logger.info(f"👑 عدد المشرفين: {len(ADMIN_IDS)}")
    
    users_count = db.get_users_count()
    logger.info(f"👥 عدد المستخدمين: {users_count}")
    
    application.run_polling(drop_pending_updates=True)

def main():
    """الدالة الرئيسية"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        logger.error("❌ يرجى تعيين BOT_TOKEN")
        return
    
    logger.info("🚀 بدء تشغيل البوت...")
    
    try:
        run_bot()
    except Exception as e:
        logger.error(f"❌ فشل في تشغيل البوت: {e}")

if __name__ == "__main__":
    main()
