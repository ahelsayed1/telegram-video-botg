# database.py - النسخة النهائية مع دعم رسالة الترحيب القابلة للتعديل
import sqlite3
import logging
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_name="bot_database.db"):
        """تهيئة قاعدة البيانات"""
        self.db_name = db_name
        self.init_database()
    
    def get_connection(self):
        """الحصول على اتصال بقاعدة البيانات"""
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """إنشاء الجداول إذا لم تكن موجودة"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # جدول المستخدمين
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    join_date TEXT,
                    message_count INTEGER DEFAULT 0,
                    last_active TEXT,
                    is_admin BOOLEAN DEFAULT 0
                )
                ''')
                
                # جدول الإذاعات
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS broadcasts (
                    broadcast_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER,
                    message_text TEXT,
                    sent_date TEXT,
                    recipients_count INTEGER
                )
                ''')
                
                # جدول سجلات النشاط
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS activity_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action TEXT,
                    timestamp TEXT,
                    details TEXT
                )
                ''')
                
                # جدول الإعدادات - الجديد
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT
                )
                ''')
                
                # إضافة الإعدادات الافتراضية
                self._add_default_settings(cursor)
                
                conn.commit()
                logger.info("✅ قاعدة البيانات مهيأة وجاهزة")
                
        except Exception as e:
            logger.error(f"❌ خطأ في تهيئة قاعدة البيانات: {e}")
    
    def _add_default_settings(self, cursor):
        """إضافة الإعدادات الافتراضية"""
        try:
            # رسالة الترحيب الافتراضية
            default_welcome = """🚀 مرحباً {first_name}!

🎯 تم تسجيل دخولك في قاعدة البيانات بنجاح!

📊 معلومات حسابك:
🆔 المعرف: {user_id}
👤 الاسم: {first_name} {last_name}
📅 وقت التسجيل: {current_time}

