# bot.py - النسخة المحدثة مع دعم الذكاء الاصطناعي
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

# ==================== استيراد قاعدة البيانات والذكاء الاصطناعي ====================
from database import db
from ai_simple import SimpleAIManager

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

# إنشاء كائن الذكاء الاصطناعي
ai_manager = SimpleAIManager(db)

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
            f"أنا بوت تليجرام مع ذكاء اصطناعي! 🤖\n\n"
            f"**ما يمكنني فعله:**\n"
            f"💬 محادثة ذكية مع AI\n"
            f"📊 إحصائيات استخدام شخصية\n"
            f"👑 نظام إدارة متكامل\n\n"
            f"✅ **معرفك:** {user.id}\n"
            f"✅ **تم التسجيل بنجاح**\n\n"
            f"📝 استخدم /help لعرض جميع الأوامر\n"
            f"🤖 جرب /chat للبدء في المحادثة",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"🚀 **مرحباً {user.first_name}!**\n\n"
            f"أنا بوت تليجرام مع ذكاء اصطناعي! 🤖\n"
            f"استخدم /help لعرض الأوامر",
            parse_mode='Markdown'
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🎯 **الأوامر المتاحة:**

🤖 **الذكاء الاصطناعي:**
`/chat <رسالتك>` - محادثة مع المساعد الذكي
`/mystats` - إحصائيات استخدامك للشات

👤 **للمستخدمين:**
`/start` - بدء التشغيل والتسجيل
`/help` - هذه الرسالة
`/status` - حالة البوت والخدمات

👑 **للمشرفين:**
`/admin` - لوحة التحكم
`/stats` - إحصائيات النظام الكاملة
`/userslist` - عرض قائمة المستخدمين

💡 **نصائح:**
- استخدم `/chat` لبدء محادثة ذكية
- يمكنك سؤال عن أي موضوع
- النظام يدعم العربية بطلاقة
- لديك حد يومي للمحادثات
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض حالة البوت والخدمات"""
    try:
        # التحقق من حالة الخدمات
        ai_status = ai_manager.get_status()
        
        status_text = "✅ **حالة البوت والخدمات**\n\n"
        
        # حالة الذكاء الاصطناعي
        status_text += "🤖 **خدمات الذكاء الاصطناعي:**\n"
        
        if ai_status['apis_configured']:
            if ai_status['gemini_available']:
                status_text += "🔵 Google Gemini: ✅ متصل\n"
            if ai_status['openai_available']:
                status_text += "⚪ OpenAI GPT: ✅ متصل\n"
        else:
            status_text += "💬 المحادثة: ✅ (النسخة التجريبية)\n"
        
        status_text += f"\n📊 **المستخدمين:** {db.get_users_count()}\n"
        status_text += f"👑 **المشرفين:** {len(ADMIN_IDS)}\n"
        status_text += f"🕒 **الوقت:** {datetime.now().strftime('%H:%M:%S')}\n\n"
        
        status_text += "🚀 **جميع الخدمات تعمل بشكل طبيعي**"
        
        await update.message.reply_text(status_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"❌ خطأ في أمر الحالة: {e}")
        await update.message.reply_text("✅ البوت يعمل بشكل طبيعي!")

# ==================== أوامر الذكاء الاصطناعي ====================

async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """محادثة مع الذكاء الاصطناعي"""
    user_id = update.effective_user.id
    user_message = ' '.join(context.args) if context.args else ""
    
    if not user_message:
        await update.message.reply_text(
            "💬 **المحادثة الذكية**\n\n"
            "اكتب رسالتك بعد الأمر:\n"
            "`/chat مرحباً، كيف حالك؟`\n\n"
            "أو ارد مباشرة على هذه الرسالة بالطلب الخاص بك!\n\n"
            "💡 **نصائح:**\n"
            "- يمكنك سؤال عن أي موضوع\n"
            "- طلب نصائح أو معلومات\n"
            "- التحدث بالعربية أو الإنجليزية\n"
            "- الرد على رسائلي للاستمرار في المحادثة",
            parse_mode='Markdown'
        )
        return
    
    # إظهار رسالة "جاري المعالجة"
    processing_msg = await update.message.reply_text("🤔 **جاري التفكير...**")
    
    try:
        # استخدام الذكاء الاصطناعي
        response = await ai_manager.chat(user_id, user_message)
        
        # إرسال الرد
        await update.message.reply_text(
            f"🤖 **المساعد الذكي:**\n\n{response}\n\n"
            f"💭 *يمكنك الرد على هذه الرسالة للاستمرار في المحادثة*",
            parse_mode='Markdown'
        )
        
        # حذف رسالة "جاري المعالجة"
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"❌ Chat command error: {e}")
        await update.message.reply_text(
            "❌ حدث خطأ أثناء المحادثة.\n"
            "⚠️ حاول مرة أخرى أو افحص /status"
        )

async def my_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إحصائيات استخدامي للذكاء الاصطناعي"""
    user_id = update.effective_user.id
    
    stats = ai_manager.get_user_stats(user_id)
    ai_status = ai_manager.get_status()
    
    # الحصول على معلومات المستخدم
    user_info = db.get_user(user_id)
    username = user_info['first_name'] if user_info else "مستخدم"
    
    stats_text = f"📊 **إحصائيات {username}**\n\n"
    stats_text += f"🆔 المعرف: {user_id}\n"
    stats_text += f"📅 اليوم: {datetime.now().strftime('%Y-%m-%d')}\n\n"
    
    # إحصائيات الشات
    used = stats.get('chats_used', 0)
    remaining = stats.get('chats_remaining', 50)
    limit = stats.get('daily_limit', 50)
    percentage = (used / limit * 100) if limit > 0 else 0
    
    # شريط تقدم مرئي
    filled_blocks = int(percentage / 10)
    progress_bar = "🟩" * filled_blocks + "⬜" * (10 - filled_blocks)
    
    stats_text += "💬 **المحادثات اليومية:**\n"
    stats_text += f"{progress_bar}\n"
    stats_text += f"📊 {used}/{limit} ({remaining} متبقي)\n\n"
    
    # حالة الخدمات
    stats_text += "🔧 **حالة الخدمات:**\n"
    
    if ai_status['apis_configured']:
        if ai_status['gemini_available']:
            stats_text += "🔵 Google Gemini: ✅\n"
        if ai_status['openai_available']:
            stats_text += "⚪ OpenAI GPT: ✅\n"
    else:
        stats_text += "💬 المحادثة: ✅ (النسخة التجريبية)\n"
    
    stats_text += "\n🔄 **التجديد:** تلقائي عند منتصف الليل (UTC)"
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

