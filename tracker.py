"""
BASE 44 — מעקב קדימה   [tracker.py]

רץ אוטומטית כל ערב מסחר דרך GitHub Actions.

━━ למה זה קיים ━━
כל מה שמדדנו עד היום הוא היסטוריה: בררנו עשרות תצורות על
אותם נתונים, והיקום עצמו נבחר בדיעבד. **מעקב קדימה הוא
המדידה היחידה שאין בה הצצה, כי העתיד עוד לא קרה.**

━━ ומה שחשוב יותר: נתונים שאי אפשר להשיג מההיסטוריה ━━
אלה הדברים שנעלמים או משתנים למפרע, ולכן כל יום שלא
נאסף הוא יום שאבד לתמיד:

  1. מרווח קנייה/מכירה (bid/ask)
     ⭐ **הפריט היקר ביותר.** אין לו היסטוריה בשום מקור חינמי,
     ומדדנו שרגישות לעלויות היא הסיכון הגדול של המערכת
     (0.10% מוחק 35 נקודות). בלי מרווח אמיתי אנחנו מנחשים.

  2. חברות ביקום נכון-להיום
     מניה שתימחק מחר תיעלם מ-yfinance לגמרי. תיעוד יומי
     הוא הדרך היחידה לבנות היסטוריה נטולת הטיית שרידות.

  3. נתונים שמתוקנים למפרע
     תחזיות אנליסטים, יעדי מחיר, מכפילים עתידיים, פוזיציות
     שורט, אחזקות מוסדיים — כולם משוכתבים בדיעבד ואין
     דרך לדעת מה היה ידוע באותו רגע.

  4. תאריך הדוח כפי שהיה ידוע היום
     תאריכי דוחות זזים. מה שידענו ביום ההחלטה הוא הנתון
     הרלוונטי, לא מה שקרה בסוף.

  5. מדד פחד/חמדנות
     נמדד כחסום-נתונים ברשימת המעקב. אין היסטוריה זמינה.

  6. וקטור הפיצ׳רים המלא ברגע ההחלטה
     כדי שנוכל בעוד חצי שנה לשחזר בדיוק מה המערכת ראתה,
     ולא לשחזר אותו מנתונים שהותאמו מאז.

━━ הכתיבה היא הוספה בלבד ━━
קובץ יומי נפרד. לא דורסים, לא מתקנים למפרע. אם משהו
נשבר ביום מסוים — הוא חסר, ולא מזויף.
"""
import os, json, csv, sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, 'tracking')
os.makedirs(OUT, exist_ok=True)
TODAY = datetime.now(timezone.utc).strftime('%Y-%m-%d')

# ============================================================
# היקום — נקרא מ-app.py, לא מועתק ביד
# ============================================================
def universe():
    import ast, re
    src = open(os.path.join(ROOT, 'app.py'), encoding='utf-8').read()
    tree = ast.parse(src)
    node = [n for n in ast.walk(tree)
            if isinstance(n, ast.Assign)
            and any(getattr(t, 'id', None) == 'CATEGORIES' for t in n.targets)
            and isinstance(n.value, ast.Dict)][0]
    cats = {}
    for k, v in zip(node.value.keys, node.value.values):
        try:
            cats[ast.literal_eval(k)] = ast.literal_eval(v)
        except Exception:
            continue
    key = next((k for k in cats if 'יקום 2023 · נקי' in k), None)
    if key is None:
        key = next(k for k in cats if 'יקום סחיר' in k and 'ליבה' not in k
                   and 'ספקולטיבי' not in k)
    return key, sorted(set(cats[key]))


CAT, TICKERS = universe()
print(f'יקום: {CAT} · {len(TICKERS)} מניות')


# ============================================================
# פיצ׳רים — בדיוק מה שהמנוע רואה
# ============================================================
def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def atr(d, n=14):
    h, l, c = d['High'], d['Low'], d['Close']
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()],
                   axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


print('שולף היסטוריה...')
hist = yf.download(TICKERS, period='1y', auto_adjust=True,
                   progress=False, threads=True, group_by='ticker')

rows = []
for t in TICKERS:
    try:
        d = hist[t].dropna(how='all') if isinstance(hist.columns, pd.MultiIndex) else hist
        if len(d) < 160:
            continue
        c = d['Close']
        up = (c > c.shift()).astype(int)
        # רצף ימים אדומים — הטריגר שאושר בשלושה חלונות
        streak = 0
        for v in up.iloc[::-1]:
            if v == 0:
                streak += 1
            else:
                break
        a = atr(d)
        rows.append({
            'date': TODAY, 'ticker': t,
            'close': round(float(c.iloc[-1]), 4),
            'red_streak': streak,
            'signal_3red': int(streak >= 3),
            'dist_sma20': round(float(c.iloc[-1] / c.rolling(20).mean().iloc[-1] - 1) * 100, 3),
            'dist_sma150': round(float(c.iloc[-1] / c.rolling(150).mean().iloc[-1] - 1) * 100, 3),
            'rsi14': round(float(rsi(c).iloc[-1]), 2),
            'atr_pct': round(float(a.iloc[-1] / c.iloc[-1] * 100), 3),
            'vol_ratio': round(float(d['Volume'].iloc[-1] /
                                     d['Volume'].rolling(20).mean().iloc[-1]), 3),
            'ret_20': round(float(c.pct_change(20).iloc[-1] * 100), 3),
            'ret_120': round(float(c.pct_change(120).iloc[-1] * 100), 3),
        })
    except Exception as e:
        print(f'  ⚠️ {t}: {e}')

