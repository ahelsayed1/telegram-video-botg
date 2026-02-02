# database.py - النسخة المبسطة والموثوقة
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
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """إنشاء الجداول إذا لم تكن موجودة"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
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
                
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS broadcasts (
                    broadcast_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER,
                    message_text TEXT,
                    sent_date TEXT,
                    recipients_count INTEGER
                )
                ''')
                
                conn.commit()
                logger.info("✅ قاعدة البيانات جاهزة")
                
        except Exception as e:
            logger.error(f"❌ خطأ في تهيئة قاعدة البيانات: {e}")
    
    def add_or_update_user(self, user_id, username, first_name, last_name=None):
        """إضافة أو تحديث مستخدم"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                current_time = datetime.now().isoformat()
                
                cursor.execute('''
                SELECT user_id FROM users WHERE user_id = ?
                ''', (user_id,))
                
                if cursor.fetchone():
                    cursor.execute('''
                    UPDATE users 
                    SET username=?, first_name=?, last_name=?, last_active=?
                    WHERE user_id=?
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
            logger.error(f"❌ خطأ في إضافة/تحديث المستخدم: {e}")
            return False
    
    def get_users_count(self):
        """الحصول على عدد المستخدمين"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users")
                return cursor.fetchone()[0] or 0
        except Exception as e:
            logger.error(f"❌ خطأ في جلب عدد المستخدمين: {e}")
            return 0
    
    def get_all_users(self):
        """الحصول على جميع المستخدمين"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users ORDER BY join_date DESC")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"❌ خطأ في جلب جميع المستخدمين: {e}")
            return []
    
    def get_stats_simple(self):
        """الحصول على إحصائيات مبسطة وموثوقة"""
        try:
            stats = {}
            
            # عدد المستخدمين
            stats['total_users'] = self.get_users_count()
            
            # عدد الرسائل
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT SUM(message_count) FROM users")
                result = cursor.fetchone()
                stats['total_messages'] = result[0] if result and result[0] is not None else 0
            
            # عدد الإذاعات
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM broadcasts")
                stats['total_broadcasts'] = cursor.fetchone()[0] or 0
            
            # المستخدمين الجدد اليوم
            with self.get_connection() as conn:
                cursor = conn.cursor()
                today = datetime.now().strftime('%Y-%m-%d')
                cursor.execute('''
                SELECT COUNT(*) FROM users 
                WHERE join_date LIKE ?
                ''', (f'{today}%',))
                stats['new_users_today'] = cursor.fetchone()[0] or 0
            
            # آخر إذاعة
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                SELECT broadcast_id, sent_date FROM broadcasts 
                ORDER BY broadcast_id DESC LIMIT 1
                ''')
                last = cursor.fetchone()
                stats['last_broadcast_id'] = last['broadcast_id'] if last else None
                stats['last_broadcast_date'] = last['sent_date'] if last else None
            
            logger.info(f"✅ الإحصائيات المحسوبة: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"❌ خطأ في جلب الإحصائيات: {e}")
            return {
                'total_users': self.get_users_count(),
                'total_messages': 0,
                'total_broadcasts': 0,
                'new_users_today': 0,
                'last_broadcast_id': None,
                'last_broadcast_date': None
            }
    
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
    
    def get_broadcast_stats(self, broadcast_id):
        """الحصول على إحصائيات إذاعة"""
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

# إنشاء كائن قاعدة بيانات عالمي
db = Database()
