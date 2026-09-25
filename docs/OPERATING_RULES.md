# Operating Rules — تشغيل المستودع

> مثبتة بعد مراجعة المستودع + دورة RSS الأولى (2026-09).  
> الهدف: منع تحويل الضوضاء إلى Opportunities.

## 1. هويتان، مساران

| | المسار A | المسار B |
|--|----------|----------|
| الاسم | Weekly micro-product factory | AI Market Opportunity Factory (V2) |
| المدخل | GitHub Issues | Signals (`data/signals/`) |
| القرار | triage + تصويت 👍 | Experiment → Decision (بشري) |
| الإنتاج | `weekly-build` → `products/weekly/` | Production Bridge → `products/bridge/` عند `execute` + `digital_micro` فقط |

لا تمرّر Issue مقبولاً تلقائياً على أنه «طلب سوق مثبت» لمسار B.

## 2. قاعدة Discovery (إلزامية)

**ممنوع** تشغيل:

```bash
python scripts/generate_opportunities.py
```

على:

- كل محتويات `data/signals/` دفعة واحدة بعد جمع RSS
- إشارات مصنّفة Supply / Promotion / Noise / Discussion العام

**مسموح** فقط بعد مراجعة يدوية، وعلى معرفات مختارة صراحةً، عندما تكون الإشارة:

- **Problem** (مفضّل) أو **Question** ضيق
- **Problem clarity** ≥ Medium
- يمكن صياغة فرضية بدون اختراع استعداد للدفع

دفعة الإشارات المجمعة في 2026-09-21 (~20 من ask/freelance) **مغلقة** لتوليد Opportunities ما لم تُراجع واحدةً واحدة ويُختار منها يدوياً.

## 3. مصادر RSS

- الجامع يقرأ **`config/signal_sources.json` → `feeds` فقط**.
- `disabled_feeds` = مجمّد (لا يُجمع تلقائياً): freelance firehose، newest، frontpage، وغيرها حسب الملاحظات في الملف.
- فشل HTTP لمصدر واحد لا يبرر اختراع بيانات.

```bash
# استكشاف حذر
python scripts/collect_web_signals.py --source hnrss_ask --limit 10 --dry-run
# جمع حقيقي بعد قرار واعٍ
python scripts/collect_web_signals.py --source hnrss_ask --limit 10
```

## 4. مسار B — لا أتمتة قرار

- Learning لا يغيّر status/score/verdict.
- Discovery Hint → Signal فقط بعد **accept بشري**.
- Analytics لا تخترع revenue أو demand.

## 5. قبل أي كود جديد

فضّل بالترتيب:

1. الالتزام بهذه القواعد
2. إشارات يدوية عالية الجودة لدورة واحدة
3. ثم hardening (تجربة running واحدة، ذرّية التخزين) عند الحاجة

لا Phase 10 / LLM discovery قبل حل عنق جودة الإشارة.


## 6. Signal Quality (Phase 2)

See [`docs/SIGNAL_QUALITY.md`](SIGNAL_QUALITY.md).

- Every ingested Signal is enriched with `intent_type`, `evidence_strength`, `qualification_status`.
- **Only `qualification_status=qualified`** may generate Opportunities (enforced in opportunity pipeline).
- `review` / `rejected` remain auditable; they are not market validation failures, they are quality filters.
- Manual override of quality fields is allowed on ingest when provided explicitly and valid.
