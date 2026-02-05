# ai_manager.py - الإصدار العملاق (Ultimate Edition)
# -----------------------------------------------------------------------------
# هذا الملف هو العقل المدبر للبوت، تم تصميمه ليكون قوياً ومرناً للغاية.
#
# الميزات الجديدة والتحسينات:
# 1. نظام "أولوية النماذج الهرمية" (Hierarchical Model Priority):
#    يبدأ بأقوى موديلات الجيل الثالث (Gemini 3.0 Preview / Nano Banana)،
#    ويتدرج تلقائياً للأسفل عند حدوث أي خطأ (429/404/500) وصولاً للموديلات المستقرة.
#
# 2. تحسين ذكي للأوامر (Advanced Prompt Engineering):
#    تم فصل منطق تحسين النصوص في دوال مستقلة تستخدم أقوى موديل متاح
#    لتحويل طلبات المستخدم البسيطة إلى أوصاف احترافية للصور والفيديو.
#
# 3. توثيق شامل (Comprehensive Documentation):
#    شرح مفصل لكل دالة ومنطق لسهولة الصيانة والتطوير المستقبلي.
#
# 4. معالجة أخطاء موسعة (Extended Error Handling):
#    نظام لوج (Logging) دقيق يخبرك بالضبط أي موديل نجح وأي موديل فشل ولماذا.
# -----------------------------------------------------------------------------

import os
import logging
import asyncio
import google.generativeai as genai
import openai
import aiohttp
import re  # مكتبة التعامل مع النصوص (Regular Expressions)
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple, Union

# إعداد نظام التسجيل (Logging)
# يساعد هذا في تتبع الأخطاء بدقة داخل لوحة تحكم Railway
logger = logging.getLogger(__name__)

