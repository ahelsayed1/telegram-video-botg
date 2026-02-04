# ai_manager.py - الإصدار المتوافق مع Google GenAI SDK الجديد
import os
import logging
import asyncio
# استيراد المكتبة الجديدة بالطريقة الصحيحة
from google import genai
from google.genai import types
import openai
import aiohttp
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import json

logger = logging.getLogger(__name__)

class AIManager:
    """مدير خدمات الذكاء الاصطناعي المتكامل"""
    
    def __init__(self, db):
        self.db = db
        self.client = None  # متغير عميل جوجل الجديد
        self.setup_apis()
        self.user_limits_cache = {}
        self.conversation_history = {}
        self.max_history_length = 10
        
    def setup_apis(self):
        """إعداد واجهات برمجة التطبيقات"""
        try:
            # 1. إعداد Google Gemini (المكتبة الجديدة)
            google_api_key = os.getenv("GOOGLE_AI_API_KEY")
            if google_api_key:
                # استخدام Client الجديد بدلاً من configure
                self.client = genai.Client(api_key=google_api_key)
                self.gemini_available = True
                logger.info("✅ Google GenAI (New SDK) Connected Successfully")
            else:
                self.gemini_available = False
                logger.warning("⚠️ Google Gemini API key not found")
            
            # 2. إعداد OpenAI
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if openai_api_key:
                openai.api_key = openai_api_key
                self.openai_available = True
                logger.info("✅ OpenAI API configured successfully")
            else:
                self.openai_available = False
            
            # 3. إعداد Luma AI
            self.luma_api_key = os.getenv("LUMAAI_API_KEY")
            self.luma_available = bool(self.luma_api_key)
            if self.luma_available:
                logger.info("✅ Luma AI API configured successfully")
            
            # 4. إعدادات الخدمات البديلة
            self.stable_diffusion_url = os.getenv("STABLE_DIFFUSION_URL", "https://api.stability.ai/v1/generation/stable-diffusion-v1-6/text-to-image")
            self.stability_api_key = os.getenv("STABILITY_API_KEY")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup AI APIs: {e}")
            self.gemini_available = False
            self.openai_available = False
            self.luma_available = False

    # ==================== نظام الحدود (لم يتغير) ====================
    def check_user_limit(self, user_id: int, service_type: str = "ai_chat") -> Tuple[bool, int]:
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
            
            # قراءة الحدود من المتغيرات أو استخدام الافتراضي
            limits_config = {
                "ai_chat": int(os.getenv("DAILY_AI_LIMIT", "20")),
                "image_gen": int(os.getenv("DAILY_IMAGE_LIMIT", "5")),
                "video_gen": int(os.getenv("DAILY_VIDEO_LIMIT", "2"))
            }
            limit = limits_config.get(service_type, 20)
            
            if current_usage >= limit:
                return False, 0
            return True, limit - current_usage
            
        except Exception as e:
            logger.error(f"❌ Error checking user limit: {e}")
            return True, 999

    def update_user_usage(self, user_id: int, service_type: str = "ai_chat") -> bool:
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            cache_key = f"{user_id}_{today}_{service_type}"
            self.user_limits_cache[cache_key] = self.user_limits_cache.get(cache_key, 0) + 1
            
            with self.db.get_connection() as conn:
                conn.execute('''
                INSERT INTO ai_usage (user_id, service_type, usage_date, usage_count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(user_id, service_type, usage_date) 
                DO UPDATE SET usage_count = usage_count + 1
                ''', (user_id, service_type, today))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Error updating usage: {e}")
            return False

    # ==================== خدمة المحادثة (تم التحديث) ====================
    async def chat_with_ai(self, user_id: int, message: str, use_gemini: bool = True) -> str:
        try:
            # التحقق من الحدود
            allowed, remaining = self.check_user_limit(user_id, "ai_chat")
            if not allowed:
                return f"❌ تجاوزت الحد اليومي. المتبقي: 0. يتجدد الرصيد غداً."
            
            # جلب التاريخ (يمكن تحسينه لاحقاً)
            # history = self.get_conversation_history(user_id) 
            
            response_text = ""
            
            # استخدام Gemini بالكود الجديد
            if use_gemini and self.gemini_available and self.client:
                response_text = await self._chat_with_gemini_new(message)
            elif self.openai_available:
                response_text = await self._chat_with_openai(message)
            else:
                return "❌ خدمة الذكاء الاصطناعي غير متاحة حالياً. تأكد من المفاتيح."
            
            # حفظ وتحديث
            self.update_user_usage(user_id, "ai_chat")
            self.db.save_ai_conversation(user_id, "chat", message, response_text)
            
            return response_text
            
        except Exception as e:
            logger.error(f"❌ Chat Error: {e}")
            return "⚠️ حدث خطأ أثناء المعالجة."

    async def _chat_with_gemini_new(self, message: str) -> str:
        """وظيفة الشات باستخدام Google GenAI SDK الجديد"""
        try:
            model_id = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
            
            # تشغيل الدالة في Thread منفصل لأن المكتبة الجديدة متزامنة (Sync)
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=model_id,
                contents=message,
                config=types.GenerateContentConfig(
                    system_instruction="أنت مساعد ذكي ومفيد تتحدث العربية بطلاقة.",
                    temperature=0.7,
                )
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"❌ Gemini New SDK Error: {e}")
            return f"عذراً، حدث خطأ في الاتصال بجوجل: {str(e)}"

    async def _chat_with_openai(self, message: str) -> str:
        try:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "أنت مساعد ذكي تتحدث العربية."},
                    {"role": "user", "content": message}
                ]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"❌ OpenAI Error: {e}")
            return "خطأ في خدمة OpenAI."

    # ==================== خدمة الصور (تحسين الوصف باستخدام Gemini الجديد) ====================
    async def generate_image(self, user_id: int, prompt: str, style: str = "realistic") -> Tuple[Optional[str], str]:
        try:
            allowed, remaining = self.check_user_limit(user_id, "image_gen")
            if not allowed:
                return None, "❌ انتهى رصيد الصور اليومي."
            
            # تحسين الوصف باستخدام Gemini الجديد
            enhanced_prompt = await self._enhance_prompt_new(prompt, style)
            
            image_url = None
            
            # 1. DALL-E
            if self.openai_available:
                try:
                    client = openai.OpenAI()
                    response = client.images.generate(
                        model="dall-e-3", prompt=enhanced_prompt, 
                        size="1024x1024", quality="standard", n=1
                    )
                    image_url = response.data[0].url
                except Exception as e:
                    logger.warning(f"DALL-E failed: {e}")

            # 2. Stable Diffusion (احتياطي)
            if not image_url and self.stability_api_key:
                try:
                    headers = {"Authorization": f"Bearer {self.stability_api_key}", "Content-Type": "application/json"}
                    data = {"text_prompts": [{"text": enhanced_prompt, "weight": 1}], "cfg_scale": 7, "height": 512, "width": 512, "samples": 1}
                    async with aiohttp.ClientSession() as session:
                        async with session.post(self.stable_diffusion_url, headers=headers, json=data) as resp:
                            if resp.status == 200:
                                res_json = await resp.json()
                                # ملاحظة: هنا نحتاج لرفع الصورة، لكن للاختصار سنفترض النجاح
                                # في الإنتاج تحتاج لخدمة رفع صور
                                logger.info("Stable Diffusion generated image (base64)")
                                return None, "✅ تم إنشاء الصورة (لكن نحتاج لسيرفر لرفعها)" 
                except Exception as e:
                    logger.warning(f"Stable Diffusion failed: {e}")

            if image_url:
                self.update_user_usage(user_id, "image_gen")
                self.db.save_generated_file(user_id, "image", prompt, image_url)
                return image_url, "✅ تم إنشاء الصورة بنجاح"
            
            return None, "❌ فشل إنشاء الصورة. تأكد من رصيد OpenAI."

        except Exception as e:
            logger.error(f"Image Gen Error: {e}")
            return None, "حدث خطأ غير متوقع."

    async def _enhance_prompt_new(self, prompt: str, style: str) -> str:
        """تحسين الوصف باستخدام عميل جوجل الجديد"""
        if not self.gemini_available or not self.client:
            return f"{prompt}, {style} style, high quality"
        
        try:
            instruction = f"Convert this description to a detailed English image prompt for DALL-E, style: {style}. Prompt: {prompt}"
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model="gemini-1.5-flash",
                contents=instruction
            )
            return response.text.strip()
        except:
            return prompt

    # ==================== خدمة الفيديو (Luma AI) ====================
    async def generate_video(self, user_id: int, prompt: str, image_url: str = None) -> Tuple[Optional[str], str]:
        try:
