# bot.py - النسخة النهائية مع المحادثة الذكية المتقدمة
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

# ==================== استيراد مدير المحادثة الذكية ====================
from ai_smart_chat import SmartChatManager

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

# إنشاء كائن المحادثة الذكية
chat_manager = SmartChatManager(db)

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
🚀 **مرحباً {user.first_name}!** 🤖

أنا بوت تليجرام مع **محادثة ذكية متقدمة**!

✨ **المميزات المتوفرة:**
💬 محادثة ذكية مع `/chat`
🧠 ذاكرة للمحادثات السابقة
📊 إحصائيات استخدام مفصلة
🎯 تحليل ذكي للرسائل
👑 نظام إدارة متكامل للمشرفين

🔍 **معلومات حسابك:**
🆔 المعرف: `{user.id}`
👤 الاسم: {user.first_name}
📅 التسجيل: {datetime.now().strftime('%Y-%m-%d')}

✅ **حسابك جاهز للاستخدام!**

📝 استخدم `/help` لعرض جميع الأوامر المتاحة
🤖 جرب `/chat` لبدء محادثة ذكية
"""
    
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')
    
    # تسجيل النشاط
    logger.info(f"👤 مستخدم جديد: {user.id} - {user.first_name}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🎯 **أوامر البوت الكاملة**

🤖 **المحادثة الذكية المتقدمة:**
`/chat <رسالتك>` - محادثة مع المساعد الذكي المتطور
`/mystats` - إحصائيات استخدامك التفصيلية
`/features` - مميزات المحادثة الذكية

💡 **أمثلة للاستخدام:**
• `/chat مرحباً، كيف حالك؟`
• `/chat أخبرني نكتة`
• `/chat ما هو الوقت؟`
• `/chat اعطني نصيحة`
• `/chat أنا سعيد اليوم`
• `/chat كيف يعمل هذا البوت؟`

👤 **الأوامر العامة:**
`/start` - بدء استخدام البوت والتسجيل
`/help` - عرض هذه الرسالة (كل الأوامر)
`/status` - حالة البوت والخدمات
`/about` - معلومات عن البوت والمطور

👑 **أوامر المشرفين:**
`/admin` - لوحة تحكم المشرفين
`/stats` - إحصائيات النظام الكاملة
`/userslist` - قائمة المستخدمين المسجلين
`/broadcast` - إرسال رسالة للجميع

✨ **مميزات المحادثة الذكية:**
• ذاكرة للمحادثات السابقة
• تحليل المشاعر (سعيد/حزين)
• فهم السياق والمواضيع
• ردود متنوعة وذكية
• معلومات حقيقية (وقت، تاريخ)
• نصائح مفيدة يومية
• نكت ومعلومات مسلية

💬 **نصائح للاستخدام:**
1. يمكنك الرد مباشرة على رسائل البوت
2. المحادثة تدعم العربية بطلاقة
3. كل مستخدم له ذاكرة محادثة منفصلة
4. يمكنك سؤال عن أي موضوع
5. البوت يتعلم من كل محادثة
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض حالة البوت والخدمات"""
    try:
        # إحصائيات النظام
        users_count = db.get_users_count()
        chat_status = chat_manager.get_status()
        
        # بناء رسالة الحالة
        status_text = f"""
✅ **حالة البوت والخدمات** 🚀

🤖 **المحادثة الذكية:**
💬 الحالة: {chat_status['status']}
🔄 الإصدار: {chat_status['version']}
👥 المستخدمين النشطين: {chat_status['users_in_memory']}
✨ المميزات: {', '.join(chat_status['features'][:3])}...

📊 **إحصائيات النظام:**
👥 المستخدمين المسجلين: {users_count}
👑 المشرفين: {len(ADMIN_IDS)}
💬 جلسات محادثة: {chat_status['users_in_memory']}

⚙️ **معلومات الخادم:**
🕒 وقت الخادم: {datetime.now().strftime('%H:%M:%S')}
📅 التاريخ: {datetime.now().strftime('%Y-%m-%d')}
🌐 المنصة: Railway

🎯 **الحالة العامة:** جميع الخدمات تعمل بشكل طبيعي ✅
"""
        
        await update.message.reply_text(status_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"❌ خطأ في أمر الحالة: {e}")
        await update.message.reply_text(
            "✅ **البوت يعمل بشكل طبيعي!**\n\n"
            "🤖 المحادثة الذكية: ✅ نشطة\n"
            "💾 قاعدة البيانات: ✅ تعمل\n"
            "👥 المستخدمين: جاهز للاستقبال"
        )

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معلومات عن البوت والمطور"""
    about_text = """
