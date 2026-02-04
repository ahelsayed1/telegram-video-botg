# test_api.py
import os
from google import genai
from dotenv import load_dotenv

# تحميل المفتاح من ملف .env
load_dotenv()
api_key = os.getenv("GOOGLE_AI_API_KEY")

if not api_key:
    print("❌ خطأ: لم يتم العثور على مفتاح API في ملف .env")
    exit()

print(f"🔎 جاري فحص المفتاح: {api_key[:5]}... (مخفي)")

try:
    # الاتصال بجوجل باستخدام المكتبة الجديدة
    client = genai.Client(api_key=api_key)
    
    print("\n📋 جاري جلب قائمة الموديلات المتاحة لهذا المفتاح...")
    
    found_flash = False
    
    # عرض كل الموديلات
    for model in client.models.list():
        print(f"- {model.name}")
        if "gemini-1.5-flash" in model.name:
            found_flash = True
            
    print("\n" + "="*50)
    if found_flash:
        print("✅ موديل (gemini-1.5-flash) متاح ويعمل مع مفتاحك!")
        print("💡 المشكلة قد تكون في طريقة كتابة الاسم في الكود فقط.")
    else:
        print("❌ موديل (gemini-1.5-flash) غير موجود في القائمة!")
        print("⚠️ هذا المفتاح لا يملك صلاحية الوصول لهذا الموديل.")
        print("💡 الحل: أنشئ مفتاح API جديد من Google AI Studio.")
    print("="*50)

except Exception as e:
    print(f"\n❌ حدث خطأ أثناء الاتصال: {e}")