✅ استخدم /help لعرض الأوامر المتاحة"""
            
            # تحقق إذا كان الإعداد موجوداً بالفعل
            cursor.execute("SELECT key FROM settings WHERE key = ?", ('welcome_message',))
            if not cursor.fetchone():
                current_time = datetime.now().isoformat()
                cursor.execute('''
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ''', ('welcome_message', default_welcome, current_time))
                logger.info("✅ تم إضافة رسالة الترحيب الافتراضية")
                
        except Exception as e:
            logger.error(f"❌ خطأ في إضافة الإعدادات الافتراضية: {e}")
    
    # ==================== دوال المستخدمين ====================
    def add_or_update_user(self, user_id, username, first_name, last_name=None):
        """إضافة أو تحديث مستخدم"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                current_time = datetime.now().isoformat()
                
                # تحقق إذا كان المستخدم موجوداً
                cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
                existing_user = cursor.fetchone()
                
                if existing_user:
                    # تحديث المستخدم الموجود
                    cursor.execute('''
                    UPDATE users 
                    SET username=?, first_name=?, last_name=?, last_active=?
                    WHERE user_id=?
                    ''', (username, first_name, last_name, current_time, user_id))
                    
                    # زيادة عداد الرسائل
                    cursor.execute('''
                    UPDATE users 
                    SET message_count = message_count + 1 
                    WHERE user_id = ?
                    ''', (user_id,))
                else:
                    # إضافة مستخدم جديد
                    cursor.execute('''
                    INSERT INTO users 
                    (user_id, username, first_name, last_name, join_date, last_active, message_count)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                    ''', (user_id, username, first_name, last_name, current_time, current_time))
                
                conn.commit()
                logger.info(f"✅ تم إضافة/تحديث المستخدم: {user_id} - {first_name}")
                return True
                
        except Exception as e:
            logger.error(f"❌ خطأ في إضافة/تحديث المستخدم: {e}")
            return False
    
    def get_user(self, user_id):
        """الحصول على معلومات مستخدم"""
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
        """الحصول على جميع المستخدمين"""
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
        """الحصول على عدد المستخدمين - موثوق 100%"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users")
                result = cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"❌ خطأ في جلب عدد المستخدمين: {e}")
            return 0
    
    def get_active_users_count(self, days=7):
        """الحصول على عدد المستخدمين النشطين"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
                cursor.execute('''
                SELECT COUNT(*) FROM users 
                WHERE last_active >= ?
                ''', (cutoff_date,))
                result = cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"❌ خطأ في جلب المستخدمين النشطين: {e}")
            return 0
    
    # ==================== دوال الإذاعة ====================
    def add_broadcast(self, admin_id, message_text, recipients_count):
        """تسجيل إذاعة جديدة"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()
                
                cursor.execute('''
                INSERT INTO broadcasts (admin_id, message_text, sent_date, recipients_count)
                VALUES (?, ?, ?, ?)
                ''', (admin_id, message_text, current_time, recipients_count))
                
                conn.commit()
                broadcast_id = cursor.lastrowid
                logger.info(f"✅ تم حفظ إذاعة #{broadcast_id}")
                return broadcast_id
        except Exception as e:
            logger.error(f"❌ خطأ في تسجيل الإذاعة: {e}")
            return None
    
    def get_broadcasts(self, limit=10):
        """الحصول على آخر الإذاعات"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                SELECT b.*, u.first_name as admin_name 
                FROM broadcasts b
                LEFT JOIN users u ON b.admin_id = u.user_id
                ORDER BY sent_date DESC
                LIMIT ?
                ''', (limit,))
                broadcasts = cursor.fetchall()
                return [dict(broadcast) for broadcast in broadcasts]
        except Exception as e:
            logger.error(f"❌ خطأ في جلب الإذاعات: {e}")
            return []
    
    def get_broadcast_stats(self, broadcast_id):
        """الحصول على إحصائيات إذاعة محددة"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                SELECT * FROM broadcasts WHERE broadcast_id = ?
                ''', (broadcast_id,))
                broadcast = cursor.fetchone()
                return dict(broadcast) if broadcast else None
        except Exception as e:
            logger.error(f"❌ خطأ في جلب إحصائيات الإذاعة: {e}")
            return None
    
    # ==================== دوال الإحصائيات ====================
    def get_stats_simple(self):
        """الحصول على إحصائيات مبسطة"""
        try:
            stats = {}
            
            # عدد المستخدمين
            stats['total_users'] = self.get_users_count()
            
            # عدد الرسائل
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT SUM(message_count) FROM users")
                result = cursor.fetchone()[0]
                stats['total_messages'] = int(result) if result else 0
            
            # عدد الإذاعات
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM broadcasts")
                stats['total_broadcasts'] = cursor.fetchone()[0] or 0
            
            # المستخدمين الجدد اليوم
            with self.get_connection() as conn:
                cursor = conn.cursor()
                today = datetime.now().strftime('%Y-%m-%d')
                cursor.execute("SELECT COUNT(*) FROM users WHERE join_date LIKE ?", (f'{today}%',))
                stats['new_users_today'] = cursor.fetchone()[0] or 0
            
            # آخر إذاعة
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT MAX(broadcast_id) FROM broadcasts")
                stats['last_broadcast_id'] = cursor.fetchone()[0]
            
            logger.info(f"✅ الإحصائيات المبسطة المحسوبة: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"❌ خطأ في جلب الإحصائيات المبسطة: {e}")
            return {
                'total_users': self.get_users_count(),
                'total_messages': 0,
                'total_broadcasts': 0,
                'new_users_today': 0,
                'last_broadcast_id': None
            }
    
    def get_stats_fixed(self):
        """إحصائيات موثوقة 100% - لا تعطي أي أخطاء"""
        try:
            logger.info("🔍 بدء جمع الإحصائيات الموثوقة...")
            stats = {}
            
            # 1. عدد المستخدمين - الطريقة الأكيدة
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users")
                result = cursor.fetchone()
                stats['total_users'] = result[0] if result else 0
            
            logger.info(f"👥 عدد المستخدمين: {stats['total_users']}")
            
            # 2. عدد الرسائل
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT SUM(message_count) FROM users")
                result = cursor.fetchone()
                total = result[0] if result else 0
                stats['total_messages'] = int(total) if total else 0
            
            logger.info(f"💬 عدد الرسائل: {stats['total_messages']}")
            
            # 3. عدد الإذاعات
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM broadcasts")
                result = cursor.fetchone()
                stats['total_broadcasts'] = result[0] if result else 0
            
            logger.info(f"📢 عدد الإذاعات: {stats['total_broadcasts']}")
            
            # 4. آخر إذاعة
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT MAX(broadcast_id) FROM broadcasts")
                result = cursor.fetchone()
                stats['last_broadcast_id'] = result[0] if result else None
            
            # 5. المستخدمين الجدد اليوم
            with self.get_connection() as conn:
                cursor = conn.cursor()
                today = datetime.now().strftime('%Y-%m-%d')
                cursor.execute("SELECT COUNT(*) FROM users WHERE join_date LIKE ?", (f'{today}%',))
                result = cursor.fetchone()
                stats['new_users_today'] = result[0] if result else 0
            
            logger.info(f"🆕 مستخدمين جدد اليوم: {stats['new_users_today']}")
            
            # 6. المستخدمين الأكثر نشاطاً
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                    SELECT first_name, message_count 
                    FROM users 
                    ORDER BY message_count DESC 
                    LIMIT 3
                    ''')
                    top_users = cursor.fetchall()
                    stats['top_users'] = [dict(row) for row in top_users]
            except Exception as top_error:
                logger.warning(f"⚠️ خطأ في جلب المستخدمين النشطين: {top_error}")
                stats['top_users'] = []
            
            logger.info(f"✅ الإحصائيات الموثوقة المحسوبة بنجاح")
            return stats
            
        except Exception as e:
            logger.error(f"❌ خطأ في get_stats_fixed: {e}", exc_info=True)
            # إرجاع قيم أساسية مضمونة
            return {
                'total_users': self.get_users_count(),
                'total_messages': 0,
                'total_broadcasts': 0,
                'last_broadcast_id': None,
                'new_users_today': 0,
                'top_users': []
            }
    
    def get_stats(self):
        """الدالة الرئيسية للإحصائيات (للتوافق)"""
        # نستخدم النسخة الموثوقة
        return self.get_stats_fixed()
    
    # ==================== دوال الإعدادات ====================
    def get_setting(self, key, default=None):
        """الحصول على إعداد"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
                result = cursor.fetchone()
                return result['value'] if result else default
                
        except Exception as e:
            logger.error(f"❌ خطأ في جلب الإعداد {key}: {e}")
            return default
    
    def set_setting(self, key, value):
        """تعيين إعداد"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()
                
                cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ''', (key, value, current_time))
                
                conn.commit()
                logger.info(f"✅ تم حفظ الإعداد: {key} = {value[:50]}...")
                return True
                
        except Exception as e:
            logger.error(f"❌ خطأ في حفظ الإعداد {key}: {e}")
            return False
    
    def get_welcome_message(self):
        """الحصول على رسالة الترحيب"""
        default_welcome = """🚀 مرحباً {first_name}!

🎯 تم تسجيل دخولك في قاعدة البيانات بنجاح!

📊 معلومات حسابك:
🆔 المعرف: {user_id}
👤 الاسم: {first_name} {last_name}
📅 وقت التسجيل: {current_time}

✅ استخدم /help لعرض الأوامر المتاحة"""
        
        return self.get_setting('welcome_message', default_welcome)
    
    def set_welcome_message(self, message):
        """تعيين رسالة الترحيب"""
        return self.set_setting('welcome_message', message)
    
    def get_all_settings(self):
        """الحصول على جميع الإعدادات"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT key, value, updated_at FROM settings")
                settings = cursor.fetchall()
                return [dict(setting) for setting in settings]
        except Exception as e:
            logger.error(f"❌ خطأ في جلب جميع الإعدادات: {e}")
            return []
    
    # ==================== دوال النشاط ====================
    def log_activity(self, user_id, action, details=None):
        """تسجيل نشاط المستخدم"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()
                
                cursor.execute('''
                INSERT INTO activity_logs (user_id, action, timestamp, details)
                VALUES (?, ?, ?, ?)
                ''', (user_id, action, current_time, details))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في تسجيل النشاط: {e}")
            return False
    
    def get_recent_activities(self, limit=20):
        """الحصول على آخر الأنشطة"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                SELECT a.*, u.first_name, u.username 
                FROM activity_logs a
                LEFT JOIN users u ON a.user_id = u.user_id
                ORDER BY timestamp DESC
                LIMIT ?
                ''', (limit,))
                activities = cursor.fetchall()
                return [dict(activity) for activity in activities]
        except Exception as e:
            logger.error(f"❌ خطأ في جلب الأنشطة: {e}")
            return []
    
    # ==================== دوال النسخ الاحتياطي ====================
    def backup_database(self, backup_name=None):
        """إنشاء نسخة احتياطية من قاعدة البيانات"""
        import shutil
        
        try:
            if backup_name is None:
                backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            
            shutil.copy2(self.db_name, backup_name)
            logger.info(f"✅ تم إنشاء نسخة احتياطية: {backup_name}")
            return backup_name
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء النسخة الاحتياطية: {e}")
            return None
    
    def cleanup_old_logs(self, days=30):
        """تنظيف سجلات النشاط القديمة"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
                cursor.execute('''
 
