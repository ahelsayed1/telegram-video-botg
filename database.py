# database.py - النسخة النهائية مع نظام البحث المتقدم
import sqlite3
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_name="bot_database.db"):
        """تهيئة قاعدة البيانات مع مسار مطلق لـ Railway"""
        # استخدام مسار مطلق متوافق مع Railway
        self.db_name = os.path.join(os.getcwd(), db_name)
        logger.info(f"📁 مسار قاعدة البيانات: {self.db_name}")
        logger.info(f"📁 المسار الحالي: {os.getcwd()}")
        self.init_database()
    
    def get_connection(self):
        """الحصول على اتصال بقاعدة البيانات"""
        try:
            conn = sqlite3.connect(self.db_name, timeout=10)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            logger.error(f"❌ فشل الاتصال بقاعدة البيانات: {e}")
            raise
    
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
                
                conn.commit()
                logger.info("✅ قاعدة البيانات جاهزة - تم إنشاء/فحص الجداول")
                
        except Exception as e:
            logger.error(f"❌ خطأ في تهيئة قاعدة البيانات: {e}", exc_info=True)
    
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
                    logger.debug(f"✅ تم تحديث المستخدم {user_id}")
                else:
                    # إضافة مستخدم جديد
                    cursor.execute('''
                    INSERT INTO users 
                    (user_id, username, first_name, last_name, join_date, last_active, message_count)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                    ''', (user_id, username, first_name, last_name, current_time, current_time))
                    logger.info(f"✅ تم إضافة مستخدم جديد: {user_id} - {first_name}")
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"❌ خطأ في إضافة/تحديث المستخدم {user_id}: {e}")
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
            logger.error(f"❌ خطأ في جلب بيانات المستخدم {user_id}: {e}")
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
    
    def is_user_active(self, user_id, days_threshold=30):
        """التحقق إذا كان المستخدم نشطاً في الأيام المحددة"""
        try:
            user = self.get_user(user_id)
            if not user or not user.get('last_active'):
                return False
            
            last_active = datetime.fromisoformat(user['last_active'])
            days_inactive = (datetime.now() - last_active).days
            return days_inactive <= days_threshold
            
        except Exception as e:
            logger.error(f"❌ خطأ في التحقق من نشاط المستخدم {user_id}: {e}")
            return False
    
    # ==================== دوال البحث المتقدمة ====================
    def search_users(self, search_term):
        """بحث عن مستخدمين حسب الاسم، المعرف، أو اليوزرنيم"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # البحث في جميع الحقول
                query = '''
                SELECT * FROM users 
                WHERE user_id LIKE ? OR 
                      username LIKE ? OR 
                      first_name LIKE ? OR 
                      last_name LIKE ?
                ORDER BY join_date DESC
                LIMIT 50
                '''
                
                search_pattern = f"%{search_term}%"
                cursor.execute(query, (
                    search_pattern, 
                    search_pattern, 
                    search_pattern, 
                    search_pattern
                ))
                
                users = cursor.fetchall()
                return [dict(user) for user in users]
                
        except Exception as e:
            logger.error(f"❌ خطأ في البحث عن المستخدمين: {e}")
            return []
    
    def search_users_with_filters(self, search_term="", join_date_filter="all", active_only=False, limit=50):
        """بحث عن مستخدمين مع عوامل تصفية متقدمة"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # بناء الاستعلام الديناميكي
                query_parts = ["SELECT * FROM users"]
                params = []
                
                # تطبيق عوامل التصفية
                conditions = []
                
                # عامل البحث
                if search_term:
                    conditions.append("(user_id LIKE ? OR username LIKE ? OR first_name LIKE ? OR last_name LIKE ?)")
                    search_pattern = f"%{search_term}%"
                    params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
                
                # عامل تصفية تاريخ الانضمام
                if join_date_filter != "all":
                    today = datetime.now()
                    if join_date_filter == "today":
                        start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
                    elif join_date_filter == "week":
                        start_date = today - timedelta(days=7)
                    elif join_date_filter == "month":
                        start_date = today - timedelta(days=30)
                    elif join_date_filter == "year":
                        start_date = today - timedelta(days=365)
                    else:
                        start_date = today - timedelta(days=36500)  # كل المستخدمين
                    
                    conditions.append("join_date >= ?")
                    params.append(start_date.isoformat())
                
                # عامل تصفية النشاط
                if active_only:
                    active_date = (datetime.now() - timedelta(days=30)).isoformat()
                    conditions.append("last_active >= ?")
                    params.append(active_date)
                
                # إضافة الشروط للاستعلام
                if conditions:
                    query_parts.append("WHERE " + " AND ".join(conditions))
                
                # الترتيب والحد
                query_parts.append("ORDER BY join_date DESC LIMIT ?")
                params.append(limit)
                
                # تنفيذ الاستعلام
                final_query = " ".join(query_parts)
                cursor.execute(final_query, params)
                
                users = cursor.fetchall()
                return [dict(user) for user in users]
                
        except Exception as e:
            logger.error(f"❌ خطأ في البحث المتقدم: {e}")
            return []
    
    def get_users_by_activity(self, days_threshold=30):
        """الحصول على المستخدمين النشطين/غير النشطين"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cutoff_date = (datetime.now() - timedelta(days=days_threshold)).isoformat()
                
                # المستخدمين النشطين
                cursor.execute('''
                SELECT * FROM users 
                WHERE last_active >= ?
                ORDER BY last_active DESC
                ''', (cutoff_date,))
                active_users = [dict(row) for row in cursor.fetchall()]
                
                # المستخدمين غير النشطين
                cursor.execute('''
                SELECT * FROM users 
                WHERE last_active < ? OR last_active IS NULL
                ORDER BY join_date DESC
                ''', (cutoff_date,))
                inactive_users = [dict(row) for row in cursor.fetchall()]
                
                return {
                    'active': active_users,
                    'inactive': inactive_users,
                    'active_count': len(active_users),
                    'inactive_count': len(inactive_users),
                    'total': len(active_users) + len(inactive_users)
                }
                
        except Exception as e:
            logger.error(f"❌ خطأ في جلب المستخدمين حسب النشاط: {e}")
            return {'active': [], 'inactive': [], 'active_count': 0, 'inactive_count': 0, 'total': 0}
    
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
                logger.info(f"✅ تم حفظ إذاعة #{broadcast_id} من المشرف {admin_id}")
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
            logger.error(f"❌ خطأ في جلب إحصائيات الإذاعة #{broadcast_id}: {e}")
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
                result = cursor.fetchone()[0]
                stats['last_broadcast_id'] = result
            
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
  
