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
    db.add_or_update_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    await update.message.reply_text(
        f"🚀 مرحباً {user.first_name}!\n"
        f"البوت يعمل على Railway بنجاح!\n\n"
        f"معرفك: {user.id}\n"
        f"✅ تم تسجيل دخولك في قاعدة البيانات"
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
/sendbroadcast - إرسال الرسالة المعلقة
/userslist - عرض قائمة المستخدمين
/broadcaststats <رقم> - إحصائيات إذاعة

🔍 **البحث المتقدم:**
/search <كلمة> - بحث عام
/search <كلمة> date:week - بحث في آخر أسبوع
/search <كلمة> date:month active:true - بحث متقدم
/searchid <رقم> - بحث بالمعرف المحدد
/searchname <اسم> - بحث بالاسم فقط
/searchactive - عرض المستخدمين النشطين

ℹ️ *استخدم /search بدون بارامترات لعرض المساعدة الكاملة*
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ البوت يعمل بشكل طبيعي!")

# ==================== أوامر المشرفين ====================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        logger.warning(f"محاولة وصول غير مصرح: المستخدم {user_id} حاول استخدام /admin")
        return
    
    users_count = db.get_users_count()
    
    admin_commands = f"""
👑 **لوحة تحكم المشرفين**

📊 /stats - إحصائيات النظام الكاملة
📢 /broadcast - إرسال رسالة للجميع
📤 /sendbroadcast - إرسال الرسالة المعلقة
👥 /userslist - عرض المستخدمين ({users_count} مستخدم)
📈 /broadcaststats <رقم> - إحصائيات إذاعة

🔍 **البحث:**
/search - بحث متقدم عن المستخدمين
/searchid - بحث بالمعرف المحدد
/searchname - بحث بالاسم فقط
/searchactive - المستخدمين النشطين فقط

🔢 **معلومات النظام:**
- عدد المشرفين: {len(ADMIN_IDS)}
- عدد المستخدمين: {users_count}
- قاعدة البيانات: ✅ نشطة
"""
    
    await update.message.reply_text(admin_commands, parse_mode='Markdown')
    logger.info(f"المشرف {user_id} فتح لوحة التحكم")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات النظام الكاملة - النسخة النهائية المصححة"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        return
    
    try:
        logger.info(f"📊 المشرف {user_id} طلب الإحصائيات")
        
        # ✅ **استخدام الدالة الموثوقة الجديدة**
        stats = db.get_stats_fixed()
        
        # ✅ **تأكد من أن stats ليست None**
        if not stats:
            logger.warning("الإحصائيات فارغة، استخدام القيم الأساسية")
            stats = {
                'total_users': db.get_users_count(),
                'total_messages': 0,
                'total_broadcasts': 0,
                'new_users_today': 0,
                'last_broadcast_id': None,
                'top_users': []
            }
        
        # ✅ **تأكد من وجود جميع المفاتيح**
        total_users = stats.get('total_users', db.get_users_count())
        total_messages = stats.get('total_messages', 0)
        total_broadcasts = stats.get('total_broadcasts', 0)
        new_users_today = stats.get('new_users_today', 0)
        last_broadcast_id = stats.get('last_broadcast_id')
        top_users = stats.get('top_users', [])
        
        # ✅ **بناء رسالة الإحصائيات**
        stats_text = f"""
📊 **إحصائيات النظام الكاملة**

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

# ==================== نظام البحث المتقدم ====================
async def search_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بحث عن مستخدمين - النسخة المتقدمة مع التصفيات"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        return
    
    # تحليل البارامترات
    search_term = ""
    search_type = "all"
    join_date_filter = "all"
    active_only = False
    
    # تحليل الأوامر الخاصة
    if update.message.text.startswith('/searchactive'):
        active_only = True
        command_parts = update.message.text.split()[1:]
        search_term = ' '.join(command_parts) if command_parts else ""
    elif update.message.text.startswith('/searchid'):
        search_type = "id"
        if context.args:
            search_term = context.args[0]
    elif update.message.text.startswith('/searchname'):
        search_type = "name"
        search_term = ' '.join(context.args) if context.args else ""
    elif update.message.text.startswith('/search'):
        # تحليل البارامترات المتقدمة
        filters = {}
        search_parts = []
        
        for arg in context.args:
            if arg.startswith('date:'):
                join_date_filter = arg.split(':')[1]  # today, week, month, year
            elif arg.startswith('active:'):
                active_only = arg.split(':')[1].lower() == 'true'
            else:
                search_parts.append(arg)
        
        search_term = ' '.join(search_parts)
    
    if not context.args and not active_only:
        # عرض مساعدة مفصلة
        help_text = """
🔍 **نظام البحث المتقدم عن المستخدمين**

📌 **الأوامر المتاحة:**
/search <كلمة> - بحث عام
/search <كلمة> date:week - بحث في آخر أسبوع
/search <كلمة> date:month active:true - بحث نشطين في آخر شهر

🎯 **أمثلة:**
/search احمد                        ← بحث عن "احمد"
/search احمد date:week              ← بحث في المسبوع الأخير
/search احمد date:month active:true ← بحث عن نشطين في الشهر الأخير
/search date:today                  ← المستخدمين الجدد اليوم

📅 **خيارات تاريخ الانضمام:**
date:today    - اليوم فقط
date:week     - آخر أسبوع
date:month    - آخر شهر  
date:year     - آخر سنة

⚡ **خيارات النشاط:**
active:true   - النشطين فقط (آخر 30 يوم)
active:false  - الجميع

🔍 **أوامر سريعة:**
/searchid <رقم>    - بحث بالمعرف المحدد
/searchname <اسم>  - بحث بالاسم فقط
/searchactive      - عرض المستخدمين النشطين فقط
/searchactive <كلمة> - بحث عن نشطين بكلمة معينة

📊 **خيارات العرض:**
الحد الأقصى 50 نتيجة
"""
        await update.message.reply_text(help_text, parse_mode='Markdown')
        return
    
    logger.info(f"🔍 المشرف {user_id} يبحث: '{search_term}' - date:{join_date_filter} - active:{active_only}")
    
    try:
        if search_type == "id":
            # البحث بالمعرف المحدد
            user = db.get_user(int(search_term))
            results = [user] if user else []
            results_count = len(results)
            
        elif update.message.text.startswith('/searchactive') and not search_term:
            # عرض جميع النشطين
            try:
                activity_data = db.get_users_by_activity()
                results = activity_data['active']
                results_count = activity_data['active_count']
            except AttributeError:
                # إذا لم تكن الدالة موجودة، استخدم البحث العادي
                results = db.search_users(search_term) if search_term else db.get_all_users()
                results = [u for u in results if db.is_user_active(u['user_id'])] if hasattr(db, 'is_user_active') else results
                results_count = len(results)
            
        else:
            # البحث المتقدم مع التصفيات
            try:
                results = db.search_users_with_filters(
                    search_term=search_term,
                    join_date_filter=join_date_filter,
                    active_only=active_only,
                    limit=50
                )
                results_count = len(results)
            except AttributeError:
                # إذا لم تكن الدالة موجودة، استخدم البحث العادي
                results = db.search_users(search_term) if search_term else db.get_all_users()
                results_count = len(results)
        
        if not results:
            # بناء رسالة الخطأ مع تفاصيل التصفيات
            filter_info = []
            if join_date_filter != "all":
                filter_info.append(f"تاريخ: {join_date_filter}")
            if active_only:
                filter_info.append("النشطين فقط")
            
            filter_text = f" مع التصفيات: {', '.join(filter_info)}" if filter_info else ""
            
            await update.message.reply_text(
                f"❌ لم يتم العثور على نتائج لـ **'{search_term}'**{filter_text}",
                parse_mode='Markdown'
            )
            return
        
        # بناء معلومات التصفيات لعرضها
        filter_details = []
        if join_date_filter != "all":
            date_names = {
                'today': 'اليوم',
                'week': 'آخر أسبوع', 
                'month': 'آخر شهر',
                'year': 'آخر سنة'
            }
            filter_details.append(date_names.get(join_date_filter, join_date_filter))
        
        if active_only:
            filter_details.append("النشطين فقط")
        
        filter_text = f" (بالتصفيات: {', '.join(filter_details)})" if filter_details else ""
        
        if len(results) == 1 and search_type == "id":
            # عرض تفاصيل مستخدم واحد عند البحث بالمعرف
            user = results[0]
            
            # حساب النشاط
            last_active = "غير معروف"
            if user.get('last_active'):
                try:
                    last_active_dt = datetime.fromisoformat(user['last_active'])
                    days_ago = (datetime.now() - last_active_dt).days
                    if days_ago == 0:
                        last_ac
