# ai_manager.py - الإصدار الذكي (Auto-Detect Model)
import os
import logging
import asyncio
import google.generativeai as genai
import openai
import aiohttp
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class AIManager:
    """مدير خدمات الذكاء الاصطناعي"""
    
    def __init__(self, db):
        self.db = db
        self.model_name = "gemini-pro" # اسم افتراضي
        self.setup_apis()
        self.user_limits_cache = {}
        
    def setup_apis(self):
        """إعداد واجهات برمجة التطبيقات واكتشاف الموديلات"""
        try:
            # 1. إعداد Google Gemini
            google_api_key = os.getenv("GOOGLE_AI_API_KEY")
            if google_api_key:
                genai.configure(api_key=google_api_key)
                self.gemini_available = True
                
                # --- الكود الذكي لاكتشاف الموديلات ---
                try:
                    logger.info("🔍 جاري البحث عن الموديلات المتاحة...")
                    found_models = []
                    target_model = None
                    
                    for m in genai.list_models():
                        if 'generateContent' in m.supported_generation_methods:
                            model_clean_name = m.name.replace('models/', '')
                            found_models.append(model_clean_name)
                    
                    logger.info(f"📋 الموديلات التي يراها حسابك: {found_models}")
                    
                    # محاولة اختيار الأفضل
                    preferred_order = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro', 'gemini-1.0-pro']
                    
                    for pref in preferred_order:
                        if pref in found_models:
                            target_model = pref
                            break
                    
                    if target_model:
                        self.model_name = target_model
                    elif found_models:
                        self.model_name = found_models[0] # خذ أي واحد متاح
                        
                    logger.info(f"✅ تم اعتماد الموديل: {self.model_name}")
                    
                except Exception as e:
                    logger.warning(f"⚠️ فشل الاكتشاف التلقائي، سنستخدم الافتراضي: {e}")
                    self.model_name = "gemini-pro"
            else:
                self.gemini_available = False
                logger.warning("⚠️ Google Gemini API key not found")
            
            # 2. إعداد OpenAI
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if openai_api_key:
                openai.api_key = openai_api_key
                self.openai_available = True
                logger.info("✅ OpenAI API Configured")
            else:
                self.openai_available = False
            
            # 3. إعداد Luma AI
            self.luma_api_key = os.getenv("LUMAAI_API_KEY")
            self.luma_available = bool(self.luma_api_key)
            
            # 4. إعدادات أخرى
            self.stability_api_key = os.getenv("STABILITY_API_KEY")
            self.stable_diffusion_url = os.getenv("STABLE_DIFFUSION_URL", "https://api.stability.ai/v1/generation/stable-diffusion-v1-6/text-to-image")
            
        except Exception as e:
            logger.error(f"❌ API Setup Failed: {e}")
            self.gemini_available = False
            self.openai_available = False
            self.luma_available = False

    # ==================== نظام الحدود ====================
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
            
            limits_config = {
                "ai_chat": int(os.getenv("DAILY_AI_LIMIT", "20")),
                "image_gen": int(os.getenv("DAILY_IMAGE_LIMIT", "5")),
                "video_gen": int(os.getenv("DAILY_VIDEO_LIMIT", "2"))
            }
            limit = limits_config.get(service_type, 20)
            return current_usage < limit, limit - current_usage
        except Exception: return True, 999

    def update_user_usage(self, user_id: int, service_type: str = "ai_chat") -> bool:
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            cache_key = f"{user_id}_{today}_{service_type}"
            self.user_limits_cache[cache_key] = self.user_limits_cache.get(cache_key, 0) + 1
            with self.db.get_connection() as conn:
                conn.execute('''INSERT INTO ai_usage (user_id, service_type, usage_date, usage_count) VALUES (?, ?, ?, 1) ON CONFLICT(user_id, service_type, usage_date) DO UPDATE SET usage_count = usage_count + 1''', (user_id, service_type, today))
                conn.commit()
            return True
        except: return False

    # ==================== الشات (يستخدم الموديل المكتشف) ====================
    async def chat_with_ai(self, user_id: int, message: str, use_gemini: bool = True) -> str:
        try:
            allowed, remaining = self.check_user_limit(user_id, "ai_chat")
            if not allowed: return "❌ تجاوزت الحد اليومي."
            
            response_text = ""
            
            if use_gemini and self.gemini_available:
                # استخدام الموديل الذي تم اكتشافه تلقائياً
                model = genai.GenerativeModel(self.model_name)
                response = await model.generate_content_async(message)
                response_text = response.text
                
            elif self.openai_available:
                client = openai.OpenAI()
                response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": message}])
                response_text = response.choices[0].message.content
            else:
                return "❌ الخدمة غير متاحة."
            
            self.update_user_usage(user_id, "ai_chat")
            self.db.save_ai_conversation(user_id, "chat", message, response_text)
            return response_text
            
        except Exception as e:
            logger.error(f"Chat Error ({self.model_name}): {e}")
            return f"⚠️ خطأ: تأكد من أن الموديل {self.model_name} مدعوم في منطقتك."

    # ==================== بقية الخدمات (كما هي) ====================
    async def generate_image(self, user_id: int, prompt: str, style: str = "realistic") -> Tuple[Optional[str], str]:
        # (نفس كود الصور السابق)
        try:
            allowed, _ = self.check_user_limit(user_id, "image_gen")
            if not allowed: return None, "❌ انتهى رصيد الصور."
            
            # تحسين الوصف
            enhanced = prompt
            if self.gemini_available:
                try:
                    model = genai.GenerativeModel(self.model_name)
                    resp = await model.generate_content_async(f"English prompt for DALL-E: {prompt}")
                    enhanced = resp.text
                except: pass

            image_url = None
            if self.openai_available:
                try:
                    client = openai.OpenAI()
                    response = client.images.generate(model="dall-e-3", prompt=enhanced[:1000], size="1024x1024")
                    image_url = response.data[0].url
                except Exception as e: logger.error(f"DALL-E: {e}")

            if image_url:
                self.update_user_usage(user_id, "image_gen")
                self.db.save_generated_file(user_id, "image", prompt, image_url)
                return image_url, "✅ تم"
            return None, "❌ فشل الإنشاء"
        except: return None, "خطأ"

    async def generate_video(self, user_id: int, prompt: str, image_url: str = None) -> Tuple[Optional[str], str]:
        if not self.luma_available: return None, "❌ خدمة الفيديو غير مفعلة."
        return None, "Video generation endpoint placeholder"

    def get_available_services(self):
        return {"chat": self.gemini_available, "image_generation": self.openai_available, "video_generation": self.luma_available}
        
    def get_user_stats(self, user_id): return {}
