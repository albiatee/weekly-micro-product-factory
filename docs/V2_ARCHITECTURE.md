# V2 Architecture — AI Market Opportunity Factory

> **حالة الوثيقة:** معمارية مثبتة للنقاش النهائي — **لا تعديل على كود التشغيل في هذه المرحلة**  
> **الهوية:** نظام **يختبر الفرص**، لا مولّد أفكار سوقية فقط  
> **الأسواق:** غير مقيد بالعربية؛ `geo` مخرَج تحليلي (محلي / MENA / عالمي)

---

## 0. التعريف الواحد (مُحدَّث)

**AI Market Opportunity Factory** = حلقة مغلقة:

```
سوق → إشارات → فرصة → فرضية → تجربة تحقق → قرار
  → (نفّذ | عدّل | ألغِ)
  → مصنع إنتاج عند التنفيذ (Layer B أو مسار غير رقمي)
  → توزيع → نتائج → تعلّم
  → يعود ليغذّي الاكتشاف من السوق من جديد
```

| طبقة | دورها |
|------|--------|
| **Discovery** | يقرّر *ماذا يستحق أن يُختبر ثم يُبنى* |
| **Production** | يبني ما نجح في البوابة (Layer B الرقمي موجود ويعمل) |
| **Analytics / Learning** | تقيس النتائج وتعيد تغذية Discovery |

**ليس الهدف:** إنتاج قائمة أفكار لا نهائية.  
**الهدف:** كل فرصة تمرّ بـ **تجربة قابلة للقياس** ثم **قرار صريح** موثّق.

---

## 1. المبادئ الحاكمة

| # | مبدأ | معنى عملي |
|---|------|-----------|
| 1 | Test, don’t only ideate | لا تُعتبر الفرصة «ناضجة» بدون تجربة تحقق |
| 2 | Discovery before full build | البناء الكامل بعد قرار `execute` من البوابة |
| 3 | Solution-type agnostic | رقمي / خدمة / SaaS / مادي / وسيط… |
| 4 | Market-agnostic | اللغة والجغرافيا لكل فرصة على حدة |
| 5 | First launch = experiment | الإطلاق الأول لاختبار الفرضية |
| 6 | Closed learning loop | النتائج تعود لإشارات ودرجات وقرارات لاحقة |
| 7 | Preserve Layer B | لا هدم لخط الإنتاج الرقمي الحالي |
| 8 | Zero-budget default | مصادر مجانية أولاً |

---

## 2. العمود الفقري (النظام كثلاثي)

```
     ┌─────────────────────────────────────────────────────────┐
     │                      MARKET                               │
     └──────────────────────────┬──────────────────────────────┘
                                │ إشارات
                                ▼
┌───────────────────────────────────────────────────────────────────┐
│  DISCOVERY                                                         │
│  signals → opportunity → hypothesis → experiment (validation)      │
│  → decision: execute | iterate | kill                              │
└─────────────┬──────────────────────────▲───────────────────────────┘
              │ execute                  │ تعلّم + إشارات جديدة
              ▼                          │
┌─────────────────────────────┐    ┌─────┴──────────────────────────┐
│  PRODUCTION                 │    │  ANALYTICS / LEARNING          │
│  Layer B (رقمي) أو playbook │───▶│  نتائج توزيع، اهتمام، إيراد    │
│  توزيع (Pages, TG, قنوات)   │    │  postmortem → يغذّي Discovery  │
└─────────────────────────────┘    └────────────────────────────────┘
```

- **Discovery بدون تجارب** = مولّد أفكار (مرفوض في V2).  
- **Production بدون بوابة** = بناء أعمى (ما نريد تقليله).  
- **Analytics بدون ربط عكسي** = تقارير ميتة (مرفوض).

---

## 3. تدفق الحالة التفصيلي

### 3.1 دورة الحياة الكاملة

```
[market]
   → signal.captured
   → opportunity.draft
   → opportunity.hypothesized
   → experiment.planned
   → experiment.running          ← اختبار الفرصة
   → experiment.completed
   → opportunity.decided         ← إلزامي: قرار موثّق قبل أي تنفيذ
         Decision { verdict, reason, evidence_refs, decided_by, decided_at }
        │ execute          │ iterate              │ kill
        ▼                  ▼                      ▼
   opportunity.building   opportunity.iterating   opportunity.killed
   → production / distribute
   → results.recorded
   → learning.applied → يغذّي Discovery من جديد
```

