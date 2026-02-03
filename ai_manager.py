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
            
            # استخدام الكاش إذا كان موجوداً
            if cache_key in self.user_limits_cache:
                current_usage = self.user_limits_cache[cache_key]
            else:
                # جلب من قاعدة البيانات
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                    SELECT usage_count FROM ai_usage 
                    WHERE user_id = ? AND service_type = ? AND usage_date = ?
                    ''', (user_id, service_type, today))
                    
                    result = cursor.fetchone()
                    current_usage = result[0] if result else 0
                    self.user_limits_cache[cache_key] = current_usage
            
            # تحديد الحدود من البيئة
            limits_config = {
                "ai_chat": int(os.getenv("DAILY_AI_LIMIT", "20")),
                "image_gen": int(os.getenv("DAILY_IMAGE_LIMIT", "5")),
                "video_gen": int(os.getenv("DAILY_VIDEO_LIMIT", "2"))
            }
            
            limit = limits_config.get(service_type, 20)
            remaining = limit - current_usage
            
            if current_usage >= limit:
                return False, 0  # تجاوز الحد
            return True, remaining  # ما زال متبقي
            
        except Exception as e:
            logger.error(f"❌ Error checking user limit: {e}")
            return True, 999  # السماح في حالة الخطأ
    
    def update_user_usage(self, user_id: int, service_type: str = "ai_chat") -> bool:
        """تحديث استخدام المستخدم"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            cache_key = f"{user_id}_{today}_{service_type}"
            
            # تحديث الكاش
            current_usage = self.user_limits_cache.get(cache_key, 0)
            self.user_limits_cache[cache_key] = current_usage + 1
            
            # تحديث قاعدة البيانات
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                INSERT INTO ai_usage (user_id, service_type, usage_date, usage_count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(user_id, service_type, usage_date) 
                DO UPDATE SET usage_count = usage_count + 1
                ''', (user_id, service_type, today))
                
                conn.commit()
                logger.debug(f"✅ Updated usage for user {user_id}, service {service_type}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error updating user usage: {e}")
            return False
    
    # ==================== نظام المحادثة ====================
    
    def get_conversation_history(self, user_id: int) -> List[Dict[str, str]]:
        """الحصول على تاريخ محادثة المستخدم"""
        try:
            if user_id not in self.conversation_history:
                # جلب آخر المحادثات من قاعدة البيانات
                conversations = self.db.get_user_ai_conversations(user_id, limit=self.max_history_length)
                
                # تحويل إلى تنسيق مناسب للـ API
                history = []
                for conv in conversations:
                    history.append({"role": "user", "content": conv['user_message']})
                    history.append({"role": "assistant", "content": conv['ai_response']})
                
                # عكس القائمة للحصول على التسلسل الزمني الصحيح
                history.reverse()
                self.conversation_history[user_id] = history[-self.max_history_length*2:]  # حفظ في الكاش
            return self.conversation_history.get(user_id, [])
            
        except Exception as e:
            logger.error(f"❌ Error getting conversation history: {e}")
            return []
    
    def update_conversation_history(self, user_id: int, user_message: str, ai_response: str):
        """تحديث تاريخ المحادثة"""
        try:
            if user_id not in self.conversation_history:
                self.conversation_history[user_id] = []
            
            # إضافة المحادثة الجديدة
            self.conversation_history[user_id].append({"role": "user", "content": user_message})
            self.conversation_history[user_id].append({"role": "assistant", "content": ai_response})
            
            # الحفاظ على الطول المحدد
            if len(self.conversation_history[user_id]) > self.max_history_length * 2:
                self.conversation_history[user_id] = self.conversation_history[user_id][-self.max_history_length*2:]
                
        except Exception as e:
            logger.error(f"❌ Error updating conversation history: {e}")
    
    # ==================== خدمة المحادثة ====================
    
    async def chat_with_ai(self, user_id: int, message: str, use_gemini: bool = True) -> str:
        """دردشة مع الذكاء الاصطناعي"""
        try:
            # التحقق من الحدود
            allowed, remaining = self.check_user_limit(user_id, "ai_chat")
            if not allowed:
                return f"❌ لقد استخدمت جميع رسائل المحادثة اليومية ({remaining} رسالة).\n🔄 يتم تجديد الحدود تلقائياً بعد منتصف الليل (توقيت UTC)."
            
            # جلب تاريخ المحادثة
            conversation_history = self.get_conversation_history(user_id)
            
            # اختيار النموذج المناسب
            if use_gemini and self.gemini_available:
                response = await self._chat_with_gemini(message, conversation_history)
            elif self.openai_available:
                response = await self._chat_with_openai(message, conversation_history)
            else:
                return "❌ خدمة الدردشة غير متاحة حالياً. يرجى المحاولة لاحقاً أو التحقق من /status."
            
            # تحديث الاستخدام
            self.update_user_usage(user_id, "ai_chat")
            
            # تحديث تاريخ المحادثة
            self.update_conversation_history(user_id, message, response)
            
            # حفظ المحادثة في قاعدة البيانات
            self.db.save_ai_conversation(user_id, "chat", message, response)
            
            logger.info(f"✅ AI chat completed for user {user_id}")
            return response
            
        except Exception as e:
            logger.error(f"❌ Error in AI chat: {e}")
            return "⚠️ حدث خطأ أثناء معالجة طلبك. يرجى المحاولة مرة أخرى أو الاتصال بالدعم إذا استمرت المشكلة."
    
    async def _chat_with_gemini(self, message: str, history: List[Dict]) -> str:
        """استخدام Google Gemini للدردشة"""
        try:
            model_name = os.getenv("GEMINI_MODEL", "gemini-pro")
            model = genai.GenerativeModel(model_name)
            
            # بناء السياق من التاريخ
            context_parts = []
            
            # إضافة تعليمات النظام
            system_prompt = """أنت مساعد ذكي ودود يتحدث العربية بطلاقة. يجب أن:
            1. تكون مفيداً ومباشراً في الإجابات
            2. تستخدم لغة عربية سليمة وواضحة
            3. تعترف عندما لا تعرف الإجابة
            4. تكون محايداً ودوداً في جميع الأوقات
            5. تقدم إجابات دقيقة وموثوقة
            
            الإجابة بالعربية ما لم يطلب المستخدم خلاف ذلك."""
            
            context_parts.append(system_prompt)
            
            # إضافة تاريخ المحادثة
            for msg in history[-6:]:  # آخر 3 تبادلات فقط
                role = "المستخدم" if msg["role"] == "user" else "المساعد"
                context_parts.append(f"{role}: {msg['content']}")
            
            # إضافة الرسالة الحالية
            context_parts.append(f"المستخدم: {message}")
            context_parts.append("المساعد:")
            
            full_prompt = "\n\n".join(context_parts)
            
            # توليد الرد
            response = model.generate_content(
                full_prompt,
                generation_config={
                    "temperature": 0.7,
                    "top_p": 0.8,
                    "top_k": 40,
                    "max_output_tokens": 1024,
                }
            )
            
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"❌ Gemini chat error: {e}")
            raise
    
    async def _chat_with_openai(self, message: str, history: List[Dict]) -> str:
        """استخدام OpenAI GPT للدردشة"""
        try:
            client = openai.OpenAI()
            
            messages = []
            
            # إضافة رسالة النظام
            messages.append({
                "role": "system",
                "content": "أنت مساعد ذكي يتحدث العربية بطلاقة. كن مفيداً، دقيقاً، وودوداً. استخدم لغة عربية سليمة."
            })
            
            # إضافة تاريخ المحادثة
            for msg in history[-8:]:  # آخر 4 تبادلات
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # إضافة رسالة المستخدم الحالية
            messages.append({
                "role": "user",
                "content": message
            })
            
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview"),
                messages=messages,
                temperature=0.7,
                max_tokens=1000,
                top_p=0.9
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"❌ OpenAI chat error: {e}")
            raise
    
    # ==================== خدمة إنشاء الصور ====================
    
    async def generate_image(self, user_id: int, prompt: str, style: str = "realistic") -> Tuple[Optional[str], str]:
        """إنشاء صور باستخدام الذكاء الاصطناعي"""
        try:
            # التحقق من الحدود
            allowed, remaining = self.check_user_limit(user_id, "image_gen")
            if not allowed:
                return None, f"❌ لقد استخدمت جميع محاولات إنشاء الصور اليومية ({remaining} صورة).\n🔄 يتم تجديد الحدود تلقائياً بعد منتصف الليل."
            
            # تحسين الوصف
            enhanced_prompt = await self._enhance_image_prompt(prompt, style)
            
            image_url = None
            error_message = None
            
            # المحاولة 1: استخدام DALL-E إذا كان متاحاً
            if self.openai_available:
                try:
                    image_url = await self._generate_with_dalle(enhanced_prompt)
                    if image_url:
                        logger.info(f"✅ Image generated with DALL-E for user {user_id}")
                except Exception as e:
                    logger.warning(f"⚠️ DALL-E failed: {e}")
            
            # المحاولة 2: استخدام Stable Diffusion
            if not image_url and self.stability_api_key:
                try:
                    image_url = await self._generate_with_stable_diffusion(enhanced_prompt)
                    if image_url:
                        logger.info(f"✅ Image generated with Stable Diffusion for user {user_id}")
                except Exception as e:
                    logger.warning(f"⚠️ Stable Diffusion failed: {e}")
            
            # المحاولة 3: استخدام Gemini إذا كان يدعم إنشاء الصور
            if not image_url and self.gemini_available:
                try:
                    image_url = await self._generate_with_gemini(enhanced_prompt)
                    if image_url:
                        logger.info(f"✅ Image generated with Gemini for user {user_id}")
                except Exception as e:
                    logger.warning(f"⚠️ Gemini image generation failed: {e}")
            
            if image_url:
                # تحديث الاستخدام
                self.update_user_usage(user_id, "image_gen")
                
                # حفظ الملف في قاعدة البيانات
                file_id = self.db.save_generated_file(user_id, "image", prompt, image_url)
                if file_id:
                    logger.info(f"✅ Image saved to database with ID {file_id}")
                
                return image_url, "✅ تم إنشاء صورتك بنجاح!"
            else:
                error_message = "❌ فشل في إنشاء الصورة. الخدمة قد تكون مشغولة أو غير متاحة."
                if not self.openai_available and not self.stability_api_key:
                    error_message += "\n⚠️ مفتاح API لإنشاء الصور غير مضبوط."
                
                return None, error_message
            
        except Exception as e:
            logger.error(f"❌ Error generating image: {e}")
            return None, "⚠️ حدث خطأ غير متوقع أثناء إنشاء الصورة. يرجى المحاولة مرة أخرى."
    
    async def _enhance_image_prompt(self, prompt: str, style: str) -> str:
        """تحسين وصف الصورة"""
        try:
            style_descriptions = {
                "realistic": "صورة فوتوغرافية واقعية عالية الجودة، تفاصيل دقيقة، إضاءة طبيعية",
                "anime": "أنمي ياباني، أسلوب رسوم متحركة، ألوان زاهية، عيون كبيرة وتعبيرات مبالغ فيها",
                "fantasy": "فنتازيا سحرية، ألوان دراماتيكية، إضاءة خلابة، جو أسطوري",
                "cyberpunk": "سيبربانك، مستقبلي تكنولوجي، أضواء نيون، أجواء حضرية مظلمة",
                "watercolor": "ألوان مائية، فرشاة فنية، انطباعية، ناعمة وتجريدية"
            }
            
            style_desc = style_descriptions.get(style, "صورة فنية عالية الجودة")
            
            enhancement_prompt = f"""
            قم بتحسين وصف الصورة التالي لجعله مفصلاً ومناسباً لإنشاء صور ذكاء اصطناعي:
            
            الوصف الأصلي: {prompt}
            النمط المطلوب: {style_desc}
            
            أضف تفاصيل عن:
            1. الإضاءة والظلال
            2. الألوان والأجواء
            3. التفاصيل والدقة
            4. التكوين والمنظور
            5. الجودة الفنية
            
            قدم الوصف باللغة الإنجليزية لتحسين النتائج.
            """
            
            if self.gemini_available:
                model = genai.GenerativeModel("gemini-pro")
                response = model.generate_content(enhancement_prompt)
                enhanced = response.text.strip()
            else:
                # وصف افتراضي إذا لم يكن Gemini متاحاً
                enhanced = f"{prompt}, {style_desc}, high quality, detailed, 4k, professional photography"
            
            # تنظيف النتيجة
            enhanced = enhanced.replace("باللغة الإنجليزية:", "").strip()
            return enhanced if enhanced else f"{prompt}, {style_desc}, high quality"
            
        except Exception as e:
            logger.error(f"❌ Error enhancing prompt: {e}")
            return f"{prompt}, {style_desc}, high quality"
    
    async def _generate_with_dalle(self, prompt: str) -> Optional[str]:
        """إنشاء صور باستخدام DALL-E"""
        try:
            client = openai.OpenAI()
            
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=os.getenv("IMAGE_SIZE", "1024x1024"),
                quality=os.getenv("IMAGE_QUALITY", "standard"),
                n=1,
                style="vivid"  # أو "natural"
            )
            
            return response.data[0].url
            
        except Exception as e:
            logger.error(f"❌ DALL-E generation error: {e}")
            return None
    
    async def _generate_with_stable_diffusion(self, prompt: str) -> Optional[str]:
        """إنشاء صور باستخدام Stable Diffusion"""
        try:
            headers = {
                "Authorization": f"Bearer {self.stability_api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "text_prompts": [{"text": prompt, "weight": 1}],
                "cfg_scale": 7,
                "height": 512,
                "width": 512,
                "samples": 1,
                "steps": 30,
                "style_preset": "photographic"  # أو "digital-art", "fantasy-art", etc.
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.stable_diffusion_url,
                    headers=headers,
                    json=data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if "artifacts" in result and result["artifacts"]:
                            # تحويل base64 إلى رابط (في حالة حقيقية، تحتاج إلى رفع الصورة)
                            image_base64 = result["artifacts"][0]["base64"]
                            # هنا يمكنك رفع الصورة إلى خدمة استضافة
                            # للمثال، نعيد رابط وهمي
                            return f"https://example.com/generated-image-{hash(prompt)}.png"
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Stable Diffusion error: {e}")
            return None
    
    async def _generate_with_gemini(self, prompt: str) -> Optional[str]:
        """محاولة إنشاء صور باستخدام Gemini (إذا كان يدعم)"""
        # ملاحظة: Gemini لا يدعم إنشاء الصور مباشرة في وقت كتابة هذا الكود
        # هذه الدالة للتوافق المستقبلي
        return None
    
    # ==================== خدمة إنشاء الفيديوهات ====================
    
    async def generate_video(self, user_id: int, prompt: str, image_url: str = None) -> Tuple[Optional[str], str]:
        """إنشاء فيديو من النص أو الصورة باستخدام Luma AI"""
        try:
            # التحقق من الحدود
            allowed, remaining = self.check_user_limit(user_id, "video_gen")
            if not allowed:
                return None, f"❌ لقد استخدمت جميع محاولات إنشاء الفيديوهات اليومية ({remaining} فيديو).\n🔄 يتم تجديد الحدود تلقائياً بعد منتصف الليل."
            
            if not self.luma_available:
                return None, "❌ خدمة إنشاء الفيديوهات غير متاحة حالياً. يرجى التحقق من إعدادات API."
            
            video_url = None
            
            if image_url:
                # إنشاء فيديو من صورة
                video_url = await self._generate_video_from_image(prompt, image_url)
            else:
                # إنشاء فيديو من نص
                video_url = await self._generate_video_from_text(prompt)
            
            if video_url:
                # تحديث الاستخدام
                self.update_user_usage(user_id, "video_gen")
                
                # حفظ الملف في قاعدة البيانات
                file_id = self.db.save_generated_file(user_id, "video", prompt, video_url)
                if file_id:
                    logger.info(f"✅ Video saved to database with ID {file_id}")
                
                return video_url, "✅ تم إنشاء الفيديو بنجاح! قد يستغرق التجهيز بضع دقائق."
            else:
                return None, "❌ فشل في إنشاء الفيديو. الخدمة قد تكون مشغولة. يرجى المحاولة مرة أخرى لاحقاً."
            
        except Exception as e:
            logger.error(f"❌ Error generating video: {e}")
            return None, "⚠️ حدث خطأ أثناء إنشاء الفيديو. يرجى المحاولة مرة أخرى."
    
    async def _generate_video_from_text(self, prompt: str) -> Optional[str]:
        """إنشاء فيديو من النص باستخدام Luma AI"""
        try:
            headers = {
                "Authorization": f"Bearer {self.luma_api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            # تحسين الوصف للفيديو
            video_prompt = await self._enhance_video_prompt(prompt)
            
            data = {
                "prompt": video_prompt,
                "aspect_ratio": "16:9",
                "duration": 5,
                "prompt_negative": "blurry, low quality, distorted, ugly, text, watermark"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.lumalabs.ai/dream-machine/v1/generations",
                    headers=headers,
                    json=data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        generation_id = result.get("id")
                        
                        if generation_id:
                            # الانتظار حتى يكتمل التوليد
                            video_url = await self._check_luma_generation_status(generation_id)
                            return video_url
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Luma AI text-to-video error: {e}")
            return None
    
    async def _generate_video_from_image(self, prompt: str, image_url: str) -> Optional[str]:
        """إنشاء فيديو من صورة باستخدام Luma AI"""
        try:
            headers = {
                "Authorization": f"Bearer {self.luma_api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            # تحسين الوصف
            video_prompt = await self._enhance_video_prompt(prompt)
            
            data = {
                "prompt": video_prompt,
                "image_url": image_url,
                "aspect_ratio": "16:9",
                "duration": 5
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.lumalabs.ai/dream-machine/v1/generations/image",
                    headers=headers,
                    json=data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        generation_id = result.get("id")
                        
                        if generation_id:
                            video_url = await self._check_luma_generation_status(generation_id)
                            return video_url
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Luma AI image-to-video error: {e}")
            return None
    
    async def _enhance_video_prompt(self, prompt: str) -> str:
        """تحسين وصف الفيديو"""
        try:
            enhancement_prompt = f"""
            قم بتحسين وصف الفيديو التالي لجعله مفصلاً ومناسباً لإنشاء فيديو ذكاء اصطناعي:
            
            الوصف الأصلي: {prompt}
            
            أضف تفاصيل عن:
            1. الحركة والديناميكية
            2. الإضاءة والتأثيرات البصرية
            3. الأجواء والمزاج
            4. الجودة السينمائية
            
            قدم الوصف باللغة الإنجليزية لتحسين النتائج.
            """
            
            if self.gemini_available:
                model = genai.GenerativeModel("gemini-pro")
                response = model.generate_content(enhancement_prompt)
                enhanced = response.text.strip()
            else:
                enhanced = f"{prompt}, cinematic, high quality, smooth motion, dynamic"
            
            return enhanced if enhanced else f"{prompt}, cinematic video"
            
        except Exception as e:
            logger.error(f"❌ Error enhancing video prompt: {e}")
            return f"{prompt}, cinematic video"
    
    async def _check_luma_generation_status(self, generation_id: str, max_attempts: int = 30) -> Optional[str]:
        """التحقق من حالة توليد Luma AI"""
        try:
            headers = {
                "Authorization": f"Bearer {self.luma_api_key}",
                "Accept": "application/json"
            }
            
            for attempt in range(max_attempts):
                await asyncio.sleep(10)  # انتظار 10 ثواني بين المحاولات
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"https://api.lumalabs.ai/dream-machine/v1/generations/{generation_id}",
                        headers=headers
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            status = result.get("status")
                            
                            if status == "completed":
                                video_url = result.get("video_url")
                                if video_url:
                                    logger.info(f"✅ Luma generation {generation_id} completed")
                                    return video_url
                            elif status == "failed":
                                error_msg = result.get("error", "Unknown error")
                                logger.error(f"❌ Luma generation {generation_id} failed: {error_msg}")
                                return None
                            elif status == "processing":
                                logger.info(f"⏳ Luma generation {generation_id} still processing (attempt {attempt + 1}/{max_attempts})")
                        else:
                            logger.error(f"❌ Status check failed for {generation_id}: {response.status}")
            
            logger.warning(f"⚠️ Luma generation {generation_id} timed out after {max_attempts} attempts")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error checking Luma status: {e}")
            return None
    
    # ==================== دوال المساعدة ====================
    
    def get_user_stats(self, user_id: int) -> Dict[str, int]:
        """الحصول على إحصائيات استخدام المستخدم"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT service_type, SUM(usage_count) as total
                FROM ai_usage 
                WHERE user_id = ? AND usage_date = ?
                GROUP BY service_type
                ''', (user_id, today))
                
                stats = {}
                for row in cursor.fetchall():
                    stats[row[0]] = row[1]
                
                # إضافة الحدود
                limits = {
                    "ai_chat": int(os.getenv("DAILY_AI_LIMIT", "20")),
                    "image_gen": int(os.getenv("DAILY_IMAGE_LIMIT", "5")),
                    "video_gen": int(os.getenv("DAILY_VIDEO_LIMIT", "2"))
                }
                
                # حساب المتبقي
                for service_type, limit in limits.items():
                    used = stats.get(service_type, 0)
                    stats[f"{service_type}_used"] = used
                    stats[f"{service_type}_remaining"] = max(0, limit - used)
                    stats[f"{service_type}_limit"] = limit
                
                return stats
                
        except Exception as e:
            logger.error(f"❌ Error getting user stats: {e}")
            return {}
    
    def get_available_services(self) -> Dict[str, bool]:
        """الحصول على الخدمات المتاحة"""
        return {
            "chat": self.gemini_available or self.openai_available,
            "image_generation": self.openai_available or bool(self.stability_api_key),
            "video_generation": self.luma_available
        }
    
    def get_service_status(self) -> Dict[str, Dict[str, Any]]:
        """الحصول على حالة الخدمات مفصلة"""
        return {
            "gemini": {
                "available": self.gemini_available,
                "models": ["gemini-pro", "gemini-pro-vision"] if self.gemini_available else []
            },
            "openai": {
                "available": self.openai_available,
                "models": ["gpt-4-turbo", "dall-e-3"] if self.openai_available else []
            },
            "luma_ai": {
                "available": self.luma_available,
                "service": "Dream Machine"
            },
            "stable_diffusion": {
                "available": bool(self.stability_api_key),
                "url": self.stable_diffusion_url if self.stability_api_key else None
            }
        }
    
    def reset_daily_limits(self):
        """إعادة تعيين كاش الحدود (يتم استدعاؤها يومياً)"""
        try:
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            # مسح الكاش للتاريخ القديم
            keys_to_remove = [k for k in self.user_limits_cache.keys() if yesterday in k]
            for key in keys_to_remove:
                del self.user_limits_cache[key]
            
            logger.info(f"🧹 Cleared cache for {len(keys_to_remove)} old entries")
            
        except Exception as e:
            logger.error(f"❌ Error resetting daily limits: {e}")
    
    def cleanup_old_conversations(self, max_age_days: int = 7):
        """تنظيف المحادثات القديمة من الكاش"""
        try:
            # هذا مثال بسيط، في التطبيق الحقيقي قد تحتاج إلى تتبع تواريخ المحادثات
            current_size = len(self.conversation_history)
            
            # مسح المحادثات الأقدم من X أيام (تنفيذ مبسط)
            if current_size > 100:  # إذا كان الكاش كبيراً جداً
                # حذف نصف المحادثات الأقل استخداماً
                keys = list(self.conversation_history.keys())
                keys_to_remove = keys[:len(keys)//2]
                
                for key in keys_to_remove:
                    del self.conversation_history[key]
                
                logger.info(f"🧹 Cleaned {len(keys_to_remove)} old conversations from cache")
                
        except Exception as e:
            logger.error(f"❌ Error cleaning old conversations: {e}")