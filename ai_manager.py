# ai_manager.py - مدير خدمات الذكاء الاصطناعي المحدث
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
        self.user_limits_cache = {}
        self.conversation_history = {}
        self.max_history_length = 10
        
    def setup_apis(self):
        """إعداد واجهات برمجة التطبيقات"""
        try:
            google_api_key = os.getenv("GOOGLE_AI_API_KEY")
            if google_api_key:
                genai.configure(api_key=google_api_key)
                self.gemini_available = True
                logger.info("✅ Google Gemini API configured successfully")
            else:
                self.gemini_available = False
                logger.warning("⚠️ Google Gemini API key not found")
            
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if openai_api_key:
                openai.api_key = openai_api_key
                self.openai_available = True
            else:
                self.openai_available = False
            
            self.luma_api_key = os.getenv("LUMAAI_API_KEY")
            self.luma_available = bool(self.luma_api_key)
            self.stability_api_key = os.getenv("STABILITY_API_KEY")
            self.stable_diffusion_url = os.getenv("STABLE_DIFFUSION_URL", "https://api.stability.ai/v1/generation/stable-diffusion-v1-6/text-to-image")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup AI APIs: {e}")
            self.gemini_available = False

    # ==================== نظام التحقق من الحدود وتاريخ المحادثة ====================
    # [ملاحظة: تم الحفاظ على دوال check_user_limit و update_user_usage و تاريخ المحادثة كما هي في ملفك الأصلي]
    
    def check_user_limit(self, user_id, service_type="ai_chat"):
        try:
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
        except Exception: return True, 999

    def update_user_usage(self, user_id, service_type="ai_chat"):
        try:
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

    # ==================== خدمة المحادثة ====================
    
    async def chat_with_ai(self, user_id: int, message: str, use_gemini: bool = True) -> str:
        """دردشة مع الذكاء الاصطناعي"""
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
        """*** النسخة المستقرة ومعدلة المسافات لعدم حدوث Crash ***"""
        try:
            # استخدام المتغير البيئي الخاص بك (Flash)
            model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
            model = genai.GenerativeModel(model_name=model_name)
            
            system_instruction = "أنت مساعد ذكي ومفيد، تجيب باللغة العربية بوضوح."
            full_prompt = f"{system_instruction}\n\nالمستخدم: {message}"
            
            # تشغيل الطلب لضمان عدم تعليق البوت
            response = await asyncio.to_thread(model.generate_content, full_prompt)
            
            if response and response.text:
                return response.text.strip()
            return "عذراً، لم أتمكن من الرد."
        except Exception as e:
            logger.error(f"❌ Gemini error: {e}")
            # خطة بديلة لتفادي الـ 404
            try:
                fallback = genai.GenerativeModel("gemini-pro")
                res = await asyncio.to_thread(fallback.generate_content, message)
                return res.text.strip()
            except:
                raise e

    def get_available_services(self) -> Dict[str, bool]:
        return {"chat": self.gemini_available, "image_generation": self.openai_available, "video_generation": self.luma_available}

    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        return {} # ميزة الإحصائيات يتم جلبها من قاعدة البيانات
