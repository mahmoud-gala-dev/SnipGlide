# خطة عمل تفعيل واختبار مفاتيح Paymob Live (السعودية KSA)
**المشروع:** `education-bot-node`  
**التاريخ:** 30 أغسطس 2026  
**البيئة المستهدفة:** Live (Production)

---

## 📑 جدول المحتويات
1. [نظرة عامة والهدف](#1-نظرة-عامة-والهدف)
2. [بيانات الحساب الحي (KSA Credentials)](#2-بيانات-الحساب-الحي-ksa-credentials)
3. [خطوات الإعداد في الباك إند (.env)](#3-خطوات-الإعداد-في-الباك-إند-env)
4. [إعدادات لوحة تحكم Paymob Dashboard](#4-إعدادات-لوحة-تحكم-paymob-dashboard)
5. [سكريبت الفحص والاختبار الحي (Unit / Intention Test)](#5-سكريبت-الفحص-والاختبار-الحي-unit--intention-test)
6. [معايير القبول والتأكد (Acceptance Criteria)](#6-معايير-القبول-والتأكد-acceptance-criteria)
7. [إجراءات الأمان وخطة التراجع السريع (Rollback)](#7-إجراءات-الأمان-وخطة-التراجع-السريع-rollback)

---

## 1. نظرة عامة والهدف
الهدف هو تحويل بوابة الدفع في مشروع `education-bot-node` من البيئة التجريبية (Sandbox) إلى البيئة الحية (Live) الخاصة بالمملكة العربية السعودية (KSA)، وتحديث المفاتيح ومعرّفات وسائل الدفع (MIGS Cards & Apple Pay)، وإجراء اختبار اتصال وإنشاء رابط دفع فعلي بمبلغ تجريبي (1 ريال سعودي = 100 هللة) للتحقق من سلامة التكامل البرمجي قبل استقبال مدفوعات العملاء.

---

## 2. بيانات الحساب الحي (KSA Credentials)

| البند | القيمة الحية (Live Value) | الوصف والملاحظات |
| :--- | :--- | :--- |
| **الدولة / العملة** | `SAR` | ريال سعودي |
| **Base URL** | `https://ksa.paymob.com` | خوادم Paymob المخصصة للسعودية |
| **Public Key** | `sau_pk_live_itKdSRiYOfosfkO10lakglFwb8rDq4ff` | المفتاح العام الحي |
| **Secret Key** | `sau_sk_live_e7ca7bef57fbab6b8382d5e825d1b01bfb6ee3db13ec560dc236236c63aebc5e` | المفتاح السري الحي للعمليات |
| **HMAC Secret** | `0F2A0FDC4A29F0EBA00B51FF01BECC4D` | مفتاح التحقق من توقيع إشعارات السيرفر (Webhook) |
| **Card Integration ID** | `32870` | وسيلة الدفع بالبطاقات (MIGS-online) |
| **Apple Pay Integration ID** | `32869` | وسيلة الدفع (MIGS-online APPLE PAY) |

---

## 3. خطوات الإعداد في الباك إند (.env)

المسار: `E:\electropi-ibos\med\edu\education-bot-node\.env`

### استبدال قسم Paymob بالقيم التالية:

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

## 4. إعدادات لوحة تحكم Paymob Dashboard

يجب الدخول إلى لوحة تحكم Paymob وتعديل الإعدادات للـ Integration IDs:
1. التوجه إلى: **Developers** ⬅️ **Payment Integrations**.
2. اختيار Integration `#32870` والضغط على **Edit**:
   - **Transaction Processed Callback (Webhook):**  
     `https://learn.modrs.ai/api/payment/paymob/webhook`
   - **Transaction Response Callback (Redirect):**  
     `https://learn.modrs.ai/api/payment/paymob/redirect`
3. اختيار Integration `#32869` والضغط على **Edit** وتعيين نفس الروابط أعلاه.
4. حفظ التغييرات.

---

## 5. سكريبت الفحص والاختبار الحي (Unit / Intention Test)

يتم تشغيل هذا الاختبار لإنشاء طلب دفع تجريبي حقيقي بمبلغ **1 ريال سعودي (100 هللة)** دون خصم حقيقي حتى فتح الرابط، وللتحقق من أن Paymob يقبل المفاتيح ويرجع رابط الدفع:

### ملف الاختبار: `test-live-paymob.mjs`

```javascript
import { getPaymobConfig } from './src/Modules/Payment/Services/paymob.config.js';
import { createPaymobIntention, buildCheckoutUrl } from './src/Modules/Payment/Services/paymob.client.js';

async function runLiveTest() {
  console.log('🔄 جاري فحص إعدادات Paymob Live...');
  const config = getPaymobConfig();

  console.log(`✅ الوضع الحالي: ${config.mode}`);
  console.log(`✅ العملة المعتمدة: ${config.currency}`);
  console.log(`✅ الخادم المستهدف: ${config.baseUrl}`);
  console.log(`✅ معرّف بطاقات الدفع: ${config.integrationIds.card}`);

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

    console.log('\n🎉 نجح الاتصال بنجاح تام!');
    console.log(`📌 Intention ID: ${result.id}`);
    console.log(`🔑 Client Secret: ${result.client_secret ? 'موجود وصالح' : 'مفقود'}`);
    
    const checkoutUrl = buildCheckoutUrl(config, result.client_secret);
    console.log(`\n🔗 رابط صفحة الدفع الحية (Unified Checkout URL):\n${checkoutUrl}\n`);
    console.log('✅ الحساب الحي يعمل وجاهز بنسبة 100% لاستقبال العمليات!');
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

### أمر التشغيل:
```bash
node --import ./src/loadEnv.js test-live-paymob.mjs
```

---

## 6. معايير القبول والتأكد (Acceptance Criteria)

- [ ] قراءة المتغيرات من `.env` بحيث يكون `PAYMOB_MODE=live`.
- [ ] قبول المفاتيح `sau_pk_live_...` و `sau_sk_live_...` من قبل خادم Paymob دون أخطاء 401/403.
- [ ] إنشاء Intention بنجاح والحصول على رابط `checkoutUrl` صالح يبدأ بـ `https://ksa.paymob.com/unifiedcheckout/...`.
- [ ] التحقق من أن العملة المعتمدة هي `SAR`.
- [ ] استلام رد الـ Webhook وتوثيقه بنجاح بواسطة `PAYMOB_LIVE_HMAC_SECRET`.

---

## 7. إجراءات الأمان وخطة التراجع السريع (Rollback)

في حال حدوث أي طارئ أو خطأ أثناء التشغيل المباشر:
1. افتح ملف `.env` وقم بتغيير المتغير إلى:
   ```env
   PAYMOB_MODE=sandbox
   ```
2. أعد تشغيل السيرفر فوراً:
   ```bash
   pm2 restart all
   # أو
   npm start
   ```
