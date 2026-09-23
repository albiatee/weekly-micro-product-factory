# Data Contracts (Phase 1)

Schema Contract معتمد → تحقق برمجي تحت `contracts/`.

## أين؟

| مسار | دور |
|------|-----|
| `contracts/constants.py` | بادئات، حالات، انتقالات، قوائم مرجعية |
| `contracts/validate.py` | تحقق الحقول، lifecycle، المراجع |
| `contracts/examples/` | أمثلة JSON صالحة |
| `tests/test_contracts.py` | اختبارات العقد |

**لا** يغيّر: `weekly-build.yml`, `issue-intake.yml`, `catalog/index.json`, `products/`.

## الكيانات

`Signal` · `Opportunity` · `Experiment` · `Decision` · `LearningRecord`  
المعرّفات: `sig_` / `opp_` / `exp_` / `dec_` / `lr_`

## قواعد مختصرة

- `created_by`: مطلوب في Opportunity و Experiment؛ اختياري في Signal
- `decided_by`: مطلوب في Decision
- `signal_ids`: اختياري في `draft`؛ مطلوب وغير فارغ من `hypothesized`+
- `active_experiment_id`: **مطلوب** عندما `opportunity.status == experimenting` (`exp_...` موجود وقابل للحل في graph)
- `measurement_plan`: مطلوب عندما `experiment.status == running` — نص غير فارغ **أو** كائن/dict غير فارغ
- `success_threshold`: اختياري دائماً
- `evidence_refs`: `exp_...` أو `sig_...` فقط، وقابلة للحل في `validate_graph`
- انتقالات Opportunity: لا قفز `hypothesized`/`experimenting`/`draft` → `building`؛ المسار `experimenting → decided → …`

## تشغيل الاختبارات

```bash
pytest tests/test_contracts.py tests/ -q
```

التفاصيل الكاملة للعقود: قرارات التصميم في المحادثة / `docs/V2_ARCHITECTURE.md` (لا تُعاد كتابتها هنا).
