# מטלה: תרחיש E2E על אתר מסחר (דוגמה: eBay)

## מטרה

לממש בדיקת **מקצה לקצה (E2E)** עם **Playwright** ו־**pytest** על אתר מסחר אמיתי, תוך שימוש ב־**Page Object Model (POM)** ונתונים מקובץ **JSON**.

## דרישות התרחיש

| שלב | תיאור |
|-----|--------|
| 1 | **חיפוש מוצרים** — חיפוש לפי מחרוזת מהנתונים (`search_text`). |
| 2 | **סינון לפי מחיר** — הגבלת מחיר מקסימלי (`max_price`): בפרויקט זה מיושם בכתובת החיפוש (`_udhi`) ובניסיון נוסף לסינון בסרגל הצד (אם האלמנטים קיימים). |
| 3 | **הוספה לסל** — פתיחת מודעת **Buy It Now** ראשונה מתאימה והוספה לעגלה. |
| 4 | **אימות סכום** — מעבר לעגלה, קריאת סכום ביניים והשוואה ל־`cart_total_max` מנתוני הבדיקה. |

## CAPTCHA (פתרון ידני)

אין לעקוף CAPTCHA באוטומציה. אם מופיע אתגר / CAPTCHA:

1. הריצו עם דפדפן גלוי ו־Inspector (מומלץ: `HEADLESS=0 PWDEBUG=1`).
2. כשהבדיקה נעצרת ב־`page.pause()` — פתרו ידנית במסך הדפדפן.
3. חזרו ל־**Playwright Inspector** ולחצו **Resume** כדי להמשיך את האוטומציה.

אופציונלי: `EBAY_ALWAYS_PAUSE=1` — עצירה אחת אחרי טעינת דף הבית (עוגיות / אתגר מאוחר).

## קבצים בפרויקט

- נתונים: `data/ebay/cases.json`
- בדיקה: `tests/test_e2e_ebay.py`
- עמודים: `src/pages/ebay/`

## הרצה

```bash
HEADLESS=0 PWDEBUG=1 pytest tests/test_e2e_ebay.py -v
```

**הערת ציות:** השתמשו ב־eBay בהתאם לתנאי השימוש והמדיניות שלהם. המטלה מיועדת ללמידה; האחריות על שימוש מותר היא עליכם.

## English summary (for instructors)

Full eBay-style commerce E2E: **search**, **price filter** (URL + optional UI facet), **add to cart** (Buy It Now), **assert cart subtotal** ≤ JSON cap. **Manual CAPTCHA** via `page.pause()` + Inspector resume.
