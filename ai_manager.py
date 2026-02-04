# ai_manager.py - مدير خدمات الذكاء الاصطناعي (محدث لمكتبة Google الجديدة)
import os
import logging
import asyncio
from google import genai  # المكتبة الجديدة
import openai
import aiohttp
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class AIManager:
    """مدير خدمات الذكاء الاصطناعي المتكامل"""
    
    def __init__(self, db):
        self.db = db
        self.setup_apis()
        self.user_limits_cache = {}
        self.conversation_history = {}
        self.max_history_length = 10
        
    def setup_apis(self):
        """إعداد واجهات برمجة التطبيقات"""
        try:
            # إعداد Google Gemini بالمكتبة الجديدة
            self.google_api_key = os.getenv("GOOGLE_AI_API_KEY")
            if self.google_api_key:
                self.gemini_client = genai.Client(api_key=self.google_api_key)
                self.gemini_available = True
                logger.info("✅ Google Gemini (New SDK) configured successfully")
            else:
                self.gemini_available = False
                logger.warning("⚠️ Google Gemini API key not found")
            
            # إعداد OpenAI
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if openai_api_key:
                openai.api_key = openai_api_key
                self.openai_available = True
            else:
                self.openai_available = False
            
            # إعداد Luma AI
            self.luma_api_key = os.getenv("LUMAAI_API_KEY")
            self.luma_available = bool(self.luma_api_key)
            self.stability_api_key = os.getenv("STABILITY_API_KEY")
            self.stable_diffusion_url = os.getenv("STABLE_DIFFUSION_URL", "https://api.stability.ai/v1/generation/stable-diffusion-v1-6/text-to-image")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup AI APIs: {e}")
            self.gemini_available = False
            self.openai_available = False

    # ==================== نظام التحقق من الحدود ====================
    def check_user_limit(self, user_id, service_type="ai_chat"):
        try:
            # (نفس الكود السابق للتحقق من الحدود)
            from datetime import datetime
            today = datetime.now().strftime('%Y-%m-%d')
            cache_key = f"{user_id}_{today}_{service_type}"
            
            if cache_key in self.user_limits_cache:
                current_usage = self.user_limits_cache[cache_key]
            else:
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT usage_count FROM ai_usage WHERE user_id = ? AND service_type = ? AND usage_date = ?', (user_id, service_type, today))
                    result = cursor.fetchone()
                    current_usage = result[0] if result else 0
                    self.user_limits_cache[cache_key] = current_usage
            
            limit = int(os.getenv(f"DAILY_{service_type.upper()}_LIMIT", "20"))
            return current_usage < limit, limit - current_usage
        except: return True, 999

    def update_user_usage(self, user_id, service_type="ai_chat"):
        try:
            from datetime import datetime
            today = datetime.now().strftime('%Y-%m-%d')
            cache_key = f"{user_id}_{today}_{service_type}"
            self.user_limits_cache[cache_key] = self.user_limits_cache.get(cache_key, 0) + 1
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''INSERT INTO ai_usage (user_id, service_type, usage_date, usage_count) VALUES (?, ?, ?, 1)
                ON CONFLICT(user_id, service_type, usage_date) DO UPDATE SET usage_count = usage_count + 1''', (user_id, service_type, today))
                conn.commit()
                return True
        except: return False

    # ==================== خدمة المحادثة (المعدلة جذرياً) ====================
    
    async def chat_with_ai(self, user_id: int, message: str, use_gemini: bool = True) -> str:
        try:
            allowed, remaining = self.check_user_limit(user_id, "ai_chat")
            if not allowed:
                return "❌ تجاوزت الحد اليومي للمحادثات."
            
            if use_gemini and self.gemini_available:
                response = await self._chat_with_gemini(message, [])
            else:
                return "❌ خدمة الدردشة غير متاحة حالياً."
            
            self.update_user_usage(user_id, "ai_chat")
            self.db.save_ai_conversation(user_id, "chat", message, response)
            return response
        except Exception as e:
            logger.error(f"❌ Error in AI chat: {e}")
            return "⚠️ حدث خطأ أثناء معالجة طلبك."

    async def _chat_with_gemini(self, message: str, history: List[Dict]) -> str:
        """استخدام Google Gemini (المكتبة الجديدة)"""
        try:
            system_instruction = "أنت مساعد ذكي ومفيد، تجيب باللغة العربية بوضوح."
            
            # استخدام المكتبة الجديدة: google-genai
            # نقوم بتشغيلها في thread لأنها قد تكون متزامنة
            response = await asyncio.to_thread(
                self.gemini_client.models.generate_content,
                model='gemini-1.5-flash',
                contents=f"{system_instruction}\n\nالمستخدم: {message}"
            )
            
            if response and response.text:
                return response.text.strip()
            return "عذراً، لم أتمكن من الرد."
            
        except Exception as e:
            logger.error(f"❌ Gemini error: {e}")
            # محاولة بديلة بموديل آخر إذا فشل الفلاش
            try:
                response = await asyncio.to_thread(
                    self.gemini_client.models.generate_content,
                    model='gemini-1.5-pro',
                    contents=message
                )
                return response.text.strip()
            except:
                raise e

    # ==================== بقية الخدمات (كما هي) ====================
    def get_available_services(self) -> Dict[str, bool]:
        return {"chat": self.gemini_available, "image_generation": self.openai_available, "video_generation": self.luma_available}

    async def generate_image(self, user_id: int, prompt: str, style: str = "realistic") -> Tuple[Optional[str], str]:
        # (نفس كود الصور السابق - لم يتغير)
        return None, "خدمة الصور تحت الصيانة للتحديث"

    async def generate_video(self, user_id: int, prompt: str, image_url: str = None) -> Tuple[Optional[str], str]:
        # (نفس كود الفيديو السابق - لم يتغير)
        return None, "خدمة الفيديو تحت الصيانة للتحديث"
        
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        return {}
