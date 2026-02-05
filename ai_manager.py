# ai_manager.py - الإصدار الكامل والمعدل (نظام الطوارئ + تنظيف الردود)
import os
import logging
import asyncio
import google.generativeai as genai
import openai
import aiohttp
import re  # مكتبة مهمة لتنظيف الردود
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class AIManager:
    """
    مدير خدمات الذكاء الاصطناعي المتكامل.
    يدعم:
    1. محادثة Gemini مع ذاكرة ونظام طوارئ (Fallback).
    2. توليد الصور (OpenAI / Stability).
    3. توليد الفيديو (Luma AI).
    4. إدارة حدود الاستخدام اليومي.
    """
    
    def __init__(self, db):
        self.db = db
        # ذاكرة المحادثات: قاموس يربط معرف المستخدم بجلسة الشات
        self.chat_sessions: Dict[int, genai.ChatSession] = {} 
        # الموديل الافتراضي المبدئي (سيتم تحديثه في setup_apis)
        self.model_name = "gemini-2.0-flash" 
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
                
                # --- اختيار الموديل الذكي ---
                try:
                    logger.info("🔍 جاري فحص موديلات Gemini المتاحة...")
                    all_models = [m.name.replace('models/', '') for m in genai.list_models()]
                    logger.info(f"📋 الموديلات الموجودة: {all_models}")
                    
                    # القائمة المفضلة (الأولوية للأحدث والأقوى)
                    preferred_models = [
                        'gemini-2.5-flash',       # الأساسي (الأقوى والأحدث)
                        'gemini-2.0-flash',       # الاحتياطي الممتاز
                        'gemini-2.0-flash-lite',  # خيار سريع جداً
                        'gemini-1.5-pro-latest',
                        'gemini-1.5-pro',
                        'gemini-1.5-flash'
                    ]
                    
                    target_model = None
                    for model in preferred_models:
                        if model in all_models:
                            target_model = model
                            break
                    
                    if target_model:
                        self.model_name = target_model
                        logger.info(f"✅ تم اعتماد الموديل الأساسي: {self.model_name}")
                    else:
                        # إذا لم يجد شيئاً، يستخدم 2.0 كخيار آمن
                        self.model_name = "gemini-2.0-flash"
                        logger.warning("⚠️ لم يتم العثور على الموديلات المفضلة، تم فرض gemini-2.0-flash")
                        
                except Exception as e:
                    logger.warning(f"⚠️ خطأ في الاكتشاف التلقائي، سنستخدم الافتراضي: {e}")
                    self.model_name = "gemini-2.0-flash"
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
  
    # ==================== دالة تنظيف الردود (الجديدة) ====================
    def clean_response(self, text: str) -> str:
        """إزالة أفكار الموديل (THOUGHT) مع حماية ضد الرسائل الفارغة"""
        if not text: return "عذراً، لم أستطع تكوين رد مناسب."
        
        # حفظ النص الأصلي للاحتياط
        original_text = text
        
        # حذف كتل الـ THOUGHT التي قد تظهر في بداية الرد
        # النمط: يبحث عن كلمة THOUGHT: ويحذف كل شيء بعدها حتى يجد سطرين فارغين أو نهاية النص
        clean_text = re.sub(r'THOUGHT:.*?(?=\n\n|\Z)', '', text, flags=re.DOTALL | re.IGNORECASE)
        
        # تنظيف إضافي لأي بقايا
        clean_text = clean_text.replace("THOUGHT:", "").strip()
        
        # 🔥 الحماية من الرسالة الفارغة 🔥
        # إذا كان التنظيف قد مسح كل شيء (مثلاً الموديل أرسل تفكيراً فقط)، نرجع النص الأصلي كما هو
        if not clean_text or len(clean_text) < 2:
            return original_text
            
        return clean_text

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

    # ==================== خدمة المحادثة (مع نظام الطوارئ الذكي) ====================
    async def chat_with_ai(self, user_id: int, message: str, use_gemini: bool = True) -> str:
        try:
            # 1. فحص الرصيد
            allowed, remaining = self.check_user_limit(user_id, "ai_chat")
            if not allowed:
                return "❌ عذراً، لقد استهلكت رصيدك اليومي من الرسائل. حاول غداً."
            
            response_text = ""
            
            if use_gemini and self.gemini_available:
                # --- إعداد الجلسة (Memory) ---
                if user_id not in self.chat_sessions:
                    try:
                        # محاولة بدء الجلسة بالموديل الأساسي (غالباً 2.5)
                        model = genai.GenerativeModel(self.model_name)
                        self.chat_sessions[user_id] = model.start_chat(history=[
                            {"role": "user", "parts": ["أنت مساعد ذكي ومفيد. رد مباشرة بالعربية ولا تظهر خطوات تفكيرك."]},
                            {"role": "model", "parts": ["حسناً، سأرد مباشرة."]}
                        ])
                    except Exception as e:
                        logger.warning(f"فشل بدء الجلسة بالموديل الأساسي: {e}. التحويل للاحتياطي.")
                        # إذا فشل الأساسي، نبدأ بالاحتياطي (2.0)
                        self.model_name = "gemini-2.0-flash"
                        model = genai.GenerativeModel(self.model_name)
                        self.chat_sessions[user_id] = model.start_chat(history=[])

                chat_session = self.chat_sessions[user_id]
                
                try:
                    # 🔥 المحاولة الأولى: الموديل الأساسي 🔥
                    response = await chat_session.send_message_async(message)
                    # تنظيف الرد من الـ THOUGHT
                    response_text = self.clean_response(response.text)
                    
                except Exception as e:
                    # 🔥 نظام الطوارئ (Fallback System) 🔥
                    error_str = str(e).lower()
                    
                    # التحقق مما إذا كان الخطأ بسبب الضغط (Quota / 429 / Resource Exhausted)
                    if "429" in error_str or "quota" in error_str or "resource" in error_str or "overloaded" in error_str:
                        logger.warning(f"⚠️ الموديل {self.model_name} مشغول (Quota). جاري التحويل لـ gemini-2.0-flash...")
                        
                        try:
                            # استخدام الموديل الاحتياطي القوي (2.0 Flash)
                            fallback_model = genai.GenerativeModel("gemini-2.0-flash")
                            
                            # نستخدم generate_content بدلاً من chat لضمان عدم حدوث خطأ في الجلسة
                            # هذا يعني أن هذه الرسالة تحديداً قد تفقد جزءاً من السياق، لكنها ستنجح في الوصول
                            response = await fallback_model.generate_content_async(message)
                            response_text = self.clean_response(response.text)
                            
                        except Exception as fallback_e:
                            logger.error(f"❌ فشل الموديل الاحتياطي أيضاً: {fallback_e}")
                            return "⚠️ الخوادم مشغولة جداً الآن، يرجى الانتظار قليلاً والمحاولة مجدداً."
                    else:
                        # إذا كان الخطأ تقنياً آخر (ليس ضغط)، نحاول إعادة ضبط الجلسة
                        logger.warning(f"Session Error: {e}. Restarting session with 2.0-flash.")
                        try:
                            # إعادة ضبط الجلسة باستخدام الموديل الآمن
                            safe_model = genai.GenerativeModel("gemini-2.0-flash")
                            self.chat_sessions[user_id] = safe_model.start_chat(history=[])
                            response = await self.chat_sessions[user_id].send_message_async(message)
                            response_text = self.clean_response(response.text)
                        except:
                            return "⚠️ حدث خطأ تقني بسيط أثناء المعالجة."

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
            
            # تحسين الوصف باستخدام Gemini (مع الاحتياطي)
            enhanced_prompt = prompt
            if self.gemini_available:
                try:
                    # نحاول بالموديل الحالي
                    model = genai.GenerativeModel(self.model_name)
                    resp = await model.generate_content_async(
                        f"Rewrite this prompt to be a detailed English description for DALL-E image generator, style: {style}. Prompt: {prompt}"
                    )
                    enhanced_prompt = self.clean_response(resp.text)
                except:
                    # إذا فشل، نحاول بالموديل الاحتياطي
                    try:
                        model = genai.GenerativeModel("gemini-2.0-flash")
                        resp = await model.generate_content_async(f"Rewrite prompt for DALL-E: {prompt}")
                        enhanced_prompt = self.clean_response(resp.text)
                    except: pass # إذا فشل الاثنان، نستخدم النص الأصلي

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

            # تحسين الوصف للفيديو (مع الاحتياطي)
            enhanced_prompt = prompt
            if self.gemini_available:
                try:
                    model = genai.GenerativeModel(self.model_name)
                    resp = await model.generate_content_async(f"Enhance this video prompt, make it cinematic and detailed (English): {prompt}")
                    enhanced_prompt = self.clean_response(resp.text)
                except:
                    try:
                        model = genai.GenerativeModel("gemini-2.0-flash")
                        resp = await model.generate_content_async(f"Enhance video prompt: {prompt}")
                        enhanced_prompt = self.clean_response(resp.text)
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
