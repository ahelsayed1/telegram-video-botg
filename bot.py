import os
import logging
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

# الحصول على التوكن من البيئة
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("❌ يرجى تعيين BOT_TOKEN في ملف .env")

# أوامر البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يرسل رسالة ترحيب عند استخدام الأمر /start"""
    user = update.effective_user
    await update.message.reply_html(
        f"مرحباً {user.mention_html()}! 👋\n"
        "أنا بوت تجريبي يعمل على Railway.\n"
        "جرب الأمر /help لرؤية الأوامر المتاحة."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعرض قائمة الأوامر"""
    help_text = """
🛠 **الأوامر المتاحة:**
/start - بدء التشغيل
/help - عرض هذه الرسالة
/about - معلومات عن البوت

✉ **يمكنك أيضاً إرسال:**
- نص وسأعيده لك
- صورة وسأرد عليها
    """
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معلومات عن البوت"""
    about_text = """
🤖 **بوت تليجرام تجريبي**
    
🏗 **المميزات:**
- يعمل على Railway
- يدعم الأوامر الأساسية
- جاهز للتطوير

📁 **المستودع:** يمكنك تطويره وإضافة مميزات جديدة!
    """
    await update.message.reply_text(about_text, parse_mode="Markdown")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يرد على الرسائل النصية"""
    user_message = update.message.text
    await update.message.reply_text(f"📝 لقد أرسلت: {user_message}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يرد على الصور"""
    photo = update.message.photo[-1]
    await update.message.reply_text("📸 شكراً للصورة! تم استلامها بنجاح.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأخطاء"""
    logger.error(f"حدث خطأ: {context.error}")
    if update and hasattr(update, 'message'):
        await update.message.reply_text("⚠️ حدث خطأ ما. حاول مرة أخرى.")

def main():
    """الدالة الرئيسية لتشغيل البوت"""
    # إنشاء تطبيق البوت
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة handlers للأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about))
    
    # إضافة handlers للرسائل
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # إضافة معالج الأخطاء
    application.add_error_handler(error_handler)
    
    # بدء البوت
    logger.info("🚀 بدأ تشغيل البوت...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