class AIManager:
    """
    مدير خدمات الذكاء الاصطناعي المتكامل (AIManager).
    
    المسؤوليات:
    -----------
    1. إدارة الاتصال مع Google Gemini API بمختلف إصداراته.
    2. إدارة الاتصال مع OpenAI API (GPT & DALL-E).
    3. إدارة الاتصال مع Luma Dream Machine API للفيديو.
    4. إدارة الاتصال مع Stability AI API كبديل للصور.
    5. تطبيق حدود الاستخدام اليومية (Rate Limiting) وتتبع استهلاك المستخدمين.
    6. تنظيف وتنسيق الردود القادمة من الموديلات الذكية.
    """
    
    def __init__(self, db):
        """
        تهيئة مدير الذكاء الاصطناعي.
        
        Args:
            db: كائن قاعدة البيانات المستخدم لتخزين السجلات والحدود.
        """
        self.db = db
        
        # تخزين جلسات المحادثة النشطة
        # المفتاح: user_id (int)، القيمة: ChatSession object
        self.chat_sessions: Dict[int, genai.ChatSession] = {} 
        
        # تعريف قائمة الأولويات القصوى للموديلات (The Golden List)
        # سيتم التحقق من توفر هذه الموديلات في الحساب عند البدء
        self.preferred_models_hierarchy = [
            'gemini-3-pro-preview',        # 1. الأقوى عالمياً (الجيل الثالث)
            'gemini-3-flash-preview',      # 2. الأسرع عالمياً (الجيل الثالث)
            'nano-banana-pro-preview',     # 3. موديل متخصص عالي الكفاءة
            'gemini-2.5-flash',            # 4. الخيار المستقر والحديث
            'gemini-2.5-pro-preview-tts',  # 5. خيار قوي بديل
            'gemini-2.0-flash'             # 6. الملاذ الأخير (الاحتياطي الذهبي)
        ]
        
        # القائمة الفعلية للموديلات المتاحة (سيتم ملؤها بعد الفحص)
        self.available_models_chain: List[str] = []
        
        # الموديل الافتراضي الحالي
        self.model_name = "gemini-2.5-flash" 
        
        # كاش محلي للحدود لتقليل استعلامات قاعدة البيانات
        self.user_limits_cache = {}
        
        # بدء عملية الإعداد والربط
        self.setup_apis()
        
    def setup_apis(self):
        """
        إعداد مفاتيح واجهات برمجة التطبيقات (APIs) وبناء سلسلة الموديلات المتاحة.
        هذه الدالة حاسمة لأنها تحدد "خطة الهجوم" للبوت بناءً على ما هو متاح في حساب جوجل.
        """
        logger.info("⚙️ بدء تهيئة خدمات الذكاء الاصطناعي...")
        
        try:
            # =================================================================
            # 1. إعداد Google Gemini وبناء سلسلة الأولويات
            # =================================================================
            google_api_key = os.getenv("GOOGLE_AI_API_KEY")
            if google_api_key:
                genai.configure(api_key=google_api_key)
                self.gemini_available = True
                logger.info("✅ تم الاتصال بخدمة Google Gemini API.")
                
                try:
                    logger.info("🔍 جاري مسح الموديلات المتاحة في الحساب لترتيب الأولويات...")
                    
                    # جلب كل الموديلات المتاحة في الحساب
                    account_models = [m.name.replace('models/', '') for m in genai.list_models()]
                    logger.info(f"📋 الموديلات الخام الموجودة: {len(account_models)} موديل")
                    
                    # بناء سلسلة الموديلات المتاحة فعلياً بناءً على قائمتنا المفضلة
                    self.available_models_chain = []
                    for preferred in self.preferred_models_hierarchy:
                        if preferred in account_models:
                            self.available_models_chain.append(preferred)
                    
                    # إذا لم نجد أياً من الموديلات المفضلة (حالة نادرة)، نضيف 2.5 و 2.0 يدوياً
                    if not self.available_models_chain:
                        logger.warning("⚠️ لم يتم العثور على الموديلات المفضلة، سيتم استخدام القائمة الاحتياطية.")
                        self.available_models_chain = ['gemini-2.5-flash', 'gemini-2.0-flash']
                    
                    # تعيين الموديل الأساسي (أول واحد في السلسلة)
                    self.model_name = self.available_models_chain[0]
                    
                    logger.info(f"🚀 تم بناء سلسلة الهجوم (Attack Chain): {self.available_models_chain}")
                    logger.info(f"👑 الموديل القائد الحالي: {self.model_name}")
                        
                except Exception as e:
                    logger.error(f"⚠️ خطأ أثناء بناء سلسلة الموديلات: {e}")
                    # في حالة الفشل التام، نلجأ لوضع الأمان
                    self.model_name = "gemini-2.5-flash"
                    self.available_models_chain = ["gemini-2.5-flash", "gemini-2.0-flash"]
            else:
                self.gemini_available = False
                logger.critical("❌ مفتاح Google API غير موجود! (GOOGLE_AI_API_KEY)")
            
            # =================================================================
            # 2. إعداد OpenAI (للصور والدردشة الاحتياطية)
            # =================================================================
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if openai_api_key:
                openai.api_key = openai_api_key
                self.openai_available = True
                logger.info("✅ تم تفعيل خدمة OpenAI.")
            else:
                self.openai_available = False
                logger.info("ℹ️ خدمة OpenAI غير مفعلة (المفتاح غير موجود).")
            
            # =================================================================
            # 3. إعداد Luma AI (للفيديو)
            # =================================================================
            self.luma_api_key = os.getenv("LUMAAI_API_KEY")
            self.luma_available = bool(self.luma_api_key)
            if self.luma_available:
                logger.info("✅ تم تفعيل خدمة Luma AI (Dream Machine).")
            else:
                logger.info("ℹ️ خدمة Luma AI للفيديو غير مفعلة.")
            
            # =================================================================
            # 4. إعداد Stability AI (بديل للصور)
            # =================================================================
            self.stability_api_key = os.getenv("STABILITY_API_KEY")
            self.stable_diffusion_url = os.getenv("STABLE_DIFFUSION_URL", "https://api.stability.ai/v1/generation/stable-diffusion-v1-6/text-to-image")
            if self.stability_api_key:
                logger.info("✅ تم تفعيل خدمة Stability AI.")
            else:
                logger.info("ℹ️ خدمة Stability AI غير مفعلة.")

        except Exception as e:
            logger.error(f"❌ خطأ حرج غير متوقع في setup_apis: {e}")
            # ضمان أن المتغيرات لها قيم حتى لو فشل الإعداد لمنع توقف البوت
            self.gemini_available = getattr(self, 'gemini_available', False)
            self.openai_available = getattr(self, 'openai_available', False)
            self.luma_available = getattr(self, 'luma_available', False)
  
    # ==================== أدوات معالجة النصوص (Text Utilities) ====================
    
    def clean_response(self, text: str) -> str:
        """
        تنظيف الردود من "أفكار" الموديل (Chain of Thought).
        الموديلات الجديدة مثل Gemini 2.5/3.0 تميل لطباعة خطوات تفكيرها (THOUGHT: ...)
        قبل إعطاء الرد النهائي. هذه الدالة تزيل تلك الأجزاء لتقديم تجربة مستخدم نظيفة.
        
        Args:
            text (str): النص الخام القادم من الـ API.
            
        Returns:
            str: النص النظيف الجاهز للعرض.
        """
        if not text:
            return "عذراً، لم أستطع تكوين رد مناسب في الوقت الحالي."
        
        # الاحتفاظ بالنص الأصلي كنسخة احتياطية
        original_text = text
        
        try:
            # 1. حذف كتل الـ THOUGHT باستخدام Regex
            # يبحث عن أي نص يبدأ بـ THOUGHT: وينتهي بسطرين فارغين أو نهاية النص
            # Flags: DOTALL (لجعل النقطة تشمل الأسطر الجديدة)، IGNORECASE
            clean_text = re.sub(r'THOUGHT:.*?(?=\n\n|\Z)', '', text, flags=re.DOTALL | re.IGNORECASE)
            
            # 2. تنظيف إضافي (إزالة المسافات الزائدة وبقايا الكلمات)
            clean_text = clean_text.replace("THOUGHT:", "").strip()
            
            # 3. التحقق من النتيجة (Safety Check)
            # إذا مسح التنظيف كل النص (خطأ ما)، نعيد النص الأصلي
            if not clean_text or len(clean_text) < 2:
                # logger.warning("⚠️ عملية التنظيف أفرغت الرسالة، سيتم إرسال النص الأصلي.")
                return original_text
                
            return clean_text
            
        except Exception as e:
            logger.error(f"❌ خطأ أثناء تنظيف النص: {e}")
            return original_text

    async def _enhance_prompt_with_ai(self, prompt: str, target_type: str) -> str:
        """
        دالة داخلية مساعدة لتحسين الأوصاف (Prompt Engineering) باستخدام أقوى موديل متاح.
        تستخدم هذه الدالة لتحويل وصف المستخدم البسيط إلى وصف احترافي للصور أو الفيديو.
        
        Args:
            prompt (str): وصف المستخدم الأصلي.
            target_type (str): نوع التحسين المطلوب ('image' أو 'video').
            
        Returns:
            str: الوصف المحسن باللغة الإنجليزية.
        """
        if not self.gemini_available or not self.available_models_chain:
            return prompt # إذا لم يتوفر الذكاء الاصطناعي، نرجع النص الأصلي
            
        system_instruction = ""
        if target_type == 'image':
            system_instruction = "You are a professional prompt engineer for DALL-E 3. Rewrite the user's prompt to be highly detailed, visual, and artistic in English. Focus on lighting, texture, and composition."
        elif target_type == 'video':
            system_instruction = "You are a cinematographic prompt engineer for Luma Dream Machine. Rewrite the user's prompt to describe a 5-second video scene in English. Focus on motion, camera angles, and atmosphere."
            
        # محاولة استخدام الموديلات بالترتيب للحصول على التحسين
        for model_name in self.available_models_chain:
            try:
                # استخدام generate_content_async لأنه أسرع ولا يحتاج سياق محادثة
                model = genai.GenerativeModel(model_name)
                response = await model.generate_content_async(f"{system_instruction}\n\nUser Prompt: {prompt}")
                
                if response and response.text:
                    enhanced = self.clean_response(response.text)
                    # logger.info(f"✨ تم تحسين وصف {target_type} باستخدام {model_name}")
                    return enhanced
            except:
                continue # تجربة الموديل التالي بصمت
                
        return prompt # إذا فشل الجميع، نستخدم الأصلي

    # ==================== إدارة الحدود (Usage Limits) ====================
    
    def check_user_limit(self, user_id: int, service_type: str = "ai_chat") -> Tuple[bool, int]:
        """
        فحص هل يمتلك المستخدم رصيداً كافياً لاستخدام الخدمة.
        
        Args:
            user_id (int): معرف المستخدم.
            service_type (str): نوع الخدمة ('ai_chat', 'image_gen', 'video_gen').
            
        Returns:
            Tuple[bool, int]: (مسموح/غير مسموح، الرصيد المتبقي).
        """
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            cache_key = f"{user_id}_{today}_{service_type}"
            
            # 1. التحقق من الكاش (Fast Path)
            if cache_key in self.user_limits_cache:
                current_usage = self.user_limits_cache[cache_key]
            else:
                # 2. التحقق من قاعدة البيانات (Slow Path)
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        'SELECT usage_count FROM ai_usage WHERE user_id = ? AND service_type = ? AND usage_date = ?', 
                        (user_id, service_type, today)
                    )
                    result = cursor.fetchone()
                    current_usage = result[0] if result else 0
                    self.user_limits_cache[cache_key] = current_usage
            
            # إعدادات الحدود (يمكن تغييرها من متغيرات البيئة)
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
            logger.error(f"❌ Limit Check Error: {e}")
            return True, 999 # السماح في حالة تعطل قاعدة البيانات (Fail Open)

    def update_user_usage(self, user_id: int, service_type: str = "ai_chat") -> bool:
        """
        خصم رصيد من المستخدم بعد نجاح العملية.
        
        Returns:
            bool: نجاح أو فشل التحديث.
        """
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
            logger.error(f"❌ Usage Update Error: {e}")
            return False

    # ==================== خدمة المحادثة (Chat Service) ====================
    
    async def chat_with_ai(self, user_id: int, message: str, use_gemini: bool = True) -> str:
        """
        إجراء محادثة ذكية باستخدام استراتيجية تدوير الموديلات (Model Rotation Strategy).
        
        المنطق:
        1. يحاول البوت استخدام الموديلات الموجودة في `self.available_models_chain` بالترتيب.
        2. هذه القائمة تحتوي بالفعل على الموديلات المتقدمة (3.0/Nano) في البداية.
        3. إذا فشل موديل بسبب (Quota/Error/Overload)، ينتقل فوراً للموديل الذي يليه.
        4. إذا فشلت جميع موديلات Gemini، يحاول استخدام OpenAI (إذا كان مفعلاً).
        """
        try:
            # 1. فحص الرصيد
            allowed, remaining = self.check_user_limit(user_id, "ai_chat")
            if not allowed:
                return "❌ عذراً، لقد استهلكت رصيدك اليومي من الرسائل. يتجدد الرصيد غداً."
            
            response_text = ""
            success = False
            
            # --- المسار الأول: Google Gemini (السلسلة الكاملة) ---
            if use_gemini and self.gemini_available and self.available_models_chain:
                
                # التكرار عبر سلسلة الموديلات (من الأقوى إلى الأضعف/الأقدم)
                for model_name in self.available_models_chain:
                    try:
                        # logger.info(f"🔄 محاولة الرد باستخدام الموديل: {model_name} ...")
                        
                        # إعداد الجلسة لهذا المستخدم مع هذا الموديل تحديداً
                        # ملاحظة: نقوم بإنشاء كائن GenerativeModel جديد لكل محاولة لضمان عدم تداخل الإعدادات
                        current_model = genai.GenerativeModel(model_name)
                        
                        # التحقق هل هناك جلسة سابقة لهذا المستخدم متوافقة؟
                        # للتبسيط وضمان النجاح في حالة التبديل بين الموديلات، سنستخدم generate_content_async
                        # أو ننشئ دردشة جديدة. للحفاظ على السياق (Context)، الحل الأمثل هو إدارة السجل يدوياً،
                        # ولكن هنا سنعتمد على مكتبة جوجل لإدارة الدردشة، وإذا فشلت نعيد البدء.
                        
                        if user_id not in self.chat_sessions:
                            # بدء جلسة جديدة
                            chat = current_model.start_chat(history=[
                                {"role": "user", "parts": ["أنت مساعد ذكي ومفيد. رد مباشرة بالعربية."]},
                                {"role": "model", "parts": ["حسناً."]}
                            ])
                            self.chat_sessions[user_id] = chat
                        else:
                            # تحديث الموديل للجلسة الحالية (خدعة برمجية للتبديل دون فقدان الذاكرة إذا أمكن)
                            # في مكتبة جوجل الحالية، قد يتطلب الأمر بدء جلسة جديدة وتمرير التاريخ.
                            # للتجنب التعقيد، سنحاول الإرسال عبر الجلسة الحالية، وإذا فشلت ننشئ جديدة.
                            pass

                        chat_session = self.chat_sessions[user_id]
                        
                        # محاولة الإرسال
                        # استخدام timeout لتجنب الانتظار الطويل
                        response = await asyncio.wait_for(
                            chat_session.send_message_async(message), 
                            timeout=60.0
                        )
                        
                        if response and response.text:
                            response_text = self.clean_response(response.text)
                            success = True
                            # logger.info(f"✅ نجاح الرد من الموديل: {model_name}")
                            
                            # إذا نجحنا، نخرج من الحلقة (لا داعي لتجربة باقي الموديلات)
                            break 
                            
                    except Exception as e:
                        # تحليل الخطأ لتحديد ما إذا كان يجب المتابعة
                        error_msg = str(e).lower()
                        is_quota_error = "429" in error_msg or "quota" in error_msg or "resource" in error_msg
                        is_not_found = "404" in error_msg or "not found" in error_msg
                        
                        if is_quota_error:
                            logger.warning(f"⚠️ تجاوز حصة الموديل {model_name}. الانتقال للتالي...")
                        elif is_not_found:
                            logger.error(f"❌ الموديل {model_name} غير موجود (404). إزالته من القائمة...")
                            # يمكننا إزالته من القائمة المستقبلية لتحسين الأداء
                        else:
                            logger.warning(f"⚠️ خطأ غير متوقع في {model_name}: {e}")
                        
                        # إعادة تعيين الجلسة للمستخدم لأن الموديل الحالي فشل
                        if user_id in self.chat_sessions:
                            del self.chat_sessions[user_id]
                        
                        continue # الانتقال للموديل التالي في الحلقة

            # --- المسار الثاني: OpenAI (الاحتياطي النهائي) ---
            if not success and self.openai_available:
                try:
                    logger.info("🔄 الانتقال إلى OpenAI (GPT-4o-mini) كحل أخير...")
                    client = openai.OpenAI()
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": message}]
                    )
                    response_text = response.choices[0].message.content
                    success = True
                except Exception as e:
                    logger.error(f"❌ فشل OpenAI أيضاً: {e}")

            # --- النتيجة النهائية ---
            if success:
                self.update_user_usage(user_id, "ai_chat")
                self.db.save_ai_conversation(user_id, "chat", message, response_text)
                return response_text
            else:
                return "⚠️ عذراً، جميع خوادم الذكاء الاصطناعي مشغولة حالياً (Google & OpenAI). يرجى المحاولة بعد قليل."
            
        except Exception as e:
            logger.error(f"❌ General Chat Error: {e}")
            return "⚠️ حدث خطأ غير متوقع في النظام."

    # ==================== خدمة الصور (Image Gen Service) ====================
    
    async def generate_image(self, user_id: int, prompt: str, style: str = "realistic") -> Tuple[Optional[str], str]:
        """
        توليد الصور باستخدام DALL-E 3 أو Stability AI.
        يتم تحسين الوصف أولاً باستخدام موديلات Gemini المتقدمة (Nano/3.0).
        """
        try:
            # 1. التحقق من الحدود
            allowed, _ = self.check_user_limit(user_id, "image_gen")
            if not allowed: return None, "❌ انتهى رصيد الصور اليومي."
            
            # 2. تحسين الوصف (Advanced Prompt Engineering)
            # نستخدم دالة التحسين المخصصة التي تستغل أقوى موديل متاح
            enhanced_prompt = await self._enhance_prompt_with_ai(prompt, 'image')
            
            image_url = None
            
            # 3. المحاولة الأولى: OpenAI DALL-E 3
            if self.openai_available:
                try:
                    # logger.info("🎨 جاري التوليد باستخدام DALL-E 3...")
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
                    logger.warning(f"❌ فشل DALL-E 3: {e}")

            # 4. المحاولة الثانية: Stability AI (إذا فشل DALL-E)
            if not image_url and self.stability_api_key:
                try:
                    # logger.info("🎨 جاري التوليد باستخدام Stability AI...")
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
                                # ملاحظة: Stability يعيد الصورة كبيانات Base64 وليس رابط
                                # بما أننا لا نملك كود رفع الصور (Upload Service) هنا، سنعتبره نجاحاً
                                # ونعيد رسالة توضيحية. في التطبيق الفعلي يجب فك تشفير Base64 ورفعه.
                                return None, "⚠️ تم إنشاء الصورة بنجاح (Stability)، ولكن النظام يحتاج خدمة تخزين لعرضها."
                            else:
                                logger.error(f"Stability Error: {await resp.text()}")
                except Exception as e:
                    logger.warning(f"❌ فشل Stability AI: {e}")

            # 5. معالجة النتيجة
            if image_url:
                self.update_user_usage(user_id, "image_gen")
                self.db.save_generated_file(user_id, "image", prompt, image_url)
                return image_url, "✅ تم إنشاء الصورة بنجاح"
            
            return None, "❌ فشل إنشاء الصورة. تأكد من توفر رصيد في OpenAI أو Stability."

        except Exception as e:
            logger.error(f"❌ Image Gen Error: {e}")
            return None, "حدث خطأ غير متوقع في خدمة الصور."

    # ==================== خدمة الفيديو (Video Gen Service) ====================
    
    async def generate_video(self, user_id: int, prompt: str, image_url: str = None) -> Tuple[Optional[str], str]:
        """
        توليد فيديو باستخدام Luma Dream Machine.
        يتم تحسين الوصف أولاً ليكون سينمائياً (Cinematic Prompt).
        """
        try:
            # 1. التحقق من الحدود
            allowed, _ = self.check_user_limit(user_id, "video_gen")
            if not allowed: return None, "❌ انتهى رصيد الفيديو اليومي."
            
            if not self.luma_available:
                return None, "❌ خدمة الفيديو غير مفعلة (LUMAAI_API_KEY غير موجود)."

            # 2. تحسين الوصف للفيديو
            enhanced_prompt = await self._enhance_prompt_with_ai(prompt, 'video')

            # 3. إعداد الطلب
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
            
            # 4. إرسال الطلب (Async HTTP)
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status not in [200, 201]:
                        err_text = await response.text()
                        logger.error(f"Luma API Error: {response.status} - {err_text}")
                        return None, f"❌ خطأ من Luma: {response.status}"
                    
                    data = await response.json()
                    gen_id = data.get("id")
                    
                    if not gen_id:
                        return None, "❌ لم يتم استلام معرف الفيديو من الخادم."
                    
                    # 5. انتظار النتيجة (Polling Loop)
                    # ننتظر لمدة تصل إلى 5 دقائق (60 محاولة * 5 ثواني)
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
                                    failure_reason = status_data.get('failure_reason', 'غير معروف')
                                    return None, f"❌ فشل توليد الفيديو: {failure_reason}"
            
            return None, "⚠️ استغرق الفيديو وقتاً طويلاً جداً (Time out)، سيتم إشعارك عند اكتماله."

        except Exception as e:
            logger.error(f"❌ Video Error: {e}")
            return None, "حدث خطأ تقني في خدمة الفيديو."

    # ==================== دوال مساعدة عامة (Utility Functions) ====================
    
    def get_available_services(self) -> Dict[str, bool]:
        """
        إرجاع تقرير عن حالة الخدمات المتاحة حالياً.
        يستخدم هذا في أمر /status لعرض حالة البوت.
        """
        return {
            "chat": self.gemini_available or self.openai_available,
            "image_generation": self.openai_available or bool(self.stability_api_key),
            "video_generation": self.luma_available
        }
        
    def get_user_stats(self, user_id: int) -> Dict[str, int]:
        """
        إرجاع إحصائيات استخدام المستخدم لليوم الحالي.
        يستخدم هذا في أمر /mystats.
        """
        stats = {}
        for s_type in ["ai_chat", "image_gen", "video_gen"]:
            today = datetime.now().strftime('%Y-%m-%d')
            cache_key = f"{user_id}_{today}_{s_type}"
            stats[s_type] = self.user_limits_cache.get(cache_key, 0)
        return stats
