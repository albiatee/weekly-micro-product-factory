# Phase 0 — مراجعة نهائية (تجميد تصميم)

> **لا تنفيذ تشغيلي.** مطابقة التصميم V2 مع المستودع الحالي فقط.  
> الحالة المعتمدة: `experimenting → decided → building | iterating | killed`

---

## 1. Schemas الخمسة — بنداً بنداً

في المستودع **لا توجد** ملفات `signals.json` / `opportunities.json` / … بعد.  
الموجود فعلياً تحت `catalog/`:

| ملف حالي | علاقته بـ V2 |
|----------|----------------|
| `catalog/index.json` | كتالوج **منتجات رقمية منشورة** (Layer B) — ليس Opportunity |
| `catalog/contributors.json` | سمعة مساهمين Issues — خارج حلقة الفرصة |

### 1.1 Signal

| حقل التصميم | موجود في المستودع؟ | ملاحظة |
|-------------|-------------------|--------|
| `id, source, raw_text, language, geo_hint, url, captured_at` | لا | يُنشأ في Phase 1 كعقد فقط |
| مصدر قريب اليوم | جزئياً | نص Issue + عنوان ≈ إشارة يدوية غير مهيكلة |

**الحكم:** العقد كافٍ كحد أدنى. لا يوجد ما يتعارض معه في الكود.

### 1.2 Opportunity

| حقل التصميم | موجود؟ | ملاحظة |
|-------------|--------|--------|
| `status` (lifecycle الكامل) | لا | Issues تستخدم `idea/approved/rejected/produced` — عالم مختلف |
| `problem, audience, hypothesis, solution_type, geo, score` | لا | |
| `signal_ids, active_experiment_id, latest_decision_id` | لا | |
| `production_ref` | لا | لاحقاً يُربط اختيارياً بـ `week` / مسار المنتج |

**الحكم:** عقد Opportunity **جديد بالكامل**؛ لا يستبدل `index.json`.

### 1.3 Experiment

| حقل التصميم | موجود؟ | ملاحظة |
|-------------|--------|--------|
| تجربة تحقق + عتبة + results | لا | |
| أقرب شبه | تصويت 👍 | يُصنَّف لاحقاً كـ `community_vote` (داعم) لا كتحقق سوق كامل |

**الحكم:** عقد جديد؛ معزول عن `weekly-build`.

### 1.4 Decision

| حقل التصميم | موجود؟ | ملاحظة |
|-------------|--------|--------|
| `verdict, reason, evidence_refs, decided_by, decided_at` | لا | |
| قرار البناء اليوم | ضمني | اختيار أسبوعي / dispatch يدوي — بدون سجل قرار تدقيقي |

**الحكم:** عقد جديد؛ يبرّر وجود حالة `decided`.

### 1.5 LearningRecord

| حقل التصميم | موجود؟ | ملاحظة |
|-------------|--------|--------|
| postmortem + تغذية Discovery | لا | |
| أقرب شبه | `critic_report` / diversity في meta | جودة **منتج**، لا تعلّم **فرصة سوق** |

**الحكم:** عقد جديد؛ لا يُخلط مع meta المنتج.

---

## 2. Lifecycle — وضوح ومطابقة

### المعتمد (مقفول)

```
experimenting → decided → building | iterating | killed
```

| حالة V2 | مقابل تقريبي في المستودع اليوم |
|---------|----------------------------------|
| `draft` / `hypothesized` | لا مقابل مباشر |
| `experimenting` | لا (التصويت ليس تجربة كاملة) |
| `decided` | لا |
| `building` | تشغيل `weekly-build` الجاري |
| `shipped` | منتج تحت `products/weekly/*` + أحياناً وسم `produced` على Issue |
| `iterating` / `killed` | لا سجل مهيكل (`rejected` على Issue ≠ kill لفرصة) |

**لا تعارض:** عوالم منفصلة حتى نربط اختيارياً `production_ref` و`source_opportunity_id`.