### 3.2 حالات Opportunity

| الحالة | المعنى | الانتقال التالي المسموح |
|--------|--------|-------------------------|
| `draft` | أُنشئت من إشارات؛ لم تُصغَ فرضية كاملة | `hypothesized`, `killed` |
| `hypothesized` | جمهور + ألم + عرض قيمة + نوع حل + geo | `experimenting`, `killed` |
| `experimenting` | تجربة تحقق نشطة مرتبطة | `decided` فقط (بعد اكتمال/إجهاض التجربة + تسجيل Decision) |
| `decided` | **حالة صريحة ومُلزمة** — قرار موثّق؛ التنفيذ لم يبدأ بعد | `building`, `iterating`, `killed` حسب `Decision.verdict` |
| `building` | قيد التنفيذ في Production | `shipped`, `killed` |
| `shipped` | أُطلق للسوق (منتج/خدمة/عرض) | `iterating` (تعلّم لاحق) |
| `iterating` | قرار `iterate` — فرضية أو تجربة جديدة | `hypothesized`, `experimenting` |
| `killed` | أُلغي مع سبب | طرف نهائي (أو إعادة فتح يدوية نادرة) |

#### لماذا `decided` صريحة؟ (مثبّتة — لا تُختصر)

تفصل زمنياً وهندسياً بين:

1. **ماذا أظهرت التجربة؟** (`experiment.completed` + `results`)
2. **ماذا قررنا بناءً عليها؟** (`Decision` + حالة `decided`)
3. **هل نفّذنا القرار؟** (`building` / `iterating` / `killed`)

هذا ضروري لنظام هدفه **التعلّم والتدقيق لاحقاً**: يمكن سؤال «هل كان القرار صحيحاً؟» بمعزل عن ضجيج التنفيذ.

**المسار المعتمد (لا يُتجاوز):**

```
experimenting → decided → building | iterating | killed
```

**قواعد ملزمة:**

- لا انتقال من `hypothesized` أو `experimenting` إلى `building` مباشرة.
- الدخول إلى `decided` يتطلب سجل `Decision` كاملاً (الحقول في 3.4).
- الخروج من `decided` فقط وفق `verdict`: `execute` → `building`، `iterate` → `iterating`، `kill` → `killed`.
- استثناء بشري نادر لتخفيف التجربة يُوثَّق في `Decision.reason` ويمرّ رغم ذلك عبر `decided` (لا قفز صامت إلى `building`).

### 3.3 حالات Experiment (تجربة التحقق)

| الحالة | المعنى |
|--------|--------|
| `planned` | صُمّم الاختبار (نوع، قناة، عتبة نجاح، مدة) |
| `running` | منشور/جارٍ جمع المقاييس |
| `completed` | انتهت النافذة الزمنية أو اكتملت العتبة |
| `aborted` | أُوقفت مبكراً (سبب إلزامي) |

أنواع التجربة (`experiment_type`):

- `smoke_page` — صفحة عرض + CTA اهتمام  
- `waitlist` — تسجيل بريد/تواصل  
- `concierge` — خدمة يدوية لأول N عملاء  
- `preorder` — نية دفع / دفع رمزي  
- `community_vote` — 👍 داخلي (إشارة **داعمة فقط**، لا تغني عن تجربة سوق إن أمكن)  
- `manual_pilot` — تجربة يدوية موثّقة  

### 3.4 قرارات Decision

كل انتقال إلى `decided` يرافقه سجل `Decision` واحد على الأقل بالحقول الإلزامية:

| حقل | إلزامي | المعنى |
|-----|--------|--------|
| `verdict` | نعم | `execute` \| `iterate` \| `kill` |
| `reason` | نعم | لماذا هذا القرار |
| `evidence_refs` | نعم | مراجع تجارب/إشارات (مثلاً `exp_...`) |
| `decided_by` | نعم | `human` أو `human_with_agent_suggestion` |
| `decided_at` | نعم | وقت القرار (ISO-8601) |

| القرار | المعنى | بعد البقاء في `decided` |
|--------|--------|-------------------------|
| `execute` | الفرضية صمدت بما يكفي للتنفيذ | → `building` ثم Production |
| `iterate` | إشارة غير حاسمة أو تصميم التجربة ضعيف | → `iterating` ثم فرضية/تجربة جديدة |
| `kill` | لا طلب كافٍ أو غير قابل للتنفيذ | → `killed` |

