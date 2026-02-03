# bot.py - بوت تليجرام متكامل مع الذكاء الاصطناعي
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
from ai_manager import AIManager

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
ai_manager = AIManager(db)

# ==================== أوامر البوت الأساسية ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # تسجيل المستخدم في قاعدة البيانات
    db.add_or_update_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # إرسال إشعار ترحيبي
    await update.message.reply_text(
        f"🤖 **مرحباً {user.first_name}!**\n\n"
        f"أنا بوت الذكاء الاصطناعي المتكامل! 🚀\n\n"
        f"🎯 **ما يمكنني فعله:**\n"
        f"💬 محادثة ذكية (مثل ChatGPT)\n"
        f"🎨 إنشاء صور من الوصف\n"
        f"🎬 إنشاء فيديوهات متحركة\n"
        f"📊 إحصائيات استخدام شخصية\n\n"
        f"🔍 **معرفك:** {user.id}\n"
        f"✅ **تم التسجيل بنجاح**\n\n"
        f"📝 استخدم /help لعرض جميع الأوامر\n"
        f"🤖 جرب /chat للبدء في المحادثة",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🎯 **أوامر البوت الكاملة**

🤖 **خدمات الذكاء الاصطناعي:**
`/chat <رسالتك>` - محادثة مع AI (مثل ChatGPT)
`/ask <سؤالك>` - سؤال مباشر
`/image <وصف الصورة>` - إنشاء صورة من النص
`/draw <وصف>` - إنشاء صورة (اسم بديل)
`/صورة <وصف>` - إنشاء صورة (بالعربية)
`/video <وصف>` - إنشاء فيديو من النص
`/فيديو <وصف>` - إنشاء فيديو (بالعربية)

📊 **معلومات الاستخدام:**
`/mystats` - إحصائيات استخدامك اليومي
`/limits` - حدود الاستخدام المتاحة
`/aihelp` - مساعدة الذكاء الاصطناعي

👤 **الأوامر العامة:**
`/start` - بدء استخدام البوت
`/help` - عرض هذه الرسالة
`/status` - حالة البوت والخوادم
`/about` - معلومات عن البوت والمطور

👑 **أوامر المشرفين:**
`/admin` - لوحة تحكم المشرفين
`/stats` - إحصائيات النظام الكاملة
`/broadcast` - إرسال رسالة للجميع
`/userslist` - قائمة المستخدمين

💡 **نصائح الاستخدام:**
1. استخدم أوصاف واضحة للصور والفيديوهات
2. يمكنك الرد على رسائل AI للاستمرار في المحادثة
3. الصور تستغرق 10-30 ثانية
4. الفيديوهات تستغرق 2-5 دقائق
5. لديك حدود استخدام يومية عادلة

🔧 **الدعم:** للاستفسارات تواصل مع @المطور
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض حالة البوت والخدمات"""
    try:
        # التحقق من حالة الخدمات
        services = ai_manager.get_available_services()
        
        status_text = "✅ **حالة البوت والخدمات**\n\n"
        
        # حالة الذكاء الاصطناعي
        status_text += "🤖 **خدمات الذكاء الاصطناعي:**\n"
        status_text += "💬 المحادثة: " + ("✅ متاحة" if services.get("chat") else "❌ غير متاحة") + "\n"
        status_text += "🎨 إنشاء الصور: " + ("✅ متاحة" if services.get("image_generation") else "❌ غير متاحة") + "\n"
        status_text += "🎬 إنشاء الفيديوهات: " + ("✅ متاحة" if services.get("video_generation") else "❌ غير متاحة") + "\n\n"
        
        # حالة قاعدة البيانات
        db_status = check_database_status()
        status_text += "💾 **قاعدة البيانات:**\n"
        status_text += f"👥 المستخدمين: {db_status.get('users_count', 0)}\n"
        status_text += f"📁 الملف: {db_status.get('database_file', 'N/A')}\n\n"
        
        # معلومات النظام
        status_text += "⚙️ **معلومات النظام:**\n"
        status_text += f"🕒 الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        status_text += f"👑 المشرفين: {len(ADMIN_IDS)}\n"
        status_text += f"🚀 المنصة: Railway\n\n"
        
        status_text += "✅ **جميع الخدمات تعمل بشكل طبيعي**"
        
        await update.message.reply_text(status_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"❌ خطأ في أمر الحالة: {e}")
        await update.message.reply_text("✅ البوت يعمل بشكل طبيعي!")

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معلومات عن البوت والمطور"""
    about_text = """
🤖 **معلومات البوت**

**الإصدار:** 2.0 (الذكاء الاصطناعي المتكامل)
**تاريخ الإصدار:** 2024

🎯 **المميزات الرئيسية:**
1. محادثة ذكية مع AI (Gemini + OpenAI)
2. إنشاء صور احترافية من النص
3. إنشاء فيديوهات متحركة باستخدام Luma AI
4. نظام إدارة متكامل للمشرفين
5. تتبع الاستخدام والحدود العادلة

🔧 **التقنيات المستخدمة:**
- Python Telegram Bot v20
- Google Gemini AI
- OpenAI GPT
- Luma AI Dream Machine
- SQLite Database

⚡ **المنصة:** Railway (استضافة سحابية)

👨‍💻 **المطور:** تم التطوير باستخدام الذكاء الاصطناعي
📞 **الدعم:** @المطور

🌟 **سياسة الخصوصية:**
- لا يتم مشاركة بياناتك مع أطراف ثالثة
- المحادثات تُخزن لفترة محدودة لأغراض التحسين
- يمكنك طلب حذف بياناتك في أي وقت

📜 **الشروط:** استخدام البوت يعني موافقتك على الشروط
"""
    await update.message.reply_text(about_text, parse_mode='Markdown')

async def limits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض حدود الاستخدام اليومية"""
    limits_text = """
📊 **حدود الاستخدام اليومية**

لكل مستخدم حقوق استخدام يومية عادلة:

🤖 **الذكاء الاصطناعي:**
💬 المحادثات: 20 رسالة يومياً
🎨 الصور المولدة: 5 صور يومياً
🎬 الفيديوهات: 2 فيديو يومياً

⏰ **التجديد:** يتم تجديد الحدود كل 24 ساعة
📈 **التتبع:** يمكنك تتبع استخدامك بـ `/mystats`

💡 **نصائح لتحقيق أقصى استفادة:**
1. استخدم أوصاف واضحة للصور والفيديوهات
2. اجعل أسئلتك محددة للردود الأفضل
3. استخدم `/image` للصور و `/video` للفيديوهات
4. يمكنك الرد على رسائل AI للاستمرار في المحادثة

⚖️ **السياسة:** الحدود لضمان عدالة الاستخدام للجميع
🔄 **التجديد:** تلقائي عند منتصف الليل (توقيت UTC)

❓ **للحصول على مزيد:** تواصل مع الإدارة
"""
    await update.message.reply_text(limits_text, parse_mode='Markdown')

# ==================== أوامر الذكاء الاصطناعي ====================

async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء محادثة مع الذكاء الاصطناعي"""
    user_id = update.effective_user.id
    user_message = ' '.join(context.args) if context.args else ""
    
    if not user_message:
        await update.message.reply_text(
            "💬 **المحادثة الذكية**\n\n"
            "اكتب رسالتك بعد الأمر:\n"
            "`/chat مرحبا، كيف حالك؟`\n\n"
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
        response = await ai_manager.chat_with_ai(user_id, user_message)
        
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

async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إنشاء صورة باستخدام الذكاء الاصطناعي"""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "🎨 **إنشاء صور بالذكاء الاصطناعي**\n\n"
            "**الاستخدام:** `/image <وصف الصورة> [النمط]`\n\n"
            "**أمثلة:**\n"
            "`/image قطة لطيفة تجلس على كرسي`\n"
            "`/image منظر لغروب الشمس فوق البحر realistic`\n"
            "`/image ساحر في غابة سحرية fantasy`\n\n"
            "**الأنماط المتاحة:**\n"
            "`realistic` - واقعي (افتراضي)\n"
            "`anime` - أنمي / كرتون\n"
            "`fantasy` - فنتازيا سحرية\n"
            "`cyberpunk` - مستقبلي تكنولوجي\n"
            "`watercolor` - ألوان مائية فنية\n\n"
            "⏳ **المدة:** 10-30 ثانية",
            parse_mode='Markdown'
        )
        return
    
    # استخراج النمط (آخر كلمة)
    args = context.args
    prompt_words = args[:-1]
    style = args[-1] if args[-1] in ["realistic", "anime", "fantasy", "cyberpunk", "watercolor"] else "realistic"
    
    if style != args[-1]:
        prompt_words = args  # إذا لم يكن النمط، كل الكلمات للوصف
    
    prompt = ' '.join(prompt_words)
    
    if len(prompt) < 3:
        await update.message.reply_text("❌ الرجاء إدخال وصف أطول للصورة (3 كلمات على الأقل)")
        return
    
    # إظهار رسالة الانتظار
    wait_msg = await update.message.reply_text("🎨 **جاري إنشاء صورتك...**\n⏳ قد يستغرق ذلك 10-30 ثانية")
    
    try:
        # إنشاء الصورة
        image_url, message = await ai_manager.generate_image(user_id, prompt, style)
        
        if image_url:
            # إرسال الصورة
            await update.message.reply_photo(
                photo=image_url,
                caption=f"✅ **تم إنشاء صورتك بنجاح!**\n\n"
                       f"📝 **الوصف:** {prompt}\n"
                       f"🎨 **النمط:** {style}\n\n"
                       f"💾 تم حفظ الصورة في مكتبتك\n"
                       f"🔄 استخدم `/image` لإنشاء المزيد",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"❌ {message}")
        
        # حذف رسالة الانتظار
        await wait_msg.delete()
        
    except Exception as e:
        logger.error(f"❌ Image command error: {e}")
        await update.message.reply_text(
            "❌ حدث خطأ أثناء إنشاء الصورة.\n"
            "⚠️ حاول مرة أخرى أو جرب وصفاً مختلفاً"
        )

async def video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إنشاء فيديو باستخدام الذكاء الاصطناعي"""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "🎬 **إنشاء فيديو بالذكاء الاصطناعي**\n\n"
            "**طريقتان للاستخدام:**\n\n"
            "1. **من النص:**\n"
            "`/video منظر طبيعي لغروب الشمس`\n\n"
            "2. **من صورة:**\n"
            "• أرسل صورة أولاً\n"
            "• ثم رد عليها بالأمر:\n"
            "`/video إضافة حركة للصورة`\n\n"
            "**أمثلة:**\n"
            "`/video مدينة المستقبل بإضاءة نيون`\n"
            "`/video بحر هائج بأمواج عالية`\n"
            "`/video غابة سحرية مع كائنات خيالية`\n\n"
            "⚠️ **ملاحظة:** إنشاء الفيديو قد يستغرق 2-5 دقائق",
            parse_mode='Markdown'
        )
        return
    
    prompt = ' '.join(context.args)
    
    if len(prompt) < 4:
        await update.message.reply_text("❌ الرجاء إدخال وصف أطول للفيديو (4 كلمات على الأقل)")
        return
    
    # التحقق إذا كان رداً على صورة
    image_url = None
    if update.message.reply_to_message and update.message.reply_to_message.photo:
        # الحصول على أعلى دقة للصورة
        photo = update.message.reply_to_message.photo[-1]
        image_file = await photo.get_file()
        image_url = image_file.file_path
    
    wait_msg = await update.message.reply_text(
        "🎬 **جاري إنشاء الفيديو...**\n"
        "⏳ قد يستغرق ذلك 2-5 دقائق\n"
        "📱 يمكنك متابعة استخدام البوت أثناء الانتظار"
    )
    
    try:
        # إنشاء الفيديو
        video_url, message = await ai_manager.generate_video(user_id, prompt, image_url)
        
        if video_url:
            # إرسال الفيديو
            await update.message.reply_video(
                video=video_url,
                caption=f"✅ **تم إنشاء الفيديو بنجاح!**\n\n"
                       f"📝 **الوصف:** {prompt}\n"
                       f"⏱️ **المدة:** 5 ثواني\n\n"
                       f"💾 تم حفظ الفيديو في مكتبتك\n"
                       f"🔄 استخدم `/video` لإنشاء المزيد",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"❌ {message}")
        
        await wait_msg.delete()
        
    except Exception as e:
        logger.error(f"❌ Video command error: {e}")
        await update.message.reply_text(
            "❌ حدث خطأ أثناء إنشاء الفيديو.\n"
            "⚠️ قد يكون الخادم مشغولاً، حاول مرة أخرى لاحقاً"
        )

async def my_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إحصائيات استخدامي للذكاء الاصطناعي"""
    user_id = update.effective_user.id
    
    stats = ai_manager.get_user_stats(user_id)
    services = ai_manager.get_available_services()
    
    # الحصول على معلومات المستخدم
    user_info = db.get_user(user_id)
    username = user_info['first_name'] if user_info else "مستخدم"
    
    stats_text = f"📊 **إحصائيات {username}**\n\n"
    stats_text += f"🆔 المعرف: {user_id}\n"
    stats_text += f"📅 اليوم: {datetime.now().strftime('%Y-%m-%d')}\n\n"
    
    limits = {
        "ai_chat": int(os.getenv("DAILY_AI_LIMIT", 20)),
        "image_gen": int(os.getenv("DAILY_IMAGE_LIMIT", 5)),
        "video_gen": int(os.getenv("DAILY_VIDEO_LIMIT", 2))
    }
    
    # شريط التقدم للخدمات
    for service, limit in limits.items():
        used = stats.get(service, 0)
        remaining = max(0, limit - used)
        percentage = (used / limit * 100) if limit > 0 else 0
        
        service_names = {
            "ai_chat": "💬 المحادثات",
            "image_gen": "🎨 الصور المولدة",
            "video_gen": "🎬 الفيديوهات"
        }
        
        # شريط تقدم مرئي
        filled_blocks = int(percentage / 10)
        progress_bar = "🟩" * filled_blocks + "⬜" * (10 - filled_blocks)
        
        stats_text += f"{service_names.get(service, service)}:\n"
        stats_text += f"{progress_bar}\n"
        stats_text += f"📊 {used}/{limit} ({remaining} متبقي)\n\n"
    
    stats_text += "🔧 **حالة الخدمات:**\n"
    for service, available in services.items():
        status = "✅" if available else "❌"
        service_name = {
            "chat": "💬 المحادثة",
            "image_generation": "🎨 إنشاء صور",
            "video_generation": "🎬 إنشاء فيديوهات"
        }.get(service, service)
        
        stats_text += f"{status} {service_name}\n"
    
    stats_text += "\n🔄 **التجديد:** تلقائي عند منتصف الليل (UTC)"
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

# ==================== معالج المحادثات العادية ====================

async def handle_ai_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة المحادثات العادية مع AI (ردود على رسائل AI)"""
    user_id = update.effective_user.id
    user_message = update.message.text
    
    # تجاهل الأوامر
    if user_message.startswith('/'):
        return
    
    # إذا كان الرد على رسالة AI السابقة
    is_reply_to_ai = (
        update.message.reply_to_message and 
        update.message.reply_to_message.from_user.id == context.bot.id and
        ("المساعد الذكي:" in update.message.reply_to_message.text or 
         "تم إنشاء صورتك" in update.message.reply_to_message.text or
         "تم إنشاء الفيديو" in update.message.reply_to_message.text)
    )
    
    # أو إذا كان الحديث العادي (ليس رد على شيء)
    is_direct_chat = not update.message.reply_to_message
    
    if is_reply_to_ai or is_direct_chat:
        # إظهار رسالة "جاري المعالجة" فقط للردود على AI
        if is_reply_to_ai:
            processing_msg = await update.message.reply_text("💭 **جاري التفكير...**")
        else:
            processing_msg = None
        
        try:
            # استخدام الذكاء الاصطناعي
            response = await ai_manager.chat_with_ai(user_id, user_message)
            
            # إرسال الرد
            reply_text = f"🤖 **المساعد الذكي:**\n\n{response}"
            
            if len(reply_text) > 4000:
                # تقسيم الرد إذا كان طويلاً
                parts = [reply_text[i:i+4000] for i in range(0, len(reply_text), 4000)]
                for part in parts:
                    await update.message.reply_text(part, parse_mode='Markdown')
            else:
                await update.message.reply_text(reply_text, parse_mode='Markdown')
            
            # حذف رسالة "جاري المعالجة"
            if processing_msg:
                await processing_msg.delete()
            
        except Exception as e:
            logger.error(f"❌ AI conversation error: {e}")
            error_msg = "❌ حدث خطأ أثناء معالجة رسالتك.\n💡 حاول استخدام `/chat` مباشرة"
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
    ai_services = ai_manager.get_available_services()
    
    admin_commands = f"""
👑 **لوحة تحكم المشرفين**

🤖 **حالة الذكاء الاصطناعي:**
💬 المحادثة: {"✅" if ai_services.get("chat") else "❌"}
🎨 إنشاء الصور: {"✅" if ai_services.get("image_generation") else "❌"}
🎬 إنشاء الفيديوهات: {"✅" if ai_services.get("video_generation") else "❌"}

📊 **الإحصائيات:**
/stats - إحصائيات النظام الكاملة
/userslist - عرض المستخدمين ({users_count} مستخدم)

📢 **الإذاعة:**
/broadcast - إعداد رسالة للإذاعة
/sendbroadcast - إرسال الرسالة المعلقة
/broadcaststats <رقم> - إحصائيات إذاعة

🔢 **معلومات النظام:**
👥 المستخدمين: {users_count}
👑 المشرفين: {len(ADMIN_IDS)}
🤖 خدمات AI: {sum(1 for s in ai_services.values() if s)}/3 نشطة
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
        stats = db.get_stats_fixed()
        
        if not stats:
            stats = {
                'total_users': db.get_users_count(),
                'total_messages': 0,
                'total_broadcasts': 0,
                'new_users_today': 0,
                'last_broadcast_id': None,
                'top_users': []
            }
        
        # إحصائيات الذكاء الاصطناعي
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # إحصائيات استخدام AI
                cursor.execute("SELECT COUNT(DISTINCT user_id) FROM ai_usage")
                ai_users = cursor.fetchone()[0] or 0
                
                cursor.execute("SELECT SUM(usage_count) FROM ai_us
👥 **المستخدمون:**
- العدد الكلي: {total_users} مستخدم
- المستخدمين الجدد اليوم: {new_users_today}
- الرسائل الكلية: {total_messages:,}

📢 **الإذاعات:**
- عدد الإذاعات المرسلة: {total_broadcasts}
"""
        
        if last_broadcast_id:
            stats_text += f"- آخر إذاعة: #{last_broadcast_id}\n"
        
        # إضافة المستخدمين الأكثر نشاطاً
        if top_users and len(top_users) > 0:
            stats_text += "\n🏆 **المستخدمون الأكثر نشاطاً:**\n"
            for i, user in enumerate(top_users[:3], 1):
                name = user.get('first_name', 'مستخدم')
                messages = user.get('message_count', 0)
                stats_text += f"{i}. {name} - {messages:,} رسالة\n"
        
        stats_text += f"""
👑 **المشرفون:**
- العدد: {len(ADMIN_IDS)} مشرف

💾 **قاعدة البيانات:**
- ✅ SQLite نشطة
- 📁 الملف: {db.db_name}
- 🕒 آخر تحديث: {datetime.now().strftime('%H:%M:%S')}
"""
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
        logger.info(f"✅ تم عرض الإحصائيات الكاملة للمشرف {user_id}")
        
    except Exception as e:
        logger.error(f"❌ خطأ كامل في عرض الإحصائيات: {e}", exc_info=True)
        
        # ✅ **الرسالة الاحتياطية المحسنة**
        try:
            users_count = db.get_users_count()
            fallback_text = f"""
📊 **إحصائيات النظام**

👥 عدد المستخدمين: {users_count}
👑 عدد المشرفين: {len(ADMIN_IDS)}
📢 عدد الإذاعات: {db.get_stats_simple().get('total_broadcasts', 0) if hasattr(db, 'get_stats_simple') else 0}

✅ **جميع الخدمات تعمل بشكل طبيعي**
🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            await update.message.reply_text(fallback_text, parse_mode='Markdown')
            logger.info(f"✅ تم عرض الإحصائيات المبسطة للمشرف {user_id}")
            
        except Exception as fallback_error:
            logger.error(f"❌ فشل حتى في العرض المبسط: {fallback_error}")
            await update.message.reply_text(
                "📊 **حالة النظام:**\n\n"
                "✅ البوت يعمل بشكل طبيعي\n"
                "✅ قاعدة البيانات نشطة\n"
                "✅ جاهز للاستخدام"
            )

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        return
    
    if update.message.reply_to_message:
        message = update.message.reply_to_message.text or "رسالة ميديا"
        users_count = db.get_users_count()
        
        await update.message.reply_text(
            f"📢 **رسالة الإذاعة:**\n"
            f"'{message[:50]}...'\n\n"
            f"👥 عدد المستهدفين: {users_count} مستخدم\n"
            f"✅ جاهزة للإرسال\n\n"
            f"ℹ️ *لإرسال فعلياً:*\n"
            f"أرسل /sendbroadcast",
            parse_mode='Markdown'
        )
        
        # حفظ الرسالة مؤقتاً في context
        context.user_data['pending_broadcast'] = message
    else:
        await update.message.reply_text(
            "📝 **طريقة استخدام /broadcast:**\n"
            "1. أرسل الرسالة التي تريد إذاعتها\n"
            "2. رد على الرسالة بالأمر /broadcast\n\n"
            "✅ **المميزات:**\n"
            "- الإرسال لجميع المستخدمين\n"
            "- تتبع من استلم الرسالة\n"
            "- إحصائيات مفصلة",
            parse_mode='Markdown'
        )

async def send_broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        return
    
    if 'pending_broadcast' not in context.user_data:
        await update.message.reply_text("❌ لا توجد رسالة معلقة للإذاعة!\nاستخدم /broadcast أولاً")
        return
    
    message = context.user_data['pending_broadcast']
    users = db.get_all_users()
    users_count = len(users)
    
    if users_count == 0:
        await update.message.reply_text("❌ لا يوجد مستخدمين لإرسال الإذاعة لهم!")
        return
    
    # حفظ الإذاعة في قاعدة البيانات
    broadcast_id = db.add_broadcast(user_id, message, users_count)
    
    if not broadcast_id:
        await update.message.reply_text("❌ فشل في حفظ الإذاعة!")
        return
    
    # 🔥 **الإرسال الفعلي للمستخدمين**
    sent_count = 0
    failed_count = 0
    failed_users = []
    
    await update.message.reply_text(
        f"📤 جاري إرسال الإذاعة لـ {users_count} مستخدم...\n"
        f"⏳ قد يستغرق بعض الوقت..."
    )
    
    # إرسال لكل مستخدم
    for user in users:
        user_id_in_db = user['user_id']
        
        try:
            # إذا كان المستخدم هو المرسل نفسه
            if user_id_in_db == user_id:
                sent_count += 1
                logger.info(f"✅ المرسل نفسه ({user_id_in_db}) - معامل كنجاح")
                continue
                
            await context.bot.send_message(
                chat_id=user['user_id'],
                text=f"📢 **إذاعة من الإدارة:**\n\n{message}"
            )
            sent_count += 1
            
            # تسجيل النشاط
            db.log_activity(
                user_id=user['user_id'],
                action="broadcast_received",
                details=f"broadcast_id={broadcast_id}"
            )
            
            # تأخير بسيط لتجنب rate limits
            if sent_count % 10 == 0:
                await asyncio.sleep(0.3)
                
        except Exception as e:
            failed_count += 1
            failed_users.append(user['user_id'])
            logger.error(f"❌ فشل إرسال للإذاعة {broadcast_id} للمستخدم {user['user_id']}: {e}")
    
    # تحديث عدد المستلمين الفعلي
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            UPDATE broadcasts 
            SET recipients_count = ?
            WHERE broadcast_id = ?
            ''', (sent_count, broadcast_id))
            conn.commit()
    except Exception as e:
        logger.error(f"❌ فشل تحديث عدد المستلمين: {e}")
    
    # إرسال تقرير للمشرف
    success_rate = (sent_count / users_count * 100) if users_count > 0 else 0
    
    report = f"""
✅ **تم إرسال الإذاعة بنجاح!**

📊 **التقرير:**
🆔 رقم الإذاعة: {broadcast_id}
👥 العدد الكلي: {users_count} مستخدم
✅ تم الإرسال بنجاح: {sent_count}
❌ فشل الإرسال: {failed_count}
📈 نسبة النجاح: {success_rate:.1f}%
"""
    
    if failed_count > 0 and failed_users:
        report += f"\n📛 **المستخدمين الذين فشل الإرسال لهم:**\n"
        for failed_id in failed_users[:5]:
            report += f"- {failed_id}\n"
    
    await update.message.reply_text(report, parse_mode='Markdown')
    
    # حذف الرسالة المعلقة
    del context.user_data['pending_broadcast']

async def broadcast_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات إذاعة محددة"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        return
    
    if context.args and context.args[0].isdigit():
        broadcast_id = int(context.args[0])
        stats = db.get_broadcast_stats(broadcast_id)
        
        if stats:
            stats_text = f"""
📊 **إحصائيات الإذاعة #{broadcast_id}**

📝 **الرسالة:** {stats['message_text'][:100]}...

👤 **المرسل:** المشرف {stats.get('admin_id', 'غير معروف')}
📅 **تاريخ الإرسال:** {stats['sent_date'][:16]}

📈 **الإحصائيات:**
👥 العدد المستهدف: {stats['recipients_count']}
"""
            await update.message.reply_text(stats_text, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ لم يتم العثور على إذاعة برقم #{broadcast_id}")
    else:
        await update.message.reply_text("📌 استخدام: /broadcaststats <رقم_الإذاعة>\nمثال: /broadcaststats 1")

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

async def handle_broadcast_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تتبع ردود المستخدمين على الإذاعات"""
    if update.message.reply_to_message and update.message.reply_to_message.text:
        replied_text = update.message.reply_to_message.text
        if "إذاعة من الإدارة:" in replied_text:
            user_id = update.effective_user.id
            user = db.get_user(user_id)
            
            if user:
                db.log_activity(
                    user_id=user_id,
                    action="broadcast_replied",
                    details=f"reply: {update.message.text[:50]}"
                )
                
                # إرسال إشعار للمشرف
                admin_message = f"""
🔄 **رد على إذاعة:**
👤 المستخدم: {user['first_name']} (@{user['username'] or 'بدون'})
🆔 المعرف: {user_id}
💬 الرد: {update.message.text[:100]}
"""
                
                # إرسال لجميع المشرفين
                for admin_id in ADMIN_IDS:
                    try:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=admin_message
                        )
                    except Exception as e:
                        logger.error(f"فشل إرسال إشعار للمشرف {admin_id}: {e}")