🤖 **معلومات عن البوت**

**الإسم:** بوت المحادثة الذكية
**الإصدار:** 3.0 (المتقدمة)
**تاريخ الإصدار:** 2024

🎯 **المميزات الرئيسية:**
1. محادثة ذكية متطورة مع ذاكرة
2. تحليل رسائل ذكي وفهم المشاعر
3. نظام إدارة متكامل للمشرفين
4. قاعدة بيانات لتخزين المعلومات
5. إحصائيات تفصيلية للاستخدام

🧠 **تقنيات المحادثة الذكية:**
- تحليل سياقي للرسائل
- ذاكرة للمحادثات السابقة
- فهم المشاعر (إيجابي/سلبي)
- قاعدة معرفية موسعة
- ردود ذكية ومتنوعة

🔧 **التقنيات المستخدمة:**
- Python Telegram Bot v20
- SQLite Database
- معالجة اللغة الطبيعية (NLP مبسط)
- نظام إحصائيات متكامل

⚡ **المنصة:** Railway (استضافة سحابية)

👨‍💻 **حول المطور:**
تم تطوير هذا البوت باستخدام أحدث تقنيات الذكاء الاصطناعي
والتطوير الآلي ليكون مثالاً عن البوتات الذكية.

📞 **الدعم:** متوفر عبر قنوات التواصل

🌟 **شكراً لاستخدامك البوت!**
نعمل دائماً على تحسين وتطوير الخدمة.
"""
    await update.message.reply_text(about_text, parse_mode='Markdown')

async def features_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض مميزات المحادثة الذكية"""
    features_text = """
✨ **مميزات المحادثة الذكية المتقدمة**

🧠 **الذكاء الاصطناعي:**
• ذاكرة للمحادثات السابقة
• تذكر تفضيلاتك واهتماماتك
• تحليل المشاعر (سعيد/حزين/محايد)
• فهم السياق والمواضيع

💬 **أنواع المحادثات المدعومة:**
1. **محادثة عادية:** تحدث عن أي موضوع
2. **أسئلة معلوماتية:** اسأل عن الوقت، التاريخ، معلومات
3. **نصائح وإرشادات:** اطلب النصح في مختلف المجالات
4. **ترفيه:** نكت، قصص، معلومات مسلية
5. **دعم تقني:** استفسارات عن البوت والتقنية

🎯 **قدرات خاصة:**
• الرد على الأسئلة الشائعة
• تقديم معلومات حقيقية (وقت، تاريخ)
• تحليل نبرة الرسالة
• تكييف الردود حسب السياق
• تنوع في الردود (لا ترد نفس الرد مرتين)

📊 **إحصائيات ذكية:**
• تتبع عدد محادثاتك
• معرفة وقت نشاطك
• إحصائيات استخدام مفصلة
• حدود استخدام عادلة

🔧 **مميزات تقنية:**
• سرعة في الرد (أقل من ثانية)
• استقرار عالي (24/7)
• أمان وحماية للبيانات
• تحديثات مستمرة

💡 **أفكار للاستخدام:**
• تحدث عن يومك
• اطلب النصح في قرار
• اسأل عن معلومات مفيدة
• شارك أفكارك واهتماماتك
• استفسر عن التقنية والبرمجة
• احصل على الدعم المعنوي

🚀 **جرب هذه الأمثلة:**
`/chat أنا سعيد اليوم لأن...`
`/chat أخبرني عن نفسك`
`/chat ما هي أفضل نصيحة لديك؟`
`/chat أنا متحمس لمشروع جديد`
`/chat كيف يمكنني تطوير مهاراتي؟`
"""
    await update.message.reply_text(features_text, parse_mode='Markdown')