df = pd.DataFrame(rows)
sig = df[df.signal_3red == 1].ticker.tolist() if len(df) else []
print(f'{len(df)} מניות · {len(sig)} סיגנלים היום')


# ============================================================
# ⭐ נתונים שאין להם היסטוריה — נאספים רק למניות המסומנות
# ------------------------------------------------------------
# רק לסיגנלים, כי `.info` איטי ומוגבל בקצב. אלה גם המניות
# היחידות שבהן הנתון באמת ישמש להחלטה.
# ============================================================
live = []
for t in sig:
    rec = {'date': TODAY, 'ticker': t}
    try:
        info = yf.Ticker(t).info
        bid, ask = info.get('bid'), info.get('ask')
        # ⭐ המרווח — הפריט שאין לו תחליף היסטורי
        if bid and ask and ask > 0:
            rec['bid'] = bid
            rec['ask'] = ask
            rec['spread_pct'] = round((ask - bid) / ((ask + bid) / 2) * 100, 4)
        for k, src_k in [('short_pct', 'shortPercentOfFloat'),
                         ('short_ratio', 'shortRatio'),
                         ('fwd_pe', 'forwardPE'),
                         ('trailing_pe', 'trailingPE'),
                         ('target_mean', 'targetMeanPrice'),
                         ('rec_mean', 'recommendationMean'),
                         ('n_analysts', 'numberOfAnalystOpinions'),
                         ('inst_pct', 'heldPercentInstitutions'),
                         ('insider_pct', 'heldPercentInsiders'),
                         ('float_shares', 'floatShares'),
                         ('mkt_cap', 'marketCap')]:
            v = info.get(src_k)
            if v is not None:
                rec[k] = v
        # תאריך הדוח **כפי שהוא ידוע היום** — הוא זז בהמשך
        try:
            cal = yf.Ticker(t).calendar
            if isinstance(cal, dict) and cal.get('Earnings Date'):
                rec['earnings_next'] = str(cal['Earnings Date'][0])
        except Exception:
            pass
    except Exception as e:
        rec['error'] = str(e)[:80]
    live.append(rec)


# ============================================================
# מצב שוק — כולל מדד פחד/חמדנות שאין לו היסטוריה זמינה
# ============================================================
market = {'date': TODAY, 'universe': CAT, 'n_universe': len(df),
          'n_signals': len(sig)}
for name, sym in [('spy', 'SPY'), ('qqq', 'QQQ'), ('vix', '^VIX'),
                  ('tnx', '^TNX'), ('hyg', 'HYG'), ('ief', 'IEF')]:
    try:
        s = yf.Ticker(sym).history(period='1y')['Close']
        market[name] = round(float(s.iloc[-1]), 4)
        market[f'{name}_ret20'] = round(float(s.pct_change(20).iloc[-1] * 100), 3)
        if name == 'spy':
            market['spy_above_sma200'] = int(s.iloc[-1] > s.rolling(200).mean().iloc[-1])
            market['spy_dd'] = round(float(s.iloc[-1] / s.cummax().iloc[-1] - 1) * 100, 3)
    except Exception:
        pass
if len(df):
    market['breadth_above_sma150'] = round(float((df.dist_sma150 > 0).mean() * 100), 2)

# מדד פחד/חמדנות — סומן "חסום בנתונים" ברשימת המעקב
try:
    import urllib.request
    req = urllib.request.Request(
        'https://production.dataviz.cnn.io/index/fearandgreed/graphdata',
        headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=20) as r:
        fg = json.loads(r.read().decode())
    market['fear_greed'] = fg['fear_and_greed']['score']
    market['fear_greed_label'] = fg['fear_and_greed']['rating']
except Exception as e:
    market['fear_greed_error'] = str(e)[:60]


# ============================================================
# כתיבה — הוספה בלבד, קובץ ליום
# ============================================================
if len(df):
    df.to_csv(f'{OUT}/features_{TODAY}.csv', index=False)
if live:
    pd.DataFrame(live).to_csv(f'{OUT}/live_{TODAY}.csv', index=False)
with open(f'{OUT}/market_{TODAY}.json', 'w') as f:
    json.dump(market, f, ensure_ascii=False, indent=1)

print(f"✅ נשמר · סיגנלים: {', '.join(sig[:15]) if sig else 'אין'}")
print(f"   פחד/חמדנות: {market.get('fear_greed', 'לא זמין')}")
