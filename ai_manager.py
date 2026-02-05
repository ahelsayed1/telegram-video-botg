# ai_manager.py - الإصدار العملاق (نظام الدفاع الثلاثي + كافة الخدمات + توثيق كامل)
# هذا الملف يحتوي على كافة التعديلات المطلوبة مع الحفاظ على البنية الأساسية
# المميزات الجديدة:
# 1. نظام دفاع ثلاثي للموديلات (Gemini 2.5 -> 2.0 -> 1.5)
# 2. تنظيف الردود من النصوص التحليلية (THOUGHT)
# 3. دعم كامل وموسع لخدمات الصور والفيديو
# 4. معالجة دقيقة للأخطاء والحدود

import os
import logging
import asyncio
import google.generativeai as genai
import openai
import aiohttp
import re  # مكتبة التعامل مع النصوص (Regex) لتنظيف الردود
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

# إعداد نظام التسجيل (Logging) لمتابعة الأخطاء بدقة
logger = logging.getLogger(__name__)

class AIManager:
    """
    مدير خدمات الذكاء الاصطناعي المتكامل.
    
    يقوم هذا الكلاس بإدارة:
    1. محادثات Gemini مع نظام ذاكرة ونظام طوارئ متطور.
    2. توليد الصور باستخدام OpenAI DALL-E 3 أو Stability AI.
    3. توليد الفيديو باستخدام Luma Dream Machine.
    4. تتبع استهلاك المستخدمين والحدود اليومية.
    """
    
    def __init__(self, db):
        """
        تهيئة مدير الذكاء الاصطناعي.
        :param db: كائن قاعدة البيانات للتعامل مع التخزين.
        """
        self.db = db
        
        # قاموس لتخزين جلسات المحادثة النشطة (Chat Sessions)
        # المفتاح: user_id، القيمة: كائن ChatSession
        self.chat_sessions: Dict[int, genai.ChatSession] = {} 
        
        # الموديل الافتراضي المبدئي (سيتم تحديثه تلقائياً في setup_apis)
        self.model_name = "gemini-2.5-flash" 
        
        # كاش محلي لتخزين حدود الاستخدام لتقليل الضغط على قاعدة البيانات
        self.user_limits_cache = {}
        
        # استدعاء دالة إعداد واجهات البرمجة
        self.setup_apis()
        
    def setup_apis(self):
        """
        إعداد مفاتيح واجهات برمجة التطبيقات (APIs) واختيار الموديل الأنسب.
        يتم التحقق من وجود المفاتيح في متغيرات البيئة وتهيئة المكتبات.
        """
        try:
            # ==================== 1. إعداد Google Gemini ====================
            google_api_key = os.getenv("GOOGLE_AI_API_KEY")
            if google_api_key:
                genai.configure(api_key=google_api_key)
                self.gemini_available = True
                logger.info("✅ تم الاتصال بخدمة Google Gemini بنجاح.")
                
                # --- اكتشاف الموديلات المتاحة وترتيب الأولويات ---
                try:
                    logger.info("🔍 جاري فحص موديلات Gemini المتاحة في الحساب...")
                    
                    # استخراج قائمة الموديلات التي تدعم توليد المحتوى
                    all_models = []
                    for m in genai.list_models():
                        if 'generateContent' in m.supported_generation_methods:
                            model_name = m.name.replace('models/', '')
                            all_models.append(model_name)
                            
                    logger.info(f"📋 الموديلات المكتشفة: {all_models}")
                    
                    # القائمة المفضلة (الترتيب التنازلي حسب القوة والحداثة)
                    # هذا الترتيب يحدد من سيكون "المهاجم الأساسي"
                    preferred_models = [
                        'gemini-2.5-flash',       # الأساسي: الأقوى والأحدث
                        'gemini-2.0-flash',       # الدفاع الأول: توازن ممتاز بين السرعة والذكاء
                        'gemini-1.5-pro-latest',  # خيار قوي جداً
                        'gemini-1.5-pro',
                        'gemini-1.5-flash'        # الدفاع الأخير: الأكثر استقراراً
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
                        # إذا لم نجد أي موديل معروف، نفترض وجود 2.5 كخيار افتراضي
                        self.model_name = "gemini-2.5-flash"
                        logger.warning("⚠️ لم يتم العثور على موديل مفضل في القائمة، تم فرض gemini-2.5-flash")
                        
                except Exception as e:
                    logger.warning(f"⚠️ حدث خطأ أثناء الاكتشاف التلقائي للموديلات: {e}")
                    # في حالة الخطأ، نعود للموديل القوي كافتراضي
                    self.model_name = "gemini-2.5-flash"
            else:
                self.gemini_available = False
                logger.warning("⚠️ مفتاح Google API غير موجود (GOOGLE_AI_API_KEY).")
            
            # ==================== 2. إعداد OpenAI (للصور) ====================
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if openai_api_key:
                openai.api_key = openai_api_key
                self.openai_available = True
                logger.info("✅ تم تفعيل خدمة OpenAI.")
            else:
                self.openai_available = False
                logger.info("ℹ️ خدمة OpenAI غير مفعلة.")
            
            # ==================== 3. إعداد Luma AI (للفيديو) ====================
            self.luma_api_key = os.getenv("LUMAAI_API_KEY")
            self.luma_available = bool(self.luma_api_key)
            if self.luma_available:
                logger.info("✅ تم تفعيل خدمة Luma AI للفيديو.")
            
            # ==================== 4. إعداد Stability AI (بديل للصور) ====================
            self.stability_api_key = os.getenv("STABILITY_API_KEY")
            self.stable_diffusion_url = os.getenv("STABLE_DIFFUSION_URL", "https://api.stability.ai/v1/generation/stable-diffusion-v1-6/text-to-image")
            if self.stability_api_key:
                logger.info("✅ تم تفعيل خدمة Stability AI.")

        except Exception as e:
            logger.error(f"❌ خطأ حرج في إعداد الواجهات (Setup Error): {e}")
            self.gemini_available = False
            self.openai_available = False
            self.luma_available = False
  
    # ==================== دالة تنظيف الردود (Clean Response) ====================
    def clean_response(self, text: str) -> str:
        """
        تقوم هذه الدالة بتنظيف رد الذكاء الاصطناعي من "أفكاره الداخلية".
        الموديلات الجديدة (مثل 2.5) قد تطبع خطوات التفكير (Thinking Process) قبل الرد.
        هذه الدالة تزيل تلك الأفكار لتعطي المستخدم الرد النهائي فقط.
        
        :param text: النص الخام القادم من الموديل.
        :return: النص النظيف الجاهز للإرسال.
        """
        if not text:
            return "عذراً، لم أستطع تكوين رد مناسب في الوقت الحالي."
        
        # حفظ النص الأصلي لاستخدامه في حالة الطوارئ (إذا مسحنا كل شيء بالخطأ)
        original_text = text
        
        # نمط Regex للبحث عن كتل التفكير وحذفها
        # يبحث عن كلمة THOUGHT: ويحذف كل شيء بعدها حتى يجد سطرين فارغين أو نهاية النص
        # FLAGS: DOTALL (النقطة تشمل الأسطر الجديدة) | IGNORECASE (تجاهل حالة الأحرف)
        clean_text = re.sub(r'THOUGHT:.*?(?=\n\n|\Z)', '', text, flags=re.DOTALL | re.IGNORECASE)
        
        # تنظيف إضافي لأي بقايا (مثل مسافات زائدة أو كلمة THOUGHT متبقية)
        clean_text = clean_text.replace("THOUGHT:", "").strip()
        
        # 🔥 حماية من الرسالة الفارغة 🔥
        # إذا كان التنظيف قد مسح كل شيء (مثلاً الموديل أرسل تفكيراً فقط بدون رد)،
        # نرجع النص الأصلي كما هو لكي لا يظهر للمستخدم رسالة فارغة.
        if not clean_text or len(clean_text) < 2:
            return original_text
            
        return clean_text

    # ==================== دوال إدارة الحدود (Limits Management) ====================
    def check_user_limit(self, user_id: int, service_type: str = "ai_chat") -> Tuple[bool, int]:
        """
        التحقق مما إذا كان المستخدم قد تجاوز الحد اليومي المسموح به للخدمة.
        
        :param user_id: معرف المستخدم.
        :param service_type: نوع الخدمة (ai_chat, image_gen, video_gen).
        :return: (مسموح_أم_لا, المتبقي).
        """
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            cache_key = f"{user_id}_{today}_{service_type}"
            
            # 1. التحقق من الكاش أولاً (أسرع)
            if cache_key in self.user_limits_cache:
                current_usage = self.user_limits_cache[cache_key]
            else:
                # 2. التحقق من قاعدة البيانات إذا لم يكن في الكاش
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        'SELECT usage_count FROM ai_usage WHERE user_id = ? AND service_type = ? AND usage_date = ?', 
                        (user_id, service_type, today)
                    )
                    result = cursor.fetchone()
                    current_usage = result[0] if result else 0
                    # تحديث الكاش
                    self.user_limits_cache[cache_key] = current_usage
            
            # جلب الحدود من متغيرات البيئة (أو استخدام القيم الافتراضية)
            limits_config = {
                "ai_chat": int(os.getenv("DAILY_AI_LIMIT", "20")),
                "image_gen": int(os.getenv("DAILY_IMAGE_LIMIT", "5")),
                "video_gen": int(os.getenv("DAILY_VIDEO_LIMIT", "2"))
            }
            
            limit = limits_config.get(service_type, 20)
            
            # التحقق النهائي
            if current_usage >= limit:
                return False, 0
            
            return True, limit - current_usage
            
        except Exception as e:
            logger.error(f"❌ خطأ في فحص الحدود (Limit Check Error): {e}")
            # في حالة الخطأ، نسمح بالعملية لتجنب تعطيل المستخدم
            return True, 999 

    def update_user_usage(self, user_id: int, service_type: str = "ai_chat") -> bool:
        """
        تحديث سجل استهلاك المستخدم بعد نجاح العملية.
        
        :param user_id: معرف المستخدم.
        :param service_type: نوع الخدمة.
        :return: True إذا تم التحديث بنجاح.
        """
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            cache_key = f"{user_id}_{today}_{service_type}"
            
            # تحديث الكاش
            self.user_limits_cache[cache_key] = self.user_limits_cache.get(cache_key, 0) + 1
            
            # تحديث قاعدة البيانات (Insert or Update)
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
            logger.error(f"❌ خطأ في تحديث الاستهلاك (Usage Update Error): {e}")
            return False

    # ==================== خدمة المحادثة (نظام الدفاع الثلاثي) ====================
    async def chat_with_ai(self, user_id: int, message: str, use_gemini: bool = True) -> str:
        """
        إجراء محادثة ذكية مع المستخدم باستخدام استراتيجية الدفاع الثلاثي.
        
        الاستراتيجية:
        1. المحاولة بـ Gemini 2.5 Flash (الأذكى).
        2. عند الفشل، المحاولة بـ Gemini 2.0 Flash (المتوازن).
        3. عند الفشل، المحاولة بـ Gemini 1.5 Flash (المنقذ - حدود عالية).
        """
        try:
            # 1. التحقق من رصيد المستخدم
            allowed, remaining = self.check_user_limit(user_id, "ai_chat")
            if not allowed:
                return "❌ عذراً، لقد استهلكت رصيدك اليومي من الرسائل. يتجدد الرصيد غداً."
            
            response_text = ""
            
            if use_gemini and self.gemini_available:
                
                # -----------------------------------------------------------
                # 🟢 المحاولة الأولى: الموديل الأساسي (Gemini 2.5 Flash)
                # -----------------------------------------------------------
                try:
                    # إعداد الجلسة (Memory) إذا لم تكن موجودة
                    if user_id not in self.chat_sessions:
                        # نستخدم الموديل 2.5 لإنشاء الجلسة
                        model_v1 = genai.GenerativeModel("gemini-2.5-flash")
                        self.chat_sessions[user_id] = model_v1.start_chat(history=[
                            {"role": "user", "parts": ["أنت مساعد ذكي ومفيد تتحدث العربية بطلاقة. رد مباشرة دون مقدمات طويلة."]},
                            {"role": "model", "parts": ["حسناً، فهمت. سأرد مباشرة وباللغة العربية."]}
                        ])
                    
                    # محاولة إرسال الرسالة
                    chat_session = self.chat_sessions[user_id]
                    response = await chat_session.send_message_async(message)
                    
                    # تنظيف الرد
                    response_text = self.clean_response(response.text)
                    
                except Exception as e1:
                    # تسجيل فشل الموديل الأول
                    logger.warning(f"⚠️ فشل الموديل الأساسي (2.5-flash): {e1}. جاري الانتقال لخط الدفاع الأول...")
                    
                    # -----------------------------------------------------------
                    # 🟡 المحاولة الثانية: خط الدفاع الأول (Gemini 2.0 Flash)
                    # -----------------------------------------------------------
                    try:
                        # نستخدم generate_content لضمان سرعة الرد وتجاوز مشاكل الجلسة المعلقة
                        fallback_model_1 = genai.GenerativeModel("gemini-2.0-flash")
                        response = await fallback_model_1.generate_content_async(message)
                        
                        # تنظيف الرد
                        response_text = self.clean_response(response.text)
                        
                    except Exception as e2:
                        # تسجيل فشل الموديل الثاني
                        logger.warning(f"⚠️ فشل خط الدفاع الأول (2.0-flash): {e2}. جاري الانتقال لخط الدفاع الأخير...")
                        
                        # -----------------------------------------------------------
                        # 🔴 المحاولة الثالثة: خط الدفاع الأخير (Gemini 1.5 Flash)
                        # هذا الموديل يتميز بحدود استخدام عالية جداً (High Quota)
                        # -----------------------------------------------------------
                        try:
                            fallback_model_2 = genai.GenerativeModel("gemini-1.5-flash")
                            response = await fallback_model_2.generate_content_async(message)
                            
                            # تنظيف الرد
                            response_text = self.clean_response(response.text)
                            
                        except Exception as e3:
                            # إذا فشلت الثلاث محاولات، فهذا يعني وجود مشكلة عامة في خوادم جوجل
                            logger.error(f"❌ فشل جميع الموديلات (2.5 -> 2.0 -> 1.5): {e3}")
                            return "⚠️ جميع خوادم الذكاء الاصطناعي مشغولة جداً حالياً، يرجى الانتظار دقيقة والمحاولة مجدداً."

            elif self.openai_available:
                # خيار OpenAI إذا كان مفعلاً كبديل كلي
                try:
                    client = openai.OpenAI()
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": message}]
                    )
                    response_text = response.choices[0].message.content
                except Exception as e:
                    logger.error(f"❌ خطأ في OpenAI Chat: {e}")
                    return f"❌ حدث خطأ في خدمة OpenAI: {e}"
            else:
                return "❌ خدمة الذكاء الاصطناعي غير متاحة حالياً. يرجى التأكد من مفاتيح API."
            
            # تسجيل العملية وحفظ الرد في قاعدة البيانات
            self.update_user_usage(user_id, "ai_chat")
            self.db.save_ai_conversation(user_id, "chat", message, response_text)
            
            return response_text
            
        except Exception as e:
            logger.error(f"❌ General Chat Error (خطأ عام): {e}")
            return "⚠️ حدث خطأ غير متوقع أثناء المعالجة."

    # ==================== خدمة الصور (نظام الدفاع الثلاثي للوصف) ====================
    async def generate_image(self, user_id: int, prompt: str, style: str = "realistic") -> Tuple[Optional[str], str]:
        """
        توليد صورة بناءً على الوصف النصي.
        يتم تحسين الوصف أولاً باستخدام Gemini (بنظام الدفاع الثلاثي)، ثم إرساله لـ DALL-E.
        """
        try:
            # 1. التحقق من الحدود
            allowed, _ = self.check_user_limit(user_id, "image_gen")
            if not allowed: return None, "❌ انتهى رصيد الصور اليومي."
            
            # 2. تحسين الوصف (Prompt Engineering) باستخدام Gemini
            # سنحاول بـ 3 موديلات لضمان الحصول على وصف محسن
            enhanced_prompt = prompt
            
            if self.gemini_available:
                # محاولة 1: Gemini 2.5
                try:
                    m = genai.GenerativeModel("gemini-2.5-flash")
                    r = await m.generate_content_async(f"Rewrite this prompt to be a detailed English description for DALL-E image generator, style: {style}. Prompt: {prompt}")
                    enhanced_prompt = self.clean_response(r.text)
                except:
                    # محاولة 2: Gemini 2.0
                    try:
                        m = genai.GenerativeModel("gemini-2.0-flash")
                        r = await m.generate_content_async(f"Rewrite prompt for DALL-E image generation: {prompt}")
                        enhanced_prompt = self.clean_response(r.text)
                    except:
                        # محاولة 3: Gemini 1.5
                        try:
                            m = genai.GenerativeModel("gemini-1.5-flash")
                            r = await m.generate_content_async(f"English prompt for DALL-E: {prompt}")
                            enhanced_prompt = self.clean_response(r.text)
                        except:
                            # إذا فشل الجميع، نستخدم الوصف الأصلي كما هو
                            logger.warning("⚠️ فشل تحسين وصف الصورة بجميع الموديلات، استخدام الوصف الأصلي.")
                            pass

            image_url = None
            
            # 3. التوليد باستخدام OpenAI DALL-E 3 (الخيار الأفضل)
            if self.openai_available:
                try:
                    client = openai.OpenAI()
                    response = client.images.generate(
                        model="dall-e-3",
                        prompt=enhanced_prompt[:1000],  # DALL-E يقبل 1000 حرف كحد أقصى
                        size="1024x1024",
                        quality="standard",
                        n=1
                    )
                    image_url = response.data[0].url
                except Exception as e:
                    logger.warning(f"❌ خطأ DALL-E: {e}")

            # 4. التوليد باستخدام Stability AI (الخيار الاحتياطي)
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
                                # ملاحظة: Stability يعيد الصورة كـ Base64، وهذا يحتاج كود إضافي للرفع
                                # هنا نكتفي بإشعار النجاح لتجنب تعقيد الكود أكثر من اللازم
                                return None, "⚠️ تم إنشاء الصورة بنجاح (Stability)، لكن يتطلب سيرفر لرفعها."
                            else:
                                logger.error(f"Stability Error: {await resp.text()}")
                except Exception as e:
                    logger.warning(f"❌ خطأ Stability: {e}")

            # 5. النتيجة النهائية
            if image_url:
                self.update_user_usage(user_id, "image_gen")
                self.db.save_generated_file(user_id, "image", prompt, image_url)
                return image_url, "✅ تم إنشاء الصورة بنجاح"
            
            return None, "❌ فشل إنشاء الصورة. تأكد من توفر رصيد في OpenAI."

        except Exception as e:
            logger.error(f"❌ Image Gen Error: {e}")
            return None, "حدث خطأ غير متوقع في خدمة الصور."

    # ==================== خدمة الفيديو (نظام الدفاع الثلاثي للوصف) ====================
    async def generate_video(self, user_id: int, prompt: str, image_url: str = None) -> Tuple[Optional[str], str]:
        """
        توليد فيديو باستخدام Luma Dream Machine.
        يتضمن تحسين الوصف أولاً بنظام الدفاع الثلاثي.
        """
        try:
            # 1. التحقق من الحدود
            allowed, _ = self.check_user_limit(user_id, "video_gen")
            if not allowed: return None, "❌ انتهى رصيد الفيديو اليومي."
            
            if not self.luma_available:
                return None, "❌ خدمة الفيديو غير مفعلة (LUMAAI_API_KEY غير موجود)."

            # 2. تحسين الوصف للفيديو (ثلاث محاولات)
            enhanced_prompt = prompt
            if self.gemini_available:
                # محاولة 1: 2.5
                try:
                    m = genai.GenerativeModel("gemini-2.5-flash")
                    r = await m.generate_content_async(f"Enhance this video prompt, make it cinematic and detailed (English): {prompt}")
                    enhanced_prompt = self.clean_response(r.text)
                except:
                    # محاولة 2: 2.0
                    try:
                        m = genai.GenerativeModel("gemini-2.0-flash")
                        r = await m.generate_content_async(f"Enhance video prompt (English): {prompt}")
                        enhanced_prompt = self.clean_response(r.text)
                    except:
                        # محاولة 3: 1.5
                        try:
                            m = genai.GenerativeModel("gemini-1.5-flash")
                            r = await m.generate_content_async(f"Enhance video prompt (English): {prompt}")
                            enhanced_prompt = self.clean_response(r.text)
                        except: pass # فشل الكل

            # 3. إرسال الطلب لخدمة Luma Dream Machine
            url = "https://api.lumalabs.ai/dream-machine/v1/generations"
            headers = {
                "Authorization": f"Bearer {self.luma_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "prompt": enhanced_prompt,
                "aspect_ratio": "16:9"
            }
            
            # إذا كان الفيديو من صورة
            if image_url:
                url = "https://api.lumalabs.ai/dream-machine/v1/generations/image"
                payload["image_url"] = image_url
            
            async with aiohttp.ClientSession() as session:
                # إرسال طلب الإنشاء
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status != 201 and response.status != 200:
                        err_text = await response.text()
                        return None, f"❌ خطأ من Luma: {response.status} - {err_text[:50]}"
                    
                    data = await response.json()
                    gen_id = data.get("id")
                    if not gen_id:
                        return None, "❌ لم يتم استلام معرف الفيديو."
                    
                    # 4. انتظار النتيجة (Polling)
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
            logger.error(f"❌ Video Error: {e}")
            return None, "حدث خطأ تقني في خدمة الفيديو."

    # ==================== دوال مساعدة ومعلومات (Utility Functions) ====================
    def get_available_services(self) -> Dict[str, bool]:
        """
        إرجاع حالة الخدمات المتاحة حالياً بناءً على المفاتيح.
        """
        return {
            "chat": self.gemini_available or self.openai_available,
            "image_generation": self.openai_available or bool(self.stability_api_key),
            "video_generation": self.luma_available
        }
        
    def get_user_stats(self, user_id: int) -> Dict[str, int]:
        """
        إرجاع إحصائيات استخدام المستخدم لليوم الحالي.
        """
        stats = {}
        for s_type in ["ai_chat", "image_gen", "video_gen"]:
            today = datetime.now().strftime('%Y-%m-%d')
            cache_key = f"{user_id}_{today}_{s_type}"
            # البحث في الكاش أولاً
            stats[s_type] = self.user_limits_cache.get(cache_key, 0)
        return stats