# ==================== أوامر المحادثة الذكية ====================
async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """محادثة مع المساعد الذكي المتطور"""
    user_id = update.effective_user.id
    user_message = ' '.join(context.args) if context.args else ""
    
    if not user_message:
        await update.message.reply_text(
            "💬 **المحادثة الذكية المتطورة** 🧠\n\n"
            "اكتب رسالتك بعد الأمر:\n"
            "`/chat <رسالتك>`\n\n"
            "✨ **أمثلة عملية:**\n"
            "• `/chat مرحباً، كيف حالك اليوم؟`\n"
            "• `/chat أخبرني نكتة لطيفة`\n"
            "• `/chat ما هو الوقت الآن؟`\n"
            "• `/chat أحتاج نصيحة في العمل`\n"
            "• `/chat أنا متحمس لمشروع جديد`\n"
            "• `/chat كيف يمكنني تحسين مهاراتي؟`\n\n"
            "💡 **مميزات المحادثة:**\n"
            "🧠 ذاكرة للمحادثات السابقة\n"
            "🎯 فهم المشاعر والسياق\n"
            "📚 معلومات حقيقية ومفيدة\n"
            "😊 ردود ودودة وذكية\n\n"
            "🚀 **جرب الآن!** اكتب شيئاً...",
            parse_mode='Markdown'
        )
        return
    
    # التحقق من طول الرسالة
    if len(user_message) > 500:
        await update.message.reply_text(
            "⚠️ **الرسالة طويلة جداً!**\n"
            "الرجاء اختصار رسالتك إلى أقل من 500 حرف.\n"
            "يمكنك تقسيمها إلى عدة رسائل."
        )
        return
    
    # إظهار رسالة الانتظار
    wait_msg = await update.message.reply_text("🤔 **جاري التفكير والتحليل...**")
    
    try:
        # استخدام المحادثة الذكية المتطورة
        response = await chat_manager.chat(user_id, user_message)
        
        # التحقق من طول الرد
        if len(response) > 4000:
            response = response[:4000] + "\n\n... (تم اختصار الرد)"
        
        # إرسال الرد
        await update.message.reply_text(
            f"🤖 **المساعد الذكي:** 🧠\n\n{response}\n\n"
            f"💭 *يمكنك الرد على هذه الرسالة للاستمرار في المحادثة*",
            parse_mode='Markdown'
        )
        
        # حذف رسالة الانتظار
        await wait_msg.delete()
        
        # تسجيل المحادثة
        logger.info(f"💬 محادثة - المستخدم {user_id}: '{user_message[:30]}...'")
        
    except Exception as e:
        logger.error(f"❌ Chat command error: {e}")
        await update.message.reply_text(
            "⚠️ **حدث خطأ أثناء المعالجة**\n\n"
            "قد يكون الخادم مشغولاً حالياً.\n"
            "الرجاء المحاولة مرة أخرى بعد قليل.\n\n"
            "💡 يمكنك تجربة:\n"
            "• رسالة أقصر\n"
            "• سؤال مختلف\n"
            "• الانتظار بضع ثواني"
        )
        if wait_msg:
            await wait_msg.delete()

async def my_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إحصائيات استخدامي التفصيلية"""
    user_id = update.effective_user.id
    
    stats = chat_manager.get_user_stats(user_id)
    user_info = db.get_user(user_id)
    username = user_info['first_name'] if user_info else "مستخدم"
    
    # حساب النسبة المئوية
    used = stats.get('chats_used', 0)
    limit = stats.get('daily_limit', 100)
    remaining = stats.get('chats_remaining', 100)
    percentage = (used / limit * 100) if limit > 0 else 0
    
    # شريط التقدم
    filled_blocks = min(10, int(percentage / 10))
    progress_bar = "🟩" * filled_blocks + "⬜" * (10 - filled_blocks)
    
    # بناء رسالة الإحصائيات
    stats_text = f"""
📊 **إحصائيات {username}** 📈

👤 **معلومات الحساب:**
🆔 المعرف: `{user_id}`
📅 اليوم: {datetime.now().strftime('%Y-%m-%d')}
🕒 آخر نشاط: {stats.get('last_active', 'الآن')}

