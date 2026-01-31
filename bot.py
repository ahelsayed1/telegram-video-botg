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
    raise ValueError("❌ يرجى تعيين BOT_TOKEN في متغيرات البيئة على Railway")

# التأكد من أن البوت يعمل
logger.info("✅ البوت يبدأ التشغيل...")

# أوامر البوت الأساسية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 البوت يعمل على Railway!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
/start - بدء التشغيل
/help - المساعدة
"""
    await update.message.reply_text(help_text)

def main():
    if not BOT_TOKEN:
        logger.error("❌ لم يتم تعيين BOT_TOKEN")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # بدء البوت
    logger.info("🤖 بدأ تشغيل البوت...")
    application.run_polling()

if __name__ == "__main__":
    main()
