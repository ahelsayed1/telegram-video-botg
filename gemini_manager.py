# gemini_manager.py - مدير Gemini API البسيط
import os
import logging
import asyncio
import google.generativeai as genai

logger = logging.getLogger(__name__)

class GeminiManager:
    """مدير Gemini API"""
    
    def __init__(self):
        self.setup_gemini()
    
    def setup_gemini(self):
        """إعداد Gemini API"""
        try:
            api_key = os.getenv("GOOGLE_AI_API_KEY")
            
            if api_key and api_key.strip():
                genai.configure(api_key=api_key.strip())
                self.gemini_available = True
                logger.info("✅ Gemini API جاهز")
            else:
                self.gemini_available = False
                logger.warning("⚠️ مفتاح Gemini API غير موجود")
                
        except Exception as e:
            logger.error(f"❌ فشل إعداد Gemini: {e}")
            self.gemini_available = False
    
    async def chat(self, message: str) -> str:
        """محادثة مع Gemini AI"""
        if not self.gemini_available:
            return "❌ خدمة Gemini غير متاحة. يرجى التحقق من مفتاح API."
        
        try:
            # إنشاء النموذج
            model = genai.GenerativeModel('gemini-pro')
            
            # تعليمات النظام بالعربية
            system_prompt = """أنت مساعد ذكي ودود يتحدث العربية بطلاقة. 
            يجب أن:
            1. تكون مفيداً ودقيقاً في الإجابات
            2. تستخدم لغة عربية سليمة وواضحة
            3. تقدم معلومات موثوقة
            4. تعترف عندما لا تعرف الإجابة
            5. تكون محايداً وموضوعياً
            
            إجابتك بالعربية ما لم يطلب المستخدم خلاف ذلك."""
            
            # النص الكامل للمحادثة
            full_prompt = f"{system_prompt}\n\nالمستخدم يقول: {message}\n\nأنت تجيب:"
            
            # توليد الرد
            response = model.generate_content(
                full_prompt,
                generation_config={
                    'temperature': 0.7,
                    'top_p': 0.8,
                    'top_k': 40,
                    'max_output_tokens': 1500,
                }
            )
            
            return response.text
            
        except Exception as e:
            logger.error(f"❌ خطأ في Gemini: {e}")
            return f"⚠️ حدث خطأ: {str(e)[:100]}..."
    
    def get_status(self):
        """حالة الخدمة"""
        if self.gemini_available:
            return "✅ Gemini AI متصل وجاهز"
        else:
            return "❌ Gemini AI غير متوفر - تحقق من GOOGLE_AI_API_KEY"