---

## 3. ماذا نحتفظ به (ممنوع كسره)

| المكوّن | السبب |
|---------|--------|
| `.github/workflows/weekly-build.yml` | خط إنتاج رقمي مستقر |
| `issue-intake.yml` + `triage_agent` | بوابة أفكار المنتج |
| `select_idea.py` + تصويت 👍 | أولوية مجتمعية داخل Layer B |
| `agents/*` الحاليون | triage → diversity → content → design → critic |
| `templates/*` | مسار حتمي |
| `catalog/index.json` + `contributors.json` | شكلها الحالي |
| `products/weekly/**` | أرشيف منشور |
| `locales/`, i18n، Telegram، stats، pytest، `docs/AGENTS_API.md` | تشغيل وجودة ومساهمات |

---

## 4. ماذا ينقص (طبقة V2)

| الناقص | الطبقة |
|--------|--------|
| الملفات الخمسة للعقود + أمثلة | بيانات |
| حالات Opportunity / Experiment / Decision في التشغيل | منطق |
| مسار معزول: إنشاء فرصة → تجربة → قرار | Discovery |
| قالب smoke / Issue opportunity | لاحقاً Phase 1+ |
| `LearningRecord` بعد النتائج | Analytics |
| ربط اختياري `execute` → Layer B | جسر رفيع لاحقاً |

---

## 5. أين تُضاف الطبقة الجديدة؟

```
docs/          ← التصميم (موجود)
catalog/       ← لاحقاً: signals, opportunities, experiments, decisions, learnings
                 بجانب index.json دون تعديله إلزامياً
.github/       ← لاحقاً: workflow منفصل opportunity-cycle (ليس تعديل weekly-build أولاً)
agents/        ← لاحقاً: وكلاء discovery جدد بملفات جديدة
templates/     ← لاحقاً: smoke-offer كإضافة
products/smoke/← لاحقاً: قطع تحقق (منفصل عن weekly/)
```

**الجسر الوحيد نحو الإنتاج الحالي (بعد Phase 1+ وعند الاتفاق):**  
`Decision.verdict = execute` + `solution_type = digital_micro` → استدعاء أو Issue يفعّل **نفس** `weekly-build` دون إعادة كتابته.

---

## 6. الممنوع لمسه في Phase 0 وبداية Phase 1

- منطق jobs داخل `weekly-build.yml` (إلا إضافة اختيارية لاحقاً وبموافقة)
- كسر شكل `catalog/index.json` أو `contributors.json`
- استبدال وسم `idea/approved/produced` بمسار الفرصة
- جعل كل بناء يمرّ إجبارياً بـ Opportunity قبل استقرار العقود
- حذف قوالب أو وكلاء Layer B

---

## 7. Phase 1 (تعريف فقط — لا تنفيذ الآن)

عند الأمر لاحقاً، بالترتيب:

1. إنشاء عقود JSON فارغة/أمثلة تحت `catalog/` (أو `schemas/` + catalog)
2. توثيق الانتقالات والحقول الإلزامية في README قسم V2 أو `docs/DATA_CONTRACTS.md`
3. مسار يدوي/سكربت معزول للتحقق من كتابة Opportunity + Experiment + Decision
4. **اختبار بدون** تشغيل أو تعديل `weekly-build`

---

## 8. خلاصة Phase 0

| بند | النتيجة |
|-----|---------|
| schemas الخمسة | كافية ومقفلة كعقود؛ **غير منفّذة** في المستودع بعد |
| lifecycle + `decided` | واضح ومقفول |
| المستودع الحالي | Layer B فقط؛ لا تعارض مع V2 |
| الاحتفاظ | كل خط الإنتاج والكتالوج الحالي |
| الإضافة | طبقة ملفات ومسارات جديدة بجانب الموجود |
| التنفيذ | **موقوف** حتى أمر صريح بـ Phase 1 |
