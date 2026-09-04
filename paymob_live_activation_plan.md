# خطة عمل تفعيل مفاتيح Paymob Live (السعودية KSA) في مشروع `education-bot-node`

---

## 📌 1. الهدف من الخطة (Objective)
تحويل بوابة الدفع **Paymob** في مشروع `education-bot-node` من البيئة التجريبية (Sandbox) إلى البيئة الحية الحقيقية (Live - السعودية)، وتحديث المفاتيح ومعرّفات وسائل الدفع (Integration IDs)، وإجراء اختبار تحقق فعلي (Live Intention Verification Test) بمبلغ تجريبي صغير (1 ريال سعودي) للتأكد من جاهزية النظام واستقرار عملية الدفع.

---

## 🔑 2. بيانات ومفاتيح الحساب الحي (Credentials & Metadata)

| البند | القيمة الحية (Live Value) | الملاحظات |
| :--- | :--- | :--- |
| **الدولة والعملة** | `SAR` (ريال سعودي) | حساب Paymob السعودية (KSA) |
| **Base URL** | `https://ksa.paymob.com` | خادم بوابة الدفع السعودية |
| **Public Key** | `sau_pk_live_itKdSRiYOfosfkO10lakglFwb8rDq4ff` | المفتاح العام الحي |
| **Secret Key** | `sau_sk_live_e7ca7bef57fbab6b8382d5e825d1b01bfb6ee3db13ec560dc236236c63aebc5e` | المفتاح السري الحي |
| **HMAC Secret** | `0F2A0FDC4A29F0EBA00B51FF01BECC4D` | مفتاح التحقق من توقيع Webhook |
| **Card Integration ID** | `32870` | وسيلة الدفع بالبطاقات (MIGS-online) |
| **Apple Pay / Wallet ID** | `32869` | وسيلة الدفع (MIGS-online APPLE PAY) |

---

## 🛠️ 3. خطوات التنفيذ في الباك إند (Backend Implementation)

### الخطوة 3.1: فتح وتعديل ملف البيئة `.env`
المسار: `E:\electropi-ibos\med\edu\education-bot-node\.env`

قم بتحديث قسم `PAYMOB` بالقيم التالية:

```env
# ==========================================
# PAYMOB CONFIGURATION (KSA LIVE)
# ==========================================
PAYMOB_ENABLED=true
PAYMOB_MODE=live
PAYMOB_BASE_URL=https://ksa.paymob.com
PAYMOB_CURRENCY=SAR
PAYMOB_FX_RATE=1

# ---- LIVE KEYS (SAUDI ARABIA) ----
PAYMOB_LIVE_PUBLIC_KEY=sau_pk_live_itKdSRiYOfosfkO10lakglFwb8rDq4ff
PAYMOB_LIVE_SECRET_KEY=sau_sk_live_e7ca7bef57fbab6b8382d5e825d1b01bfb6ee3db13ec560dc236236c63aebc5e
PAYMOB_LIVE_HMAC_SECRET=0F2A0FDC4A29F0EBA00B51FF01BECC4D
PAYMOB_LIVE_INTEGRATION_ID_CARD=32870
PAYMOB_LIVE_INTEGRATION_ID_WALLET=32869

# ---- CALLBACKS & REDIRECTS ----
PAYMOB_WEBHOOK_URL=https://learn.modrs.ai/api/payment/paymob/webhook
PAYMOB_REDIRECT_URL=https://learn.modrs.ai/api/payment/paymob/redirect
PAYMOB_RESULT_BASE_URL=https://learn.modrs.ai
PAYMOB_RESULT_PATH_SUCCESS=/build?payment=success
PAYMOB_RESULT_PATH_PENDING=/build?payment=pending
PAYMOB_RESULT_PATH_FAILED=/build?payment=failed
```

---

## 🌐 4. ضبط لوحة تحكم Paymob Dashboard

يجب الدخول إلى لوحة تحكم Paymob السعودية (`accept.paymob.com` أو `ksa.paymob.com`):
1. التوجه إلى **Developers** ⬅️ **Payment Integrations**.
2. الضغط على **Edit** لكل من:
   - Integration `#32870` (MIGS-online)
   - Integration `#32869` (MIGS-online APPLE PAY)
