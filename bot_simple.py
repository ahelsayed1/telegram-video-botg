# bot_simple.py - بوت شات فقط مع Gemini API
import os
import logging
import asyncio
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

# استيراد Gemini Manager
from gemini_manager import GeminiManager

# إنشاء مدير Gemini
gemini_manager = GeminiManager()

# ==================== أوامر البوت ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    welcome_msg = f"""
🤖 **مرحباً {user.first_name}!**

أنا بوت الشات الذكي المدعوم بـ **Google Gemini AI**!

✨ **مميزاتي:**
💬 محادثة ذكية مع الذكاء الاصطناعي
🧠 فهم عميق للغة العربية والإنجليزية
🎯 إجابات دقيقة ومفيدة
⚡ سرعة في الرد

🔧 **كيفية الاستخدام:**
1. اكتب `/chat` متبوعاً برسالتك
2. أو ارد مباشرة على رسائلي
3. يمكنك سؤالي عن أي موضوع!

🚀 **جرب الآن:** `/chat مرحباً، كيف حالك؟`

🔑 **الحالة:** {gemini_manager.get_status()}
"""
    
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🎯 **أوامر البوت:**

🤖 **الشات الذكي:**
`/chat <رسالتك>` - محادثة مع Gemini AI
أو ارد على رسائلي مباشرة

💡 **أمثلة:**
• `/chat كيف حالك؟`
• `/chat اشرح لي نظرية النسبية`
• `/chat اكتب لي قصيدة عن الحب`
• `/chat ساعدني في حل مشكلة برمجية`
• `/chat ما هو أفضل نظام غذائي صحي؟`

🌐 **المدعوم:**
• العربية والإنجليزية
• جميع المواضيع (علمية، أدبية، تقنية)
• نصائح وإرشادات
• كتابة نصوص وإبداعات

⚡ **ملاحظات:**
- استخدم لغة واضحة
- يمكنك كتابة رسائل طويلة
- الرد يستغرق 2-5 ثواني
- الخدمة مجانية ضمن الحدود
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = gemini_manager.get_status()
    await update.message.reply_text(f"📊 **حالة البوت:**\n\n{status}", parse_mode='Markdown')

async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر الشات مع Gemini"""
    user_message = ' '.join(context.args) if context.args else ""
    
    if not user_message:
        await update.message.reply_text(
            "💬 **الشات مع Gemini AI**\n\n"
            "اكتب رسالتك بعد الأمر:\n"
            "`/chat <رسالتك>`\n\n"
            "مثال: `/chat اشرح لي الذكاء الاصطناعي ببساطة`\n\n"
            "🚀 **Gemini AI يمكنه:**\n"
            "• الإجابة على الأسئلة\n• كتابة النصوص\n• الشرح والتوضيح\n• حل المشكلات\n• الإبداع والكتابة",
            parse_mode='Markdown'
        )
        return
    
    # إظهار رسالة الانتظار
    processing_msg = await update.message.reply_text("🤔 **جاري التفكير...**")
    
    try:
        # استخدام Gemini AI
        response = await gemini_manager.chat(user_message)
        
        # إرسال الرد
        await update.message.reply_text(
            f"🤖 **Gemini AI:**\n\n{response}\n\n"
            f"💬 *يمكنك الرد للاستمرار في المحادثة*",
            parse_mode='Markdown'
        )
        
        # حذف رسالة الانتظار
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"❌ خطأ في الشات: {e}")
        await update.message.reply_text(
            "⚠️ **حدث خطأ في الخادم**\n\n"
            "الرجاء المحاولة مرة أخرى بعد قليل.\n"
            "أو تحقق من مفتاح Gemini API."
        )
        if processing_msg:
            await processing_msg.delete()

async def handle_direct_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة المحادثة المباشرة (رد على البوت)"""
    user_message = update.message.text
    
    # تجاهل الأوامر
    if user_message.startswith('/'):
        return
    
    # إذا كان رداً على رسالة البوت
    is_reply_to_bot = (
        update.message.reply_to_message and 
        update.message.reply_to_message.from_user.id == context.bot.id
    )
    
    if is_reply_to_bot:
        processing_msg = await update.message.reply_text("💭 **جاري الرد...**")
        
        try:
            response = await gemini_manager.chat(user_message)
            
            await update.message.reply_text(
                f"🤖 **Gemini AI:**\n\n{response}",
                parse_mode='Markdown'
            )
            
            await processing_msg.delete()
            
        except Exception as e:
            logger.error(f"❌ خطأ في الرد المباشر: {e}")
            await update.message.reply_text(
                "⚠️ **تعذر الرد حالياً**\n"
                "جرب استخدام `/chat` مباشرة."
            )
            if processing_msg:
                await processing_msg.delete()

# ==================== إعداد البوت ====================
def setup_handlers(application):
    """إعداد معالجات الأوامر"""
    
    # الأوامر الأساسية
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    
    # أمر الشات
    application.add_handler(CommandHandler("chat", chat_command))
    
    # معالجة الردود المباشرة
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_direct_chat
    ), group=1)

def run_bot():
    """تشغيل البوت"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير معين")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    setup_handlers(application)
    
    logger.info("🤖 بدأ تشغيل بوت الشات مع Gemini AI...")
    logger.info(f"🔑 حالة Gemini: {gemini_manager.get_status()}")
    
    application.run_polling(drop_pending_updates=True)

def main():
    """الدالة الرئيسية"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        logger.error("❌ يرجى تعيين BOT_TOKEN في Railway")
        return
    
    logger.info("🚀 بدء تشغيل البوت...")
    
    try:
        run_bot()
    except Exception as e:
        logger.error(f"❌ فشل في تشغيل البوت: {e}")

if __name__ == "__main__":
    main()
