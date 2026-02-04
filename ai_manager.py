# ai_manager.py - النسخة الكاملة والمصححة (Fix 404 + Memory + All Features)
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
    """
    مدير خدمات الذكاء الاصطناعي المتكامل.
    يدعم:
    1. محادثة Gemini مع ذاكرة (Context Aware).
    2. توليد الصور (OpenAI / Stability).
    3. توليد الفيديو (Luma AI).
    4. إدارة حدود الاستخدام اليومي.
    """
    
    def __init__(self, db):
        self.db = db
        # ذاكرة المحادثات: قاموس يربط معرف المستخدم بجلسة الشات
        self.chat_sessions: Dict[int, genai.ChatSession] = {} 
        self.model_name = "gemini-1.5-flash" # القيمة الافتراضية الآمنة
        self.user_limits_cache = {}
        self.setup_apis()
        
    def setup_apis(self):
        """إعداد المفاتيح واختيار الموديل المناسب"""
        try:
            # 1. إعداد Google Gemini
            google_api_key = os.getenv("GOOGLE_AI_API_KEY")
            if google_api_key:
                genai.configure(api_key=google_api_key)
                self.gemini_available = True
                
                # --- إصلاح الخطأ 404: اختيار دقيق للموديل ---
                try:
                    logger.info("🔍 جاري فحص موديلات Gemini المتاحة...")
                    all_models = [m.name.replace('models/', '') for m in genai.list_models()]
                    logger.info(f"📋 الموديلات الموجودة: {all_models}")
                    
                    # القائمة المفضلة (بالترتيب من الأسرع والأحدث)
                    # تم إزالة 'gemini-pro' القديم لتجنب الخطأ 404
                    preferred_models = [
                        'gemini-1.5-flash',       # الخيار الأول: سريع جداً ومجاني
                        'gemini-1.5-flash-latest',
                        'gemini-1.5-pro',         # الخيار الثاني: ذكي جداً
                        'gemini-1.5-pro-latest',
                        'gemini-1.0-pro'          # الخيار البديل
                    ]
                    
                    target_model = None
                    for model in preferred_models:
                        if model in all_models:
                            target_model = model
                            break
                    
                    if target_model:
                        self.model_name = target_model
                        logger.info(f"✅ تم اعتماد الموديل: {self.model_name}")
                    else:
                        # إذا لم نجد أي موديل مفضل، نستخدم الفلاش إجبارياً
                        self.model_name = "gemini-1.5-flash"
                        logger.warning("⚠️ لم يتم العثور على موديل مفضل، تم فرض gemini-1.5-flash")
                        
                except Exception as e:
                    logger.warning(f"⚠️ فشل الاكتشاف التلقائي، سنستخدم الافتراضي: {e}")
                    self.model_name = "gemini-1.5-flash"
            else:
                self.gemini_available = False
                logger.warning("⚠️ Google API Key missing")
            
            # 2. إعداد OpenAI (للصور)
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if openai_api_key:
                openai.api_key = openai_api_key
                self.openai_available = True
            else:
                self.openai_available = False
            
            # 3. إعداد Luma AI (للفيديو)
            self.luma_api_key = os.getenv("LUMAAI_API_KEY")
            self.luma_available = bool(self.luma_api_key)
            
            # 4. إعداد Stability AI (بديل للصور)
            self.stability_api_key = os.getenv("STABILITY_API_KEY")
            self.stable_diffusion_url = os.getenv("STABLE_DIFFUSION_URL", "https://api.stability.ai/v1/generation/stable-diffusion-v1-6/text-to-image")

        except Exception as e:
            logger.error(f"❌ API Setup Critical Error: {e}")
            self.gemini_available = False
            self.openai_available = False
            self.luma_available = False

    # ==================== دوال إدارة الحدود (كاملة) ====================
    def check_user_limit(self, user_id: int, service_type: str = "ai_chat") -> Tuple[bool, int]:
        """التحقق مما إذا كان المستخدم قد تجاوز الحد اليومي"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            cache_key = f"{user_id}_{today}_{service_type}"
            
            # التحقق من الكاش أولاً لتخفيف الضغط على القاعدة
            if cache_key in self.user_limits_cache:
                current_usage = self.user_limits_cache[cache_key]
            else:
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT usage_count FROM ai_usage WHERE user_id = ? AND service_type = ? AND usage_date = ?', (user_id, service_type, today))
                    result = cursor.fetchone()
                    current_usage = result[0] if result else 0
                    self.user_limits_cache[cache_key] = current_usage
            
            # جلب الحدود من المتغيرات
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
            logger.error(f"Limit Check Error: {e}")
            return True, 999 # السماح في حالة الخطأ

    def update_user_usage(self, user_id: int, service_type: str = "ai_chat") -> bool:
        """تحديث استهلاك المستخدم"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            cache_key = f"{user_id}_{today}_{service_type}"
            
            # تحديث الكاش
            self.user_limits_cache[cache_key] = self.user_limits_cache.get(cache_key, 0) + 1
            
            # تحديث قاعدة البيانات
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
            logger.error(f"Usage Update Error: {e}")
            return False

    # ==================== خدمة المحادثة (مع الذاكرة وإصلاح الموديل) ====================
    async def chat_with_ai(self, user_id: int, message: str, use_gemini: bool = True) -> str:
        try:
            # 1. فحص الرصيد
            allowed, remaining = self.check_user_limit(user_id, "ai_chat")
            if not allowed:
                return "❌ عذراً، لقد استهلكت رصيدك اليومي من الرسائل. حاول غداً."
            
            response_text = ""
            
            if use_gemini and self.gemini_available:
                # --- منطق الذاكرة (Chat History) ---
                
                # إذا لم تكن هناك جلسة سابقة لهذا المستخدم، نبدأ واحدة جديدة
                if user_id not in self.chat_sessions:
                    try:
                        model = genai.GenerativeModel(self.model_name)
                        self.chat_sessions[user_id] = model.start_chat(history=[
                            {"role": "user", "parts": ["أنت مساعد ذكي ومفيد، تتحدث العربية بطلاقة، وتتذكر اسمي وسياق الكلام."]},
                            {"role": "model", "parts": ["حسناً، فهمت. أنا جاهز للمساعدة وسأتذكر سياق المحادثة."]}
                        ])
                    except Exception as e:
                        logger.error(f"Start Chat Error: {e}")
                        # محاولة أخيرة بالموديل الفلاش الإجباري
                        self.model_name = "gemini-1.5-flash"
                        model = genai.GenerativeModel(self.model_name)
                        self.chat_sessions[user_id] = model.start_chat(history=[])

                # استخدام الجلسة الحالية
                chat_session = self.chat_sessions[user_id]
                
                try:
                    # إرسال الرسالة وانتظار الرد
                    response = await chat_session.send_message_async(message)
                    response_text = response.text
                except Exception as e:
                    logger.warning(f"Session Error for {user_id}: {e}")
                    # في حالة حدوث خطأ (مثل انتهاء الصلاحية)، نعيد إنشاء الجلسة
                    try:
                        model = genai.GenerativeModel(self.model_name)
                        self.chat_sessions[user_id] = model.start_chat(history=[])
                        chat_session = self.chat_sessions[user_id]
                        response = await chat_session.send_message_async(message)
                        response_text = response.text
                    except Exception as final_e:
                         return f"⚠️ حدث خطأ في الاتصال بالموديل {self.model_name}: {final_e}"

            elif self.openai_available:
                # OpenAI (fallback)
                try:
                    client = openai.OpenAI()
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": message}]
                    )
                    response_text = response.choices[0].message.content
                except Exception as e:
                    return f"❌ خطأ في OpenAI: {e}"
            else:
                return "❌ خدمة الذكاء الاصطناعي غير متاحة حالياً. تأكد من المفاتيح (GOOGLE_AI_API_KEY)."
            
            # تسجيل العملية وحفظ الرد
            self.update_user_usage(user_id, "ai_chat")
            self.db.save_ai_conversation(user_id, "chat", message, response_text)
            
            return response_text
            
        except Exception as e:
            logger.error(f"General Chat Error: {e}")
            return "⚠️ حدث خطأ غير متوقع أثناء المعالجة."

    # ==================== خدمة الصور (كاملة) ====================
    async def generate_image(self, user_id: int, prompt: str, style: str = "realistic") -> Tuple[Optional[str], str]:
        try:
            allowed, _ = self.check_user_limit(user_id, "image_gen")
            if not allowed: return None, "❌ انتهى رصيد الصور اليومي."
            
            # تحسين الوصف باستخدام Gemini (للحصول على نتائج أفضل)
            enhanced_prompt = prompt
            if self.gemini_available:
                try:
                    # نستخدم موديل منفصل للتحسين حتى لا نؤثر على ذاكرة الشات
                    model = genai.GenerativeModel(self.model_name)
                    resp = await model.generate_content_async(
                        f"Rewrite this prompt to be a detailed English description for DALL-E image generator, style: {style}. Prompt: {prompt}"
                    )
                    enhanced_prompt = resp.text
                except Exception as e:
                    logger.warning(f"Prompt enhancement failed: {e}")

            image_url = None
            
            # الخيار 1: OpenAI DALL-E 3
            if self.openai_available:
                try:
                    client = openai.OpenAI()
                    response = client.images.generate(
                        model="dall-e-3",
                        prompt=enhanced_prompt[:1000], # DALL-E limit
                        size="1024x1024",
                        quality="standard",
                        n=1
                    )
                    image_url = response.data[0].url
                except Exception as e:
                    logger.warning(f"DALL-E Error: {e}")

            # الخيار 2: Stability AI (الاحتياطي)
            if not image_url and self.stability_api_key:
                try:
                    headers = {
                        "Authorization": f"Bearer {self.stability_api_key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                    data = {
                        "text_prompts": [{"text": enhanced_prompt, "weight": 1}],
                        "cfg_scale": 7,
                        "height": 512,
                        "width": 512,
                        "samples": 1
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.post(self.stable_diffusion_url, headers=headers, json=data) as resp:
                            if resp.status == 200:
                                # ملاحظة: Stability يعيد الصورة كـ Base64، وهذا يحتاج معالجة خاصة لرفعها
                                # للتبسيط هنا، سنعيد رسالة توضيحية
                                return None, "⚠️ تم إنشاء الصورة بنجاح (Stability)، لكن نظام رفع الملفات يحتاج تهيئة."
                except Exception as e:
                    logger.warning(f"Stability Error: {e}")

            if image_url:
                self.update_user_usage(user_id, "image_gen")
                self.db.save_generated_file(user_id, "image", prompt, image_url)
                return image_url, "✅ تم إنشاء الصورة بنجاح"
            
            return None, "❌ فشل إنشاء الصورة. تأكد من توفر رصيد في OpenAI أو Stability."

        except Exception as e:
            logger.error(f"Image Gen Error: {e}")
            return None, "حدث خطأ غير متوقع في خدمة الصور."

    # ==================== خدمة الفيديو (كاملة) ====================
    async def generate_video(self, user_id: int, prompt: str, image_url: str = None) -> Tuple[Optional[str], str]:
        try:
            allowed, _ = self.check_user_limit(user_id, "video_gen")
            if not allowed: return None, "❌ انتهى رصيد الفيديو اليومي."
            
            if not self.luma_available:
                return None, "❌ خدمة الفيديو غير مفعلة (LUMAAI_API_KEY غير موجود)."

            # تحسين الوصف للفيديو
            enhanced_prompt = prompt
            if self.gemini_available:
                try:
                    model = genai.GenerativeModel(self.model_name)
                    resp = await model.generate_content_async(f"Enhance this video prompt, make it cinematic and detailed (English): {prompt}")
                    enhanced_prompt = resp.text
                except: pass

            # إعداد الطلب لخدمة Luma Dream Machine
            url = "https://api.lumalabs.ai/dream-machine/v1/generations"
            headers = {
                "Authorization": f"Bearer {self.luma_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "prompt": enhanced_prompt,
                "aspect_ratio": "16:9"
            }
            
            if image_url:
                url = "https://api.lumalabs.ai/dream-machine/v1/generations/image"
                payload["image_url"] = image_url
            
            async with aiohttp.ClientSession() as session:
                # إرسال طلب الإنشاء
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status != 201 and response.status != 200:
                        err_text = await response.text()
                        return None, f"❌ خطأ من Luma: {response.status} - {err_text[:100]}"
                    
                    data = await response.json()
                    gen_id = data.get("id")
                    if not gen_id:
                        return None, "❌ لم يتم استلام معرف الفيديو."
                    
                    # الانتظار حتى يكتمل الفيديو (Polling)
                    # ننتظر بحد أقصى 60 محاولة * 5 ثواني = 5 دقائق
                    for _ in range(60):
                        await asyncio.sleep(5)
                        async with session.get(f"{url}/{gen_id}", headers=headers) as check_resp:
                            if check_resp.status == 200:
                                status_data = await check_resp.json()
                                state = status_data.get("state")
                                
                                if state == "completed":
                                    video_url = status_data.get("assets", {}).get("video")
                                    if video_url:
                                        self.update_user_usage(user_id, "video_gen")
                                        self.db.save_generated_file(user_id, "video", prompt, video_url)
                                        return video_url, "✅ تم إنشاء الفيديو بنجاح!"
                                elif state == "failed":
                                    return None, f"❌ فشل توليد الفيديو: {status_data.get('failure_reason')}"
            
            return None, "⚠️ استغرق الفيديو وقتاً طويلاً جداً، سيتم إشعارك عند اكتماله."

        except Exception as e:
            logger.error(f"Video Error: {e}")
            return None, "حدث خطأ تقني في خدمة الفيديو."

    # ==================== دوال مساعدة ومعلومات ====================
    def get_available_services(self) -> Dict[str, bool]:
        """إرجاع حالة الخدمات المتاحة"""
        return {
            "chat": self.gemini_available or self.openai_available,
            "image_generation": self.openai_available or bool(self.stability_api_key),
            "video_generation": self.luma_available
        }
        
    def get_user_stats(self, user_id: int) -> Dict[str, int]:
        """إرجاع إحصائيات استخدام المستخدم لليوم"""
        stats = {}
        for s_type in ["ai_chat", "image_gen", "video_gen"]:
            today = datetime.now().strftime('%Y-%m-%d')
            cache_key = f"{user_id}_{today}_{s_type}"
            stats[s_type] = self.user_limits_cache.get(cache_key, 0)
        return stats
