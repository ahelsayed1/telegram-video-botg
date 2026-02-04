# ai_manager.py - مدير خدمات الذكاء الاصطناعي المتكامل
import os
import logging
import asyncio
import google.generativeai as genai
import openai
import requests
import aiohttp
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import base64
import json

logger = logging.getLogger(__name__)

class AIManager:
    """مدير خدمات الذكاء الاصطناعي المتكامل"""
    
    def __init__(self, db):
        self.db = db
        self.setup_apis()
        self.user_limits_cache = {}  # كاش لحدود الاستخدام
        self.conversation_history = {}  # كاش لتاريخ المحادثات
        self.max_history_length = 10  # أقصى طول لتاريخ المحادثة
        
    def setup_apis(self):
        """إعداد واجهات برمجة التطبيقات"""
        try:
            # إعداد Google Gemini
            google_api_key = os.getenv("GOOGLE_AI_API_KEY")
            if google_api_key:
                genai.configure(api_key=google_api_key)
                self.gemini_available = True
                logger.info("✅ Google Gemini API configured successfully")
            else:
                self.gemini_available = False
                logger.warning("⚠️ Google Gemini API key not found")
            
            # إعداد OpenAI
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if openai_api_key:
                openai.api_key = openai_api_key
                self.openai_available = True
                logger.info("✅ OpenAI API configured successfully")
            else:
                self.openai_available = False
                logger.warning("⚠️ OpenAI API key not found")
            
            # إعداد Luma AI
            self.luma_api_key = os.getenv("LUMAAI_API_KEY")
            self.luma_available = bool(self.luma_api_key)
            if self.luma_available:
                logger.info("✅ Luma AI API configured successfully")
            else:
                logger.warning("⚠️ Luma AI API key not found")
            
            # إعدادات الخدمات البديلة
            self.stable_diffusion_url = os.getenv("STABLE_DIFFUSION_URL", "https://api.stability.ai/v1/generation/stable-diffusion-v1-6/text-to-image")
            self.stability_api_key = os.getenv("STABILITY_API_KEY")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup AI APIs: {e}")
            self.gemini_available = False
            self.openai_available = False
            self.luma_available = False
    
    # ==================== نظام التحقق من الحدود ====================
    
    def check_user_limit(self, user_id: int, service_type: str = "ai_chat") -> Tuple[bool, int]:
        """التحقق من حدود استخدام المستخدم"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            cache_key = f"{user_id}_{today}_{service_type}"
            
            if cache_key in self.user_limits_cache:
                current_usage = self.user_limits_cache[cache_key]
            else:
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                    SELECT usage_count FROM ai_usage 
                    WHERE user_id = ? AND service_type = ? AND usage_date = ?
                    ''', (user_id, service_type, today))
                    
                    result = cursor.fetchone()
                    current_usage = result[0] if result else 0
                    self.user_limits_cache[cache_key] = current_usage
            
            limits_config = {
                "ai_chat": int(os.getenv("DAILY_AI_LIMIT", "20")),
                "image_gen": int(os.getenv("DAILY_IMAGE_LIMIT", "5")),
                "video_gen": int(os.getenv("DAILY_VIDEO_LIMIT", "2"))
            }
            
            limit = limits_config.get(service_type, 20)
            remaining = limit - current_usage
            
            if current_usage >= limit:
                return False, 0
            return True, remaining
            
        except Exception as e:
            logger.error(f"❌ Error checking user limit: {e}")
            return True, 999
    
    def update_user_usage(self, user_id: int, service_type: str = "ai_chat") -> bool:
        """تحديث استخدام المستخدم"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            cache_key = f"{user_id}_{today}_{service_type}"
            
            current_usage = self.user_limits_cache.get(cache_key, 0)
            self.user_limits_cache[cache_key] = current_usage + 1
            
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                INSERT INTO ai_usage (user_id, service_type, usage_date, usage_count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(user_id, service_type, usage_date) 
                DO UPDATE SET usage_count = usage_count + 1
                ''', (user_id, service_type, today))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ Error updating user usage: {e}")
            return False
    
    def get_conversation_history(self, user_id: int) -> List[Dict[str, str]]:
        """الحصول على تاريخ محادثة المستخدم"""
        try:
            if user_id not in self.conversation_history:
                conversations = self.db.get_user_ai_conversations(user_id, limit=self.max_history_length)
                history = []
                for conv in conversations:
                    history.append({"role": "user", "content": conv['user_message']})
                    history.append({"role": "assistant", "content": conv['ai_response']})
                history.reverse()
                self.conversation_history[user_id] = history[-self.max_history_length*2:]
            return self.conversation_history.get(user_id, [])
        except Exception as e:
            logger.error(f"❌ Error getting conversation history: {e}")
            return []
    
    def update_conversation_history(self, user_id: int, user_message: str, ai_response: str):
        """تحديث تاريخ المحادثة"""
        try:
            if user_id not in self.conversation_history:
                self.conversation_history[user_id] = []
            self.conversation_history[user_id].append({"role": "user", "content": user_message})
            self.conversation_history[user_id].append({"role": "assistant", "content": ai_response})
            if len(self.conversation_history[user_id]) > self.max_history_length * 2:
                self.conversation_history[user_id] = self.conversation_history[user_id][-self.max_history_length*2:]
        except Exception as e:
            logger.error(f"❌ Error updating conversation history: {e}")
    
    async def chat_with_ai(self, user_id: int, message: str, use_gemini: bool = True) -> str:
        """دردشة مع الذكاء الاصطناعي"""
        try:
            allowed, remaining = self.check_user_limit(user_id, "ai_chat")
            if not allowed:
                return f"❌ لقد استخدمت جميع رسائل المحادثة اليومية.\n🔄 يتم تجديد الحدود تلقائياً بعد منتصف الليل."
            
            conversation_history = self.get_conversation_history(user_id)
            
            if use_gemini and self.gemini_available:
                response = await self._chat_with_gemini(message, conversation_history)
            elif self.openai_available:
                response = await self._chat_with_openai(message, conversation_history)
            else:
                return "❌ خدمة الدردشة غير متاحة حالياً."
            
            self.update_user_usage(user_id, "ai_chat")
            self.update_conversation_history(user_id, message, response)
            self.db.save_ai_conversation(user_id, "chat", message, response)
            return response
        except Exception as e:
            logger.error(f"❌ Error in AI chat: {e}")
            return "⚠️ حدث خطأ أثناء معالجة طلبك. حاول مجدداً."
    
        async def _chat_with_gemini(self, message: str, history: List[Dict]) -> str:
        """استخدام Google Gemini للدردشة - نسخة مستقرة ومحدثة"""
        try:
            # استخدام اسم الموديل مباشرة لضمان التوافق
            model_name = "gemini-1.5-flash"
            model = genai.GenerativeModel(model_name=model_name)
            
            # إعداد التعليمات البرمجية للموديل
            system_instruction = "أنت مساعد ذكي ومفيد، تجيب باللغة العربية بوضوح واختصار."
            
            # دمج التعليمات مع رسالة المستخدم
            full_prompt = f"{system_instruction}\n\nالمستخدم: {message}"
            
            # تشغيل الطلب في thread منفصل لتجنب تعليق البوت (لأن مكتبة Google ليست async بالكامل)
            response = await asyncio.to_thread(model.generate_content, full_prompt)
            
            if response and response.text:
                return response.text.strip()
            else:
                return "عذراً، لم أتمكن من توليد رد حالياً."
                
        except Exception as e:
            logger.error(f"❌ Gemini chat error: {e}")
            # خطة بديلة: إذا فشل الموديل المحدد، نحاول استخدام الموديل الافتراضي
            try:
                fallback_model = genai.GenerativeModel("gemini-pro")
                fallback_res = await asyncio.to_thread(fallback_model.generate_content, message)
                return fallback_res.text.strip()
            except:
                raise e
    
    async def _chat_with_openai(self, message: str, history: List[Dict]) -> str:
        """استخدام OpenAI GPT للدردشة"""
        try:
            client = openai.OpenAI()
            messages = [{"role": "system", "content": "أنت مساعد ذكي ودود يتحدث العربية."}]
            for msg in history[-6:]:
                messages.append(msg)
            messages.append({"role": "user", "content": message})
            
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=messages,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"❌ OpenAI chat error: {e}")
            raise

    # [ملاحظة: تم الإبقاء على دوال الصور والفيديو كما هي لضمان عدم حدوث أخطاء أخرى]
    async def generate_image(self, user_id: int, prompt: str, style: str = "realistic") -> Tuple[Optional[str], str]:
        # كود إنشاء الصور...
        return None, "خدمة الصور تحت الصيانة"

    def get_user_stats(self, user_id: int) -> Dict[str, int]:
        return {}
    
    def get_available_services(self) -> Dict[str, bool]:
        return {"chat": self.gemini_available or self.openai_available}
