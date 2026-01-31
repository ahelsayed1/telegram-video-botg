import os
import logging
import sqlite3
import asyncio
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv

# تحميل المتغيرات البيئية
load_dotenv()

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

print("=" * 50)
print("🚀 بدء تشغيل البوت على Railway...")
print("=" * 50)

# ==================== قاعدة البيانات ====================
class Database:
    def __init__(self, db_name="bot_database.db"):
        self.db_name = db_name
        self.init_database()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    join_date DATETIME,
                    message_count INTEGER DEFAULT 0,
                    last_active DATETIME,
                    is_admin BOOLEAN DEFAULT 0
                )
                ''')
                
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS broadcasts (
                    broadcast_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER,
                    message_text TEXT,
                    sent_date DATETIME,
                    recipients_count INTEGER,
                    success_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0
                )
                ''')
                
                conn.commit()
                print("✅ قاعدة البيانات مهيأة وجاهزة")
                
        except Exception as e:
            print(f"❌ خطأ في قاعدة البيانات: {e}")

    def add_or_update_user(self, user_id, username, first_name, last_name=None):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                existing_user = cursor.fetchone()
                
                current_time = datetime.now().isoformat()
                
                if existing_user:
                    cursor.execute('''
                    UPDATE users 
                    SET username = ?, first_name = ?, last_name = ?, last_active = ?
                    WHERE user_id = ?
                    ''', (username, first_name, last_name, current_time, user_id))
                    
                    cursor.execute('''
                    UPDATE users 
                    SET message_count = message_count + 1 
                    WHERE user_id = ?
                    ''', (user_id,))
                    
                else:
                    cursor.execute('''
                    INSERT INTO users 
                    (user_id, username, first_name, last_name, join_date, last_active, message_count)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                    ''', (user_id, username, first_name, last_name, current_time, current_time))
                
                conn.commit()
                return True
                
        except Exception as e:
            print(f"❌ خطأ في إضافة مستخدم: {e}")
            return False

    def get_all_users(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users ORDER BY join_date DESC")
                users = cursor.fetchall()
                return [dict(user) for user in users]
        except Exception as e:
            print(f"❌ خطأ في جلب المستخدمين: {e}")
            return []

    def get_users_count(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM users")
                result = cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            print(f"❌ خطأ في جلب عدد المستخدمين: {e}")
            return 0

    def add_broadcast(self, admin_id, message_text, recipients_count, success_count, failed_count):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()
                
                cursor.execute('''
                INSERT INTO broadcasts 
                (admin_id, message_text, sent_date, recipients_count, success_count, failed_count)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (admin_id, message_text, current_time, recipients_count, success_count, failed_count))
                
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"❌ خطأ في تسجيل الإذاعة: {e}")
            return None

# كائن قاعدة البيانات العالمي
db = Database()

# ==================== HTTP Server للـ Healthcheck ====================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ['/', '/health']:
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

def run_health_server():
    try:
        port = int(os.getenv("PORT", 8080))
        server = HTTPServer(('', port), HealthHandler)
        print(f"✅ Healthcheck server started on port {port}")
        server.serve_forever()
    except Exception as e:
        print(f"❌ Healthcheck error: {e}")

# ==================== نظام المشرفين ====================
def get_admin_ids():
    admin_ids_str = os.getenv("ADMIN_IDS", "")
    if admin_ids_str:
        try:
            return [int(admin_id.strip()) for admin_id in admin_ids_str.split(",")]
        except ValueError:
            print("❌ خطأ في تنسيق ADMIN_IDS")
            return []
    return []

ADMIN_IDS = get_admin_ids()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# ==================== أوامر البوت الأساسية ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
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
/userslist - عرض قائمة المستخدمين
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ البوت يعمل بشكل طبيعي!")

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
📢 /broadcast - إرسال رسالة للجميع
👥 /userslist - عرض المستخدمين ({users_count} مستخدم)

🔢 **معلومات النظام:**
- عدد المشرفين: {len(ADMIN_IDS)}
- عدد المستخدمين: {users_count}
- قاعدة البيانات: ✅ نشطة
"""
    
    await update.message.reply_text(admin_commands, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        return
    
    users_count = db.get_users_count()
    
    stats_text = f"""
📊 **إحصائيات النظام**

👥 **المستخدمون:**
- العدد الكلي: {users_count} مستخدم

👑 **المشرفون:**
- العدد: {len(ADMIN_IDS)} مشرف
- القائمة: {ADMIN_IDS}

💾 **قاعدة البيانات:**
- ✅ SQLite نشطة
- 📁 الملف: bot_database.db
"""
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        return
    
    if update.message.reply_to_message:
        message = update.message.reply_to_message.text or "📎 (رسالة ميديا)"
        users_count = db.get_users_count()
        
        await update.message.reply_text(
            f"📢 **رسالة الإذاعة:**\n\n"
            f"{message}\n\n"
            f"👥 عدد المستهدفين: {users_count} مستخدم\n\n"
            f"⚠️ **لإرسال الرسالة للجميع:**\n"
            f"استخدم الأمر /sendbroadcast",
            parse_mode='Markdown'
        )
        
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
        await update.message.reply_text(
            "❌ لا توجد رسالة معلقة للإذاعة!\n\n"
            "**الطريقة الصحيحة:**\n"
            "1. أرسل الرسالة\n"
            "2. رد عليها بـ /broadcast\n"
            "3. استخدم /sendbroadcast"
        )
        return
    
    message = context.user_data['pending_broadcast']
    users = db.get_all_users()
    users_count = len(users)
    
    if users_count == 0:
        await update.message.reply_text("❌ لا يوجد مستخدمين لإرسال الرسالة لهم!")
        return
    
    keyboard = [
        [
            InlineKeyboardButton("✅ نعم، أرسل للجميع", callback_data="confirm_broadcast"),
            InlineKeyboardButton("❌ إلغاء", callback_data="cancel_broadcast")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📢 **تأكيد الإذاعة**\n\n"
        f"📝 الرسالة: {message[:200]}\n\n"
        f"👥 عدد المستهدفين: {users_count} مستخدم\n\n"
        f"⚠️ **هل تريد الإرسال فعلياً؟**",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    context.user_data['broadcast_data'] = {
        'message': message,
        'admin_id': user_id,
        'users_count': users_count
    }

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
        users_text += f"\n📋 عرض 10 من أصل {users_count} مستخدم"
    
    await update.message.reply_text(users_text, parse_mode='Markdown')

# ==================== معالج أزرار الإذاعة ====================
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not is_admin(user_id):
        await query.edit_message_text("⛔ ليس لديك صلاحية للقيام بهذا!")
        return
    
    if query.data == "confirm_broadcast":
        broadcast_data = context.user_data.get('broadcast_data')
        
        if not broadcast_data:
            await query.edit_message_text("❌ بيانات الإذاعة غير موجودة!")
            return
        
        message = broadcast_data['message']
        admin_id = broadcast_data['admin_id']
        users_count = broadcast_data['users_count']
        
        await query.edit_message_text(
            f"🔄 **جاري إرسال الرسالة...**\n\n"
            f"📝 إلى {users_count} مستخدم\n"
            f"⏳ قد يستغرق بضع ثوانٍ...",
            parse_mode='Markdown'
        )
        
        users = db.get_all_users()
        success_count = 0
        failed_count = 0
        
        for user in users:
            try:
                await context.bot.send_message(
                    chat_id=user['user_id'],
                    text=f"📢 **إذاعة من المشرف**\n\n{message}\n\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
                success_count += 1
            except Exception as e:
                failed_count += 1
            
            await asyncio.sleep(0.1)
        
        broadcast_id = db.add_broadcast(admin_id, message, users_count, success_count, failed_count)
        
        success_rate = (success_count / users_count * 100) if users_count > 0 else 0
        
        await query.edit_message_text(
            f"✅ **تم إكمال الإذاعة بنجاح!**\n\n"
            f"🆔 رقم الإذاعة: #{broadcast_id}\n"
            f"📝 الرسالة: '{message[:50]}...'\n\n"
            f"📊 **الإحصائيات:**\n"
            f"• ✅ تم الإرسال لـ: {success_count} مستخدم\n"
            f"• ❌ فشل الإرسال لـ: {failed_count} مستخدم\n"
            f"• 👥 الإجمالي: {users_count} مستخدم\n"
            f"• 📈 نسبة النجاح: {success_rate:.1f}%\n\n"
            f"💾 تم حفظ التفاصيل في قاعدة البيانات",
            parse_mode='Markdown'
        )
        
        if 'pending_broadcast' in context.user_data:
            del context.user_data['pending_broadcast']
        if 'broadcast_data' in context.user_data:
            del context.user_data['broadcast_data']
    
    elif query.data == "cancel_broadcast":
        await query.edit_message_text("❌ تم إلغاء الإذاعة.")
        
        if 'pending_broadcast' in context.user_data:
            del context.user_data['pending_broadcast']
        if 'broadcast_data' in context.user_data:
            del context.user_data['broadcast_data']

# ==================== الوظائف الرئيسية ====================
def setup_handlers(application):
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("sendbroadcast", send_broadcast_command))
    application.add_handler(CommandHandler("userslist", users_list_command))
    
    application.add_handler(CallbackQueryHandler(handle_callback_query))

def run_bot():
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        print("❌ ERROR: BOT_TOKEN not set!")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    setup_handlers(application)
    
    print("🤖 بدأ تشغيل بوت تليجرام...")
    print(f"👑 عدد المشرفين: {len(ADMIN_IDS)}")
    
    users_count = db.get_users_count()
    print(f"👥 عدد المستخدمين المسجلين: {users_count}")
    
    application.run_polling(drop_pending_updates=True)

def main():
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        print("❌ ERROR: BOT_TOKEN not set in Railway variables!")
        return
    
    print(f"✅ BOT_TOKEN: {'SET' if BOT_TOKEN else 'MISSING'}")
    print(f"👑 ADMIN_IDS: {os.getenv('ADMIN_IDS', 'Not set')}")
    
    health_thread = Thread(target=run_health_server, daemon=True)
    health_thread.start()
    print("✅ Healthcheck server started in background")
    
    import time
    time.sleep(3)
    print("✅ Waiting 3 seconds for healthcheck to be ready...")
    
    print("🤖 Starting Telegram Bot...")
    run_bot()

if __name__ == "__main__":
    main()                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"❌ خطأ في إضافة/تحديث المستخدم: {e}")
            return False
    
    def get_user(self, user_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                user = cursor.fetchone()
                return dict(user) if user else None
        except Exception as e:
            logger.error(f"❌ خطأ في جلب بيانات المستخدم: {e}")
            return None
    
    def get_all_users(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users ORDER BY join_date DESC")
                users = cursor.fetchall()
                return [dict(user) for user in users]
        except Exception as e:
            logger.error(f"❌ خطأ في جلب جميع المستخدمين: {e}")
            return []
    
    def get_users_count(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM users")
                result = cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"❌ خطأ في جلب عدد المستخدمين: {e}")
            return 0
    
    def get_stats(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                stats = {}
                
                cursor.execute("SELECT COUNT(*) as count FROM users")
                stats['total_users'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) as count FROM users WHERE date(join_date) = date('now')")
                stats['new_users_today'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT SUM(message_count) as total FROM users")
                result = cursor.fetchone()
                stats['total_messages'] = result[0] if result[0] else 0
                
                cursor.execute("SELECT COUNT(*) as count FROM broadcasts")
                stats['total_broadcasts'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT SUM(success_count) as total FROM broadcasts")
                result = cursor.fetchone()
                stats['total_broadcast_messages'] = result[0] if result[0] else 0
                
                return stats
                
        except Exception as e:
            logger.error(f"❌ خطأ في جلب الإحصائيات: {e}")
            return {}
    
    def add_broadcast(self, admin_id, message_text, recipients_count, success_count, failed_count):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()
                
                cursor.execute('''
                INSERT INTO broadcasts 
                (admin_id, message_text, sent_date, recipients_count, success_count, failed_count)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (admin_id, message_text, current_time, recipients_count, success_count, failed_count))
                
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"❌ خطأ في تسجيل الإذاعة: {e}")
            return None
    
    def add_broadcast_status(self, broadcast_id, user_id, status):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()
                
                cursor.execute('''
                INSERT INTO broadcast_status (broadcast_id, user_id, status, sent_date)
                VALUES (?, ?, ?, ?)
                ''', (broadcast_id, user_id, status, current_time))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في تسجيل حالة الإرسال: {e}")
            return False
    
    def get_broadcast_details(self, broadcast_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM broadcasts WHERE broadcast_id = ?", (broadcast_id,))
                broadcast = cursor.fetchone()
                return dict(broadcast) if broadcast else None
        except Exception as e:
            logger.error(f"❌ خطأ في جلب تفاصيل الإذاعة: {e}")
            return None

# كائن قاعدة البيانات العالمي
db = Database()

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
        pass

def run_health_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    logger.info(f"🌐 خادم الـ healthcheck يعمل على المنفذ {port}")
    server.serve_forever()

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
/userslist - عرض قائمة المستخدمين
/broadcasts - عرض الإذاعات السابقة
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
    stats = db.get_stats()
    
    admin_commands = f"""
👑 **لوحة تحكم المشرفين**

📊 /stats - إحصائيات النظام
📢 /broadcast - إرسال رسالة للجميع
👥 /userslist - عرض المستخدمين ({users_count} مستخدم)
📋 /broadcasts - الإذاعات السابقة

🔢 **معلومات النظام:**
- المشرفين: {len(ADMIN_IDS)}
- المستخدمين: {users_count}
- الرسائل: {stats.get('total_messages', 0)}
- الإذاعات: {stats.get('total_broadcasts', 0)}
- قاعدة البيانات: ✅ نشطة
"""
    
    await update.message.reply_text(admin_commands, parse_mode='Markdown')
    logger.info(f"المشرف {user_id} فتح لوحة التحكم")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        return
    
    stats = db.get_stats()
    users_count = db.get_users_count()
    
    stats_text = f"""
📊 **إحصائيات النظام الحقيقية**

👥 **المستخدمون:**
- العدد الكلي: {users_count} مستخدم
- الجدد اليوم: {stats.get('new_users_today', 0)}
- الرسائل الكلية: {stats.get('total_messages', 0)}

📢 **الإذاعات:**
- عدد الإذاعات: {stats.get('total_broadcasts', 0)}
- رسائل الإذاعة: {stats.get('total_broadcast_messages', 0)}

👑 **المشرفون:**
- العدد: {len(ADMIN_IDS)} مشرف
- القائمة: {ADMIN_IDS}

💾 **قاعدة البيانات:**
- ✅ SQLite نشطة
- 📁 الملف: bot_database.db
"""
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')
    logger.info(f"المشرف {user_id} طلب الإحصائيات")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        return
    
    if update.message.reply_to_message:
        message = update.message.reply_to_message.text
        if not message:
            message = "📎 (رسالة ميديا)"
        
        users_count = db.get_users_count()
        
        await update.message.reply_text(
            f"📢 **رسالة الإذاعة المعدة:**\n\n"
            f"{message}\n\n"
            f"👥 عدد المستهدفين: {users_count} مستخدم\n\n"
            f"⚠️ **لإرسال الرسالة للجميع:**\n"
            f"استخدم الأمر /sendbroadcast",
            parse_mode='Markdown'
        )
        
        # حفظ الرسالة مؤقتاً في context
        context.user_data['pending_broadcast'] = message
    else:
        await update.message.reply_text(
            "📝 **طريقة استخدام /broadcast:**\n\n"
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
        await update.message.reply_text(
            "❌ لا توجد رسالة معلقة للإذاعة!\n\n"
            "**الطريقة الصحيحة:**\n"
            "1. أرسل الرسالة\n"
            "2. رد عليها بـ /broadcast\n"
            "3. استخدم /sendbroadcast"
        )
        return
    
    message = context.user_data['pending_broadcast']
    users = db.get_all_users()
    users_count = len(users)
    
    if users_count == 0:
        await update.message.reply_text("❌ لا يوجد مستخدمين لإرسال الرسالة لهم!")
        return
    
    # زر التأكيد
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    keyboard = [
        [
            InlineKeyboardButton("✅ نعم، أرسل للجميع", callback_data="confirm_broadcast"),
            InlineKeyboardButton("❌ إلغاء", callback_data="cancel_broadcast")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📢 **تأكيد الإذاعة**\n\n"
        f"📝 الرسالة: {message[:200]}\n\n"
        f"👥 عدد المستهدفين: {users_count} مستخدم\n\n"
        f"⚠️ **هل تريد الإرسال فعلياً؟**",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    # حفظ البيانات للاستخدام لاحقاً
    context.user_data['broadcast_data'] = {
        'message': message,
        'admin_id': user_id,
        'users_count': users_count
    }

async def broadcasts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        return
    
    # جلب آخر 5 إذاعات (ستحتاج دالة جديدة في قاعدة البيانات)
    await update.message.reply_text(
        "📋 **قائمة الإذاعات السابقة**\n\n"
        "🔧 هذه الميزة قيد التطوير\n\n"
        "ستظهر هنا:\n"
        "- تاريخ الإذاعة\n"
        "- عدد المستلمين\n"
        "- نسبة النجاح\n"
        "- نص الرسالة\n\n"
        "🎯 قادم قريباً...",
        parse_mode='Markdown'
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

# ==================== معالج أزرار الإذاعة ====================
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not is_admin(user_id):
        await query.edit_message_text("⛔ ليس لديك صلاحية للقيام بهذا!")
        return
    
    if query.data == "confirm_broadcast":
        # بدء عملية الإرسال
        broadcast_data = context.user_data.get('broadcast_data')
        
        if not broadcast_data:
            await query.edit_message_text("❌ بيانات الإذاعة غير موجودة!")
            return
        
        message = broadcast_data['message']
        admin_id = broadcast_data['admin_id']
        users_count = broadcast_data['users_count']
        
        await query.edit_message_text(
            f"🔄 **جاري إرسال الرسالة...**\n\n"
            f"📝 إلى {users_count} مستخدم\n"
            f"⏳ قد يستغرق بضع ثوانٍ...",
            parse_mode='Markdown'
        )
        
        # جلب جميع المستخدمين
        users = db.get_all_users()
        success_count = 0
        failed_count = 0
        
        # إرسال الرسالة لكل مستخدم
        for user in users:
            try:
                await context.bot.send_message(
                    chat_id=user['user_id'],
                    text=f"📢 **إذاعة من المشرف**\n\n{message}\n\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
                success_count += 1
                logger.info(f"✅ تم إرسال إذاعة للمستخدم {user['user_id']}")
            except Exception as e:
                failed_count += 1
                logger.error(f"❌ فشل إرسال إذاعة للمستخدم {user['user_id']}: {e}")
            
            # تأخير بسيط لتجنب rate limits
            await asyncio.sleep(0.05)
        
        # حفظ الإذاعة في قاعدة البيانات
        broadcast_id = db.add_broadcast(admin_id, message, users_count, success_count, failed_count)
        
        # تسجيل حالة كل إرسال
        if broadcast_id:
            for user in users:
                try:
                    await context.bot.s                
                cursor.execute("SELECT COUNT(*) as count FROM users")
                stats['total_users'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) as count FROM users WHERE date(join_date) = date('now')")
                stats['new_users_today'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT SUM(message_count) as total FROM users")
                result = cursor.fetchone()
                stats['total_messages'] = result[0] if result[0] else 0
                
                cursor.execute("SELECT COUNT(*) as count FROM broadcasts")
                stats['total_broadcasts'] = cursor.fetchone()[0]
                
                return stats
                
        except Exception as e:
            logger.error(f"❌ خطأ في جلب الإحصائيات: {e}")
            return {}
    
    def add_broadcast(self, admin_id, message_text, recipients_count):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()
                
                cursor.execute('''
                INSERT INTO broadcasts (admin_id, message_text, sent_date, recipients_count)
                VALUES (?, ?, ?, ?)
                ''', (admin_id, message_text, current_time, recipients_count))
                
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"❌ خطأ في تسجيل الإذاعة: {e}")
            return None

# كائن قاعدة البيانات العالمي
db = Database()

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
        pass

def run_health_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    logger.info(f"🌐 خادم الـ healthcheck يعمل على المنفذ {port}")
    server.serve_forever()

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
/userslist - عرض قائمة المستخدمين
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

📊 /stats - إحصائيات النظام
📢 /broadcast - إرسال رسالة للجميع
👥 /userslist - عرض المستخدمين ({users_count} مستخدم)

🔢 **معلومات النظام:**
- عدد المشرفين: {len(ADMIN_IDS)}
- عدد المستخدمين: {users_count}
- قاعدة البيانات: ✅ نشطة
"""
    
    await update.message.reply_text(admin_commands, parse_mode='Markdown')
    logger.info(f"المشرف {user_id} فتح لوحة التحكم")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط!")
        return
    
    stats = db.get_stats()
    users_count = db.get_users_count()
    
    stats_text = f"""
📊 **إحصائيات النظام الحقيقية**

👥 **المستخدمون:**
- العدد الكلي: {users_count} مستخدم
- المستخدمين الجدد اليوم: {stats.get('new_users_today', 0)}
- الرسائل الكلية: {stats.get('total_messages', 0)}

📢 **الإذاعات:**
- عدد الإذاعات: {stats.get('total_broadcasts', 0)}

👑 **المشرفون:**
- العدد: {len(ADMIN_IDS)} مشرف
- القائمة: {ADMIN_IDS}

💾 **قاعدة البيانات:**
- ✅ SQLite نشطة
- 📁 الملف: bot_database.db
"""
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')
    logger.info(f"المشرف {user_id} طلب الإحصائيات")

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
    users_count = db.get_users_count()
    
    # هنا سيكون كود الإرسال الفعلي للمستخدمين
    # حالياً، نحفظها في قاعدة البيانات فقط
    
    broadcast_id = db.add_broadcast(user_id, message, users_count)
    
    if broadcast_id:
        await update.message.reply_text(
            f"✅ **تم حفظ الإذاعة في قاعدة البيانات**\n\n"
            f"📝 الرسالة: '{message[:100]}...'\n"
            f"👥 عدد المستهدفين: {users_count}\n"
            f"🆔 رقم الإذاعة: {broadcast_id}\n\n"
            f"ℹ️ *لاحظ:* نظام الإرسال الفعلي يحتاج تطوير إضافي.",
            parse_mode='Markdown'
        )
        del context.user_data['pending_broadcast']
    else:
        await update.message.reply_text("❌ فشل في حفظ الإذاعة!")

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

# ==================== الوظائف الرئيسية ====================
def setup_handlers(application):
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("sendbroadcast", send_broadcast_command))
    application.add_handler(CommandHandler("userslist", users_list_command))

def run_bot():
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير معين")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    setup_handlers(application)
    
    logger.info(f"🤖 بدأ تشغيل بوت تليجرام...")
    logger.info(f"👑 عدد المشرفين: {len(ADMIN_IDS)}")
    
    users_count = db.get_users_count()
    logger.info(f"👥 عدد المستخدمين المسجلين: {users_count}")
    
    application.run_polling(drop_pending_updates=True)

def main():
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        logger.error("❌ يرجى تعيين BOT_TOKEN في متغيرات Railway")
        return
    
    health_thread = Thread(target=run_health_server, daemon=True)
    health_thread.start()
    logger.info("✅ بدأ خادم الـ healthcheck")
    
    run_bot()

if __name__ == "__main__":
    main()