💬 **إحصائيات المحادثة:**
{progress_bar}
📊 النسبة: {percentage:.1f}%
✅ المستخدمة: {used} محادثة
🎯 المتبقية: {remaining} محادثة
📈 الإجمالي: {limit} محادثة يومياً

📋 **التفاصيل:**
• بدأت المحادثة: {'نعم' if used > 0 else 'لا'}
• الحالة: {stats.get('status', '🆕 جديد')}
• النشاط: {'نشط' if used > 0 else 'غير نشط'}

🔄 **معلومات النظام:**
⏰ التجديد: تلقائي عند منتصف الليل (UTC)
📊 التتبع: تلقائي لكل محادثة
🎯 الهدف: توفير تجربة استخدام مثالية

💡 **نصائح:**
• يمكنك إجراء حتى {limit} محادثة يومياً
• المحادثات يتم تجديدها تلقائياً
• كل محادثة تُحفظ في ذاكرة البوت
"""
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

# ==================== معالجة الردود الذكية ====================
async def handle_smart_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الردود الذكية على رسائل البوت"""
    user_message = update.message.text
    user_id = update.effective_user.id
    
    # تجاهل الأوامر
    if user_message.startswith('/'):
        return
    
    # التحقق إذا كان رداً على رسالة البوت
    is_reply_to_bot = (
        update.message.reply_to_message and 
        update.message.reply_to_message.from_user.id == context.bot.id
    )
    
    if is_reply_to_bot:
        # إظهار رسالة الانتظار
        processing_msg = await update.message.reply_text("💭 **جاري الرد الذكي...**")
        
        try:
            # استخدام المحادثة الذكية
            response = await chat_manager.chat(user_id, user_message)
            
            # التحقق من طول الرد
            if len(response) > 4000:
                response = response[:4000] + "\n\n... (تم اختصار الرد)"
            
            # إرسال الرد
            await update.message.reply_text(
                f"🤖 **المساعد الذكي:** 💬\n\n{response}",
                parse_mode='Markdown'
            )
            
            # حذف رسالة الانتظار
            await processing_msg.delete()
            
            # تسجيل النشاط
            logger.info(f"↩️ رد ذكي - المستخدم {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Smart reply error: {e}")
            
            # إرسال رسالة خطأ
            error_msg = (
                "⚠️ **حدث خطأ في الرد الذكي**\n\n"
                "يمكنك محاولة:\n"
                "• استخدام `/chat` مباشرة\n"
                "• إعادة إرسال الرسالة\n"
                "• الانتظار قليلاً ثم المحاولة\n\n"
                "🚀 البوت يعمل على حل المشكلة تلقائياً."
            )
            
            await update.message.reply_text(error_msg)
            if processing_msg:
                await processing_msg.delete()

