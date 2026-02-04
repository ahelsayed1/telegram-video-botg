# ai_manager.py - النسخة الكاملة مع الذاكرة (Memory Support)
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
    """مدير خدمات الذكاء الاصطناعي مع ذاكرة للمحادثة"""
    
    def __init__(self, db):
        self.db = db
        # هنا نحفظ جلسات الدردشة لكل مستخدم (الذاكرة)
        self.chat_sessions: Dict[int, genai.ChatSession] = {} 
        self.model_name = "gemini-pro"
        self.user_limits_cache = {}
        self.setup_apis()
        
    def setup_apis(self):
        """إعداد واجهات برمجة التطبيقات واكتشاف الموديلات"""
        try:
            # 1. إعداد Google Gemini
            google_api_key = os.getenv("GOOGLE_AI_API_KEY")
            if google_api_key:
                genai.configure(api_key=google_api_key)
                self.gemini_available = True
                
                # الكود الذكي لاكتشاف الموديل
                try:
                    found_models = []
                    # البحث عن الموديلات التي تدعم إنشاء المحتوى
                    for m in genai.list_models():
                        if 'generateContent' in m.supported_generation_methods:
                            name = m.name.replace('models/', '')
                            found_models.append(name)
                    
                    logger.info(f"📋 الموديلات المتاحة: {found_models}")
                    
                    # ترتيب الأولويات
                    preferred = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro', 'gemini-1.0-pro']
                    
                    for p in preferred:
                        if p in found_models:
                            self.model_name = p
                            break
                            
                    logger.info(f"✅ تم اعتماد الموديل: {self.model_name}")
                except Exception as e:
                    logger.warning(f"⚠️ فشل الاكتشاف التلقائي، سنستخدم الافتراضي: {e}")
                    self.model_name = "gemini-pro"
            else:
                self.gemini_available = False
                logger.warning("⚠️ Google API Key missing")
            
            # 2. إعداد OpenAI
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if openai_api_key:
                openai.api_key = openai_api_key
                self.openai_available = True
            else:
                self.openai_available = False
            
            # 3. إعداد Luma AI (فيديو)
            self.luma_api_key = os.getenv("LUMAAI_API_KEY")
            self.luma_available = bool(self.luma_api_key)
            
            # 4. إعداد Stability AI (صور بديلة)
            self.stability_api_key = os.getenv("STABILITY_API_KEY")
            self.stable_diffusion_url = os.getenv("STABLE_DIFFUSION_URL", "https://api.stability.ai/v1/generation/stable-diffusion-v1-6/text-to-image")

        except Exception as e:
            logger.error(f"❌ Setup Error: {e}")
            self.gemini_available = False
            self.openai_available = False
            self.luma_available = False

    # ==================== إدارة الحدود والاستخدام ====================
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
        except Exception:
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
        except: return False

    # ==================== المحادثة (مع الذاكرة) ====================
    async def chat_with_ai(self, user_id: int, message: str, use_gemini: bool = True) -> str:
        try:
            allowed, remaining = self.check_user_limit(user_id, "ai_chat")
            if not allowed: return "❌ عذراً، لقد استهلكت رصيدك اليومي من الرسائل."
            
            response_text = ""
            
            if use_gemini and self.gemini_available:
                # 1. التحقق هل توجد جلسة سابقة؟
                if user_id not in self.chat_sessions:
                    # إنشاء جلسة جديدة مع تعليمات النظام
                    model = genai.GenerativeModel(self.model_name)
                    self.chat_sessions[user_id] = model.start_chat(history=[
                        {"role": "user", "parts": ["أنت مساعد ذكي مفيد، تتحدث العربية بطلاقة وتتذكر سياق الحديث."]},
                        {"role": "model", "parts": ["حسناً، فهمت. أنا جاهز للمساعدة وتذكر السياق."]}
                    ])
                
                chat_session = self.chat_sessions[user_id]
                
                try:
                    # إرسال الرسالة في سياق الجلسة
                    response = await chat_session.send_message_async(message)
                    response_text = response.text
                except Exception as e:
                    # في حالة الخطأ (مثل انتهاء صلاحية التوكن)، نعيد بدء الجلسة
                    logger.warning(f"Session Error for {user_id}: {e} - Restarting session")
                    model = genai.GenerativeModel(self.model_name)
                    self.chat_sessions[user_id] = model.start_chat(history=[])
                    chat_session = self.chat_sessions[user_id]
                    response = await chat_session.send_message_async(message)
                    response_text = response.text

            elif self.openai_available:
                # OpenAI (بدون ذاكرة متقدمة في هذا الإصدار البسيط)
                client = openai.OpenAI()
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": message}]
                )
                response_text = response.choices[0].message.content
            else:
                return "❌ خدمة الذكاء الاصطناعي غير متاحة حالياً."
            
            # حفظ الاستخدام والسجلات
            self.update_user_usage(user_id, "ai_chat")
            self.db.save_ai_conversation(user_id, "chat", message, response_text)
            
            return response_text
            
        except Exception as e:
            logger.error(f"Chat Error: {e}")
            return "⚠️ حدث خطأ أثناء المعالجة، حاول مرة أخرى."

    # ==================== خدمة الصور ====================
    async def generate_image(self, user_id: int, prompt: str, style: str = "realistic") -> Tuple[Optional[str], str]:
        try:
            allowed, _ = self.check_user_limit(user_id, "image_gen")
            if not allowed: return None, "❌ انتهى رصيد الصور اليومي."
            
            # تحسين الوصف باستخدام Gemini (إذا متاح)
            enhanced_prompt = prompt
            if self.gemini_available:
                try:
                    # نستخدم موديل منفصل للتحسين لعدم التأثير على ذاكرة الشات
                    model = genai.GenerativeModel(self.model_name)
                    resp = await model.generate_content_async(
                        f"Rewrite this prompt to be a detailed English description for an AI image generator (DALL-E), style: {style}. Prompt: {prompt}"
                    )
                    enhanced_prompt = resp.text
                except: pass

            image_url = None
            
            # محاولة 1: OpenAI DALL-E
            if self.openai_available:
                try:
                    client = openai.OpenAI()
                    response = client.images.generate(
                        model="dall-e-3", prompt=enhanced_prompt[:1000], size="1024x1024", quality="standard", n=1
                    )
                    image_url = response.data[0].url
                except Exception as e: logger.warning(f"DALL-E Error: {e}")

            # محاولة 2: Stability AI (إذا وجد المفتاح)
            if not image_url and self.stability_api_key:
                try:
                    headers = {"Authorization": f"Bearer {self.stability_api_key}", "Content-Type": "application/json"}
                    data = {"text_prompts": [{"text": enhanced_prompt, "weight": 1}], "cfg_scale": 7, "height": 512, "width": 512, "samples": 1}
                    async with aiohttp.ClientSession() as session:
                        async with session.post(self.stable_diffusion_url, headers=headers, json=data) as resp:
                            if resp.status == 200:
                                # ملاحظة: Stability يعيد الصورة Base64، نحتاج لرفعها. 
                                # للتبسيط هنا سنعيد رسالة نجاح وهمية إذا لم يكن هناك تخزين سحابي
                                return None, "⚠️ تم الإنشاء (يتطلب سيرفر لرفع الصور)" 
                except: pass

            if image_url:
                self.update_user_usage(user_id, "image_gen")
                self.db.save_generated_file(user_id, "image", prompt, image_url)
                return image_url, "✅ تم إنشاء الصورة بنجاح"
            
            return None, "❌ فشل إنشاء الصورة. تأكد من إعدادات API."

        except Exception as e:
            logger.error(f"Image Gen Error: {e}")
            return None, "حدث خطأ غير متوقع."

    # ==================== خدمة الفيديو ====================
    async def generate_video(self, user_id: int, prompt: str, image_url: str = None) -> Tuple[Optional[str], str]:
        try:
            allowed, _ = self.check_user_limit(user_id, "video_gen")
            if not allowed: return None, "❌ انتهى رصيد الفيديو اليومي."
            
            if not self.luma_available: return None, "❌ خدمة الفيديو غير مفعلة (LUMAAI_API_KEY missing)."

            # تحسين الوصف للفيديو
            enhanced_prompt = prompt
            if self.gemini_available:
                try:
                    model = genai.GenerativeModel(self.model_name)
                    resp = await model.generate_content_async(f"Enhance this video prompt for AI generation, make it cinematic and detailed: {prompt}")
                    enhanced_prompt = resp.text
                except: pass

            url = "https://api.lumalabs.ai/dream-machine/v1/generations"
            headers = {"Authorization": f"Bearer {self.luma_api_key}", "Content-Type": "application/json"}
            payload = {"prompt": enhanced_prompt, "aspect_ratio": "16:9"}
            
            if image_url:
                url = "https://api.lumalabs.ai/dream-machine/v1/generations/image"
                payload["image_url"] = image_url
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        err = await response.text()
                        return None, f"❌ خطأ من Luma: {err[:50]}"
                    
                    data = await response.json()
                    gen_id = data.get("id")
                    
                    # انتظار النتيجة (Polling)
                    for _ in range(40): # انتظار حتى 6-7 دقائق
                        await asyncio.sleep(10)
                        async with session.get(f"{url}/{gen_id}", headers=headers) as check_resp:
                            if check_resp.status == 200:
                                status_data = await check_resp.json()
                                state = status_data.get("state")
                                if state == "completed":
                                    video_url = status_data.get("assets", {}).get("video")
                                    if video_url:
                                        self.update_user_usage(user_id, "video_gen")
                                        self.db.save_generated_file(user_id, "video", prompt, video_url)
                                        return video_url, "✅ تم إنشاء الفيديو!"
                                elif state == "failed":
                                    return None, "❌ فشل توليد الفيديو من المصدر."
            
            return None, "⚠️ استغرق الفيديو وقتاً طويلاً، سيصلك لاحقاً إذا اكتمل."

        except Exception as e:
            logger.error(f"Video Error: {e}")
            return None, "خطأ تقني في خدمة الفيديو."

    # ==================== دوال مساعدة ====================
    def get_available_services(self) -> Dict[str, bool]:
        return {
            "chat": self.gemini_available or self.openai_available,
            "image_generation": self.openai_available or bool(self.stability_api_key),
            "video_generation": self.luma_available
        }
        
    def get_user_stats(self, user_id: int) -> Dict[str, int]:
        stats = {}
        for s_type in ["ai_chat", "image_gen", "video_gen"]:
            today = datetime.now().strftime('%Y-%m-%d')
            cache_key = f"{user_id}_{today}_{s_type}"
            stats[s_type] = self.user_limits_cache.get(cache_key, 0)
        return stats