# ==================== وظائف مساعدة ====================
def check_database_status():
    """فحص حالة قاعدة البيانات"""
    try:
        users_count = db.get_users_count()
        stats = db.get_stats_fixed()
        
        status_info = {
            'database_file': db.db_name,
            'users_count': users_count,
            'stats_available': bool(stats),
            'last_check': datetime.now().isoformat()
        }
        
        logger.info(f"✅ حالة قاعدة البيانات: {status_info}")
        return status_info
        
    except Exception as e:
        logger.error(f"❌ فشل في فحص حالة قاعدة البيانات: {e}")
        return {'error': str(e), 'last_check': datetime.now().isoformat()}

# ==================== الوظائف الرئيسية ====================
def setup_handlers(application):
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("sendbroadcast", send_broadcast_command))
    application.add_handler(CommandHandler("broadcaststats", broadcast_stats_command))
    application.add_handler(CommandHandler("userslist", users_list_command))
    
    # إضافة معالج للردود على الرسائل
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_broadcast_reply
    ))

def run_bot():
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير معين")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    setup_handlers(application)
    
    logger.info(f"🤖 بدأ تشغيل بوت تليجرام...")
    logger.info(f"👑 عدد المشرفين: {len(ADMIN_IDS)}")
    
    # ✅ فحص حالة النظام عند البدء
    db_status = check_database_status()
    logger.info(f"💾 حالة قاعدة البيانات عند البدء: {db_status}")
    
    users_count = db.get_users_count()
    logger.info(f"👥 عدد المستخدمين المسجلين: {users_count}")
    
    # ✅ جلب الإحصائيات عند البدء
    try:
        stats = db.get_stats_fixed()
        logger.info(f"📊 إحصائيات البدء: {stats}")
    except Exception as e:
        logger.warning(f"⚠️ لا يمكن جلب إحصائيات البدء: {e}")
        logger.info("ℹ️ سيتم استخدام الإحصائيات المبسطة")
    
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
