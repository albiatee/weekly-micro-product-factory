# المساهمة

## قبل أي PR

1. اقرأ [`docs/OPERATING_RULES.md`](docs/OPERATING_RULES.md) — مساران (A أسبوعي / B فرص).
2. لا تشغّل `generate_opportunities` على دفعات RSS غير المراجعة.
3. لا تكسر `weekly-build` أو `issue-intake` إلا بسبب تقني مباشر ومتفق عليه.
4. لا تختلق مقاييس طلب أو إيراد في الكود أو البيانات.

## اختبارات

```bash
python -m pytest tests/ -q --tb=line
```

يجب أن يبقى الجناح أخضر.

## نطاقات شائعة

| تغيير | أين |
|--------|-----|
| مصنع أسبوعي / قوالب / Issues | مسار A — workflows، agents، templates |
| Signals → Decision → Bridge | مسار B — `discovery/` … `discovery_feedback/`، `contracts/` |
| مصادر RSS | `config/signal_sources.json` فقط ما أمكن |

## إشارات السوق

فضّل نص مشكلة حقيقي (مراجعة، Issue، مقابلة) على firehose عام.  
التصويت 👍 على Issue ≠ تحقق سوق لمسار B.