3. تعديل الروابط كالتالي:
   - **Transaction Processed Callback (Webhook)**: 
     ضع رابط السيرفر: `https://learn.modrs.ai/api/payment/paymob/webhook`
   - **Transaction Response Callback (Redirect)**: 
     ضع رابط التوجيه: `https://learn.modrs.ai/api/payment/paymob/redirect`
4. الضغط على **Save**.

---

## 🧪 5. اختبار التحقق الحقيقي (Live Verification Test)

### إنشاء سكريبت فحص سريع: `test-live-paymob.mjs`
قم بإنشاء ملف في مجلد المشروع لتجربة إنشاء عملية دفع حية بمبلغ 1 ريال (100 هللة):

```javascript
// test-live-paymob.mjs
import { getPaymobConfig } from './src/Modules/Payment/Services/paymob.config.js';
import { createPaymobIntention, buildCheckoutUrl } from './src/Modules/Payment/Services/paymob.client.js';

async function runLiveTest() {
  console.log('🔄 جاري فحص إعدادات Paymob Live...');
  const config = getPaymobConfig();

  console.log(` الوضع الحالي: ${config.mode}`);
  console.log(` العملة: ${config.currency}`);
  console.log(` Base URL: ${config.baseUrl}`);
  console.log(` Card Integration ID: ${config.integrationIds.card}`);

  const testPayload = {
    amount: 100, // 1 SAR (100 Halalas)
    currency: 'SAR',
    payment_methods: [Number(config.integrationIds.card)],
    special_reference: `TEST-LIVE-${Date.now()}`,
    billing_data: {
      first_name: 'Test',
      last_name: 'LiveUser',
      email: 'test@modrs.ai',
      phone_number: '+966500000000',
      country: 'SA',
      street: 'King Fahd Road',
      building: '10',
      floor: '1',
      apartment: '1',
      city: 'Riyadh',
      state: 'Riyadh'
    }
  };

  try {
    console.log('\n🚀 جاري إرسال طلب إنشاء Intention تجريبي (1 ريال)...');
    const result = await createPaymobIntention(testPayload, config);

    console.log('\n✅ نجح الاتصال بنجاح تام!');
    console.log(`📌 Intention ID: ${result.id}`);
    console.log(`🔑 Client Secret: ${result.client_secret ? '[موجود وقانوني]' : '[مفقود]'}`);
    
    const checkoutUrl = buildCheckoutUrl(config, result.client_secret);
    console.log(`\n🔗 رابط صفحة الدفع الحية (Unified Checkout URL):\n${checkoutUrl}\n`);
    console.log('🎉 الحساب الحي يعمل وجاهز لاستقبال المدفوعات!');
  } catch (error) {
    console.error('\n❌ فشل الاتصال بخوادم Paymob:');
    console.error(error.message);
    if (error.response?.data) {
      console.error('تفاصيل الخطأ من Paymob:', JSON.stringify(error.response.data, null, 2));
    }
  }
}

runLiveTest();
```

### تشغيل الاختبار:
```bash
node --import ./src/loadEnv.js test-live-paymob.mjs
```

---

## 🎯 6. معايير النجاح (Acceptance Criteria)

- [ ] قراءة المتغيرات من `.env` بحيث يكون `PAYMOB_MODE=live`.
- [ ] قبول المفاتيح `sau_pk_live_...` و `sau_sk_live_...` من قبل خادم Paymob دون أخطاء 401/403.
- [ ] إنشاء Intention بنجاح والحصول على رابط `checkoutUrl` صالح يبدأ بـ `https://ksa.paymob.com/unifiedcheckout/...`.
- [ ] التحقق من أن العملة المعتمدة هي `SAR`.
- [ ] استلام رد الـ Webhook وتوثيقه بنجاح بواسطة `PAYMOB_LIVE_HMAC_SECRET`.

---

## 🔄 7. خطة التراجع السريع (Rollback Plan)
في حال حدوث أي طارئ أو رغبة في العودة لبيئة الاختبار:
1. تغيير المتغير في `.env`:
   ```env
   PAYMOB_MODE=sandbox
   ```
2. إعادة تشغيل السيرفر (`pm2 restart all` أو `npm start`).