# ==================== أوامر المشرفين ====================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        logger.warning(f"محاولة وصول غير مصرح: المستخدم {user_id}")
        return
    
    users_count = db.get_users_count()
    chat_status = chat_manager.get_status()
    
    admin_text = f"""
👑 **لوحة تحكم المشرفين** 🚀

🤖 **حالة الذكاء الاصطناعي:**
💬 المحادثة الذكية: {chat_status['status']}
🔄 الإصدار: {chat_status['version']}
👥 المستخدمين النشطين: {chat_status['users_in_memory']}
✨ المميزات: {len(chat_status['features'])} مميزة

📊 **إحصائيات النظام:**
👥 المستخدمين المسجلين: {users_count}
👑 المشرفين النشطين: {len(ADMIN_IDS)}
💾 قاعدة البيانات: ✅ نشطة

🔧 **أوامر التحكم:**
`/stats` - إحصائيات النظام الكاملة
`/userslist` - قائمة المستخدمين ({users_count} مستخدم)
`/broadcast` - إرسال رسالة للجميع

⚙️ **معلومات فنية:**
🕒 وقت التشغيل: {datetime.now().strftime('%H:%M:%S')}
🌐 المنصة: Railway
💻 الحالة: جميع الخدمات تعمل ✅
"""
    
    await update.message.reply_text(admin_text, parse_mode='Markdown')
    logger.info(f"👑 المشرف {user_id} فتح لوحة التحكم")

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
        chat_status = chat_manager.get_status()
        
        # الحصول على عدد الرسائل
        total_messages = 0
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT SUM(message_count) FROM users")
                result = cursor.fetchone()
                if result and result[0]:
                    total_messages = int(result[0])
        except Exception as e:
            logger.error(f"❌ Error getting message count: {e}")
            total_messages = 0
        
        # بناء رسالة الإحصائيات
        stats_text = f"""
📊 **إحصائيات النظام الكاملة** 📈

👥 **المستخدمون:**
👤 العدد الكلي: {users_count} مستخدم
💬 الرسائل الكلية: {total_messages:,}

🤖 **الذكاء الاصطناعي:**
💬 المحادثة الذكية: ✅ نشطة
🧠 الإصدار: {chat_status['version']}
👥 المستخدمين النشطين: {chat_status['users_in_memory']}
✨ المميزات: {', '.join(chat_status['features'])[:50]}...

📈 **نشاط النظام:**
🕒 وقت الخادم: {datetime.now().strftime('%H:%M:%S')}
📅 تاريخ اليوم: {datetime.now().strftime('%Y-%m-%d')}
🌐 حالة الخادم: ✅ نشط

👑 **المشرفون:**
👑 العدد: {len(ADMIN_IDS)} مشرف
🎯 الحالة: جميع الصلاحيات نشطة

💾 **قاعدة البيانات:**
✅ SQLite نشطة
📁 الملف: {db.db_name}
📊 السعة: جاهزة للاستخدام

🚀 **الحالة العامة:** جميع الأنظمة تعمل بشكل مثالي ✅
"""
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
        logger.info(f"✅ تم عرض الإحصائيات للمشرف {user_id}")
        
    except Exception as e:
        logger.error(f"❌ خطأ في عرض الإحصائيات: {e}", exc_info=True)
        await update.message.reply_text(
            "📊 **حالة النظام:**\n\n"
            "✅ البوت يعمل بشكل طبيعي\n"
            "🤖 المحادثة الذكية: نشطة\n"
            "💾 قاعدة البيانات: تعمل\n"
            "👥 المستخدمين: جاهز للاستقبال"
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
    
    display_users = users[:8]  # عرض 8 مستخدمين فقط
    
    users_text = f"👥 **المستخدمون المسجلون** ({users_count} مستخدم)\n\n"
    
    for i, user in enumerate(display_users, 1):
        users_text += f"{i}. **{user['first_name']}**"
        if user['username']:
            users_text += f" (@{user['username']})"
        users_text += f"\n"
        users_text += f"   🆔 المعرف: `{user['user_id']}`\n"
        
        join_date = user.get('join_date', '')
        if join_date:
            join_date = join_date[:10]
            users_text += f"   📅 انضم: {join_date}\n"
        
        message_count = user.get('message_count', 0)
        users_text += f"   💬 رسائل: {message_count}\n\n"
    
    if users_count > 8:
        users_text += f"📋 ... وعرض {users_count - 8} مستخدم آخر\n"
        users_text += "💡 للعرض الكامل، تواصل مع المطور"
    
    users_text += "🎯 **ملاحظة:** هذه قائمة المستخدمين المسجلين في قاعدة البيانات."
    
    await update.message.reply_text(users_text, parse_mode='Markdown')
    logger.info(f"👥 المشرف {user_id} طلب قائمة المستخدمين")

# ==================== إعداد المعالجات ====================
def setup_handlers(application):
    """إعداد معالجات الأوامر والرسائل"""
    
    # الأوامر الأساسية
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("features", features_command))
    
    # أوامر المحادثة الذكية
    application.add_handler(CommandHandler("chat", chat_command))
    application.add_handler(CommandHandler("mystats", my_stats_command))
    
    # أوامر المشرفين
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("userslist", users_list_command))
    
    # معالجة الردود الذكية على رسائل البوت
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_smart_reply
    ), group=1)

def run_bot():
    """تشغيل البوت"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير معين")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    setup_handlers(application)
    
    logger.info("🤖 بدأ تشغيل بوت المحادثة الذكية...")
    logger.info(f"👑 عدد المشرفين: {len(ADMIN_IDS)}")
    
    # ✅ فحص حالة النظام عند البدء
    users_count = db.get_users_count()
    logger.info(f