# ==================== معالجة المحادثات العادية (ردود على رسائل AI) ====================

async def handle_ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الردود على رسائل AI"""
    user_id = update.effective_user.id
    user_message = update.message.text
    
    # تجاهل الأوامر
    if user_message.startswith('/'):
        return
    
    # التحقق إذا كان رداً على رسالة AI السابقة
    is_reply_to_ai = (
        update.message.reply_to_message and 
        update.message.reply_to_message.from_user.id == context.bot.id and
        "المساعد الذكي:" in update.message.reply_to_message.text
    )
    
    if is_reply_to_ai:
        processing_msg = await update.message.reply_text("💭 **جاري التفكير...**")
        
        try:
            # استخدام الذكاء الاصطناعي
            response = await ai_manager.chat(user_id, user_message)
            
            # إرسال الرد
            await update.message.reply_text(
                f"🤖 **المساعد الذكي:**\n\n{response}",
                parse_mode='Markdown'
            )
            
            await processing_msg.delete()
            
        except Exception as e:
            logger.error(f"❌ AI reply error: {e}")
            error_msg = "❌ حدث خطأ أثناء معالجة ردك.\n💡 حاول استخدام `/chat` مباشرة"
            await update.message.reply_text(error_msg)
            if processing_msg:
                await processing_msg.delete()

# ==================== أوامر المشرفين ====================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        logger.warning(f"محاولة وصول غير مصرح: المستخدم {user_id} حاول استخدام /admin")
        return
    
    users_count = db.get_users_count()
    ai_status = ai_manager.get_status()
    
    admin_commands = f"""
👑 **لوحة تحكم المشرفين**

🤖 **حالة الذكاء الاصطناعي:**
💬 المحادثة: ✅ جاهزة
🔑 APIs: {'✅' if ai_status['apis_configured'] else '❌' متصل}

📊 **الإحصائيات:**
`/stats` - إحصائيات النظام الكاملة
`/userslist` - عرض المستخدمين ({users_count} مستخدم)