**تدقيق لاحق:** من الثلاثية `(Experiment.results, Decision, Opportunity.status بعد التنفيذ)` نعرف: ماذا أظهرت التجربة، ماذا قررنا، وهل طابق الواقع القرار.

---

## 4. Schemas (JSON) — عقد البيانات

> التخزين المقترح: ملفات تحت `catalog/` عند التنفيذ لاحقاً.  
> الآن: **تعريف فقط** — لا إنشاء ملفات تشغيلية إلزامي قبل Phase 1.

### 4.1 `Signal`

```json
{
  "id": "sig_01H...",
  "source": "github_issue|x|reddit|trends|review|competitor|manual",
  "raw_text": "string",
  "language": "ar|en|other",
  "geo_hint": "SA|EG|US|GLOBAL|unknown",
  "url": "string|null",
  "captured_at": "2026-09-20T12:00:00Z",
  "cluster_id": "cl_...|null",
  "meta": {}
}
```

### 4.2 `Opportunity`

```json
{
  "id": "opp_01H...",
  "status": "draft|hypothesized|experimenting|decided|building|shipped|iterating|killed",
  "title": "string",
  "problem": "string",
  "audience": "string",
  "value_proposition": "string|null",
  "hypothesis": "string|null",
  "solution_type": "digital_micro|content_pack|concierge|saas|physical_hybrid|marketplace|unknown",
  "geo": {
    "primary": "SA|AE|EG|US|EU|GLOBAL|...",
    "region": "MENA|NA|EU|APAC|GLOBAL",
    "languages": ["ar", "en"],
    "rationale": "string"
  },
  "score": {
    "total": 0,
    "intensity": 0,
    "willingness_to_pay": 0,
    "reachability": 0,
    "competition_gap": 0,
    "feasibility": 0,
    "ethics": 0
  },
  "signal_ids": ["sig_..."],
  "active_experiment_id": "exp_...|null",
  "latest_decision_id": "dec_...|null",
  "production_ref": {
    "path": "products/weekly/2026-w56|null",
    "week_id": "string|null",
    "solution_playbook": "string|null"
  },
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

### 4.3 `Experiment`

```json
{
  "id": "exp_01H...",
  "opportunity_id": "opp_...",
  "status": "planned|running|completed|aborted",
  "experiment_type": "smoke_page|waitlist|concierge|preorder|community_vote|manual_pilot",
  "hypothesis_test": "ماذا نختبر بجملة واحدة",
  "channel": "string",
  "start_at": "ISO-8601|null",
  "end_at": "ISO-8601|null",
  "success_threshold": {
    "metric": "signups|cta_clicks|paid|qualitative|votes",
    "operator": "gte",
    "value": 10,
    "window_days": 7
  },
  "results": {
    "metrics": {},
    "qualitative_notes": [],
    "passed": null
  },
  "artifact_path": "products/smoke/opp_...|null",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

### 4.4 `Decision`

```json
{
  "id": "dec_01H...",
  "opportunity_id": "opp_...",
  "experiment_id": "exp_...|null",
  "verdict": "execute|iterate|kill",
  "reason": "string",
  "evidence_refs": ["exp_...", "sig_..."],
  "decided_by": "human|human_with_agent_suggestion",
  "decided_at": "ISO-8601"
}
```

### 4.5 `LearningRecord` (تغذية راجعة لـ Discovery)

```json
{
  "id": "lrn_01H...",
  "opportunity_id": "opp_...",
  "decision_id": "dec_...",
  "what_worked": "string",
  "what_failed": "string",
  "next_signals_hint": "string",
  "score_calibration_notes": "string|null",
  "created_at": "ISO-8601"
}
```

### 4.6 ملفات الكتالوج المقترحة (Phase 1 لاحقاً)

| ملف | محتوى |
|-----|--------|
| `catalog/signals.json` | قائمة `Signal` |
| `catalog/opportunities.json` | قائمة `Opportunity` |
| `catalog/experiments.json` | قائمة `Experiment` |
| `catalog/decisions.json` | قائمة `Decision` |
| `catalog/learnings.json` | قائمة `LearningRecord` |
| `catalog/index.json` | منتجات رقمية (موجود — لا يُكسر) |

---

## 5. ربط Production (Layer B) دون هدمه

عند `decision.execute` و `solution_type = digital_micro`:

1. تُوسم الفرصة `building`.  
2. تُمرَّر إلى طابور البناء (Issue بوسم `build` أو مدخل `weekly-build`).  
3. يُشغَّل المسار الحالي: triage → diversity → content → design → critic → publish.  
4. يُحدَّث `production_ref` + حالة `shipped`.  
5. التوزيع (Pages / Telegram / قنوات التجربة) يُسجَّل كجزء من النتائج.  
6. Analytics يكتب `LearningRecord` ويعود لـ Discovery.

عند أنواع غير رقمية: `playbook` موجز بدلاً من HTML — **نفس** حالات الفرصة والقرار؛ يختلف التنفيذ فقط.

---

## 6. Analytics يغذّي Discovery

مخرجات التعلّم الإلزامية بعد كل `completed` experiment أو بعد `shipped`:

- هل العتبة تحققت؟  
- أي قناة/رسالة عملت؟  
- هل `solution_type` كان مناسباً؟  
- هل `geo` كان ضيقاً أو واسعاً زيادة؟  
- تعديل مقترح على أوزان الـ score (ملاحظة بشرية في البداية)

بدون هذه الحلقة، النظام يتوقف عند «أفكار + صفحات» ويصبح مولّد أفكار متخفّي.

---

## 7. الأيجنتس (مرتبة على الحلقة)

| مرحلة الحلقة | وكلاء |
|--------------|--------|
| إشارات | `signal_ingest` (جديد) + Issues الحالية |
| فرصة / فرضية | `opportunity_agent`, `market_geo_agent`, `solution_router`, `opportunity_scorer` |
| تجربة | `smoke_builder`, `validation_tracker` |
| قرار | `gate_reporter` (اقتراح) + **اعتماد بشري** |
| إنتاج رقمي | وكلاء Layer B الحاليون كما هم |
| إنتاج غير رقمي | `playbook_agent` لاحقاً |
| توزيع/نتائج/تعلّم | `notify_*` الحالي + `learning_summarizer`, `growth_suggester` |

---

## 8. مقارنة سريعة: مولّد أفكار vs نظام اختبار

| | مولّد أفكار (نرفضه) | نظام اختبار (V2) |
|--|---------------------|------------------|
| المخرج الرئيسي | قائمة فرص | تجربة + قرار |
| النجاح | كثرة الأفكار | جودة القرارات والتعلّم |
| البناء | مبكر أو عشوائي | بعد `execute` |
| القياس | اختياري | إلزامي على مستوى التجربة |
| التغذية الراجعة | ضعيفة | `LearningRecord` → Discovery |

---

## 9. ما لا نفعله الآن (تجميد الكود)

- لا تعديل `weekly-build.yml` / الوكلاء الحاليين  
- لا حذف قوالب أو i18n أو Telegram  
- لا Phase 1 تنفيذية حتى اعتماد هذه المعمارية صراحةً  

**المسموح الآن:** توثيق فقط (هذه الوثيقة + لاحقاً README بعد موافقتك).

---

## 10. Phase 1 (لاحقاً، بهدوء)

عندما تأمر بالتنفيذ فقط:

1. إنشاء ملفات schema فارغة + أمثلة  
2. وسوم Issue: `opportunity`, `experiment`, `validated`, `build`  
3. قالب Issue «فرصة / تجربة»  
4. قالب `smoke-offer`  
5. قسم في stats للقراءة فقط  

كل ذلك **إضافة** بجانب المسار الشغّال.

---

## 11. معايير قبول هذه المراجعة

- [x] العمود الفقري: سوق → … → تجربة → قرار → إنتاج → نتائج → تعلّم → سوق  
- [x] Discovery / Production / Analytics أدوار واضحة  
- [x] النظام يختبر فرصاً لا يولّد أفكاراً فقط  
- [x] schemas + حالات Opportunity و Experiment و Decision  
- [x] Layer B محفوظ كمسار تنفيذ  
- [x] لا تغيير كود تشغيلي في هذه المرحلة  

---

## 12. الخلاصة

V2 = **مصنع قرارات مبنية على تجارب**، ومصنع المنتجات الرقمية الحالي هو ذراع التنفيذ عندما يكون القرار `execute` والحل رقمياً.

بعد موافقتك النهائية على هذه الصيغة، نحدّث README فقط إن طلبت، ثم Phase 1 عند أمرك — بدون كسر ما يعمل.
