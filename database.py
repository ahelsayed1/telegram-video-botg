# database.py
import sqlite3
import logging
from datetime import datetime
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
        conn.row_factory = sqlite3.Row  # للحصول على نتائج كـ dictionary
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
                    join_date DATETIME,
                    message_count INTEGER DEFAULT 0,
                    last_active DATETIME,
                    is_admin BOOLEAN DEFAULT 0
                )
                ''')
                
                # جدول الإذاعات
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS broadcasts (
                    broadcast_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER,
                    message_text TEXT,
                    sent_date DATETIME,
                    recipients_count INTEGER,
                    FOREIGN KEY (admin_id) REFERENCES users (user_id)
                )
                ''')
                
                # جدول سجلات النشاط
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS activity_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action TEXT,
                    timestamp DATETIME,
                    details TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
                ''')
                
                # إنشاء الفهارس لتحسين الأداء
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_join_date ON users(join_date DESC)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_active DESC)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_broadcasts_date ON broadcasts(sent_date DESC)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_activity_user_action ON activity_logs(user_id, action)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_activity_timestamp ON activity_logs(timestamp DESC)')
                
                conn.commit()
                logger.info("✅ قاعدة البيانات مهيأة وجاهزة")
                
        except Exception as e:
            logger.error(f"❌ خطأ في تهيئة قاعدة البيانات: {e}")
    
    # ==================== دوال المستخدمين ====================
    def add_or_update_user(self, user_id, username, first_name, last_name=None):
        """إضافة أو تحديث مستخدم"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # تحقق إذا كان المستخدم موجوداً
                cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                existing_user = cursor.fetchone()
                
                current_time = datetime.now().isoformat()
                
                if existing_user:
                    # تحديث المستخدم الموجود
                    cursor.execute('''
                    UPDATE users 
                    SET username = ?, first_name = ?, last_name = ?, last_active = ?
                    WHERE user_id = ?
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
        """الحصول على عدد المستخدمين"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM users")
                result = cursor.fetchone()
                return result['count'] if result else 0
        except Exception as e:
            logger.error(f"❌ خطأ في جلب عدد المستخدمين: {e}")
            return 0
    
    def get_active_users_count(self, days=7):
        """الحصول على عدد المستخدمين النشطين خلال الأيام المحددة"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                SELECT COUNT(*) as count FROM users 
                WHERE last_active >= datetime('now', ?)
                ''', (f'-{days} days',))
                result = cursor.fetchone()
                return result['count'] if result else 0
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
                return cursor.lastrowid
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
                SELECT b.*, u.first_name as admin_name,
                       (SELECT COUNT(*) FROM activity_logs 
                        WHERE action = 'broadcast_received' 
                        AND details LIKE ?) as delivered_count,
                       (SELECT COUNT(*) FROM activity_logs 
                        WHERE action = 'broadcast_replied' 
                        AND details LIKE ?) as replied_count
                FROM broadcasts b
                LEFT JOIN users u ON b.admin_id = u.user_id
                WHERE b.broadcast_id = ?
                ''', (f'%broadcast_id={broadcast_id}%', f'%broadcast_id={broadcast_id}%', broadcast_id))
                
                broadcast = cursor.fetchone()
                return dict(broadcast) if broadcast else None
                
        except Exception as e:
            logger.error(f"❌ خطأ في جلب إحصائيات الإذاعة: {e}")
            return None
    
    # ==================== دوال الإحصائيات ====================
    def get_stats(self):
        """الحصول على إحصائيات شاملة"""
        try:
            logger.info("🔍 بدء جمع الإحصائيات...")
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                stats = {}
                
                # 1. عدد المستخدمين الكلي
                cursor.execute("SELECT COUNT(*) as count FROM users")
                result = cursor.fetchone()
                stats['total_users'] = result['count'] if result and 'count' in result.keys() else 0
                logger.info(f"👥 عدد المستخدمين: {stats['total_users']}")
                
                # 2. عدد المستخدمين الجدد اليوم
                cursor.execute('''
                SELECT COUNT(*) as count FROM users 
                WHERE date(join_date) = date('now', 'localtime')
                ''')
                result = cursor.fetchone()
                stats['new_users_today'] = result['count'] if result and 'count' in result.keys() else 0
                logger.info(f"🆕 مستخدمين جدد اليوم: {stats['new_users_today']}")
                
                # 3. عدد الرسائل الكلي
                cursor.execute("SELECT COALESCE(SUM(message_count), 0) as total FROM users")
                result = cursor.fetchone()
                stats['total_messages'] = result['total'] if result and 'total' in result.keys() else 0
                logger.info(f"💬 عدد الرسائل: {stats['total_messages']}")
                
                # 4. عدد الإذاعات
                cursor.execute("SELECT COUNT(*) as count FROM broadcasts")
                result = cursor.fetchone()
                stats['total_broadcasts'] = result['count'] if result and 'count' in result.keys() else 0
                logger.info(f"📢 عدد الإذاعات: {stats['total_broadcasts']}")
                
                # 5. المستخدمين الأكثر نشاطاً (اختياري)
                try:
                    cursor.execute('''
                    SELECT first_name, message_count 
                    FROM users 
                    ORDER BY message_count DESC 
                    LIMIT 5
                    ''')
                    stats['top_users'] = [dict(row) for row in cursor.fetchall()]
                except:
                    stats['top_users'] = []
                
                logger.info(f"✅ الإحصائيات المحسوبة بنجاح: {stats}")
                return stats
                
        except Exception as e:
            logger.error(f"❌ خطأ في جلب الإحصائيات: {e}", exc_info=True)
            # إرجاع قيم افتراضية في حالة الخطأ
            return {
                'total_users': self.get_users_count(),
                'new_users_today': 0,
                'total_messages': 0,
                'total_broadcasts': 0,
                'top_users': []
            }
    
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
    
    # ==================== دوال النسخ الاحتياطي ====================
    def backup_database(self, backup_name=None):
        """إنشاء نسخة احتياطية من قاعدة البيانات"""
        import shutil
        from datetime import datetime
        
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
                cursor.execute('''
                DELETE FROM activity_logs 
                WHERE timestamp < datetime('now', ?)
                ''', (f'-{days} days',))
                deleted_count = cursor.rowcount
                conn.commit()
                logger.info(f"✅ تم تنظيف {deleted_count} سجل نشاط قديم")
                return deleted_count
        except Exception as e:
            logger.error(f"❌ خطأ في تنظيف السجلات: {e}")
            return 0

# إنشاء كائن قاعدة بيانات عالمي
db = Database()
