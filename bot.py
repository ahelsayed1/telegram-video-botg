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

# ==================== بوت تليجرام ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 البوت يعمل على Railway بنجاح!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
/start - بدء التشغيل
/help - المساعدة
/status - حالة البوت
"""
    await update.message.reply_text(help_text)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ البوت يعمل بشكل طبيعي!")

def run_bot():
    """تشغيل بوت تليجرام"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير معين")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    
    logger.info("🤖 بدأ تشغيل بوت تليجرام...")
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
