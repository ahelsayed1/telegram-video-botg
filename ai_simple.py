# ai_simple.py - مدير الذكاء الاصطناعي المبسط (للشات فقط)
import os
import logging
import random
from typing import Optional, Tuple
import google.generativeai as genai
import openai

logger = logging.getLogger(__name__)

class SimpleAIManager:
    """مدير ذكاء اصطناعي مبسط للشات فقط"""
    
    def __init__(self, db):
        self.db = db
        self.setup_apis()
        self.conversation_memory = {}  # ذاكرة المحادثات المؤقتة
        
    def setup_apis(self):
        """إعداد واجهات برمجة التطبيقات"""
        try:
            # إعداد Google Gemini
            google_api_key = os.getenv("GOOGLE_AI_API_KEY")
            if google_api_key:
                genai.configure(api_key=google_api_key)
                self.gemini_available = True
                logger.info("✅ Google Gemini API configured")
            else:
                self.gemini_available = False
                logger.warning("⚠️ Google Gemini API key not found")
            
            # إعداد OpenAI
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if openai_api_key:
                openai.api_key = openai_api_key
                self.openai_available = True
                logger.info("✅ OpenAI API configured")
            else:
                self.openai_available = False
                logger.warning("⚠️ OpenAI API key not found")
                
        except Exception as e:
            logger.error(f"❌ Failed to setup AI APIs: {e}")
            self.gemini_available = False
            self.openai_available = False
    
    def check_user_limit(self, user_id: int) -> Tuple[bool, int]:
        """التحقق من حدود استخدام المستخدم (نسخة مبسطة)"""
        try:
            # حد افتراضي: 50 رسالة يومياً
            daily_limit = int(os.getenv("DAILY_CHAT_LIMIT", "50"))
            
            # في هذه النسخة المبسطة، نستخدم ذاكرة مؤقتة
            if user_id not in self.conversation_memory:
                self.conversation_memory[user_id] = {
                    'count': 0,
                    'last_reset': None
                }
            
            # إذا مر يوم، نعيد العداد
            current_count = self.conversation_memory[user_id]['count']
            
            if current_count >= daily_limit:
                return False, 0  # تجاوز الحد
            
            return True, daily_limit - current_count  # ما زال متبقي
            
        except Exception as e:
            logger.error(f"❌ Error checking user limit: {e}")
            return True, 999  # السماح في حالة الخطأ
    
    def update_user_usage(self, user_id: int):
        """تحديث استخدام المستخدم (نسخة مبسطة)"""
        try:
            if user_id not in self.conversation_memory:
                self.conversation_memory[user_id] = {
                    'count': 1,
                    'last_reset': None
                }
            else:
                self.conversation_memory[user_id]['count'] += 1
                
            logger.debug(f"✅ Updated chat usage for user {user_id}")
            return True
                
        except Exception as e:
            logger.error(f"❌ Error updating user usage: {e}")
            return False
    
    def get_conversation_history(self, user_id: int):
        """الحصول على تاريخ محادثة المستخدم (نسخة مبسطة)"""
        # في النسخة المبسطة، نستخدم كاش بسيط
        # في النسخة الكاملة، سيتم تخزينها في قاعدة البيانات
        return []
    
    async def chat(self, user_id: int, message: str) -> str:
        """محادثة مع الذكاء الاصطناعي"""
        try:
            # التحقق من الحدود
            allowed, remaining = self.check_user_limit(user_id)
            if not allowed:
                return f"❌ لقد استخدمت جميع رسائل المحادثة اليومية.\n🔄 يتم تجديد الحدود تلقائياً بعد منتصف الليل."
            
            # الاختيار: استخدام Gemini أو OpenAI أو الردود المسبقة
            if self.gemini_available:
                response = await self._chat_with_gemini(message)
            elif self.openai_available:
                response = await self._chat_with_openai(message)
            else:
                response = await self._fallback_chat(message)
            
            # تحديث الاستخدام
            self.update_user_usage(user_id)
            
            # تسجيل المحادثة (مبسط)
            self._log_conversation(user_id, message, response)
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Error in AI chat: {e}")
            return await self._fallback_chat(message)
    
    async def _chat_with_gemini(self, message: str) -> str:
        """استخدام Google Gemini للدردشة"""
        try:
            model_name = os.getenv("GEMINI_MODEL", "gemini-pro")
            model = genai.GenerativeModel(model_name)
            
            # إضافة تعليمات للنموذج
            prompt = f"""أنت مساعد ذكي ودود يتحدث العربية بطلاقة.
            كن مفيداً، دقيقاً، وودوداً في إجاباتك.
            استخدم لغة عربية سليمة وواضحة.
            
            سؤال المستخدم: {message}
            
            الرد:"""
            
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.7,
                    "max_output_tokens": 1000,
                }
            )
            
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"❌ Gemini chat error: {e}")
            raise
    
    async def _chat_with_openai(self, message: str) -> str:
        """استخدام OpenAI GPT للدردشة"""
        try:
            client = openai.OpenAI()
            
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview"),
                messages=[
                    {"role": "system", "content": "أنت مساعد ذكي يتحدث العربية بطلاقة. كن مفيداً ودوداً."},
                    {"role": "user", "content": message}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"❌ OpenAI chat error: {e}")
            raise
    
    async def _fallback_chat(self, message: str) -> str:
        """ردود مسبقة التحضير عندما لا تكون APIs متاحة"""
        # تحليل الرسالة لتحديد الرد المناسب
        message_lower = message.lower()
        
        # قائمة بالردود الذكية
        responses = [
            "مرحباً! 👋 أنا المساعد الذكي. يمكنني الإجابة على أسئلتك ومساعدتك في مختلف المواضيع.",
            "أهلاً وسهلاً! 😊 أنا هنا لمساعدتك. ما الذي تريد أن تعرفه؟",
            "مرحباً بك! 🤖 أنا بوت الذكاء الاصطناعي. يمكنني مساعدتك في:\n• الإجابة على الأسئلة\n• تقديم النصائح\n• شرح المفاهيم\n• وغيرها الكثير!",
            "أهلًا! 💭 سعيد بتواصلك معي. يمكنك سؤالي عن أي شيء وسأحاول مساعدتك بأفضل ما لدي.",
            "مرحباً! 🚀 أنا المساعد الذكي للبوت. حاليًا أعمل في النسخة التجريبية، وسيتم إضافة المزيد من المميزات قريباً.",
        ]
        
        # ردود خاصة بناءً على محتوى الرسالة
        if any(word in message_lower for word in ["مرحبا", "اهلا", "السلام", "هلا"]):
            return "وعليكم السلام! 🌟 أهلاً وسهلاً بك. كيف يمكنني مساعدتك اليوم؟"
        
        elif any(word in message_lower for word in ["شكرا", "مشكور", "تسلم"]):
            return "العفو! 😊 سعيد لأنني استطعت المساعدة. هل هناك أي شيء آخر تحتاج إليه؟"
        
        elif any(word in message_lower for word in ["اسمك", "من انت", "ما أنت"]):
            return "أنا المساعد الذكي لـ بوت تليجرام! 🤖\nتم تطويري باستخدام تقنيات الذكاء الاصطناعي المتقدمة لأكون عوناً لك في مختلف المجالات."
        
        elif any(word in message_lower for word in ["مساعدة", "help", "مساعده"]):
            return "يمكنني مساعدتك في:\n\n💬 **المحادثات الذكية**\n📚 **الإجابة على الأسئلة**\n💡 **تقديم النصائح**\n🔍 **شرح المفاهيم**\n\nما الذي تريد معرفته؟"
        
        elif "؟" in message or "?" in message:
            # إذا كانت الرسالة تحتوي على سؤال
            question_responses = [
                f"سؤال ممتاز! 🤔 فيما يتعلق بـ '{message[:30]}...'، يمكنني القول أن هذا الموضوع مثير للاهتمام وسأحاول تقديم أفضل إجابة ممكنة.",
                f"أفهم سؤالك حول '{message[:20]}'، وسأبذل قصارى جهدي للإجابة بدقة ووضوح.",
                f"شكراً للسؤال! 💡 سأحتاج إلى مزيد من التفاصيل حول '{message[:25]}' لأتمكن من تقديم إجابة شاملة.",
            ]
            return random.choice(question_responses)
        
        # رد عشوائي من القائمة العامة
        return random.choice(responses)
    
    def _log_conversation(self, user_id: int, user_message: str, ai_response: str):
        """تسجيل المحادثة (نسخة مبسطة)"""
        try:
            logger.info(f"💬 Chat log - User {user_id}: {user_message[:50]}... -> AI: {ai_response[:50]}...")
        except Exception as e:
            logger.error(f"❌ Error logging conversation: {e}")
    
    def get_status(self) -> dict:
        """الحصول على حالة خدمات الذكاء الاصطناعي"""
        return {
            'chat_available': True,
            'gemini_available': self.gemini_available,
            'openai_available': self.openai_available,
            'apis_configured': self.gemini_available or self.openai_available,
            'fallback_mode': not (self.gemini_available or self.openai_available)
        }
    
    def get_user_stats(self, user_id: int) -> dict:
        """الحصول على إحصائيات استخدام المستخدم (نسخة مبسطة)"""
        try:
            if user_id in self.conversation_memory:
                used = self.conversation_memory[user_id]['count']
            else:
                used = 0
            
            daily_limit = int(os.getenv("DAILY_CHAT_LIMIT", "50"))
            remaining = max(0, daily_limit - used)
            
            return {
                'chats_used': used,
                'chats_remaining': remaining,
                'daily_limit': daily_limit,
                'percentage': (used / daily_limit * 100) if daily_limit > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting user stats: {e}")
            return {'chats_used': 0, 'chats_remaining': 50, 'daily_limit': 50}
    
    def cleanup_old_data(self):
        """تنظيف البيانات القديمة من الذاكرة المؤقتة"""
        try:
            # في النسخة المبسطة، نمسح فقط إذا كان هناك أكثر من 1000 مستخدم في الذاكرة
            if len(self.conversation_memory) > 1000:
                # نمسح نصف البيانات الأقل استخداماً
                items = list(self.conversation_memory.items())
                items.sort(key=lambda x: x[1]['count'])
                
                for user_id, _ in items[:len(items)//2]:
                    del self.conversation_memory[user_id]
                
                logger.info(f"🧹 Cleaned {len(items)//2} old entries from conversation memory")
                
        except Exception as e:
            logger.error(f"❌ Error cleaning old data: {e}")
