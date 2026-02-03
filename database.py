# database.py - النسخة البسيطة المصححة
import sqlite3
import logging
from datetime import datetime

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
                
                conn.commit()
                logger.info("✅ قاعدة البيانات جاهزة")
                
        except Exception as e:
            logger.error(f"❌ خطأ في تهيئة قاعدة البيانات: {e}")
    
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
                cursor.execute("SELECT COUNT(*) FROM users")
                result = cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"❌ خطأ في جلب عدد المستخدمين: {e}")
            return 0

# إنشاء كائن قاعدة بيانات عالمي
db = Database()