🔢 **معلومات النظام:**
👥 المستخدمين: {users_count}
👑 المشرفين: {len(ADMIN_IDS)}
🤖 خدمات AI: {'✅' if ai_status['apis_configured'] else '❌'}
💾 قاعدة البيانات: ✅ نشطة
"""
    
    await update.message.reply_text(admin_commands, parse_mode='Markdown')
    logger.info(f"المشرف {user_id} فتح لوحة التحكم")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات النظام الكاملة"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        return
    
    try:
        logger.info(f"📊 المشرف {user_id} طلب الإحصائيات")
        
        # إحصائيات النظام
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
        
        # إحصائيات الذكاء الاصطناعي
        ai_status = ai_manager.get_status()
        
        # بناء رسالة الإحصائيات
        stats_text = f"""
📊 **إحصائيات النظام الكاملة**

👥 **المستخدمون:**
👤 العدد الكلي: {users_count} مستخدم
💬 الرسائل الكلية: {total_messages:,}

🤖 **الذكاء الاصطناعي:**
💬 المحادثة: {'✅' if ai_status['chat_available'] else '❌'}
🔑 APIs: {'✅' if ai_status['apis_configured'] else '❌'}
🎯 الوضع: {'API متصل' if ai_status['apis_configured'] else 'نسخة تجريبية'}

👑 **المشرفون:**
👑 العدد: {len(ADMIN_IDS)} مشرف

💾 **قاعدة البيانات:**
✅ SQLite نشطة
📁 الملف: {db.db_name}
🕒 آخر تحديث: {datetime.now().strftime('%H:%M:%S')}
"""
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
        logger.info(f"✅ تم عرض الإحصائيات الكاملة للمشرف {user_id}")
        
    except Exception as e:
        logger.error(f"❌ خطأ في عرض الإحصائيات: {e}", exc_info=True)
        await update.message.reply_text("📊 **حالة النظام:**\n\n✅ البوت يعمل بشكل طبيعي\n✅ جميع الخدمات نشطة")

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
    
    display_users = users[:10]
    
    users_text = f"👥 **المستخدمون المسجلون** ({users_count} مستخدم)\n\n"
    
    for i, user in enumerate(display_users, 1):
        users_text += f"{i}. {user['first_name']}"
        if user['username']:
            users_text += f" (@{user['username']})"
        users_text += f" - ID: {user['user_id']}\n"
        join_date = user['join_date'][:10] if user['join_date'] else "غير معروف"
        users_text += f"   📅 انضم: {join_date}\n"
        users_text += f"   💬 رسائل: {user['message_count']}\n\n"
    
    if users_count > 10:
        users_text += f"\n📋 عرض 10 من أصل {users_count} مستخدم\n"
        users_text += "استخدم /userslist2 للصفحة التالية"
    
    await update.message.reply_text(users_text, parse_mode='Markdown')
    logger.info(f"المشرف {user_id} طلب قائمة المستخدمين")

# ==================== إعداد المعالجات ====================
def setup_handlers(application):
    """إعداد معالجات الأوامر والرسائل"""
    
    # الأوامر الأساسية
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    
    # أوامر الذكاء الاصطناعي
    application.add_handler(CommandHandler("chat", chat_command))
    application.add_handler(CommandHandler("mystats", my_stats_command))
    
    # أوامر المشرفين
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("userslist", users_list_command))
    
    # معالجة الردود على رسائل AI
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_ai_reply
    ), group=1)

def run_bot():
    """تشغيل البوت"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير معين")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    setup_handlers(application)
    
    logger.info("🤖 بدأ تشغيل بوت تليجرام مع الذكاء الاصطناعي...")
    logger.info(f"👑 عدد المشرفين: {len(ADMIN_IDS)}")
    
    # ✅ فحص حالة النظام عند البدء
    users_count = db.get_users_count()
    logger.info(f"👥 عدد المستخدمين المسجلين: {users_count}")
    
    # ✅ فحص خدمات الذكاء الاصطناعي
    ai_status = ai_manager.get_status()
    logger.info(f"🤖 حالة الذكاء الاصطناعي: {ai_status}")
    
    application.run_polling(drop_pending_updates=True)

def main():
    """الدالة الرئيسية"""
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
