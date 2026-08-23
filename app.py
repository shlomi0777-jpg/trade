import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
from pathlib import Path
import time
import re
from datetime import datetime

# ================= הגדרות עמוד =================
st.set_page_config(page_title="Base 44 - Technical Scanner", layout="centered", initial_sidebar_state="collapsed")
st.markdown("""
<style>
    .fail-box { background-color: #f8d7da; color: #721c24; padding: 10px; border-radius: 5px; border-left: 5px solid #dc3545; margin-bottom: 10px; font-weight: bold; font-family: monospace; font-size: 0.9rem; }
    .unknown-box { background-color: #fff3cd; color: #856404; padding: 8px; border-radius: 5px; border-left: 5px solid #ffc107; margin-bottom: 8px; font-size: 0.85rem; }
    .metric-row { display: flex; justify-content: space-between; align-items: center; background-color: #1e1e1e; color: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    .metric-item { text-align: center; flex: 1; border-right: 1px solid #444; }
    .metric-item:last-child { border-right: none; }
    .metric-title { font-size: 0.8rem; color: #aaa; font-weight: 600; text-transform: uppercase; }
    .metric-value { font-size: 1.3rem; font-weight: bold; color: #fff; }
    .disclaimer { background-color: #262730; color: #ccc; padding: 10px; border-radius: 5px; font-size: 0.78rem; margin-top: 10px; border: 1px solid #444; }
    .proxy-tag { background-color: #3a2f00; color: #ffd966; padding: 6px 10px; border-radius: 4px; font-size: 0.78rem; border-left: 4px solid #ffc107; margin: 6px 0; display: block; }
    .real-tag { background-color: #0d2818; color: #7ee2a8; padding: 6px 10px; border-radius: 4px; font-size: 0.78rem; border-left: 4px solid #28a745; margin: 6px 0; display: block; }
</style>
""", unsafe_allow_html=True)

# ===== אימות הוסר (לא נדרש בשלב הנוכחי) =====

# ================= תיק אישי נשמר (Drive) =================
PORTFOLIO_FILE = Path('/content/drive/MyDrive/base44/portfolio.json')

DEFAULT_PORTFOLIO = ["ADBE", "AMZN", "ANET", "ARM", "AVGO", "BLK", "BNO", "CAT", "CVX",
                     "ETN", "GLD", "GLDM", "IWM", "KO", "LMT", "MA", "MSFT", "NVDA",
                     "QQQ", "RSP", "RTX", "SCHW", "SMR", "SPMO", "TT", "XLV", "AAOI", "OUST"]

def load_portfolio():
    """ טוען את התיק האישי מ-Drive. אם אין קובץ - מחזיר את ברירת המחדל.
    השמירה ב-Drive ולא בזיכרון כדי שהתיק ישרוד איפוס של הרנטיים. """
    try:
        if PORTFOLIO_FILE.exists():
            data = json.loads(PORTFOLIO_FILE.read_text(encoding='utf-8'))
            if isinstance(data, list) and data:
                return [str(x).upper() for x in data]
    except Exception:
        pass
    return list(DEFAULT_PORTFOLIO)

def save_portfolio(lst):
    try:
        PORTFOLIO_FILE.parent.mkdir(parents=True, exist_ok=True)
        PORTFOLIO_FILE.write_text(json.dumps(sorted(set(lst)), ensure_ascii=False),
                                   encoding='utf-8')
        return True, None
    except Exception as e:
        return False, str(e)

# ===== גיבוי אוטומטי לתיק האישי =====
# לפני כל שינוי נשמר עותק של המצב הקודם, כדי ששינוי שגוי יהיה בר-ביטול.
PORTFOLIO_BAK = Path('/content/drive/MyDrive/base44/portfolio_backup.json')

def _backup_portfolio():
    try:
        cur = load_portfolio()
        hist = []
        if PORTFOLIO_BAK.exists():
            hist = json.loads(PORTFOLIO_BAK.read_text(encoding='utf-8'))
            if not isinstance(hist, list):
                hist = []
        hist.insert(0, {"ts": datetime.now().strftime("%d/%m %H:%M"), "list": cur})
        PORTFOLIO_BAK.parent.mkdir(parents=True, exist_ok=True)
        PORTFOLIO_BAK.write_text(json.dumps(hist[:10], ensure_ascii=False), encoding='utf-8')
    except Exception:
        pass

def load_backups():
    try:
        if PORTFOLIO_BAK.exists():
            h = json.loads(PORTFOLIO_BAK.read_text(encoding='utf-8'))
            if isinstance(h, list):
                return h
    except Exception:
        pass
    return []

_save_portfolio_raw = save_portfolio

def save_portfolio(lst):
    """ עוטף את השמירה המקורית ומגבה את המצב הקודם לפניה. """
    _backup_portfolio()
    return _save_portfolio_raw(lst)


# ================= שמות ותחומים =================
# מוצג לצד הטיקר כדי שלא צריך לזכור מה כל סימול. אם טיקר לא ברשימה - מוצג הסימול בלבד.
STOCK_INFO = {
    "AAPL": ("Apple", "מכשירים"), "MSFT": ("Microsoft", "תוכנה וענן"),
    "GOOGL": ("Alphabet", "חיפוש ופרסום"), "AMZN": ("Amazon", "מסחר וענן"),
    "META": ("Meta", "רשתות חברתיות"), "TSLA": ("Tesla", "רכב חשמלי"),
    "NVDA": ("Nvidia", "שבבי AI"), "NFLX": ("Netflix", "סטרימינג"),
    "CRM": ("Salesforce", "תוכנה עסקית"), "ADBE": ("Adobe", "תוכנת עיצוב"),
    "INTU": ("Intuit", "תוכנה פיננסית"), "ORCL": ("Oracle", "מסדי נתונים"),
    "CSCO": ("Cisco", "ציוד רשת"), "IBM": ("IBM", "שירותי IT"),
    "SAP": ("SAP", "תוכנה עסקית"), "NOW": ("ServiceNow", "אוטומציה עסקית"),
    "SHOP": ("Shopify", "מסחר מקוון"), "UBER": ("Uber", "שירותי נסיעות"),
    "ABNB": ("Airbnb", "אירוח"), "SPOT": ("Spotify", "מוזיקה"),
    "MU": ("Micron", "זיכרון"), "WDC": ("Western Digital", "אחסון"),
    "STX": ("Seagate", "אחסון"), "RMBS": ("Rambus", "קניין רוחני שבבים"),
    "MRAM": ("Everspin", "זיכרון MRAM"), "INTC": ("Intel", "מעבדים"),
    "AMD": ("AMD", "מעבדים"), "TSM": ("TSMC", "ייצור שבבים"),
    "AVGO": ("Broadcom", "שבבי תקשורת"), "QCOM": ("Qualcomm", "שבבי מובייל"),
    "TXN": ("Texas Instruments", "שבבים אנלוגיים"), "AMAT": ("Applied Materials", "ציוד ייצור"),
    "LRCX": ("Lam Research", "ציוד ייצור"), "KLAC": ("KLA", "בקרת ייצור"),
    "ASML": ("ASML", "ליתוגרפיה"), "MRVL": ("Marvell", "שבבי תשתית"),
    "ARM": ("Arm Holdings", "ארכיטקטורת שבבים"), "NXPI": ("NXP", "שבבי רכב"),
    "ADI": ("Analog Devices", "שבבים אנלוגיים"), "ON": ("ON Semiconductor", "שבבי הספק"),
    "SNPS": ("Synopsys", "תכנון שבבים"), "CDNS": ("Cadence", "תכנון שבבים"),
    "TER": ("Teradyne", "בדיקת שבבים"), "ENTG": ("Entegris", "חומרי ייצור"),
    "PLTR": ("Palantir", "ניתוח נתונים"), "SNOW": ("Snowflake", "מחסני נתונים"),
    "DDOG": ("Datadog", "ניטור"), "MDB": ("MongoDB", "מסדי נתונים"),
    "NET": ("Cloudflare", "תשתית רשת"), "CFLT": ("Confluent", "זרימת נתונים"),
    "PATH": ("UiPath", "אוטומציה"), "AI": ("C3.ai", "AI ארגוני"),
    "SOUN": ("SoundHound", "זיהוי קול"), "BBAI": ("BigBear.ai", "AI ביטחוני"),
    "SYM": ("Symbotic", "רובוטיקה למחסנים"), "MNDY": ("Monday.com", "ניהול עבודה"),
    "ESTC": ("Elastic", "חיפוש נתונים"), "GTLB": ("GitLab", "פיתוח תוכנה"),
    "ISRG": ("Intuitive Surgical", "רובוטיקה רפואית"), "ABB": ("ABB", "אוטומציה תעשייתית"),
    "ROK": ("Rockwell", "אוטומציה תעשייתית"), "FANUY": ("Fanuc", "רובוטים תעשייתיים"),
    "IRBT": ("iRobot", "רובוטיקה ביתית"), "SERV": ("Serve Robotics", "רובוטי משלוח"),
    "CRWD": ("CrowdStrike", "הגנת קצה"), "PANW": ("Palo Alto", "אבטחת רשת"),
    "FTNT": ("Fortinet", "אבטחת רשת"), "ZS": ("Zscaler", "אבטחת ענן"),
    "OKTA": ("Okta", "ניהול זהויות"), "CHKP": ("Check Point", "אבטחת רשת"),
    "CYBR": ("CyberArk", "הרשאות גישה"), "S": ("SentinelOne", "הגנת קצה"),
    "TENB": ("Tenable", "ניהול חשיפות"), "VRNS": ("Varonis", "אבטחת מידע"),
    "QLYS": ("Qualys", "סריקת פגיעויות"), "RPD": ("Rapid7", "אבטחת מידע"),
    "IONQ": ("IonQ", "מחשוב קוונטי"), "QBTS": ("D-Wave", "מחשוב קוונטי"),
    "RGTI": ("Rigetti", "מחשוב קוונטי"), "QUBT": ("Quantum Computing", "מחשוב קוונטי"),
    "LMT": ("Lockheed Martin", "מטוסי קרב"), "RTX": ("RTX", "מערכות הגנה"),
    "NOC": ("Northrop Grumman", "מערכות חלל"), "GD": ("General Dynamics", "כלי שיט וקרקע"),
    "LHX": ("L3Harris", "תקשורת ביטחונית"), "BA": ("Boeing", "תעופה"),
    "HII": ("Huntington Ingalls", "בניית ספינות"), "TXT": ("Textron", "מסוקים"),
    "RKLB": ("Rocket Lab", "שיגורים"), "AVAV": ("AeroVironment", "כלי טיס בלתי מאוישים"),
    "KTOS": ("Kratos", "מערכות בלתי מאוישות"), "LDOS": ("Leidos", "שירותי ביטחון"),
    "ESLT": ("Elbit Systems", "מערכות ביטחון"), "PLTK": ("Playtika", "גיימינג"),
    "SPCE": ("Virgin Galactic", "תיירות חלל"), "ASTS": ("AST SpaceMobile", "לוויינים סלולריים"),
    "IRDM": ("Iridium", "תקשורת לוויינית"), "PL": ("Planet Labs", "צילום לוויני"),
    "LUNR": ("Intuitive Machines", "נחיתות ירח"), "RDW": ("Redwire", "תשתית חלל"),
    "CCJ": ("Cameco", "כריית אורניום"), "UEC": ("Uranium Energy", "כריית אורניום"),
    "URA": ("Uranium ETF", "סל אורניום"), "SMR": ("NuScale", "כורים מודולריים"),
    "BWXT": ("BWX Technologies", "רכיבים גרעיניים"), "NLR": ("Nuclear ETF", "סל גרעיני"),
    "URNM": ("Uranium Miners ETF", "סל כורים"), "DNN": ("Denison Mines", "כריית אורניום"),
    "LEU": ("Centrus Energy", "העשרת אורניום"), "OKLO": ("Oklo", "כורים קטנים"),
    "XOM": ("Exxon Mobil", "נפט וגז"), "CVX": ("Chevron", "נפט וגז"),
    "COP": ("ConocoPhillips", "הפקת נפט"), "SLB": ("SLB", "שירותי קידוח"),
    "HAL": ("Halliburton", "שירותי קידוח"), "EOG": ("EOG Resources", "הפקת נפט"),
    "OXY": ("Occidental", "נפט וגז"), "PSX": ("Phillips 66", "זיקוק"),
    "MPC": ("Marathon Petroleum", "זיקוק"), "KMI": ("Kinder Morgan", "צנרת"),
    "ENPH": ("Enphase", "ממירים סולאריים"), "FSLR": ("First Solar", "פאנלים סולאריים"),
    "SEDG": ("SolarEdge", "ממירים סולאריים"), "RUN": ("Sunrun", "סולארי ביתי"),
    "PLUG": ("Plug Power", "מימן"), "BE": ("Bloom Energy", "תאי דלק"),
    "NEE": ("NextEra Energy", "אנרגיה מתחדשת"), "GEV": ("GE Vernova", "ציוד חשמל"),
    "VST": ("Vistra", "ייצור חשמל"), "CEG": ("Constellation Energy", "חשמל גרעיני"),
    "FCX": ("Freeport-McMoRan", "כריית נחושת"), "NEM": ("Newmont", "כריית זהב"),
    "GOLD": ("Barrick", "כריית זהב"), "AA": ("Alcoa", "אלומיניום"),
    "SCCO": ("Southern Copper", "נחושת"), "MP": ("MP Materials", "מתכות נדירות"),
    "ALB": ("Albemarle", "ליתיום"), "X": ("US Steel", "פלדה"),
    "NUE": ("Nucor", "פלדה"), "CLF": ("Cleveland-Cliffs", "פלדה"),
    "DE": ("John Deere", "ציוד חקלאי"), "ADM": ("Archer-Daniels", "עיבוד תבואה"),
    "BG": ("Bunge", "סחר חקלאי"), "MOS": ("Mosaic", "דשנים"),
    "CF": ("CF Industries", "דשנים"), "NTR": ("Nutrien", "דשנים"),
    "CTVA": ("Corteva", "זרעים והגנת צמח"), "FMC": ("FMC", "כימיקלים חקלאיים"),
    "TSN": ("Tyson Foods", "עיבוד בשר"), "KHC": ("Kraft Heinz", "מזון ארוז"),
    "GIS": ("General Mills", "מזון ארוז"), "HSY": ("Hershey", "ממתקים"),
    "JPM": ("JPMorgan", "בנקאות"), "BAC": ("Bank of America", "בנקאות"),
    "WFC": ("Wells Fargo", "בנקאות"), "GS": ("Goldman Sachs", "בנקאות השקעות"),
    "MS": ("Morgan Stanley", "בנקאות השקעות"), "C": ("Citigroup", "בנקאות"),
    "BLK": ("BlackRock", "ניהול נכסים"), "SCHW": ("Charles Schwab", "ברוקראז'"),
    "AXP": ("American Express", "כרטיסי אשראי"), "V": ("Visa", "תשלומים"),
    "MA": ("Mastercard", "תשלומים"), "PYPL": ("PayPal", "תשלומים"),
    "SQ": ("Block", "תשלומים"), "SOFI": ("SoFi", "בנקאות דיגיטלית"),
    "COIN": ("Coinbase", "מסחר בקריפטו"), "HOOD": ("Robinhood", "ברוקראז'"),
    "MSTR": ("MicroStrategy", "החזקות ביטקוין"), "MARA": ("Marathon Digital", "כריית ביטקוין"),
    "RIOT": ("Riot Platforms", "כריית ביטקוין"), "CLSK": ("CleanSpark", "כריית ביטקוין"),
    "JNJ": ("Johnson & Johnson", "פארמה"), "UNH": ("UnitedHealth", "ביטוח בריאות"),
    "LLY": ("Eli Lilly", "פארמה"), "NVO": ("Novo Nordisk", "פארמה"),
    "PFE": ("Pfizer", "פארמה"), "MRK": ("Merck", "פארמה"),
    "ABBV": ("AbbVie", "פארמה"), "TMO": ("Thermo Fisher", "ציוד מעבדה"),
    "VRTX": ("Vertex", "ביוטכנולוגיה"), "AMGN": ("Amgen", "ביוטכנולוגיה"),
    "GILD": ("Gilead", "ביוטכנולוגיה"), "REGN": ("Regeneron", "ביוטכנולוגיה"),
    "BMY": ("Bristol Myers", "פארמה"), "MRNA": ("Moderna", "חיסונים"),
    "BIIB": ("Biogen", "ביוטכנולוגיה"), "ABT": ("Abbott", "ציוד רפואי"),
    "MDT": ("Medtronic", "ציוד רפואי"), "SYK": ("Stryker", "ציוד רפואי"),
    "BSX": ("Boston Scientific", "ציוד רפואי"), "DXCM": ("Dexcom", "ניטור סוכר"),
    "CAT": ("Caterpillar", "ציוד כבד"), "HON": ("Honeywell", "תעשייה מגוונת"),
    "GE": ("GE Aerospace", "מנועי מטוסים"), "MMM": ("3M", "תעשייה מגוונת"),
    "UNP": ("Union Pacific", "רכבות"), "UPS": ("UPS", "משלוחים"),
    "FDX": ("FedEx", "משלוחים"), "ETN": ("Eaton", "ניהול חשמל"),
    "ITW": ("Illinois Tool Works", "ציוד תעשייתי"), "EMR": ("Emerson", "אוטומציה"),
    "PH": ("Parker Hannifin", "מערכות תנועה"), "TT": ("Trane", "מיזוג אוויר"),
    "CSX": ("CSX", "רכבות"), "NSC": ("Norfolk Southern", "רכבות"),
    "DAL": ("Delta Air Lines", "תעופה"), "UAL": ("United Airlines", "תעופה"),
    "LUV": ("Southwest", "תעופה"), "PWR": ("Quanta Services", "תשתיות חשמל"),
    "VMC": ("Vulcan Materials", "אגרגטים"), "MLM": ("Martin Marietta", "אגרגטים"),
    "URI": ("United Rentals", "השכרת ציוד"), "J": ("Jacobs", "הנדסה"),
    "WMT": ("Walmart", "קמעונאות"), "TGT": ("Target", "קמעונאות"),
    "COST": ("Costco", "מועדון סיטונאי"), "HD": ("Home Depot", "שיפוץ הבית"),
    "LOW": ("Lowe's", "שיפוץ הבית"), "SBUX": ("Starbucks", "בתי קפה"),
    "MCD": ("McDonald's", "מסעדות"), "NKE": ("Nike", "הנעלה וביגוד"),
    "LULU": ("Lululemon", "ביגוד ספורט"), "CMG": ("Chipotle", "מסעדות"),
    "KO": ("Coca-Cola", "משקאות"), "PEP": ("PepsiCo", "משקאות וחטיפים"),
    "PG": ("Procter & Gamble", "מוצרי צריכה"), "DIS": ("Disney", "בידור"),
    "BKNG": ("Booking", "תיירות"), "MAR": ("Marriott", "מלונאות"),
    "RCL": ("Royal Caribbean", "שיוט"), "CCL": ("Carnival", "שיוט"),
    "LVS": ("Las Vegas Sands", "קזינו"), "DKNG": ("DraftKings", "הימורים"),
    "T": ("AT&T", "תקשורת"), "VZ": ("Verizon", "תקשורת"),
    "TMUS": ("T-Mobile", "תקשורת"), "CMCSA": ("Comcast", "כבלים"),
    "WBD": ("Warner Bros Discovery", "תוכן"), "PARA": ("Paramount", "תוכן"),
    "PLD": ("Prologis", "לוגיסטיקה REIT"), "AMT": ("American Tower", "אנטנות REIT"),
    "EQIX": ("Equinix", "מרכזי נתונים REIT"), "DLR": ("Digital Realty", "מרכזי נתונים REIT"),
    "SPG": ("Simon Property", "קניונים REIT"), "O": ("Realty Income", "נדלן מניב"),
    "AWK": ("American Water", "מים"), "WM": ("Waste Management", "פסולת"),
    "RSG": ("Republic Services", "פסולת"), "XYL": ("Xylem", "טכנולוגיות מים"),
    "ECL": ("Ecolab", "טיפול במים"), "VLTO": ("Veralto", "איכות מים"),
    "BRK-B": ("Berkshire Hathaway", "החזקות"), "PGR": ("Progressive", "ביטוח"),
    "TRV": ("Travelers", "ביטוח"), "ALL": ("Allstate", "ביטוח"),
    "CB": ("Chubb", "ביטוח"), "AIG": ("AIG", "ביטוח"),
    "ANET": ("Arista Networks", "ציוד רשת"), "AAOI": ("Applied Optoelectronics", "אופטיקה"),
    "OUST": ("Ouster", "חיישני לידאר"), "BNO": ("Brent Oil ETF", "סל נפט"),
    "SPY": ("S&P 500 ETF", "מדד רחב"), "QQQ": ("Nasdaq 100 ETF", "מדד טכנולוגיה"),
    "DIA": ("Dow Jones ETF", "מדד תעשייתי"), "IWM": ("Russell 2000 ETF", "מניות קטנות"),
    "VOO": ("Vanguard S&P 500", "מדד רחב"), "RSP": ("S&P משוקלל שווה", "מדד רחב"),
    "SMH": ("Semiconductor ETF", "סל שבבים"), "SOXX": ("Semiconductor ETF", "סל שבבים"),
    "XLK": ("Technology ETF", "סל טכנולוגיה"), "XLV": ("Healthcare ETF", "סל בריאות"),
    "XLE": ("Energy ETF", "סל אנרגיה"), "XLF": ("Financials ETF", "סל פיננסים"),
    "XLI": ("Industrials ETF", "סל תעשייה"), "XLP": ("Staples ETF", "סל צריכה בסיסית"),
    "XLU": ("Utilities ETF", "סל תשתיות"), "XLRE": ("Real Estate ETF", "סל נדלן"),
    "ARKK": ("ARK Innovation", "חדשנות"), "GLD": ("Gold ETF", "זהב"),
    "GLDM": ("Gold MiniShares", "זהב"), "SLV": ("Silver ETF", "כסף"),
    "TLT": ("20+ Year Treasury", "אגח ארוך"), "SPMO": ("S&P Momentum", "מומנטום"),
    "USO": ("Oil Fund", "נפט"), "UNG": ("Natural Gas Fund", "גז טבעי"),
    "DBA": ("Agriculture Fund", "סחורות חקלאיות"), "COPX": ("Copper Miners", "כריית נחושת"),
    "ICLN": ("Clean Energy ETF", "אנרגיה נקייה"), "TAN": ("Solar ETF", "סולארי"),
    "BOTZ": ("Robotics ETF", "רובוטיקה"), "ARKX": ("Space ETF", "חלל"),
    "IBIT": ("Bitcoin ETF", "ביטקוין"), "HACK": ("Cybersecurity ETF", "סייבר"),
}

def stock_label(t):
    """ מחזיר תווית תצוגה: שם החברה אם ידוע, אחרת הסימול. """
    info = STOCK_INFO.get(t)
    return info[0] if info else t

def stock_sector(t):
    info = STOCK_INFO.get(t)
    return info[1] if info else ""

# ================= תיק אישי נשמר (Drive) =================
PORTFOLIO_FILE = Path('/content/drive/MyDrive/base44/portfolio.json')

DEFAULT_PORTFOLIO = ["ADBE", "AMZN", "ANET", "ARM", "AVGO", "BLK", "BNO", "CAT", "CVX",
                     "ETN", "GLD", "GLDM", "IWM", "KO", "LMT", "MA", "MSFT", "NVDA",
                     "QQQ", "RSP", "RTX", "SCHW", "SMR", "SPMO", "TT", "XLV", "AAOI", "OUST"]

def load_portfolio():
    """ טוען את התיק האישי מ-Drive. אם אין קובץ - מחזיר את ברירת המחדל.
    השמירה ב-Drive ולא בזיכרון כדי שהתיק ישרוד איפוס של הרנטיים. """
    try:
        if PORTFOLIO_FILE.exists():
            data = json.loads(PORTFOLIO_FILE.read_text(encoding='utf-8'))
            if isinstance(data, list) and data:
                return [str(x).upper() for x in data]
    except Exception:
        pass
    return list(DEFAULT_PORTFOLIO)

def save_portfolio(lst):
    try:
        PORTFOLIO_FILE.parent.mkdir(parents=True, exist_ok=True)
        PORTFOLIO_FILE.write_text(json.dumps(sorted(set(lst)), ensure_ascii=False),
                                   encoding='utf-8')
        return True, None
    except Exception as e:
        return False, str(e)

# ================= שמות ותחומים =================
# מוצג לצד הטיקר כדי שלא צריך לזכור מה כל סימול. אם טיקר לא ברשימה - מוצג הסימול בלבד.
STOCK_INFO = {
    "LCID": ("Lucid", "רכב חשמלי"),
    "WBA": ("Walgreens", "בתי מרקחת"),
    "PTON": ("Peloton", "כושר ביתי"),
    "GME": ("GameStop", "קמעונאות גיימינג"),
    "BBBY": ("Bed Bath Beyond", "קמעונאות בית"),
    "NKLA": ("Nikola", "משאיות חשמל"),
    "WISH": ("ContextLogic", "מסחר מקוון"),
    "GOEV": ("Canoo", "רכב חשמלי"),
    "FSR": ("Fisker", "רכב חשמלי"),
    "AMC": ("AMC", "בתי קולנוע"),
    "BYND": ("Beyond Meat", "תחליפי בשר"),
    "RIDE": ("Lordstown", "רכב חשמלי"),
    "WKHS": ("Workhorse", "רכב מסחרי"),
    "SDC": ("SmileDirectClub", "יישור שיניים"),
    "CLOV": ("Clover Health", "ביטוח בריאות"),
    "OPEN": ("Opendoor", "נדלן דיגיטלי"),
    "OATLY": ("Oatly", "משקאות שיבולת"),
    "FCEL": ("FuelCell", "תאי דלק"),
    "BLDP": ("Ballard", "תאי דלק"),
    "HUT": ("Hut 8", "כריית ביטקוין"),
    "BITF": ("Bitfarms", "כריית ביטקוין"),
    "UPST": ("Upstart", "אשראי AI"),
    "AFRM": ("Affirm", "אשראי צרכני"),
    "RDFN": ("Redfin", "נדלן דיגיטלי"),
    "NXE": ("NexGen", "אורניום"),
    "VTRS": ("Viatris", "גנריקה"),
    "TDOC": ("Teladoc", "רפואה מרחוק"),
    "JOBY": ("Joby", "מוניות אוויר"),
    "ACHR": ("Archer", "מוניות אוויר"),
    "ROOT": ("Root", "ביטוח דיגיטלי"),
    "AAPL": ("Apple", "מכשירים"), "MSFT": ("Microsoft", "תוכנה וענן"),
    "GOOGL": ("Alphabet", "חיפוש ופרסום"), "AMZN": ("Amazon", "מסחר וענן"),
    "META": ("Meta", "רשתות חברתיות"), "TSLA": ("Tesla", "רכב חשמלי"),
    "NVDA": ("Nvidia", "שבבי AI"), "NFLX": ("Netflix", "סטרימינג"),
    "CRM": ("Salesforce", "תוכנה עסקית"), "ADBE": ("Adobe", "תוכנת עיצוב"),
    "INTU": ("Intuit", "תוכנה פיננסית"), "ORCL": ("Oracle", "מסדי נתונים"),
    "CSCO": ("Cisco", "ציוד רשת"), "IBM": ("IBM", "שירותי IT"),
    "SAP": ("SAP", "תוכנה עסקית"), "NOW": ("ServiceNow", "אוטומציה עסקית"),
    "SHOP": ("Shopify", "מסחר מקוון"), "UBER": ("Uber", "שירותי נסיעות"),
    "ABNB": ("Airbnb", "אירוח"), "SPOT": ("Spotify", "מוזיקה"),
    "MU": ("Micron", "זיכרון"), "WDC": ("Western Digital", "אחסון"),
    "STX": ("Seagate", "אחסון"), "RMBS": ("Rambus", "קניין רוחני שבבים"),
    "MRAM": ("Everspin", "זיכרון MRAM"), "INTC": ("Intel", "מעבדים"),
    "AMD": ("AMD", "מעבדים"), "TSM": ("TSMC", "ייצור שבבים"),
    "AVGO": ("Broadcom", "שבבי תקשורת"), "QCOM": ("Qualcomm", "שבבי מובייל"),
    "TXN": ("Texas Instruments", "שבבים אנלוגיים"), "AMAT": ("Applied Materials", "ציוד ייצור"),
    "LRCX": ("Lam Research", "ציוד ייצור"), "KLAC": ("KLA", "בקרת ייצור"),
    "ASML": ("ASML", "ליתוגרפיה"), "MRVL": ("Marvell", "שבבי תשתית"),
    "ARM": ("Arm Holdings", "ארכיטקטורת שבבים"), "NXPI": ("NXP", "שבבי רכב"),
    "ADI": ("Analog Devices", "שבבים אנלוגיים"), "ON": ("ON Semiconductor", "שבבי הספק"),
    "SNPS": ("Synopsys", "תכנון שבבים"), "CDNS": ("Cadence", "תכנון שבבים"),
    "TER": ("Teradyne", "בדיקת שבבים"), "ENTG": ("Entegris", "חומרי ייצור"),
    "PLTR": ("Palantir", "ניתוח נתונים"), "SNOW": ("Snowflake", "מחסני נתונים"),
    "DDOG": ("Datadog", "ניטור"), "MDB": ("MongoDB", "מסדי נתונים"),
    "NET": ("Cloudflare", "תשתית רשת"), "CFLT": ("Confluent", "זרימת נתונים"),
    "PATH": ("UiPath", "אוטומציה"), "AI": ("C3.ai", "AI ארגוני"),
    "SOUN": ("SoundHound", "זיהוי קול"), "BBAI": ("BigBear.ai", "AI ביטחוני"),
    "SYM": ("Symbotic", "רובוטיקה למחסנים"), "MNDY": ("Monday.com", "ניהול עבודה"),
    "ESTC": ("Elastic", "חיפוש נתונים"), "GTLB": ("GitLab", "פיתוח תוכנה"),
    "ISRG": ("Intuitive Surgical", "רובוטיקה רפואית"), "ABB": ("ABB", "אוטומציה תעשייתית"),
    "ROK": ("Rockwell", "אוטומציה תעשייתית"), "FANUY": ("Fanuc", "רובוטים תעשייתיים"),
    "IRBT": ("iRobot", "רובוטיקה ביתית"), "SERV": ("Serve Robotics", "רובוטי משלוח"),
    "CRWD": ("CrowdStrike", "הגנת קצה"), "PANW": ("Palo Alto", "אבטחת רשת"),
    "FTNT": ("Fortinet", "אבטחת רשת"), "ZS": ("Zscaler", "אבטחת ענן"),
    "OKTA": ("Okta", "ניהול זהויות"), "CHKP": ("Check Point", "אבטחת רשת"),
    "CYBR": ("CyberArk", "הרשאות גישה"), "S": ("SentinelOne", "הגנת קצה"),
    "TENB": ("Tenable", "ניהול חשיפות"), "VRNS": ("Varonis", "אבטחת מידע"),
    "QLYS": ("Qualys", "סריקת פגיעויות"), "RPD": ("Rapid7", "אבטחת מידע"),
    "IONQ": ("IonQ", "מחשוב קוונטי"), "QBTS": ("D-Wave", "מחשוב קוונטי"),
    "RGTI": ("Rigetti", "מחשוב קוונטי"), "QUBT": ("Quantum Computing", "מחשוב קוונטי"),
    "LMT": ("Lockheed Martin", "מטוסי קרב"), "RTX": ("RTX", "מערכות הגנה"),
    "NOC": ("Northrop Grumman", "מערכות חלל"), "GD": ("General Dynamics", "כלי שיט וקרקע"),
    "LHX": ("L3Harris", "תקשורת ביטחונית"), "BA": ("Boeing", "תעופה"),
    "HII": ("Huntington Ingalls", "בניית ספינות"), "TXT": ("Textron", "מסוקים"),
    "RKLB": ("Rocket Lab", "שיגורים"), "AVAV": ("AeroVironment", "כלי טיס בלתי מאוישים"),
    "KTOS": ("Kratos", "מערכות בלתי מאוישות"), "LDOS": ("Leidos", "שירותי ביטחון"),
    "ESLT": ("Elbit Systems", "מערכות ביטחון"), "PLTK": ("Playtika", "גיימינג"),
    "SPCE": ("Virgin Galactic", "תיירות חלל"), "ASTS": ("AST SpaceMobile", "לוויינים סלולריים"),
    "IRDM": ("Iridium", "תקשורת לוויינית"), "PL": ("Planet Labs", "צילום לוויני"),
    "LUNR": ("Intuitive Machines", "נחיתות ירח"), "RDW": ("Redwire", "תשתית חלל"),
    "CCJ": ("Cameco", "כריית אורניום"), "UEC": ("Uranium Energy", "כריית אורניום"),
    "URA": ("Uranium ETF", "סל אורניום"), "SMR": ("NuScale", "כורים מודולריים"),
    "BWXT": ("BWX Technologies", "רכיבים גרעיניים"), "NLR": ("Nuclear ETF", "סל גרעיני"),
    "URNM": ("Uranium Miners ETF", "סל כורים"), "DNN": ("Denison Mines", "כריית אורניום"),
    "LEU": ("Centrus Energy", "העשרת אורניום"), "OKLO": ("Oklo", "כורים קטנים"),
    "XOM": ("Exxon Mobil", "נפט וגז"), "CVX": ("Chevron", "נפט וגז"),
    "COP": ("ConocoPhillips", "הפקת נפט"), "SLB": ("SLB", "שירותי קידוח"),
    "HAL": ("Halliburton", "שירותי קידוח"), "EOG": ("EOG Resources", "הפקת נפט"),
    "OXY": ("Occidental", "נפט וגז"), "PSX": ("Phillips 66", "זיקוק"),
    "MPC": ("Marathon Petroleum", "זיקוק"), "KMI": ("Kinder Morgan", "צנרת"),
    "ENPH": ("Enphase", "ממירים סולאריים"), "FSLR": ("First Solar", "פאנלים סולאריים"),
    "SEDG": ("SolarEdge", "ממירים סולאריים"), "RUN": ("Sunrun", "סולארי ביתי"),
    "PLUG": ("Plug Power", "מימן"), "BE": ("Bloom Energy", "תאי דלק"),
    "NEE": ("NextEra Energy", "אנרגיה מתחדשת"), "GEV": ("GE Vernova", "ציוד חשמל"),
    "VST": ("Vistra", "ייצור חשמל"), "CEG": ("Constellation Energy", "חשמל גרעיני"),
    "FCX": ("Freeport-McMoRan", "כריית נחושת"), "NEM": ("Newmont", "כריית זהב"),
    "GOLD": ("Barrick", "כריית זהב"), "AA": ("Alcoa", "אלומיניום"),
    "SCCO": ("Southern Copper", "נחושת"), "MP": ("MP Materials", "מתכות נדירות"),
    "ALB": ("Albemarle", "ליתיום"), "X": ("US Steel", "פלדה"),
    "NUE": ("Nucor", "פלדה"), "CLF": ("Cleveland-Cliffs", "פלדה"),
    "DE": ("John Deere", "ציוד חקלאי"), "ADM": ("Archer-Daniels", "עיבוד תבואה"),
    "BG": ("Bunge", "סחר חקלאי"), "MOS": ("Mosaic", "דשנים"),
    "CF": ("CF Industries", "דשנים"), "NTR": ("Nutrien", "דשנים"),
    "CTVA": ("Corteva", "זרעים והגנת צמח"), "FMC": ("FMC", "כימיקלים חקלאיים"),
    "TSN": ("Tyson Foods", "עיבוד בשר"), "KHC": ("Kraft Heinz", "מזון ארוז"),
    "GIS": ("General Mills", "מזון ארוז"), "HSY": ("Hershey", "ממתקים"),
    "JPM": ("JPMorgan", "בנקאות"), "BAC": ("Bank of America", "בנקאות"),
    "WFC": ("Wells Fargo", "בנקאות"), "GS": ("Goldman Sachs", "בנקאות השקעות"),
    "MS": ("Morgan Stanley", "בנקאות השקעות"), "C": ("Citigroup", "בנקאות"),
    "BLK": ("BlackRock", "ניהול נכסים"), "SCHW": ("Charles Schwab", "ברוקראז'"),
    "AXP": ("American Express", "כרטיסי אשראי"), "V": ("Visa", "תשלומים"),
    "MA": ("Mastercard", "תשלומים"), "PYPL": ("PayPal", "תשלומים"),
    "SQ": ("Block", "תשלומים"), "SOFI": ("SoFi", "בנקאות דיגיטלית"),
    "COIN": ("Coinbase", "מסחר בקריפטו"), "HOOD": ("Robinhood", "ברוקראז'"),
    "MSTR": ("MicroStrategy", "החזקות ביטקוין"), "MARA": ("Marathon Digital", "כריית ביטקוין"),
    "RIOT": ("Riot Platforms", "כריית ביטקוין"), "CLSK": ("CleanSpark", "כריית ביטקוין"),
    "JNJ": ("Johnson & Johnson", "פארמה"), "UNH": ("UnitedHealth", "ביטוח בריאות"),
    "LLY": ("Eli Lilly", "פארמה"), "NVO": ("Novo Nordisk", "פארמה"),
    "PFE": ("Pfizer", "פארמה"), "MRK": ("Merck", "פארמה"),
    "ABBV": ("AbbVie", "פארמה"), "TMO": ("Thermo Fisher", "ציוד מעבדה"),
    "VRTX": ("Vertex", "ביוטכנולוגיה"), "AMGN": ("Amgen", "ביוטכנולוגיה"),
    "GILD": ("Gilead", "ביוטכנולוגיה"), "REGN": ("Regeneron", "ביוטכנולוגיה"),
    "BMY": ("Bristol Myers", "פארמה"), "MRNA": ("Moderna", "חיסונים"),
    "BIIB": ("Biogen", "ביוטכנולוגיה"), "ABT": ("Abbott", "ציוד רפואי"),
    "MDT": ("Medtronic", "ציוד רפואי"), "SYK": ("Stryker", "ציוד רפואי"),
    "BSX": ("Boston Scientific", "ציוד רפואי"), "DXCM": ("Dexcom", "ניטור סוכר"),
    "CAT": ("Caterpillar", "ציוד כבד"), "HON": ("Honeywell", "תעשייה מגוונת"),
    "GE": ("GE Aerospace", "מנועי מטוסים"), "MMM": ("3M", "תעשייה מגוונת"),
    "UNP": ("Union Pacific", "רכבות"), "UPS": ("UPS", "משלוחים"),
    "FDX": ("FedEx", "משלוחים"), "ETN": ("Eaton", "ניהול חשמל"),
    "ITW": ("Illinois Tool Works", "ציוד תעשייתי"), "EMR": ("Emerson", "אוטומציה"),
    "PH": ("Parker Hannifin", "מערכות תנועה"), "TT": ("Trane", "מיזוג אוויר"),
    "CSX": ("CSX", "רכבות"), "NSC": ("Norfolk Southern", "רכבות"),
    "DAL": ("Delta Air Lines", "תעופה"), "UAL": ("United Airlines", "תעופה"),
    "LUV": ("Southwest", "תעופה"), "PWR": ("Quanta Services", "תשתיות חשמל"),
    "VMC": ("Vulcan Materials", "אגרגטים"), "MLM": ("Martin Marietta", "אגרגטים"),
    "URI": ("United Rentals", "השכרת ציוד"), "J": ("Jacobs", "הנדסה"),
    "WMT": ("Walmart", "קמעונאות"), "TGT": ("Target", "קמעונאות"),
    "COST": ("Costco", "מועדון סיטונאי"), "HD": ("Home Depot", "שיפוץ הבית"),
    "LOW": ("Lowe's", "שיפוץ הבית"), "SBUX": ("Starbucks", "בתי קפה"),
    "MCD": ("McDonald's", "מסעדות"), "NKE": ("Nike", "הנעלה וביגוד"),
    "LULU": ("Lululemon", "ביגוד ספורט"), "CMG": ("Chipotle", "מסעדות"),
    "KO": ("Coca-Cola", "משקאות"), "PEP": ("PepsiCo", "משקאות וחטיפים"),
    "PG": ("Procter & Gamble", "מוצרי צריכה"), "DIS": ("Disney", "בידור"),
    "BKNG": ("Booking", "תיירות"), "MAR": ("Marriott", "מלונאות"),
    "RCL": ("Royal Caribbean", "שיוט"), "CCL": ("Carnival", "שיוט"),
    "LVS": ("Las Vegas Sands", "קזינו"), "DKNG": ("DraftKings", "הימורים"),
    "T": ("AT&T", "תקשורת"), "VZ": ("Verizon", "תקשורת"),
    "TMUS": ("T-Mobile", "תקשורת"), "CMCSA": ("Comcast", "כבלים"),
    "WBD": ("Warner Bros Discovery", "תוכן"), "PARA": ("Paramount", "תוכן"),
    "PLD": ("Prologis", "לוגיסטיקה REIT"), "AMT": ("American Tower", "אנטנות REIT"),
    "EQIX": ("Equinix", "מרכזי נתונים REIT"), "DLR": ("Digital Realty", "מרכזי נתונים REIT"),
    "SPG": ("Simon Property", "קניונים REIT"), "O": ("Realty Income", "נדלן מניב"),
    "AWK": ("American Water", "מים"), "WM": ("Waste Management", "פסולת"),
    "RSG": ("Republic Services", "פסולת"), "XYL": ("Xylem", "טכנולוגיות מים"),
    "ECL": ("Ecolab", "טיפול במים"), "VLTO": ("Veralto", "איכות מים"),
    "BRK-B": ("Berkshire Hathaway", "החזקות"), "PGR": ("Progressive", "ביטוח"),
    "TRV": ("Travelers", "ביטוח"), "ALL": ("Allstate", "ביטוח"),
    "CB": ("Chubb", "ביטוח"), "AIG": ("AIG", "ביטוח"),
    "ANET": ("Arista Networks", "ציוד רשת"), "AAOI": ("Applied Optoelectronics", "אופטיקה"),
    "OUST": ("Ouster", "חיישני לידאר"), "BNO": ("Brent Oil ETF", "סל נפט"),
    "SPY": ("S&P 500 ETF", "מדד רחב"), "QQQ": ("Nasdaq 100 ETF", "מדד טכנולוגיה"),
    "DIA": ("Dow Jones ETF", "מדד תעשייתי"), "IWM": ("Russell 2000 ETF", "מניות קטנות"),
    "VOO": ("Vanguard S&P 500", "מדד רחב"), "RSP": ("S&P משוקלל שווה", "מדד רחב"),
    "SMH": ("Semiconductor ETF", "סל שבבים"), "SOXX": ("Semiconductor ETF", "סל שבבים"),
    "XLK": ("Technology ETF", "סל טכנולוגיה"), "XLV": ("Healthcare ETF", "סל בריאות"),
    "XLE": ("Energy ETF", "סל אנרגיה"), "XLF": ("Financials ETF", "סל פיננסים"),
    "XLI": ("Industrials ETF", "סל תעשייה"), "XLP": ("Staples ETF", "סל צריכה בסיסית"),
    "XLU": ("Utilities ETF", "סל תשתיות"), "XLRE": ("Real Estate ETF", "סל נדלן"),
    "ARKK": ("ARK Innovation", "חדשנות"), "GLD": ("Gold ETF", "זהב"),
    "GLDM": ("Gold MiniShares", "זהב"), "SLV": ("Silver ETF", "כסף"),
    "TLT": ("20+ Year Treasury", "אגח ארוך"), "SPMO": ("S&P Momentum", "מומנטום"),
    "USO": ("Oil Fund", "נפט"), "UNG": ("Natural Gas Fund", "גז טבעי"),
    "DBA": ("Agriculture Fund", "סחורות חקלאיות"), "COPX": ("Copper Miners", "כריית נחושת"),
    "ICLN": ("Clean Energy ETF", "אנרגיה נקייה"), "TAN": ("Solar ETF", "סולארי"),
    "BOTZ": ("Robotics ETF", "רובוטיקה"), "ARKX": ("Space ETF", "חלל"),
    "IBIT": ("Bitcoin ETF", "ביטקוין"), "HACK": ("Cybersecurity ETF", "סייבר"),
}

def stock_label(t):
    """ מחזיר תווית תצוגה: שם החברה אם ידוע, אחרת הסימול. """
    info = STOCK_INFO.get(t)
    return info[0] if info else t

def stock_sector(t):
    info = STOCK_INFO.get(t)
    return info[1] if info else ""

# ================= קטגוריות מניות =================

# ================= רשימת מעקב =================
# מקבילה לתיק האישי: נשמרת ב-Drive, נערכת מהממשק, ומניה שנוספת אליה
# מקוטלגת גם לקטגוריה הסקטוריאלית שלה.
WATCHLIST_FILE = Path('/content/drive/MyDrive/base44/watchlist.json')
WATCHLIST_BAK = Path('/content/drive/MyDrive/base44/watchlist_backup.json')

def load_watchlist():
    try:
        if WATCHLIST_FILE.exists():
            d = json.loads(WATCHLIST_FILE.read_text(encoding='utf-8'))
            if isinstance(d, list):
                return [str(x).upper() for x in d]
    except Exception:
        pass
    return []

def save_watchlist(lst):
    try:
        cur = load_watchlist()
        hist = []
        if WATCHLIST_BAK.exists():
            try:
                hist = json.loads(WATCHLIST_BAK.read_text(encoding='utf-8'))
                if not isinstance(hist, list):
                    hist = []
            except Exception:
                hist = []
        hist.insert(0, {"ts": datetime.now().strftime("%d/%m %H:%M"), "list": cur})
        WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
        WATCHLIST_BAK.write_text(json.dumps(hist[:10], ensure_ascii=False), encoding='utf-8')
        WATCHLIST_FILE.write_text(json.dumps(sorted(set(lst)), ensure_ascii=False), encoding='utf-8')
        return True, None
    except Exception as e:
        return False, str(e)

def load_wl_backups():
    try:
        if WATCHLIST_BAK.exists():
            h = json.loads(WATCHLIST_BAK.read_text(encoding='utf-8'))
            if isinstance(h, list):
                return h
    except Exception:
        pass
    return []


CATEGORIES = {
    "🌍 יקום רחב (198)": [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "LLY", "JPM", "V", "UNH",
    "XOM", "MA", "JNJ", "PG", "COST", "HD", "WMT", "ABBV", "NFLX", "MRK", "KO", "PEP", "ADBE",
    "CVX", "CRM", "AMD", "BAC", "ORCL", "TMO", "ACN", "LIN", "MCD", "CSCO", "ABT", "PFE",
    "DHR", "WFC", "TXN", "DIS", "VZ", "INTU", "CAT", "AMGN", "QCOM", "CMCSA", "PM", "IBM",
    "NOW", "UNP", "SPGI", "GE", "NKE", "RTX", "HON", "COP", "LOW", "ELV", "BKNG", "T", "BA",
    "SBUX", "PLD", "BLK", "MDT", "DE", "LMT", "SYK", "ADI", "MMC", "TJX", "GILD", "AXP",
    "VRTX", "ISRG", "CVS", "SCHW", "MO", "CI", "ZTS", "REGN", "SO", "CB", "SLB", "ETN", "BSX",
    "PGR", "MU", "EOG", "DUK", "AON", "ITW", "APD", "CL", "NSC", "EMR", "FDX", "GM", "F",
    "DAL", "UAL", "LUV", "CCL", "RCL", "NCLH", "MAR", "HLT", "DKNG", "ROKU", "SNAP", "PINS",
    "UBER", "LYFT", "ABNB", "DASH", "SQ", "SHOP", "SPOT", "ZM", "DOCU", "TWLO", "NET", "DDOG",
    "SNOW", "CRWD", "ZS", "OKTA", "PANW", "FTNT", "TEAM", "WDAY", "VEEV", "HUBS", "MDB",
    "ETSY", "EBAY", "CHWY", "W", "PLUG", "FCEL", "BLDP", "RIOT", "MARA", "CLSK", "HUT", "BITF",
    "SOFI", "UPST", "AFRM", "OPEN", "RDFN", "CVNA", "PTON", "BYND", "OATLY", "LCID", "RIVN",
    "NKLA", "GOEV", "FSR", "WKHS", "RIDE", "SPCE", "JOBY", "ACHR", "AMC", "GME", "BBBY",
    "WISH", "CLOV", "SDC", "ROOT", "HOOD", "PLTR", "AI", "BBAI", "SOUN", "IONQ", "RGTI",
    "QBTS", "SMR", "OKLO", "NNE", "LEU", "UEC", "CCJ", "DNN", "NXE", "INTC", "PYPL", "MRNA",
    "WBA", "VTRS", "TDOC", "PENN", "CZR", "MGM"
    ],
    "🌍 יקום רחב · ענק": [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "LLY", "JPM", "V", "UNH",
    "XOM", "MA", "JNJ", "PG", "COST", "HD", "WMT", "ABBV", "NFLX", "MRK", "KO", "PEP", "ADBE",
    "CVX", "CRM", "AMD", "BAC", "ORCL", "TMO", "ACN", "LIN", "MCD", "CSCO", "ABT"
    ],
    "🌍 יקום רחב · קטנות ותנודתיות": [
    "PLUG", "FCEL", "BLDP", "RIOT", "MARA", "CLSK", "HUT", "BITF", "SOFI", "UPST", "AFRM",
    "OPEN", "RDFN", "CVNA", "PTON", "BYND", "OATLY", "LCID", "RIVN", "NKLA", "GOEV", "FSR",
    "WKHS", "RIDE", "SPCE", "JOBY", "ACHR", "AMC", "GME", "BBBY", "WISH", "CLOV", "SDC",
    "ROOT", "HOOD", "PLTR", "AI", "BBAI", "SOUN", "IONQ", "RGTI", "QBTS", "SMR", "OKLO", "NNE",
    "LEU", "UEC", "CCJ", "DNN", "NXE", "INTC", "PYPL", "MRNA", "WBA", "VTRS", "TDOC", "PENN",
    "CZR", "MGM"
    ],
    "💰 יקום סחיר (159)": [
    "SERV", "QUBT", "RGTI", "QBTS", "ASTS", "LUNR", "SMR", "BBAI", "OKLO", "SOUN", "PLUG",
    "CLSK", "IONQ", "SEDG", "BE", "RUN", "MARA", "SYM", "RIOT", "MSTR", "LEU", "RKLB", "ARM",
    "COIN", "MP", "ENPH", "UEC", "HOOD", "MRVL", "RMBS", "PLTR", "AI", "MRNA", "MDB", "MU",
    "INTC", "AVAV", "CLF", "MNDY", "PATH", "SOFI", "TSLA", "ALB", "UNG", "FMC", "TER", "DNN",
    "AMD", "SHOP", "WDC", "GTLB", "ESTC", "ON", "FSLR", "VST", "SNOW", "ENTG", "KTOS", "NET",
    "RPD", "DDOG", "GEV", "CEG", "AA", "STX", "IRDM", "OKTA", "LRCX", "WBD", "ORCL", "S",
    "AVGO", "UAL", "VRNS", "IBIT", "ZS", "AMAT", "CCJ", "KLAC", "DKNG", "DXCM", "CRWD", "NVDA",
    "CCL", "URNM", "SNPS", "FCX", "NXPI", "NOW", "ASML", "LULU", "URA", "NVO", "QCOM", "SLV",
    "SCCO", "SPOT", "RCL", "PANW", "TENB", "QLYS", "NEM", "DAL", "LUV", "FTNT", "TSM", "TAN",
    "ARKK", "SOXX", "URI", "PWR", "MOS", "COPX", "UBER", "PYPL", "BWXT", "META", "CDNS", "USO",
    "SMH", "UNH", "INTU", "HII", "ABNB", "TXN", "NKE", "CRM", "ADBE", "NLR", "LLY", "ADI",
    "TGT", "HAL", "CF", "IBM", "BA", "CMG", "ETN", "LVS", "NFLX", "NUE", "SLB", "SBUX", "ISRG",
    "MPC", "ROK", "AMZN", "CAT", "OXY", "REGN", "FDX", "GE", "CHKP", "PSX", "SAP", "GOOGL",
    "BIIB", "MMM", "BKNG"
    ],
    "💰 יקום סחיר · ליבה (120)": [
    "PATH", "SOFI", "TSLA", "ALB", "UNG", "FMC", "TER", "DNN", "AMD", "SHOP", "WDC", "GTLB",
    "ESTC", "ON", "FSLR", "VST", "SNOW", "ENTG", "KTOS", "NET", "RPD", "DDOG", "GEV", "CEG",
    "AA", "STX", "IRDM", "OKTA", "LRCX", "WBD", "ORCL", "S", "AVGO", "UAL", "VRNS", "IBIT",
    "ZS", "AMAT", "CCJ", "KLAC", "DKNG", "DXCM", "CRWD", "NVDA", "CCL", "URNM", "SNPS", "FCX",
    "NXPI", "NOW", "ASML", "LULU", "URA", "NVO", "QCOM", "SLV", "SCCO", "SPOT", "RCL", "PANW",
    "TENB", "QLYS", "NEM", "DAL", "LUV", "FTNT", "TSM", "TAN", "ARKK", "SOXX", "URI", "PWR",
    "MOS", "COPX", "UBER", "PYPL", "BWXT", "META", "CDNS", "USO", "SMH", "UNH", "INTU", "HII",
    "ABNB", "TXN", "NKE", "CRM", "ADBE", "NLR", "LLY", "ADI", "TGT", "HAL", "CF", "IBM", "BA",
    "CMG", "ETN", "LVS", "NFLX", "NUE", "SLB", "SBUX", "ISRG", "MPC", "ROK", "AMZN", "CAT",
    "OXY", "REGN", "FDX", "GE", "CHKP", "PSX", "SAP", "GOOGL", "BIIB", "MMM", "BKNG"
    ],
    "💰 יקום סחיר · ספקולטיבי (39)": [
    "SERV", "QUBT", "RGTI", "QBTS", "ASTS", "LUNR", "SMR", "BBAI", "OKLO", "SOUN", "PLUG",
    "CLSK", "IONQ", "SEDG", "BE", "RUN", "MARA", "SYM", "RIOT", "MSTR", "LEU", "RKLB", "ARM",
    "COIN", "MP", "ENPH", "UEC", "HOOD", "MRVL", "RMBS", "PLTR", "AI", "MRNA", "MDB", "MU",
    "INTC", "AVAV", "CLF", "MNDY"
    ],
    "🔬 ליבה≤45% (74)": [
    "BKNG", "MMM", "BIIB", "GOOGL", "SAP", "PSX", "CHKP", "GE", "FDX", "REGN", "OXY", "CAT",
    "AMZN", "ROK", "MPC", "ISRG", "SBUX", "SLB", "NUE", "NFLX", "LVS", "ETN", "CMG", "BA",
    "IBM", "CF", "HAL", "ADI", "TGT", "LLY", "NLR", "ADBE", "CRM", "NKE", "TXN", "ABNB", "HII",
    "INTU", "UNH", "SMH", "USO", "CDNS", "BWXT", "META", "PYPL", "UBER", "COPX", "MOS", "PWR",
    "URI", "SOXX", "ARKK", "TAN", "TSM", "FTNT", "LUV", "DAL", "NEM", "QLYS", "TENB", "PANW",
    "RCL", "SPOT", "SLV", "SCCO", "QCOM", "NVO", "URA", "LULU", "ASML", "NOW", "NXPI", "FCX",
    "SNPS"
    ],
    "🔬 ליבה≤50% (87)": [
    "BKNG", "MMM", "BIIB", "GOOGL", "SAP", "PSX", "CHKP", "GE", "FDX", "REGN", "OXY", "CAT",
    "AMZN", "ROK", "MPC", "ISRG", "SBUX", "SLB", "NUE", "NFLX", "LVS", "ETN", "CMG", "BA",
    "IBM", "CF", "HAL", "ADI", "TGT", "LLY", "NLR", "ADBE", "CRM", "NKE", "TXN", "ABNB", "HII",
    "INTU", "UNH", "SMH", "USO", "CDNS", "BWXT", "META", "PYPL", "UBER", "COPX", "MOS", "PWR",
    "URI", "SOXX", "ARKK", "TAN", "TSM", "FTNT", "LUV", "DAL", "NEM", "QLYS", "TENB", "PANW",
    "RCL", "SPOT", "SLV", "SCCO", "QCOM", "NVO", "URA", "LULU", "ASML", "NOW", "NXPI", "FCX",
    "SNPS", "URNM", "CCL", "NVDA", "CRWD", "DXCM", "DKNG", "KLAC", "CCJ", "AMAT", "ZS", "IBIT",
    "VRNS", "UAL"
    ],
    "🔬 ליבה≤55% (101)": [
    "BKNG", "MMM", "BIIB", "GOOGL", "SAP", "PSX", "CHKP", "GE", "FDX", "REGN", "OXY", "CAT",
    "AMZN", "ROK", "MPC", "ISRG", "SBUX", "SLB", "NUE", "NFLX", "LVS", "ETN", "CMG", "BA",
    "IBM", "CF", "HAL", "ADI", "TGT", "LLY", "NLR", "ADBE", "CRM", "NKE", "TXN", "ABNB", "HII",
    "INTU", "UNH", "SMH", "USO", "CDNS", "BWXT", "META", "PYPL", "UBER", "COPX", "MOS", "PWR",
    "URI", "SOXX", "ARKK", "TAN", "TSM", "FTNT", "LUV", "DAL", "NEM", "QLYS", "TENB", "PANW",
    "RCL", "SPOT", "SLV", "SCCO", "QCOM", "NVO", "URA", "LULU", "ASML", "NOW", "NXPI", "FCX",
    "SNPS", "URNM", "CCL", "NVDA", "CRWD", "DXCM", "DKNG", "KLAC", "CCJ", "AMAT", "ZS", "IBIT",
    "VRNS", "UAL", "AVGO", "S", "ORCL", "WBD", "LRCX", "OKTA", "IRDM", "STX", "AA", "CEG",
    "GEV", "RPD", "DDOG", "NET"
    ],
    "🔬 ליבה≤70% (133)": [
    "BKNG", "MMM", "BIIB", "GOOGL", "SAP", "PSX", "CHKP", "GE", "FDX", "REGN", "OXY", "CAT",
    "AMZN", "ROK", "MPC", "ISRG", "SBUX", "SLB", "NUE", "NFLX", "LVS", "ETN", "CMG", "BA",
    "IBM", "CF", "HAL", "ADI", "TGT", "LLY", "NLR", "ADBE", "CRM", "NKE", "TXN", "ABNB", "HII",
    "INTU", "UNH", "SMH", "USO", "CDNS", "BWXT", "META", "PYPL", "UBER", "COPX", "MOS", "PWR",
    "URI", "SOXX", "ARKK", "TAN", "TSM", "FTNT", "LUV", "DAL", "NEM", "QLYS", "TENB", "PANW",
    "RCL", "SPOT", "SLV", "SCCO", "QCOM", "NVO", "URA", "LULU", "ASML", "NOW", "NXPI", "FCX",
    "SNPS", "URNM", "CCL", "NVDA", "CRWD", "DXCM", "DKNG", "KLAC", "CCJ", "AMAT", "ZS", "IBIT",
    "VRNS", "UAL", "AVGO", "S", "ORCL", "WBD", "LRCX", "OKTA", "IRDM", "STX", "AA", "CEG",
    "GEV", "RPD", "DDOG", "NET", "KTOS", "ENTG", "SNOW", "VST", "FSLR", "ESTC", "ON", "GTLB",
    "WDC", "SHOP", "AMD", "DNN", "TER", "FMC", "UNG", "ALB", "TSLA", "SOFI", "PATH", "MNDY",
    "CLF", "AVAV", "INTC", "MU", "MDB", "MRNA", "AI", "PLTR", "RMBS", "MRVL", "HOOD", "UEC"
    ],
    "🔬 ליבה60 אימון (60)": [
    "AA", "ADI", "AMAT", "AMD", "ARKK", "ASML", "BIIB", "BKNG", "CCJ", "CCL", "CF", "COPX",
    "DAL", "DDOG", "DXCM", "ENTG", "ETN", "FMC", "FSLR", "GE", "GOOGL", "HAL", "IBIT", "IBM",
    "INTU", "IRDM", "KLAC", "LLY", "LUV", "LVS", "NKE", "NOW", "NUE", "NVDA", "NXPI", "OKTA",
    "ORCL", "OXY", "PATH", "RPD", "S", "SAP", "SHOP", "SLB", "SLV", "SMH", "SNPS", "SOXX",
    "STX", "TAN", "TENB", "TER", "TGT", "TSLA", "UBER", "UNH", "USO", "VST", "WDC", "ZS"
    ],
    "🔬 ליבה60 מבחן (60)": [
    "ABNB", "ADBE", "ALB", "AMZN", "AVGO", "BA", "BWXT", "CAT", "CDNS", "CEG", "CHKP", "CMG",
    "CRM", "CRWD", "DKNG", "DNN", "ESTC", "FCX", "FDX", "FTNT", "GEV", "GTLB", "HII", "ISRG",
    "KTOS", "LRCX", "LULU", "META", "MMM", "MOS", "MPC", "NEM", "NET", "NFLX", "NLR", "NVO",
    "ON", "PANW", "PSX", "PWR", "PYPL", "QCOM", "QLYS", "RCL", "REGN", "ROK", "SBUX", "SCCO",
    "SNOW", "SOFI", "SPOT", "TSM", "TXN", "UAL", "UNG", "URA", "URI", "URNM", "VRNS", "WBD"
    ],
    "🧩 סחיר·U0001F4BB שבבים וח (23)": [
    "ADI", "AMAT", "AMD", "ARM", "ASML", "AVGO", "CDNS", "ENTG", "INTC", "KLAC", "LRCX",
    "MRVL", "MU", "NXPI", "ON", "QCOM", "RMBS", "SNPS", "STX", "TER", "TSM", "TXN", "WDC"
    ],
    "🧩 סחיר·U0001F680 ענקיות ט (17)": [
    "ABNB", "ADBE", "AMZN", "CRM", "GOOGL", "IBM", "INTU", "META", "NFLX", "NOW", "NVDA",
    "ORCL", "SAP", "SHOP", "SPOT", "TSLA", "UBER"
    ],
    "🧩 סחיר·U0001F916 בינה מלא (13)": [
    "AI", "BBAI", "DDOG", "ESTC", "GTLB", "MDB", "MNDY", "NET", "PATH", "PLTR", "SNOW", "SOUN",
    "SYM"
    ],
    "🧩 סחיר·U0001F512 סייבר וא (11)": [
    "CHKP", "CRWD", "FTNT", "OKTA", "PANW", "QLYS", "RPD", "S", "TENB", "VRNS", "ZS"
    ],
    "🧩 סחיר·u2622uFE0F גרעיני (10)": [
    "BWXT", "CCJ", "DNN", "LEU", "NLR", "OKLO", "SMR", "UEC", "URA", "URNM"
    ],
    "🧩 סחיר·U0001F331 אנרגיה מ (10)": [
    "BE", "CEG", "ENPH", "FSLR", "GEV", "PLUG", "RUN", "SEDG", "TAN", "VST"
    ],
    "🧩 סחיר·u26CFuFE0F סחורות (10)": [
    "AA", "ALB", "CLF", "COPX", "FCX", "MP", "NEM", "NUE", "SCCO", "SLV"
    ],
    "🧩 סחיר·שאר (65)": [
    "ARKK", "ASTS", "AVAV", "BA", "BIIB", "BKNG", "CAT", "CCL", "CF", "CLSK", "CMG", "COIN",
    "DAL", "DKNG", "DXCM", "ETN", "FDX", "FMC", "GE", "HAL", "HII", "HOOD", "IBIT", "IONQ",
    "IRDM", "ISRG", "KTOS", "LLY", "LULU", "LUNR", "LUV", "LVS", "MARA", "MMM", "MOS", "MPC",
    "MRNA", "MSTR", "NKE", "NVO", "OXY", "PSX", "PWR", "PYPL", "QBTS", "QUBT", "RCL", "REGN",
    "RGTI", "RIOT", "RKLB", "ROK", "SBUX", "SERV", "SLB", "SMH", "SOFI", "SOXX", "TGT", "UAL",
    "UNG", "UNH", "URI", "USO", "WBD"
    ],
    "📊 מדדים לניהול (31)": [
    "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "RSP", "MDY", "XLK", "XLF", "XLV", "XLE", "XLI",
    "XLY", "XLP", "XLU", "XLB", "XLC", "XLRE", "SMH", "SOXX", "IGV", "XBI", "ITA", "TQQQ",
    "QLD", "SSO", "UPRO", "SPXL", "TECL", "SOXL"
    ],
    "📊 מדדים · רחבים (8)": [
    "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "RSP", "MDY"
    ],
    "📊 מדדים · סקטוריאליים (16)": [
    "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLC", "XLRE", "SMH",
    "SOXX", "IGV", "XBI", "ITA"
    ],
    "📊 מדדים · ממונפים (7)": [
    "TQQQ", "QLD", "SSO", "UPRO", "SPXL", "TECL", "SOXL"
    ],
    "\U0001F9EA תיק בדיקות (מהיר)": ["MSFT", "NVDA", "JPM", "CVX", "LLY", "CAT", "WMT", "LMT", "CRWD", "SMR", "GLD", "SPY"],
    "\U0001F4BC התיק האישי": load_portfolio(),
    "\U0001F680 ענקיות טכנולוגיה": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "NFLX", "CRM", "ADBE", "INTU", "ORCL", "CSCO", "IBM", "SAP", "NOW", "SHOP", "UBER", "ABNB", "SPOT"],
    "\U0001F4BB שבבים וחצי מוליכים": ["MU", "WDC", "STX", "RMBS", "MRAM", "INTC", "AMD", "TSM", "AVGO", "QCOM", "TXN", "AMAT", "LRCX", "KLAC", "ASML", "MRVL", "ARM", "NXPI", "ADI", "ON", "SNPS", "CDNS", "TER", "ENTG"],
    "\U0001F916 בינה מלאכותית וענן": ["PLTR", "SNOW", "DDOG", "MDB", "NET", "CFLT", "PATH", "AI", "SOUN", "BBAI", "SYM", "MNDY", "ESTC", "GTLB"],
    "\U0001F9BE רובוטיקה ואוטומציה": ["ISRG", "ROK", "SYM", "PATH", "IRBT", "SERV", "TER", "EMR", "HON", "BOTZ"],
    "\U0001F512 סייבר ואבטחת מידע": ["CRWD", "PANW", "FTNT", "ZS", "OKTA", "CHKP", "CYBR", "S", "TENB", "VRNS", "QLYS", "RPD", "HACK"],
    "\u269B\uFE0F מחשוב קוונטי": ["IONQ", "QBTS", "RGTI", "QUBT"],
    "\U0001F6E1\uFE0F ביטחון, צבא ונשק": ["LMT", "RTX", "NOC", "GD", "LHX", "BA", "HII", "TXT", "PLTR", "RKLB", "AVAV", "KTOS", "LDOS", "ESLT"],
    "\U0001F6F0\uFE0F חלל ולוויינים": ["RKLB", "ASTS", "IRDM", "PL", "LUNR", "RDW", "SPCE", "NOC", "BA", "ARKX"],
    "\u2622\uFE0F גרעיני ואורניום": ["CCJ", "UEC", "URA", "SMR", "BWXT", "NLR", "URNM", "DNN", "LEU", "OKLO"],
    "\U0001F50C אנרגיה מסורתית": ["XOM", "CVX", "COP", "SLB", "HAL", "EOG", "OXY", "PSX", "MPC", "KMI", "USO", "XLE"],
    "\U0001F331 אנרגיה מתחדשת ורשתות": ["ENPH", "FSLR", "SEDG", "RUN", "PLUG", "BE", "NEE", "GEV", "VST", "CEG", "ICLN", "TAN"],
    "\u26CF\uFE0F סחורות, מתכות וכרייה": ["FCX", "NEM", "GOLD", "AA", "SCCO", "MP", "ALB", "X", "NUE", "CLF", "COPX", "GLD", "SLV"],
    "\U0001F33E חקלאות, מזון ודשנים": ["DE", "ADM", "BG", "MOS", "CF", "NTR", "CTVA", "FMC", "TSN", "KHC", "GIS", "HSY", "DBA"],
    "\U0001F3E6 פיננסים ובנקים": ["JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "SCHW", "AXP", "BRK-B", "XLF"],
    "\U0001F4B3 תשלומים ופינטך": ["V", "MA", "PYPL", "SQ", "SOFI", "COIN", "HOOD", "AXP"],
    "\U0001FA99 קריפטו ובלוקצ'יין": ["COIN", "MSTR", "MARA", "RIOT", "CLSK", "HOOD", "IBIT"],
    "\U0001F48A ביוטכנולוגיה ופארמה": ["JNJ", "LLY", "NVO", "PFE", "MRK", "ABBV", "VRTX", "AMGN", "GILD", "REGN", "BMY", "MRNA", "BIIB"],
    "\U0001F3E5 בריאות וציוד רפואי": ["UNH", "TMO", "ABT", "MDT", "SYK", "BSX", "ISRG", "DXCM", "XLV"],
    "\U0001F3D7\uFE0F תשתיות ובנייה": ["PWR", "VMC", "MLM", "URI", "J", "CAT", "ETN", "GEV", "XLI"],
    "\U0001F3ED תעשייה מסורתית": ["CAT", "DE", "HON", "GE", "MMM", "UNP", "UPS", "FDX", "ETN", "ITW", "EMR", "PH", "TT"],
    "\U0001F69A תחבורה ולוגיסטיקה": ["UNP", "CSX", "NSC", "UPS", "FDX", "DAL", "UAL", "LUV", "UBER"],
    "\U0001F6D2 קמעונאות וצריכה": ["WMT", "TGT", "COST", "HD", "LOW", "SBUX", "MCD", "NKE", "LULU", "CMG", "KO", "PEP", "PG", "XLP"],
    "\U0001F3E8 תיירות, פנאי ובידור": ["BKNG", "MAR", "RCL", "CCL", "LVS", "DKNG", "ABNB", "DIS", "UBER"],
    "\U0001F4FA תקשורת ומדיה": ["T", "VZ", "TMUS", "CMCSA", "DIS", "NFLX", "WBD", "PARA", "SPOT"],
    "\U0001F3D8\uFE0F נדלן ו-REITs": ["PLD", "AMT", "EQIX", "DLR", "SPG", "O", "XLRE"],
    "\U0001F4A7 מים וסביבה": ["AWK", "WM", "RSG", "XYL", "ECL", "VLTO"],
    "\U0001F6E1\uFE0F ביטוח": ["PGR", "TRV", "ALL", "CB", "AIG", "BRK-B"],
    "\U0001F4CA תעודות סל ומדדים": ["SPY", "QQQ", "DIA", "IWM", "VOO", "RSP", "SPMO", "SMH", "SOXX", "XLK", "XLV", "XLE", "XLF", "XLI", "XLU", "ARKK"],
    "\U0001F947 סחורות ומטבעות (ETF)": ["GLD", "GLDM", "SLV", "USO", "UNG", "BNO", "DBA", "COPX", "TLT", "IBIT"],
}


# ===== הרחבה שנייה: קטגוריות מתמחות =====
STOCK_INFO.update({
    "LITE": ("Lumentum", "רכיבים פוטוניים"),
    "POET": ("POET Technologies", "אינטגרציה אופטית"),
    "EMKR": ("EMCORE", "רכיבי תקשורת אופטית"),
    "OCC": ("Optical Cable", "כבלים אופטיים"),
    "FN": ("Fabrinet", "ייצור אופטו-אלקטרוני"),
    "CIEN": ("Ciena", "רשתות אופטיות"),
    "SIMO": ("Silicon Motion", "בקרי זיכרון"),
    "ALAB": ("Astera Labs", "קישוריות לשרתי AI"),
    "CRDO": ("Credo Technology", "קישוריות מהירה"),
    "EXTR": ("Extreme Networks", "ציוד רשת"),
    "UUUU": ("Energy Fuels", "אורניום ומתכות נדירות"),
    "REMX": ("Rare Earth ETF", "סל מתכות נדירות"),
    "TMC": ("TMC the metals co", "כריית קרקעית ים"),
    "NB": ("NioCorp", "ניוביום ומתכות נדירות"),
    "IDR": ("Idaho Strategic", "זהב ומתכות נדירות"),
    "IPGP": ("IPG Photonics", "לייזרי סיב"),
    "LASR": ("nLIGHT", "לייזרים תעשייתיים"),
    "MKSI": ("MKS Instruments", "ציוד ותהליכי לייזר"),
    "VRT": ("Vertiv", "תשתית למרכזי נתונים"),
    "SMCI": ("Super Micro", "שרתי AI"),
    "MOD": ("Modine", "קירור מרכזי נתונים"),
    "CRWV": ("CoreWeave", "ענן GPU"),
    "APLD": ("Applied Digital", "מרכזי נתונים ל-AI"),
    "IREN": ("IREN", "מרכזי נתונים ואנרגיה"),
    "NBIS": ("Nebius", "תשתית ענן ל-AI"),
    "GDS": ("GDS Holdings", "מרכזי נתונים"),
    "CORZ": ("Core Scientific", "תשתית מחשוב"),
    "UCTT": ("Ultra Clean", "תת-מערכות לייצור שבבים"),
    "ICHR": ("Ichor Holdings", "מערכות זרימה לשבבים"),
    "ONTO": ("Onto Innovation", "בקרת תהליך בשבבים"),
    "APD": ("Air Products", "גזים תעשייתיים"),
    "OLED": ("Universal Display", "חומרי OLED"),
    "AMSC": ("American Superconductor", "מוליכי-על"),
    "ROG": ("Rogers Corp", "חומרים מתקדמים"),
    "DD": ("DuPont", "חומרים מתקדמים"),
    "TEM": ("Tempus AI", "AI ברפואה"),
    "RXRX": ("Recursion", "גילוי תרופות ב-AI"),
    "INOD": ("Innodata", "נתוני אימון ל-AI"),
    "AUR": ("Aurora Innovation", "נהיגה אוטונומית"),
    "TLN": ("Talen Energy", "חשמל למרכזי נתונים"),
    "NRG": ("NRG Energy", "ייצור חשמל"),
    "NNE": ("Nano Nuclear", "כורים זעירים"),
    "POWL": ("Powell Industries", "ציוד חשמל תעשייתי"),
    "AEHR": ("Aehr Test Systems", "בדיקת שבבים"),
    "KLIC": ("Kulicke & Soffa", "אריזת שבבים"),
    "COHU": ("Cohu", "בדיקת שבבים"),
    "FORM": ("FormFactor", "בדיקת ופרים"),
    "ACLS": ("Axcelis", "השתלת יונים"),
    "VTI": ("Total Market ETF", "מדד רחב"),
    "XLB": ("Materials ETF", "סל חומרים"),
    "XLY": ("Consumer Disc ETF", "סל צריכה מחזורית"),
    "XLC": ("Communication ETF", "סל תקשורת"),
    "AIQ": ("AI & Tech ETF", "סל בינה מלאכותית"),
    "WCLD": ("Cloud Computing ETF", "סל ענן"),
    "SKYY": ("Cloud ETF", "סל ענן"),
    "CIBR": ("Cybersecurity ETF", "סל סייבר"),
    "ROBO": ("Robotics ETF", "סל רובוטיקה"),
    "IEF": ("7-10Y Treasury", "אגח בינוני"),
    "SHY": ("1-3Y Treasury", "אגח קצר"),
    "AGG": ("Aggregate Bond ETF", "סל אגח"),
    "BND": ("Total Bond ETF", "סל אגח"),
    "LQD": ("Corporate Bond ETF", "אגח קונצרני"),
    "HYG": ("High Yield ETF", "אגח זבל"),
    "JEPI": ("JPM Equity Premium", "הכנסה מאופציות"),
    "SCHD": ("Schwab Dividend", "מניות דיבידנד"),
    "VYM": ("Vanguard High Div", "מניות דיבידנד"),
    "PPLT": ("Platinum ETF", "פלטינה"),
})

_NEW_CATS2 = {
    "🔦 פוטוניקה ואופטיקה": ["COHR", "LITE", "AAOI", "FN", "CIEN", "POET", "EMKR", "OCC", "IPGP", "LASR"],
    "💾 שבבי זיכרון": ["MU", "SNDK", "WDC", "STX", "RMBS", "MRAM", "SIMO", "PENG"],
    "🔗 קישוריות AI": ["ANET", "AVGO", "MRVL", "ALAB", "CRDO", "CSCO", "COHR", "LITE", "FN", "EXTR"],
    "💎 חומרים נדירים": ["MP", "UUUU", "REMX", "TMC", "NB", "IDR", "LYB"] if False else ["MP", "UUUU", "REMX", "TMC", "NB", "IDR"],
    "🔬 לייזרים ומכשור": ["IPGP", "COHR", "LITE", "LASR", "MKSI", "VECO", "AEHR"],
    "🖥️ מרכזי נתונים": ["EQIX", "DLR", "VRT", "SMCI", "DELL", "HPE", "ANET", "MOD", "CRWV", "APLD", "IREN", "NBIS", "GDS"],
    "⚗️ חומרי גלם לשבבים": ["ENTG", "MKSI", "UCTT", "ICHR", "ONTO", "AXTI", "PLAB", "ASYS", "LIN", "APD"],
    "🧪 חומרים מתקדמים": ["MRAM", "AXTI", "OLED", "AMSC", "POET", "EMKR", "ROG", "DD"],
    "🚀 סטארט-אפ AI": ["ALAB", "CRDO", "SOUN", "BBAI", "AI", "TEM", "RXRX", "INOD", "AUR", "SERV", "SYM"],
    "⚡ אנרגיה ל-AI": ["VST", "CEG", "TLN", "NRG", "GEV", "ETN", "PWR", "SMR", "OKLO", "NNE", "POWL", "BE"],
    "📦 אריזה ובדיקת שבבים": ["AEHR", "ONTO", "KLIC", "COHU", "FORM", "TER", "ACLS", "AMAT"],
    "📐 תכנון שבבים (EDA)": ["SNPS", "CDNS", "ARM", "RMBS", "ALAB"],
    "📈 ETF מדדים רחבים": ["SPY", "QQQ", "QQQM", "VOO", "VTI", "DIA", "IWM", "RSP", "SPMO"],
    "🏭 ETF סקטוריאליים": ["XLK", "XLV", "XLE", "XLF", "XLI", "XLP", "XLU", "XLRE", "XLB", "XLY", "XLC"],
    "🤖 ETF נושאתיים": ["SMH", "SOXX", "IGV", "HACK", "CIBR", "BOTZ", "ROBO", "KOID", "ARKK", "ARKX", "CHAT", "AIQ", "WCLD", "SKYY", "UFO", "NLR", "NUKZ", "URA"],
    "🥇 ETF סחורות": ["GLD", "GLDM", "SLV", "PPLT", "USO", "UNG", "BNO", "DBO", "DBA", "COPX", "REMX", "URNM"],
    "💵 ETF אגח והכנסה": ["TLT", "IEF", "SHY", "AGG", "BND", "LQD", "HYG", "JEPI", "SCHD", "VYM"],
}
CATEGORIES.update(_NEW_CATS2)


# ===== רשימת בקשות =====
# מקבילה לרשימת המעקב: נשמרת ב-Drive, נערכת מהממשק, ומניה שנוספת אליה
# מקוטלגת גם לקטגוריה הסקטוריאלית שלה.
REQUESTS_FILE = Path('/content/drive/MyDrive/base44/requests.json')
REQUESTS_BAK = Path('/content/drive/MyDrive/base44/requests_backup.json')

def load_requests():
    try:
        if REQUESTS_FILE.exists():
            d = json.loads(REQUESTS_FILE.read_text(encoding='utf-8'))
            if isinstance(d, list):
                return [str(x).upper() for x in d]
    except Exception:
        pass
    return []

def save_requests(lst):
    try:
        cur = load_requests()
        hist = []
        if REQUESTS_BAK.exists():
            try:
                hist = json.loads(REQUESTS_BAK.read_text(encoding='utf-8'))
                if not isinstance(hist, list):
                    hist = []
            except Exception:
                hist = []
        hist.insert(0, {"ts": datetime.now().strftime("%d/%m %H:%M"), "list": cur})
        REQUESTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        REQUESTS_BAK.write_text(json.dumps(hist[:10], ensure_ascii=False), encoding='utf-8')
        REQUESTS_FILE.write_text(json.dumps(sorted(set(lst)), ensure_ascii=False), encoding='utf-8')
        return True, None
    except Exception as e:
        return False, str(e)

def load_rq_backups():
    try:
        if REQUESTS_BAK.exists():
            h = json.loads(REQUESTS_BAK.read_text(encoding='utf-8'))
            if isinstance(h, list):
                return h
    except Exception:
        pass
    return []

# רשימת המעקב, ממוקמת מיד אחרי התיק האישי
_WLK = "👁️ רשימת מעקב"
CATEGORIES[_WLK] = load_watchlist()
_RQK = "\U0001F4DD רשימת בקשות"
CATEGORIES[_RQK] = load_requests()
try:
    _ks = [k for k in CATEGORIES.keys() if k != _WLK]
    _pi = next((i for i, k in enumerate(_ks) if "התיק האישי" in k), 0) + 1
    _ks.insert(_pi, _WLK)
    CATEGORIES = {k: CATEGORIES[k] for k in _ks}
    # PRICE-SANITY: יקום 2023 בלי מניות עם נתוני מחיר
    # פגומים. BYND הוסרה — פיצול הפוך 1:30 עם התאמה
    # שבורה שייצרה +2,472% מזויפים בחמישה טריידים.
    CATEGORIES["🧼 יקום 2023 · נקי (219)"] = ["AA", "AAPL", "ABNB", "ACN", "ADBE", "ADI", "ADM", "AFRM", "AI", "AIG", "ALB", "AMAT", "AMC", "AMD", "AMT", "AMZN", "ARKK", "ASML", "AVGO", "AXP", "BA", "BAC", "BBBY", "BE", "BG", "BIIB", "BKNG", "BLDP", "BLK", "BNO", "C", "CAT", "CCJ", "CCL", "CDNS", "CF", "CHWY", "CLF", "CMG", "COIN", "COP", "COST", "CRM", "CRWD", "CVNA", "CVX", "CZR", "DAL", "DASH", "DDOG", "DE", "DHR", "DIS", "DKNG", "DLR", "DOCU", "DXCM", "EBAY", "ECL", "ENPH", "ENTG", "EOG", "EQIX", "ESTC", "ETSY", "F", "FCEL", "FCX", "FDX", "FSLR", "FTNT", "GE", "GM", "GME", "GOOGL", "GTLB", "HAL", "HD", "HLT", "HOOD", "HUBS", "HUT", "ICLN", "INTC", "INTU", "IONQ", "IRDM", "ISRG", "JOBY", "KLAC", "LCID", "LHX", "LOW", "LRCX", "LULU", "LUV", "LVS", "LYFT", "MA", "MAR", "MARA", "MDB", "META", "MGM", "MLM", "MNDY", "MOS", "MP", "MPC", "MRNA", "MRVL", "MS", "MSFT", "MSTR", "MU", "NCLH", "NEE", "NEM", "NET", "NFLX", "NKE", "NOC", "NOW", "NTR", "NUE", "NVDA", "NVO", "NXPI", "OKTA", "ON", "OPEN", "ORCL", "OXY", "PANW", "PATH", "PENN", "PH", "PINS", "PLD", "PLTR", "PLUG", "PSX", "PTON", "PWR", "PYPL", "QCOM", "QLYS", "RCL", "REGN", "RIOT", "RIVN", "RKLB", "RMBS", "ROK", "ROKU", "RPD", "RUN", "S", "SAP", "SBUX", "SCCO", "SCHW", "SEDG", "SHOP", "SLB", "SLV", "SMH", "SNAP", "SNOW", "SNPS", "SOFI", "SOXX", "SPCE", "SPG", "SPGI", "SPOT", "STX", "SYK", "TAN", "TDOC", "TEAM", "TENB", "TER", "TGT", "TJX", "TMO", "TSLA", "TSM", "TT", "TWLO", "TXN", "TXT", "UAL", "UBER", "UEC", "UNG", "UPS", "UPST", "URA", "URI", "USO", "V", "VEEV", "VMC", "VRNS", "VRTX", "VST", "VTRS", "W", "WBD", "WDAY", "WDC", "WFC", "XLE", "XOM", "XYL", "ZM", "ZS", "ZTS"]
    # PIT-UNIVERSE: יקום שנבחר נכון ל-1.1.2023 בלבד —
    # מחזור ותנודתיות מ-12 החודשים שקדמו, בלי מידע מאוחר.
    # נועד למדוד כמה מקו הבסיס נובע מהטיית בחירה.
    CATEGORIES["🧭 יקום 2023 · נכון-לתאריך (220)"] = ["AA", "AAPL", "ABNB", "ACN", "ADBE", "ADI", "ADM", "AFRM", "AI", "AIG", "ALB", "AMAT", "AMC", "AMD", "AMT", "AMZN", "ARKK", "ASML", "AVGO", "AXP", "BA", "BAC", "BBBY", "BE", "BG", "BIIB", "BKNG", "BLDP", "BLK", "BNO", "BYND", "C", "CAT", "CCJ", "CCL", "CDNS", "CF", "CHWY", "CLF", "CMG", "COIN", "COP", "COST", "CRM", "CRWD", "CVNA", "CVX", "CZR", "DAL", "DASH", "DDOG", "DE", "DHR", "DIS", "DKNG", "DLR", "DOCU", "DXCM", "EBAY", "ECL", "ENPH", "ENTG", "EOG", "EQIX", "ESTC", "ETSY", "F", "FCEL", "FCX", "FDX", "FSLR", "FTNT", "GE", "GM", "GME", "GOOGL", "GTLB", "HAL", "HD", "HLT", "HOOD", "HUBS", "HUT", "ICLN", "INTC", "INTU", "IONQ", "IRDM", "ISRG", "JOBY", "KLAC", "LCID", "LHX", "LOW", "LRCX", "LULU", "LUV", "LVS", "LYFT", "MA", "MAR", "MARA", "MDB", "META", "MGM", "MLM", "MNDY", "MOS", "MP", "MPC", "MRNA", "MRVL", "MS", "MSFT", "MSTR", "MU", "NCLH", "NEE", "NEM", "NET", "NFLX", "NKE", "NOC", "NOW", "NTR", "NUE", "NVDA", "NVO", "NXPI", "OKTA", "ON", "OPEN", "ORCL", "OXY", "PANW", "PATH", "PENN", "PH", "PINS", "PLD", "PLTR", "PLUG", "PSX", "PTON", "PWR", "PYPL", "QCOM", "QLYS", "RCL", "REGN", "RIOT", "RIVN", "RKLB", "RMBS", "ROK", "ROKU", "RPD", "RUN", "S", "SAP", "SBUX", "SCCO", "SCHW", "SEDG", "SHOP", "SLB", "SLV", "SMH", "SNAP", "SNOW", "SNPS", "SOFI", "SOXX", "SPCE", "SPG", "SPGI", "SPOT", "STX", "SYK", "TAN", "TDOC", "TEAM", "TENB", "TER", "TGT", "TJX", "TMO", "TSLA", "TSM", "TT", "TWLO", "TXN", "TXT", "UAL", "UBER", "UEC", "UNG", "UPS", "UPST", "URA", "URI", "USO", "V", "VEEV", "VMC", "VRNS", "VRTX", "VST", "VTRS", "W", "WBD", "WDAY", "WDC", "WFC", "XLE", "XOM", "XYL", "ZM", "ZS", "ZTS"]
    # מעבדה: יקום זעיר וקבוע לאיתור באגים. לא למדידת ביצועים.
    CATEGORIES["🔬 מעבדה (3)"] = ["TSM", "ON", "DKNG"]
except Exception:
    pass

# ================= קטלוג וסיווג אוטומטי =================
# כשמוסיפים סימול שאינו במאגר, המערכת שולפת ממנו שם וענף ומשייכת אותו לקטגוריה.
# הסיווג נשמר בקובץ נפרד ב-Drive (catalog.json) ולכן הוא **שורד הסרה מהתיק האישי**.
#
# ⚠️ מגבלות ידועות שחשוב להכיר:
#   1. לתעודות סל אין ענף ב-yfinance - כולן ייפלו ל"תעודות סל ומדדים"
#   2. סייבר, ענן ו-AI חולקים את אותו ענף (Software-Infrastructure) ולא ניתנים להפרדה
#   3. ענף שלא במיפוי ייפול לקטגוריה כללית
# לכן יש תיקון ידני בממשק - הסיווג האוטומטי הוא הצעה, לא פסק דין.
CATALOG_FILE = Path('/content/drive/MyDrive/base44/catalog.json')

CAT_SEMIS   = "💻 שבבים וחצי מוליכים"
CAT_BIGTECH = "🚀 ענקיות טכנולוגיה"
CAT_AI      = "🤖 בינה מלאכותית וענן"
CAT_ROBOT   = "🦾 רובוטיקה ואוטומציה"
CAT_CYBER   = "🔒 סייבר ואבטחת מידע"
CAT_DEF     = "🛡️ ביטחון, צבא ונשק"
CAT_SPACE   = "🛰️ חלל ולוויינים"
CAT_NUKE    = "☢️ גרעיני ואורניום"
CAT_OIL     = "🔌 אנרגיה מסורתית"
CAT_GREEN   = "🌱 אנרגיה מתחדשת ורשתות"
CAT_MINE    = "⛏️ סחורות, מתכות וכרייה"
CAT_AGRI    = "🌾 חקלאות, מזון ודשנים"
CAT_BANK    = "🏦 פיננסים ובנקים"
CAT_PAY     = "💳 תשלומים ופינטק"
CAT_CRYPTO  = "🪙 קריפטו ובלוקצ'יין"
CAT_BIO     = "💊 ביוטכנולוגיה ופארמה"
CAT_HEALTH  = "🏥 בריאות וציוד רפואי"
CAT_INFRA   = "🏗️ תשתיות ובנייה"
CAT_IND     = "🏭 תעשייה מסורתית"
CAT_TRANS   = "🚚 תחבורה ולוגיסטיקה"
CAT_RETAIL  = "🛒 קמעונאות וצריכה"
CAT_TRAVEL  = "🏨 תיירות, פנאי ובידור"
CAT_MEDIA   = "📺 תקשורת ומדיה"
CAT_REIT    = "🏘️ נדלן ו-REITs"
CAT_WATER   = "💧 מים וסביבה"
CAT_INSUR   = "🛡️ ביטוח"
CAT_ETF     = "📊 תעודות סל ומדדים"

INDUSTRY_MAP = {
    "Semiconductors": CAT_SEMIS,
    "Semiconductor Equipment & Materials": CAT_SEMIS,
    "Software - Infrastructure": CAT_AI, "Software—Infrastructure": CAT_AI,
    "Software - Application": CAT_AI, "Software—Application": CAT_AI,
    "Information Technology Services": CAT_BIGTECH,
    "Computer Hardware": CAT_BIGTECH, "Consumer Electronics": CAT_BIGTECH,
    "Electronic Components": CAT_SEMIS,
    "Electronics & Computer Distribution": CAT_BIGTECH,
    "Communication Equipment": CAT_MEDIA,
    "Aerospace & Defense": CAT_DEF,
    "Uranium": CAT_NUKE,
    "Solar": CAT_GREEN,
    "Oil & Gas Integrated": CAT_OIL, "Oil & Gas E&P": CAT_OIL,
    "Oil & Gas Equipment & Services": CAT_OIL, "Oil & Gas Midstream": CAT_OIL,
    "Oil & Gas Refining & Marketing": CAT_OIL, "Oil & Gas Drilling": CAT_OIL,
    "Thermal Coal": CAT_OIL,
    "Utilities - Regulated Electric": CAT_GREEN, "Utilities—Regulated Electric": CAT_GREEN,
    "Utilities - Renewable": CAT_GREEN, "Utilities—Renewable": CAT_GREEN,
    "Utilities - Independent Power Producers": CAT_GREEN,
    "Utilities - Regulated Water": CAT_WATER, "Utilities—Regulated Water": CAT_WATER,
    "Waste Management": CAT_WATER, "Pollution & Treatment Controls": CAT_WATER,
    "Gold": CAT_MINE, "Silver": CAT_MINE, "Copper": CAT_MINE,
    "Other Industrial Metals & Mining": CAT_MINE, "Steel": CAT_MINE,
    "Aluminum": CAT_MINE, "Other Precious Metals & Mining": CAT_MINE,
    "Specialty Chemicals": CAT_MINE, "Chemicals": CAT_MINE,
    "Agricultural Inputs": CAT_AGRI, "Farm Products": CAT_AGRI,
    "Packaged Foods": CAT_AGRI, "Confectioners": CAT_AGRI,
    "Beverages - Non-Alcoholic": CAT_RETAIL, "Beverages - Brewers": CAT_RETAIL,
    "Banks - Diversified": CAT_BANK, "Banks—Diversified": CAT_BANK,
    "Banks - Regional": CAT_BANK, "Banks—Regional": CAT_BANK,
    "Capital Markets": CAT_BANK, "Asset Management": CAT_BANK,
    "Financial Data & Stock Exchanges": CAT_BANK,
    "Credit Services": CAT_PAY,
    "Biotechnology": CAT_BIO,
    "Drug Manufacturers - General": CAT_BIO, "Drug Manufacturers—General": CAT_BIO,
    "Drug Manufacturers - Specialty & Generic": CAT_BIO,
    "Medical Devices": CAT_HEALTH, "Medical Instruments & Supplies": CAT_HEALTH,
    "Diagnostics & Research": CAT_HEALTH, "Healthcare Plans": CAT_HEALTH,
    "Medical Care Facilities": CAT_HEALTH, "Health Information Services": CAT_HEALTH,
    "Engineering & Construction": CAT_INFRA, "Building Materials": CAT_INFRA,
    "Building Products & Equipment": CAT_INFRA, "Infrastructure Operations": CAT_INFRA,
    "Specialty Industrial Machinery": CAT_IND, "Industrial Distribution": CAT_IND,
    "Conglomerates": CAT_IND, "Farm & Heavy Construction Machinery": CAT_IND,
    "Tools & Accessories": CAT_IND, "Electrical Equipment & Parts": CAT_IND,
    "Metal Fabrication": CAT_IND, "Rental & Leasing Services": CAT_IND,
    "Railroads": CAT_TRANS, "Integrated Freight & Logistics": CAT_TRANS,
    "Airlines": CAT_TRANS, "Trucking": CAT_TRANS, "Marine Shipping": CAT_TRANS,
    "Auto Manufacturers": CAT_TRANS, "Auto Parts": CAT_TRANS,
    "Specialty Retail": CAT_RETAIL, "Discount Stores": CAT_RETAIL,
    "Home Improvement Retail": CAT_RETAIL, "Restaurants": CAT_RETAIL,
    "Apparel Retail": CAT_RETAIL, "Footwear & Accessories": CAT_RETAIL,
    "Apparel Manufacturing": CAT_RETAIL, "Household & Personal Products": CAT_RETAIL,
    "Internet Retail": CAT_RETAIL, "Grocery Stores": CAT_RETAIL,
    "Lodging": CAT_TRAVEL, "Resorts & Casinos": CAT_TRAVEL,
    "Travel Services": CAT_TRAVEL, "Gambling": CAT_TRAVEL, "Leisure": CAT_TRAVEL,
    "Telecom Services": CAT_MEDIA, "Entertainment": CAT_MEDIA,
    "Internet Content & Information": CAT_MEDIA, "Broadcasting": CAT_MEDIA,
    "Advertising Agencies": CAT_MEDIA, "Electronic Gaming & Multimedia": CAT_MEDIA,
    "Insurance - Property & Casualty": CAT_INSUR, "Insurance—Property & Casualty": CAT_INSUR,
    "Insurance - Life": CAT_INSUR, "Insurance - Diversified": CAT_INSUR,
    "Insurance Brokers": CAT_INSUR, "Insurance - Specialty": CAT_INSUR,
}

SECTOR_MAP = {
    "Technology": CAT_BIGTECH, "Healthcare": CAT_HEALTH,
    "Financial Services": CAT_BANK, "Energy": CAT_OIL,
    "Industrials": CAT_IND, "Consumer Cyclical": CAT_RETAIL,
    "Consumer Defensive": CAT_RETAIL, "Utilities": CAT_GREEN,
    "Real Estate": CAT_REIT, "Basic Materials": CAT_MINE,
    "Communication Services": CAT_MEDIA,
}

ALL_CAT_KEYS = [CAT_SEMIS, CAT_BIGTECH, CAT_AI, CAT_ROBOT, CAT_CYBER, CAT_DEF,
                CAT_SPACE, CAT_NUKE, CAT_OIL, CAT_GREEN, CAT_MINE, CAT_AGRI,
                CAT_BANK, CAT_PAY, CAT_CRYPTO, CAT_BIO, CAT_HEALTH, CAT_INFRA,
                CAT_IND, CAT_TRANS, CAT_RETAIL, CAT_TRAVEL, CAT_MEDIA,
                CAT_REIT, CAT_WATER, CAT_INSUR, CAT_ETF]

def load_catalog():
    try:
        if CATALOG_FILE.exists():
            d = json.loads(CATALOG_FILE.read_text(encoding='utf-8'))
            if isinstance(d, dict):
                return d
    except Exception:
        pass
    return {}

def save_catalog(d):
    try:
        CATALOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CATALOG_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
        return True, None
    except Exception as e:
        return False, str(e)

@st.cache_data(ttl=86400)
def fetch_ticker_meta(t):
    """ מחזיר (שם, ענף, קטגוריה מוצעת, ביטחון, שגיאה).
    'ביטחון' מציין עד כמה הסיווג אמין: high = מיפוי ענף ישיר,
    med = מיפוי לפי סקטור בלבד, low = ברירת מחדל. """
    def _f():
        return yf.Ticker(t).get_info()
    res, err = fetch_with_retry(_f, retries=1)
    if not res or not isinstance(res, dict):
        return None, None, None, None, (err or "לא נמצא")
    name = res.get("longName") or res.get("shortName") or t
    qt = str(res.get("quoteType") or "").upper()
    ind = res.get("industry") or ""
    sec = res.get("sector") or ""
    if qt in ("ETF", "MUTUALFUND"):
        return name, "תעודת סל", CAT_ETF, "low", None
    if ind in INDUSTRY_MAP:
        return name, ind, INDUSTRY_MAP[ind], "high", None
    if sec in SECTOR_MAP:
        return name, (ind or sec), SECTOR_MAP[sec], "med", None
    return name, (ind or sec or ""), None, "low", None

# ===== החלת הקטלוג על המאגר והקטגוריות =====
_CATALOG = load_catalog()
for _t, _v in _CATALOG.items():
    try:
        STOCK_INFO[_t] = (_v.get("name", _t), _v.get("sector", ""))
        _ck = _v.get("cat")
        if _ck and _ck in CATEGORIES and _t not in CATEGORIES[_ck]:
            CATEGORIES[_ck] = sorted(set(CATEGORIES[_ck]) | {_t})
    except Exception:
        pass


# ================= תצורת ברירת מחדל (נעולה לפי תוצאות בקטסט) =================
# התצורה הזו לא נבחרה על סמך תחושה - היא תוצאה של סדרת בקטסטים על ארבע קטגוריות
# שונות. מה שנכלל כאן עבר את הרף של "שיפור עקבי ביותר מקטגוריה אחת":
#
#   🏗️ Swing Low (סטופ מבני) - ניצח את ATR בכל ארבע הקטגוריות שנבדקו, בכל המדדים.
#   🔀 מדיניות דוחות משולבת - שיפרה את אחוז ההצלחה בכל הקטגוריות (51-54%),
#      וב-Mag7 העלתה את ה-Sharpe מ-0.72 ל-1.26 *תוך הגדלת* מספר הטריידים.
#   📊 ציון מורכב + נפח מכוון - שיפור מוכח בתיק האישי; בקטגוריות אחרות ניטרלי-חיובי.
#
# מה שנוסה ו**הוסר**: מכפיל "יעילות סטופ" שהעניש סטופים רחבים. הוא חסם ~200 טריידים
# רווחיים והפיל את ה-Sharpe מ-1.93 ל-1.23, כי הוא נלחם ישירות ב-Swing Low שמייצר
# סטופים רחבים בכוונה (לפי מבנה מחיר, לא לפי נוחות).
#
# ⚠️ אזהרת כיול-יתר: התיק האישי נותן Sharpe ~2.1-2.4, בעוד שלוש קטגוריות אחרות
# מתכנסות סביב 0.6-1.3. התיק האישי הוא **חריג סטטיסטי**, לא נציג. הציפייה הריאלית
# מהשיטה היא Sharpe ~0.7-1.3 עם Drawdown נמוך משמעותית מ-Buy&Hold - לא יותר.
# כל שינוי עתידי בתצורה צריך להוכיח את עצמו על **לפחות שלוש קטגוריות** לפני שייכנס.
DEFAULTS = {
    "stop_style": "structural",      # Swing Low - הראיה החזקה ביותר במערכת
    "structural_lookback": 15,
    "structural_buffer_pct": 1.0,
    "earnings_mode": "combined",     # יציאה יזומה לפני דוח + חזרה אחריו
    "entry_buffer_days": 2,          # לא נכנסים אם דוח בתוך יומיים
    "exit_buffer_days": 1,           # יוצאים מפוזיציה קיימת יום לפני דוח
    "exit_style": "trailing",           # TP קבוע 2.5x הסיכון
    "use_composite": False,  # נמצא מזיק בבדיקה 02 (2.28 כבוי מול 2.06 דלוק)           # ציון מורכב (בלי מכפיל הסטופ שהוסר)
    "directional_vol": False,  # נמצא מזיק בבדיקה 03 (2.41 רגיל מול 2.28 מכוון)         # נפח חריג נספר שלילית ביום ירידה
    "overext_threshold": 8.0,
    "block_overextended": True,
    "score_threshold": 65,           # מכויל לציון המורכב (שקול ל-70 בציון הישן)
    "max_holding_days": 30,  # 30 חתך מהלכים באמצע - עבר כל 4 השערים 18.8
    "bt_period": "3y",
    "position_pct": 5,
    "use_vol_norm": True,   # ניצחה ב-5/5 קטגוריות
    "vb1": 3.0, "vb2": 4.5, "vb3": 6.5,
}


# ===== סולמות סטופ מדורג =====
# (רווח שהושג באחוזים, הסטופ עולה לרווח נעול באחוזים)
# שמרני: המרווח כמעט קבוע (3-4%)
STOP_LADDER_STEADY = [(3.0, 0.0), (6.0, 3.0), (10.0, 6.0),
                      (15.0, 11.0), (20.0, 16.0), (30.0, 26.0)]
# מצטמצם: המרווח קטן ככל שהרווח גדל (3% -> 1%)
STOP_LADDER_TIGHT = [(3.0, 0.0), (6.0, 3.5), (10.0, 8.0),
                     (15.0, 13.5), (20.0, 19.0)]

# מאוחר: המדרגה הראשונה רק ב-10%, אחרי שהמהלך הוכיח את עצמו
STOP_LADDER_LATE = [(10.0, 0.0), (15.0, 5.0), (20.0, 10.0),
                    (30.0, 20.0), (40.0, 30.0)]
# מאוחר מאוד: רק הגנה על רווח משמעותי
STOP_LADDER_VERYLATE = [(15.0, 0.0), (25.0, 10.0), (40.0, 25.0)]
# ביניים: מדרגה ראשונה ב-8%
STOP_LADDER_MID = [(8.0, 0.0), (12.0, 4.0), (18.0, 10.0),
                   (25.0, 17.0), (35.0, 26.0)]

# ===== זהות הגרסה =====
# תווית קריאה במקום MD5. מתעדכנת בכל כתיבה.
APP_VERSION = "v085 · 23/08/2026 18:40"
_AUDIT_DONE = {}

# VIX-SIZING: גודל חשיפה לפי VIX.
# הממצא היחיד ששרד מבחן תת-תקופות ורצפת רעש הוגנת —
# ועם חולשה מוכחת ב-2022-23. ניסוי, לא ברירת מחדל.
_VIX_SIZING = "off"

# COOL-MODE: מדיניות ההמתנה אחרי יציאה, ניתנת לכיול.
# ההשערה: המתנה מוצדקת אחרי כישלון (סטופ), לא אחרי
# יציאה מתוכננת כמו לפני-דוח או סוף האופק.
# SECTOR-CAP: סקטורים אמיתיים מ-yfinance.
# STOCK_INFO מכיל תת-ענף מדויק (128 ערכים ל-159
# מניות) ולכן ממוצע סקטור עליו הוא ממוצע של מניה
# אחת. 386 טריידים יצאו עם סקטור ריק.
SECTOR_MAP = {"AA": "Basic Materials", "AAPL": "Technology", "ABNB": "Consumer Cyclical", "ACN": "Technology", "ADBE": "Technology", "ADI": "Technology", "ADM": "Consumer Defensive", "AFRM": "Financial Services", "AI": "Technology", "AIG": "Financial Services", "ALB": "Basic Materials", "AMAT": "Technology", "AMC": "Communication Services", "AMD": "Technology", "AMT": "Real Estate", "AMZN": "Consumer Cyclical", "ARKK": "ETF", "ASML": "Technology", "AVGO": "Technology", "AXP": "Financial Services", "BA": "Industrials", "BAC": "Financial Services", "BBBY": "Unknown", "BE": "Industrials", "BG": "Consumer Defensive", "BIIB": "Healthcare", "BKNG": "Consumer Cyclical", "BLDP": "Industrials", "BLK": "Financial Services", "BNO": "ETF", "C": "Financial Services", "CAT": "Industrials", "CCJ": "Energy", "CCL": "Consumer Cyclical", "CDNS": "Technology", "CF": "Basic Materials", "CHWY": "Consumer Cyclical", "CLF": "Basic Materials", "CMG": "Consumer Cyclical", "COIN": "Financial Services", "COP": "Energy", "COST": "Consumer Defensive", "CRM": "Technology", "CRWD": "Technology", "CVNA": "Consumer Cyclical", "CVX": "Energy", "CZR": "Consumer Cyclical", "DAL": "Industrials", "DASH": "Consumer Cyclical", "DDOG": "Technology", "DE": "Industrials", "DHR": "Healthcare", "DIS": "Communication Services", "DKNG": "Consumer Cyclical", "DLR": "Real Estate", "DOCU": "Technology", "DXCM": "Healthcare", "EBAY": "Consumer Cyclical", "ECL": "Basic Materials", "ENPH": "Technology", "ENTG": "Technology", "EOG": "Energy", "EQIX": "Real Estate", "ESTC": "Technology", "ETSY": "Consumer Cyclical", "F": "Consumer Cyclical", "FCEL": "Industrials", "FCX": "Basic Materials", "FDX": "Industrials", "FSLR": "Technology", "FTNT": "Technology", "GE": "Industrials", "GM": "Consumer Cyclical", "GME": "Consumer Cyclical", "GOOGL": "Communication Services", "GTLB": "Technology", "HAL": "Energy", "HD": "Consumer Cyclical", "HLT": "Consumer Cyclical", "HOOD": "Financial Services", "HUBS": "Technology", "HUT": "Financial Services", "ICLN": "ETF", "INTC": "Technology", "INTU": "Technology", "IONQ": "Technology", "IRDM": "Communication Services", "ISRG": "Healthcare", "JOBY": "Industrials", "KLAC": "Technology", "LCID": "Consumer Cyclical", "LHX": "Industrials", "LOW": "Consumer Cyclical", "LRCX": "Technology", "LULU": "Consumer Cyclical", "LUV": "Industrials", "LVS": "Consumer Cyclical", "LYFT": "Technology", "MA": "Financial Services", "MAR": "Consumer Cyclical", "MARA": "Financial Services", "MDB": "Technology", "META": "Communication Services", "MGM": "Consumer Cyclical", "MLM": "Basic Materials", "MNDY": "Technology", "MOS": "Basic Materials", "MP": "Basic Materials", "MPC": "Energy", "MRNA": "Healthcare", "MRVL": "Technology", "MS": "Financial Services", "MSFT": "Technology", "MSTR": "Technology", "MU": "Technology", "NCLH": "Consumer Cyclical", "NEE": "Utilities", "NEM": "Basic Materials", "NET": "Technology", "NFLX": "Communication Services", "NKE": "Consumer Cyclical", "NOC": "Industrials", "NOW": "Technology", "NTR": "Basic Materials", "NUE": "Basic Materials", "NVDA": "Technology", "NVO": "Healthcare", "NXPI": "Technology", "OKTA": "Technology", "ON": "Technology", "OPEN": "Real Estate", "ORCL": "Technology", "OXY": "Energy", "PANW": "Technology", "PATH": "Technology", "PENN": "Consumer Cyclical", "PH": "Industrials", "PINS": "Communication Services", "PLD": "Real Estate", "PLTR": "Technology", "PLUG": "Industrials", "PSX": "Energy", "PTON": "Consumer Cyclical", "PWR": "Industrials", "PYPL": "Financial Services", "QCOM": "Technology", "QLYS": "Technology", "RCL": "Consumer Cyclical", "REGN": "Healthcare", "RIOT": "Financial Services", "RIVN": "Consumer Cyclical", "RKLB": "Industrials", "RMBS": "Technology", "ROK": "Industrials", "ROKU": "Communication Services", "RPD": "Technology", "RUN": "Technology", "S": "Technology", "SAP": "Technology", "SBUX": "Consumer Cyclical", "SCCO": "Basic Materials", "SCHW": "Financial Services", "SEDG": "Technology", "SHOP": "Technology", "SLB": "Energy", "SLV": "ETF", "SMH": "ETF", "SNAP": "Communication Services", "SNOW": "Technology", "SNPS": "Technology", "SOFI": "Financial Services", "SOXX": "ETF", "SPCE": "Industrials", "SPG": "Real Estate", "SPGI": "Financial Services", "SPOT": "Communication Services", "STX": "Technology", "SYK": "Healthcare", "TAN": "ETF", "TDOC": "Healthcare", "TEAM": "Technology", "TENB": "Technology", "TER": "Technology", "TGT": "Consumer Defensive", "TJX": "Consumer Cyclical", "TMO": "Healthcare", "TSLA": "Consumer Cyclical", "TSM": "Technology", "TT": "Industrials", "TWLO": "Technology", "TXN": "Technology", "TXT": "Industrials", "UAL": "Industrials", "UBER": "Technology", "UEC": "Energy", "UNG": "ETF", "UPS": "Industrials", "UPST": "Financial Services", "URA": "ETF", "URI": "Industrials", "USO": "ETF", "V": "Financial Services", "VEEV": "Healthcare", "VMC": "Basic Materials", "VRNS": "Technology", "VRTX": "Healthcare", "VST": "Utilities", "VTRS": "Healthcare", "W": "Consumer Cyclical", "WBD": "Communication Services", "WDAY": "Technology", "WDC": "Technology", "WFC": "Financial Services", "XLE": "ETF", "XOM": "Energy", "XYL": "Industrials", "ZM": "Technology", "ZS": "Technology", "ZTS": "Healthcare"}
# ATR-COST: תוספת עלות פר יחידת ATR%. 0 = מנוטרל.
# ספרד והחלקה גדלים בתנודתיות; מספר קבוע מחמיא
# למניות התנודתיות ומעניש את השקטות.
_ATR_COST = 0.0
_SEC_CAP = 0   # 0 = ללא תקרה

_COOL_MODE = "current"


def _cool_days(reason):
    """כמה ימים להמתין לפני כניסה חוזרת, לפי הסיבה."""
    if _COOL_MODE == "off":
        return 0
    if _COOL_MODE == "sl_only":
        return 10 if reason == "SL" else 0
    if _COOL_MODE == "short":
        return 3
    return COOLDOWN_BY_REASON.get(reason, COOLDOWN_DEFAULT)
_VIX_MAP = None          # {date -> vix}
_VIX_EXPOSURE = []       # מקדמים בפועל, לדיווח


def _vix_key(d):
    """VIX-KEY: תאריך נקי. מקורות שונים מגיעים עם אזור זמן
    ושעה שונים, ולכן השוואה ישירה של חותמות נכשלת בשקט."""
    try:
        t = pd.Timestamp(d)
        if t.tz is not None:
            t = t.tz_localize(None)
        return t.normalize()
    except Exception:
        return None


def _vix_weight(d):
    """מקדם לגודל הפוזיציה ביום d. 1.0 = ללא שינוי."""
    if _VIX_SIZING != "tiered" or not _VIX_MAP:
        return 1.0
    v = _VIX_MAP.get(_vix_key(d))
    if v is None or not np.isfinite(v):
        return 1.0
    if v < 15:  return 0.5
    if v < 20:  return 1.0
    if v < 25:  return 1.5
    return 2.0

# ===== זיכרון: כמה ימים להמתין לפני כניסה חוזרת =====
# הסיבה ליציאה משנה. יציאה לפני דוח היא ניהול סיכון מתוכנן,
# לא כישלון - ולכן ההמתנה קצרה. סטופ הוא כישלון.
COOLDOWN_BY_REASON = {"SL": 10, "TP": 3, "זמן": 5, "לפני-דוח": 1,
                      "היפוך": 5, "מאקרו": 5}
COOLDOWN_DEFAULT = 3

# ===== חסר-סיכון =====
# Sharpe חייב להיות עודף. בלי זה תיק עתיר-מזומן מקבל ציון מנופח,
# כי תנודתיות נמוכה נספרת כיתרון גם כשהתשואה נמוכה.
RISK_FREE_ANNUAL = 0.04

# ================= פונקציית עזר: ניסיון חוזר לשליפת נתונים =================
def fetch_with_retry(fn, retries=2, delay=1.0):
    last_err = None
    for attempt in range(retries + 1):
        try:
            return fn(), None
        except Exception as e:
            last_err = str(e)
            if attempt < retries:
                time.sleep(delay)
    return None, last_err

# ================= מאקרו שוק =================
@st.cache_data(ttl=1800)
def fetch_fear_greed():
    """
    מושך את מדד Fear & Greed של CNN.
    ⚠️ חשוב: זהו endpoint לא-רשמי (production.dataviz.cnn.io) - הוא יכול להישבר בכל רגע
    בלי התראה. לכן כל כשל מטופל בעדינות והמדד פשוט לא נכלל בציון המאקרו במקום להפיל הכל.
    זהו מדד שוק כללי (סנטימנט), לא מדד פר-מניה - ולכן הוא שייך לרכיב המאקרו בלבד.
    ערך: 0 = פחד קיצוני, 100 = חמדנות קיצונית.
    """
    def _fetch():
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        fg = data.get("fear_and_greed", {})
        score = float(fg.get("score"))
        rating = fg.get("rating", "")
        return round(score, 1), rating
    result, err = fetch_with_retry(_fetch, retries=1)
    if result is None:
        return None, None, err
    return result[0], result[1], None

def fear_greed_to_score(fg_value):
    """
    ממיר Fear & Greed לציון תורם למאקרו - בגישה *קונטרה* מתונה, לא לינארית.
    ההיגיון: חמדנות קיצונית (80+) היא דווקא אזהרה (השוק מתוח, סיכון לתיקון),
    ופחד קיצוני (<20) מציע לרוב הזדמנויות טובות יותר לקונים לטווח בינוני.
    האזור האמצעי (40-70) הוא הבריא ביותר לכניסות מגמה רגילות.
    """
    if fg_value is None:
        return None
    if fg_value >= 85: return 25   # חמדנות קיצונית - סיכון גבוה
    if fg_value >= 70: return 50   # חמדנות
    if fg_value >= 40: return 80   # ניטרלי/בריא
    if fg_value >= 20: return 70   # פחד - לרוב הזדמנות
    return 55                       # פחד קיצוני - הזדמנות אך גם תנודתיות גבוהה

@st.cache_data(ttl=300)
def fetch_live_macro(use_fear_greed=True):
    def _fetch():
        vix = round(yf.Ticker("^VIX").fast_info.get("lastPrice", 18.5), 2)
        spy_df = yf.Ticker("SPY").history(period="3mo")
        if spy_df.empty or len(spy_df) < 50:
            raise ValueError("נתוני SPY לא מספיקים")
        curr_spy = spy_df['Close'].iloc[-1]
        sma50_spy = spy_df['Close'].rolling(50).mean().iloc[-1]
        sma20_spy = spy_df['Close'].rolling(20).mean().iloc[-1]
        return vix, curr_spy, sma50_spy, sma20_spy

    result, err = fetch_with_retry(_fetch)
    if result is None:
        return {"vix": None, "macro_score": None, "error": err, "spy_penalty": 0.0,
                "fg_value": None, "fg_rating": None, "fg_err": "לא נשלף (מאקרו נכשל)"}

    vix, curr_spy, sma50_spy, sma20_spy = result
    vix_score = max(0, min(100, 100 - (vix - 10) * 3))
    trend_score = 65.0 if curr_spy > sma50_spy else 35.0
    spy_penalty = 15.0 if curr_spy < sma20_spy else 0.0

    fg_value = fg_rating = fg_err = None
    fg_score = None
    if use_fear_greed:
        fg_value, fg_rating, fg_err = fetch_fear_greed()
        fg_score = fear_greed_to_score(fg_value)

    if fg_score is not None:
        # משקלים כשיש Fear&Greed: VIX 40%, מגמת SPY 35%, סנטימנט 25%
        macro_score = (vix_score * 0.40) + (trend_score * 0.35) + (fg_score * 0.25) - spy_penalty
    else:
        # נפילה חזרה למשקלים המקוריים אם Fear&Greed לא זמין
        macro_score = (vix_score * 0.55) + (trend_score * 0.45) - spy_penalty

    macro_score = max(0, round(macro_score, 1))
    return {"vix": vix, "macro_score": macro_score, "spy_penalty": spy_penalty, "error": None,
            "fg_value": fg_value, "fg_rating": fg_rating, "fg_err": fg_err, "fg_score": fg_score}

@st.cache_data(ttl=120)
def fetch_stock_data(ticker):
    result, err = fetch_with_retry(lambda: yf.Ticker(ticker).history(period="1y"))
    if result is None or result.empty:
        return pd.DataFrame(), err
    return result, None

@st.cache_data(ttl=86400)
# DATE-RANGE: תקופה יחסית ("3y") או טווח מפורש
# ("2023-01-01:2024-12-31"). כל השליפות עוברות כאן,
# כדי שלא יהיה מסלול שמפרש אחרת ממסלול אחר.
def _hist_window(tk, period):
    try:
        if isinstance(period, str) and ":" in period:
            _s, _e = period.split(":", 1)
            return yf.Ticker(tk).history(start=_s.strip(), end=_e.strip())
    except Exception:
        pass
    return yf.Ticker(tk).history(period=period)


def fetch_stock_data_backtest(ticker, period="3y"):
    """ שליפה נפרדת עם טווח ארוך יותר (ברירת מחדל 3 שנים), ייעודית לבקטסט בלבד -
    כדי לצבור מספיק טריידים למדגם סטטיסטי משמעותי. מטמון ל-24 שעות כי לא צריך רענון תכוף. """
    result, err = fetch_with_retry(lambda: _hist_window(ticker, period))
    if result is None or result.empty:
        return pd.DataFrame(), err
    return result, None

@st.cache_data(ttl=86400)
def get_earnings_days(ticker):
    """ מחזיר (ימים עד דוח, שגיאה). אם שגיאה - הימים הם None, לא ברירת מחדל מזויפת. """
    def _fetch():
        dates = yf.Ticker(ticker).get_earnings_dates(limit=3)
        if dates is not None and not dates.empty:
            future = dates[dates.index.tz_localize(None) > datetime.now()]
            if not future.empty:
                return (future.index[0].tz_localize(None) - datetime.now()).days
        return 999  # אין דוח עתידי ידוע בטווח הנתונים
    result, err = fetch_with_retry(_fetch, retries=1)
    return result, err

@st.cache_data(ttl=86400)
def fetch_earnings_dates_backtest(ticker):
    """ שולף היסטוריית תאריכי דוחות מלאה (לא רק הדוח הבא) - לשימוש בבקטסט לבדיקת
    'הימנעות ממסחר סביב דוחות'. מחזיר set של תאריכים (date בלבד, ללא שעה).
    מניות ETF (כמו SPY, GLD) לרוב לא מפרסמות דוחות - אז יחזור set ריק, וזה תקין. """
    def _fetch():
        dates = yf.Ticker(ticker).get_earnings_dates(limit=40)
        if dates is None or dates.empty:
            return set()
        idx = dates.index.tz_localize(None) if dates.index.tz is not None else dates.index
        return set(d.date() for d in idx)
    result, err = fetch_with_retry(_fetch, retries=1)
    return result if result is not None else set()

# ================= נתוני אופציות אמיתיים =================
@st.cache_data(ttl=900)
def fetch_options_signals(ticker, curr_price):
    """
    שולף נתוני אופציות אמיתיים מ-yfinance (option_chain) - בשונה מה'מנוע אופציות' הישן
    שהיה בעצם נגזרת של ממוצע נע ולא נתון אמיתי כלל.

    מה נשלף בפועל (נתונים אמיתיים מהבורסה):
      - Put/Call Open Interest Ratio: יחס בין פוזיציות Put פתוחות ל-Call פתוחות.
        גבוה (>1.2) = פוזיציונינג דובי כבד. זה גם דלק פוטנציאלי ל-Squeeze אם המחיר מתהפך.
      - Put/Call Volume Ratio: אותו רעיון אבל בפעילות היומית (זרימה טרייה, פחות "תקוע").
      - ATM IV: התנודתיות הגלומה סביב הכסף - כמה השוק מתמחר תנועה עתידית.

    ⚠️ מה זה *לא*: זה לא Short Interest אמיתי, לא Gamma Exposure, ולא Cost to Borrow.
    yfinance לא מספק אותם. ראה 'compute_squeeze_proxy' להסבר על המגבלה.

    שולף עד 2 תאריכי פקיעה קרובים בלבד - קרוב יותר להתנהגות הסוחרים בפועל,
    ומונע עיוות מפקיעות רחוקות מאוד (LEAPS) שמייצגות פוזיציות ארוכות טווח שונות באופיין.
    """
    def _atm_price(row):
        """ מחיר החוזה: מעדיף אמצע bid/ask (מייצג טוב יותר מחיר סחיר בפועל),
        ונופל ל-lastPrice אם אין ציטוטים חיים (למשל מחוץ לשעות המסחר). """
        bid = row.get('bid'); ask = row.get('ask'); last = row.get('lastPrice')
        if pd.notna(bid) and pd.notna(ask) and bid > 0 and ask > 0:
            return float((bid + ask) / 2)
        if pd.notna(last) and last > 0:
            return float(last)
        return None

    def _fetch():
        tk = yf.Ticker(ticker)
        exps = tk.options
        if not exps:
            return None
        calls_oi = puts_oi = calls_vol = puts_vol = 0
        iv_samples = []
        atm_call_px = atm_put_px = None
        first_exp = None
        for idx, exp in enumerate(list(exps)[:2]):
            chain = tk.option_chain(exp)
            c, p = chain.calls, chain.puts
            if c is not None and not c.empty:
                calls_oi += float(c['openInterest'].fillna(0).sum())
                calls_vol += float(c['volume'].fillna(0).sum())
                # IV סביב הכסף: החוזה שה-strike שלו הכי קרוב למחיר הנוכחי
                atm = c.iloc[(c['strike'] - curr_price).abs().argsort()[:1]]
                if not atm.empty and pd.notna(atm['impliedVolatility'].iloc[0]):
                    iv_samples.append(float(atm['impliedVolatility'].iloc[0]))
                if idx == 0 and not atm.empty:
                    atm_call_px = _atm_price(atm.iloc[0])
                    first_exp = exp
            if p is not None and not p.empty:
                puts_oi += float(p['openInterest'].fillna(0).sum())
                puts_vol += float(p['volume'].fillna(0).sum())
                atm = p.iloc[(p['strike'] - curr_price).abs().argsort()[:1]]
                if not atm.empty and pd.notna(atm['impliedVolatility'].iloc[0]):
                    iv_samples.append(float(atm['impliedVolatility'].iloc[0]))
                if idx == 0 and not atm.empty:
                    atm_put_px = _atm_price(atm.iloc[0])

        if calls_oi + puts_oi < 100:  # נזילות אופציות זניחה - הנתון לא אמין
            return None

        pc_oi = (puts_oi / calls_oi) if calls_oi > 0 else None
        pc_vol = (puts_vol / calls_vol) if calls_vol > 0 else None
        atm_iv = float(np.mean(iv_samples)) if iv_samples else None
        return {"pc_oi_ratio": pc_oi, "pc_vol_ratio": pc_vol, "atm_iv": atm_iv,
                "total_oi": calls_oi + puts_oi, "expirations_used": list(exps)[:2],
                "atm_call_px": atm_call_px, "atm_put_px": atm_put_px,
                "expected_move_exp": first_exp}

    result, err = fetch_with_retry(_fetch, retries=1)
    return result, err

def compute_iv_percentile(df, atm_iv, window=252):
    """
    משווה את ה-IV הנוכחי לתנודתיות ההיסטורית *בפועל* (Realized Volatility) של המניה.
    יחס IV/RV גבוה = השוק מתמחר תנועה חריגה קדימה יחסית למה שקרה בפועל - שווה תשומת לב.
    זה קירוב ל-'IV Rank' אמיתי (שדורש היסטוריית IV, שאין ב-yfinance).
    """
    if atm_iv is None or len(df) < 60:
        return None, None
    daily_ret = df['Close'].pct_change().dropna().iloc[-min(window, len(df)):]
    if len(daily_ret) < 30 or daily_ret.std() == 0:
        return None, None
    realized_vol = float(daily_ret.std() * np.sqrt(252))
    if realized_vol <= 0:
        return None, None
    return realized_vol, (atm_iv / realized_vol)

def compute_expected_move(opt_sig, curr_price):
    """
    ===== תנועה צפויה (Expected Move) =====
    הנוסחה הסטנדרטית שבה שוק האופציות מתמחר את גודל התנועה הצפויה:
        (מחיר Call בכסף + מחיר Put בכסף) / מחיר המניה = % תנועה צפויה

    מה זה אומר: אם התוצאה היא 8%, השוק מתמחר תנועה של 8% - **למעלה או למטה**.
    שוק האופציות מתמחר את *גודל* התנועה, ואין לו שום יכולת לנבא את **הכיוון**.
    מי שמסיק מ-Expected Move גבוה שהמניה תעלה - טועה בקריאה של המספר.

    למה זה חשוב דווקא לנו: אנחנו סוחרים מניות עם סטופ. אם הסטופ שלנו במרחק 5%
    והשוק מתמחר תנועה של 12% בפקיעה הקרובה (בדרך כלל סביב דוח) - הסטופ שלנו
    צפוי להיפגע ברמת הסתברות גבוהה, גם אם כיוון המהלך יהיה לטובתנו בסופו של דבר.
    זה הופך את כלל האצבע "צא יומיים לפני דוח" למספר קונקרטי שאפשר להשוות לסטופ.

    ⚠️ הסתייגות: החישוב מבוסס על הפקיעה הקרובה ביותר, שלא בהכרח מכסה את תאריך
    הדוח. אם הדוח רחוק מהפקיעה, המספר מייצג תנודתיות רגילה ולא סיכון דוח.
    """
    if not opt_sig or curr_price <= 0:
        return None
    call_px = opt_sig.get("atm_call_px")
    put_px = opt_sig.get("atm_put_px")
    if call_px is None or put_px is None:
        return None
    move_abs = call_px + put_px
    move_pct = (move_abs / curr_price) * 100
    if move_pct <= 0 or move_pct > 60:  # מחוץ לטווח סביר - כנראה ציטוט פגום
        return None
    return {"move_pct": round(move_pct, 2), "move_abs": round(move_abs, 2),
            "upper": round(curr_price + move_abs, 2), "lower": round(curr_price - move_abs, 2),
            "expiration": opt_sig.get("expected_move_exp")}


def assess_stop_vs_expected_move(exp_move, sl_pct):
    """
    משווה את מרחק הסטופ שלנו לתנועה שהשוק מתמחר. זו בדיקת שפיות פשוטה אך חשובה:
    סטופ שצר משמעותית מהתנועה הצפויה = הסתברות גבוהה להיפגע על רעש, לא על טעות בניתוח.
    מחזיר (רמת סיכון, טקסט הסבר, יחס).
    """
    if exp_move is None or sl_pct is None:
        return None, None, None
    stop_dist = abs(sl_pct)
    if stop_dist <= 0:
        return None, None, None
    ratio = exp_move["move_pct"] / stop_dist
    if ratio >= 2.0:
        return "high", f"התנועה הצפויה ({exp_move['move_pct']:.1f}%) גדולה פי {ratio:.1f} מהסטופ ({stop_dist:.1f}%) - סיכון גבוה מאוד שהסטופ ייפגע על תנודתיות רגילה", ratio
    if ratio >= 1.2:
        return "medium", f"התנועה הצפויה ({exp_move['move_pct']:.1f}%) גדולה מהסטופ ({stop_dist:.1f}%) פי {ratio:.1f} - שקול סטופ רחב יותר או פוזיציה קטנה יותר", ratio
    return "low", f"הסטופ ({stop_dist:.1f}%) רחב מהתנועה הצפויה ({exp_move['move_pct']:.1f}%) - יחס סביר", ratio


def compute_earnings_move_history(df, earnings_dates):
    """
    ===== תנועת דוחות היסטורית (התחליף הבר-בדיקה ל-Expected Move) =====
    Expected Move האמיתי (מחירי אופציות) לא ניתן לבקטסט - yfinance נותן רק את
    שרשרת האופציות של היום, בלי היסטוריה. שימוש בערך של היום על תאריכים היסטוריים
    היה Look-ahead Bias. אז במקום מה שהשוק *תמחר*, מודדים מה בפועל *קרה*:
    לכל דוח בעבר - מה הייתה התנועה המוחלטת של המניה ביום המסחר שאחריו.

    מחזיר רשימה ממוינת של (תאריך, אחוז תנועה מוחלט). התנועה מחושבת מהסגירה שלפני
    הדוח לסגירה שאחריו - כלומר קופצת מעל הפער (gap), שזה בדיוק מה שמעניין אותנו.
    """
    if not earnings_dates or df.empty:
        return []
    idx_dates = [d.date() for d in df.index]
    closes = df['Close'].values
    moves = []
    for ed in sorted(earnings_dates):
        # יום המסחר הראשון שבו התגובה לדוח כבר משתקפת במחיר. דוחות מתפרסמים לרוב
        # אחרי הסגירה, אז התגובה נמדדת ביום המסחר שבתאריך הדוח או הראשון שאחריו.
        pos = None
        for i in range(1, len(idx_dates)):
            if idx_dates[i] >= ed:
                pos = i
                break
        if pos is None or closes[pos-1] <= 0:
            continue
        move = abs((closes[pos] / closes[pos-1]) - 1) * 100
        if 0 < move < 80:  # סינון ערכים חריגים (פיצולי מניה וכו')
            moves.append((idx_dates[pos], move))
    moves.sort(key=lambda x: x[0])
    return moves


def avg_past_earnings_move(move_history, before_date, min_samples=2):
    """
    ממוצע התנועה בדוחות שקרו **לפני** התאריך הנתון בלבד.
    זו הנקודה הקריטית: אם ניקח את הממוצע של כל ההיסטוריה, נשתמש בדוחות עתידיים
    שהסוחר לא יכול היה להכיר - וזה מזייף את התוצאות. מחזיר None אם אין מספיק דגימות.
    """
    past = [m for d, m in move_history if d < before_date]
    if len(past) < min_samples:
        return None
    return float(np.mean(past))


def apply_trade_cost(ret_pct, cost_pct_per_side):
    """
    מנכה עלויות מסחר מתשואת הטרייד. cost_pct_per_side מייצג עמלה + מחצית הספרד
    לכל כיוון, ולכן מוכפל ב-2 (כניסה + יציאה).
    למה זה חשוב: עם מאות טריידים ותשואות של 5-11%, עלות של 0.1% לכיוון מצטברת
    למספר שיכול להפוך אסטרטגיה "עובדת" ללא-כדאית. בקטסט בלי עלויות תמיד נראה טוב יותר.
    """
    return ret_pct - (cost_pct_per_side * 2)


def analyze_earnings_exposure(trades):
    """
    מפצל את הטריידים לשתי קבוצות - אלה שהוחזקו דרך דוח ואלה שלא - ומשווה ביצועים.
    זה נותן **מספר** למדיניות הדוחות במקום להסיק אותה מהפרש ב-Sharpe:
    אם החזקה דרך דוח מורידה את התוחלת ב-2%, יש הצדקה כמותית ליציאה מוקדמת.
    אם ההפרש אפסי - המדיניות מיותרת ורק מקטינה את מספר ההזדמנויות.
    """
    held = [t for t in trades if t.get("held_earnings")]
    clean = [t for t in trades if not t.get("held_earnings")]
    if not held or not clean:
        return None

    def _stats(group):
        rets = [t["return_pct"] for t in group]
        wins = [r for r in rets if r > 0]
        losses = [r for r in rets if r <= 0]
        return {"n": len(rets), "avg": float(np.mean(rets)),
                "win_rate": len(wins) / len(rets) * 100,
                "avg_win": float(np.mean(wins)) if wins else 0,
                "avg_loss": float(np.mean(losses)) if losses else 0,
                "worst": float(min(rets)), "best": float(max(rets)),
                "std": float(np.std(rets))}

    h, c = _stats(held), _stats(clean)
    return {"held": h, "clean": c, "edge": c["avg"] - h["avg"]}



def build_text_report(label, cfg, sm, bm, trades, pts, blocked, failed):
    L=[];A=L.append
    A("="*54); A(f"RUN: {label}")
    A(f"TIME: {datetime.now().strftime('%Y-%m-%d %H:%M')}"); A("="*54)
    A("--- CONFIG ---")
    for k,v in cfg.items(): A(f"  {k}: {v}")
    # ===== RUN-SIG: חתימת ריצה ומבדקי שפיות =====
    # רצים בכל הרצה. חתימה זהה = ריצה בת-שחזור.
    # כל הפרה מודפסת עם הטרייד עצמו, לא כמספר מצטבר.
    if trades:
        import hashlib as _hl, math as _mt
        _rows = []
        for _t in trades:
            _rows.append("|".join([str(_t.get("ticker","")),
                                   str(_t.get("entry_date","")),
                                   str(_t.get("exit_date","")),
                                   str(_t.get("reason","")),
                                   f'{_t.get("return_pct",0):.6f}']))
        _sig = _hl.md5("\n".join(sorted(_rows)).encode("utf-8")).hexdigest()[:12]
        A("--- RUN SIGNATURE ---")
        A(f"  sig: {_sig}  (טריידים: {len(trades)})")
        _bad = []
        for _t in trades:
            _r = _t.get("return_pct")
            if _t.get("days", 1) < 1:            _bad.append(("החזקה<יום", _t))
            elif _r is None or not _mt.isfinite(float(_r)): _bad.append(("תשואה לא סופית", _t))
            elif str(_t.get("exit_date","")) < str(_t.get("entry_date","")): _bad.append(("יציאה לפני כניסה", _t))
            elif not _t.get("sector"):           _bad.append(("סקטור ריק", _t))
            elif not _t.get("entry_score"):      _bad.append(("ציון כניסה 0", _t))
            # PRICE-SANITY: תשואה מעל 100% בטרייד בודד היא
            # כמעט תמיד פיצול עם התאמה שבורה. BYND הראתה
            # תנועות של 2900% שעברו בשקט.
            elif abs(float(_r)) > 100:           _bad.append(("תשואה בלתי אפשרית", _t))
        A("--- SANITY ---")
        # SCORE-BUCKETS: האם הציון בכניסה מנבא תוצאה?
        _sc = [t for t in trades if t.get("entry_score")]
        if len(_sc) >= 30:
            _edges = [0, 65, 70, 75, 80, 999]
            _rows = []
            for _a, _b in zip(_edges[:-1], _edges[1:]):
                _g = [t for t in _sc if _a <= float(t["entry_score"]) < _b]
                if not _g:
                    continue
                _r = [float(t["return_pct"]) for t in _g]
                _w = [x for x in _r if x > 0]
                _l = [x for x in _r if x <= 0]
                _gp = sum(_w)
                _gl = abs(sum(_l))
                _pf = (_gp / _gl) if _gl > 0 else float("inf")
                _rows.append((_a, _b, len(_g), sum(_r)/len(_r),
                              sorted(_r)[len(_r)//2],
                              len(_w)/len(_r)*100, _pf))
            A("--- SCORE BUCKETS ---")
            for _a, _b, _n, _av, _md, _wr, _pf in _rows:
                _lbl = f"{_a}-{_b}" if _b < 999 else f"{_a}+"
                _pfs = "inf" if _pf == float("inf") else f"{_pf:.2f}"
                A(f"  {_lbl:>7}: n={_n:<5} avg={_av:+6.2f}%  med={_md:+6.2f}%"
                  f"  win={_wr:4.1f}%  PF={_pfs}")
            _vals = sorted({round(float(t["entry_score"]), 2) for t in _sc})
            _byday = {}
            for t in _sc:
                _byday.setdefault(str(t["entry_date"]), []).append(
                    round(float(t["entry_score"]), 2))
            _multi = [v for v in _byday.values() if len(v) > 1]
            _tied = sum(1 for v in _multi if len(set(v)) < len(v))
            A(f"  ערכי ציון שונים: {len(_vals)} · טווח {min(_vals):.1f}-{max(_vals):.1f}")
            A(f"  ימים עם יותר ממועמד אחד: {len(_multi)} · מתוכם עם תיקו: {_tied}")
        if _bad:
            A(f"  ⛔ {len(_bad)} הפרות מתוך {len(trades)} טריידים")
            for _w, _t in _bad[:15]:
                A(f"     ⛔ {_w}: {_t.get('ticker')} {_t.get('entry_date')} → {_t.get('exit_date')}")
            if len(_bad) > 15: A(f"     ... ועוד {len(_bad)-15}")
        else:
            A(f"  ✅ נקי — {len(trades)} טריידים עברו את כל המבדקים")
        # ===== מעבדה: כל טרייד בשורה, רק כשהמדגם קריא =====
        if len(trades) <= 60 or "מעבדה" in str(cfg.get("cat","")):
            A("--- TRADES ---")
            for _t in sorted(trades, key=lambda x: str(x.get("entry_date",""))):
                A(f"  {str(_t.get('ticker','')):6} "
                  f"{str(_t.get('entry_date',''))[:10]} → {str(_t.get('exit_date',''))[:10]} "
                  f"{str(_t.get('days','')):>3}d "
                  f"{_t.get('return_pct',0):+7.2f}%  "
                  f"{str(_t.get('reason','')):10} "
                  f"score={_t.get('entry_score',0):.0f} "
                  f"{str(_t.get('sector',''))[:18]}")
    if sm is None or not trades:
        A("--- NO TRADES ---"); return "\n".join(L)
    pf = "inf" if sm['profit_factor']==float('inf') else f"{sm['profit_factor']:.2f}"
    A("--- RESULTS ---")
    A(f"  trades: {sm['num_trades']}")
    A(f"  win_rate: {sm['win_rate']:.1f}%")
    A(f"  profit_factor: {pf}")
    A(f"  avg_win: {sm['avg_win']:+.2f}%")
    A(f"  avg_loss: {sm['avg_loss']:+.2f}%")
    A(f"  compound_return: {sm['total_return_pct']:+.1f}%")
    A(f"  compound_dd: {sm['max_drawdown_pct']:.1f}%")
    A(f"  avg_days: {sm['avg_days_held']:.1f}")
    if sm.get("realistic_return_pct") is not None:
        sh=sm.get('realistic_sharpe'); ca=sm.get('realistic_calmar')
        A("--- PORTFOLIO ---")
        A(f"  return: {sm['realistic_return_pct']:+.1f}%")
        A(f"  max_dd: {sm['realistic_dd_pct']:.1f}%")
        # CAPITAL-PRESSURE: לחץ הון — כמה הזדמנויות לא מומנו
        _sk = sm.get("skipped_trades")
        _mc = sm.get("max_concurrent")
        if _sk is not None:
            _tot = sm.get("num_trades") or 0
            _pct = (_sk / _tot * 100) if _tot else 0
            A(f"  נדחו מחוסר הון: {_sk} ({_pct:.0f}% מהטריידים — התיק רץ על השאר)")
            A(f"  שיא פוזיציות במקביל: {_mc}")
            if _VIX_EXPOSURE:
                _av = sum(_VIX_EXPOSURE) / len(_VIX_EXPOSURE)
                _nm = len(_VIX_MAP) if _VIX_MAP else 0
                _hit = sum(1 for _x in _VIX_EXPOSURE if _x != 1.0)
                A(f"  מקדם חשיפה ממוצע: {_av:.2f}  (1.00 = ללא שינוי)")
                A(f"  סכמה: {_VIX_SIZING} · ימי VIX במפה: {_nm} · הקצאות שהושפעו: {_hit}/{len(_VIX_EXPOSURE)}")
        A(f"  SHARPE: {sh:.2f}" if sh else "  SHARPE: n/a")
        A(f"  CALMAR: {ca:.2f}" if ca else "  CALMAR: n/a")
    rs={}
    for t in trades: rs[t["reason"]]=rs.get(t["reason"],0)+1
    A("--- EXIT REASONS ---")
    for r,c in sorted(rs.items(), key=lambda x:-x[1]):
        A(f"  {r}: {c} ({c/len(trades)*100:.0f}%)")
    if bm:
        f2=lambda v: f"{v:.2f}" if v is not None else "n/a"
        A("--- BENCHMARKS ---")
        A(f"  BuyHold: ret {bm['bh_return']:+.1f}% dd {bm['bh_dd']:.1f}% sharpe {f2(bm.get('bh_sharpe'))} calmar {f2(bm.get('bh_calmar'))}")
        A(f"  SMA50200: ret {bm['sma_return']:+.1f}% dd {bm['sma_dd']:.1f}% sharpe {f2(bm.get('sma_sharpe'))} calmar {f2(bm.get('sma_calmar'))}")
        if bm.get("ew_return") is not None:
            A(f"  EqualWeight: ret {bm['ew_return']:+.1f}% dd {bm['ew_dd']:.1f}% "
              f"sharpe {f2(bm.get('ew_sharpe'))} calmar {f2(bm.get('ew_calmar'))} "
              f"(תיק אמיתי, {bm.get('ew_n')} מניות)")
            A("  ** BuyHold/SMA50200 הם ממוצע פר-מניה — לא בני-השוואה לתיק **")
    ee=analyze_earnings_exposure(trades)
    A("--- EARNINGS SPLIT ---")
    if ee:
        A(f"  held: n={ee['held']['n']} avg {ee['held']['avg']:+.2f}% win {ee['held']['win_rate']:.0f}% worst {ee['held']['worst']:.1f}% std {ee['held']['std']:.1f}")
        A(f"  clean: n={ee['clean']['n']} avg {ee['clean']['avg']:+.2f}% win {ee['clean']['win_rate']:.0f}% worst {ee['clean']['worst']:.1f}% std {ee['clean']['std']:.1f}")
        A(f"  edge: {ee['edge']:+.2f}%")
    else:
        A("  n/a")
    if blocked:
        A("--- BLOCKED BY FILTER ---")
        for k,v in blocked.items(): A(f"  {k}: {v}")
    if pts:
        kr="\u05ea\u05e9\u05d5\u05d0\u05d4 \u05de\u05e6\u05d8\u05d1\u05e8\u05ea %"
        kt="\u05d8\u05d9\u05e7\u05e8"; kn="\u05d8\u05e8\u05d9\u05d9\u05d3\u05d9\u05dd"
        kw="\u05d4\u05e6\u05dc\u05d7\u05d4 %"
        p=sorted(pts,key=lambda x:x[kr],reverse=True)
        # VS-BUYHOLD: האם ההפסד מגיע מבחירה או מניהול?
        try:
            if price_map:
                _by = {}
                for _t in trades:
                    _by.setdefault(_t["ticker"], []).append(_t["return_pct"])
                _rows = []
                for _tk, _rs in _by.items():
                    _s = price_map.get(_tk)
                    if _s is None or len(_s) < 2:
                        continue
                    _bh = (float(_s.iloc[-1]) / float(_s.iloc[0]) - 1) * 100
                    _ours = float(np.sum(_rs))
                    _rows.append((_tk, _ours, _bh, _ours - _bh, len(_rs)))
                if _rows:
                    _win = [r for r in _rows if r[3] > 0]
                    A("--- STRATEGY vs BUY&HOLD ---")
                    A(f"  ניצחנו ב-{len(_win)} מתוך {len(_rows)} מניות ({len(_win)/len(_rows)*100:.0f}%)")
                    _md = float(np.median([r[3] for r in _rows]))
                    _mn = float(np.mean([r[3] for r in _rows]))
                    A(f"  הפרש חציוני: {_md:+.1f} נק׳ · ממוצע: {_mn:+.1f} נק׳")
                    _rows.sort(key=lambda r: r[3])
                    A("  חמש הגרועות (הפסדנו הכי הרבה מול החזקה):")
                    for _tk, _o, _b, _d, _n in _rows[:5]:
                        A(f"     {_tk:6} שלנו {_o:+7.1f}%  החזקה {_b:+7.1f}%  פער {_d:+7.1f}  ({_n} טר׳)")
                    A("  חמש הטובות:")
                    for _tk, _o, _b, _d, _n in _rows[-5:][::-1]:
                        A(f"     {_tk:6} שלנו {_o:+7.1f}%  החזקה {_b:+7.1f}%  פער {_d:+7.1f}  ({_n} טר׳)")
                    # פילוח לפי כיוון המניה: האם אנחנו טובים דווקא
                    # במניות יורדות (הגנה) וגרועים בעולות (זנב ימני)?
                    _up = [r for r in _rows if r[2] > 20]
                    _dn = [r for r in _rows if r[2] < -20]
                    if _up:
                        A(f"  במניות שעלו >20%: ניצחנו ב-{sum(1 for r in _up if r[3]>0)}/{len(_up)} · פער חציוני {float(np.median([r[3] for r in _up])):+.1f}")
                    if _dn:
                        A(f"  במניות שירדו >20%: ניצחנו ב-{sum(1 for r in _dn if r[3]>0)}/{len(_dn)} · פער חציוני {float(np.median([r[3] for r in _dn])):+.1f}")
        except Exception as _e:
            A(f"  ⚠️ vs-buyhold נכשל: {_e}")
        A("--- PER TICKER ---")
        for r in p[:5]: A(f"  + {r[kt]}: {r[kr]:+.1f}% ({r[kn]} tr, {r[kw]:.0f}% win)")
        if len(p)>5:
            for r in p[-5:]: A(f"  - {r[kt]}: {r[kr]:+.1f}% ({r[kn]} tr, {r[kw]:.0f}% win)")
    if failed:
        A(f"--- FAILED ({len(failed)}) ---")
        A("  "+", ".join(str(f).split(" (")[0] for f in failed))
    return "\n".join(L)


def render_report_export(reports, key=""):
    if not reports: return
    full="\n\n".join(reports)
    st.markdown("---")
    st.markdown("### \U0001F4CB \u05d3\u05d5\u05d7 \u05d8\u05e7\u05e1\u05d8")
    st.code(full, language="text")
    st.download_button("\u05d4\u05d5\u05e8\u05d3", full,
        file_name=f"base44_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
        mime="text/plain", key=f"dl_{key}")


@st.cache_data(ttl=86400)
def fetch_vix_history(period="3y"):
    """
    היסטוריית VIX לבקטסט. עד עכשיו הבקטסט השתמש ב-macro_proxy קבוע - כלומר
    לא בדק בכלל את השפעת מצב השוק. זה מאפשר לבדוק את הסתירה שזיהינו:
    הסורק שלנו חוסם כניסות כש-VIX > 28, בעוד ש"כללי קניית הדיפ" טוענים
    ש-VIX > 30 הוא דווקא **איתות כניסה**. אחד מהם טועה - הבקטסט יכריע.
    """
    result, err = fetch_with_retry(lambda: _hist_window("^VIX", period))
    if result is None or result.empty:
        return None
    return result['Close']


def align_series_to_index(series, target_index):
    """ מיישר סדרה חיצונית (למשל VIX) לאינדקס התאריכים של המניה, עם ffill.
    מסיר timezone כדי למנוע אי-התאמה בין מקורות נתונים שונים. """
    if series is None or len(series) == 0:
        return None
    s = series.copy()
    try:
        if s.index.tz is not None:
            s.index = s.index.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    ti = target_index
    try:
        if ti.tz is not None:
            ti = ti.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    return s.reindex(ti, method='ffill')


def compute_weekly_trend_ok(df, weekly_sma_weeks=30):
    """
    ===== אישור מגמה שבועי ("Zoom Out") =====
    הרעיון: לפני שנכנסים לפי הגרף היומי, לוודא שגם התמונה הגדולה חיובית -
    כלומר הסגירה השבועית מעל ממוצע נע שבועי. זה מסנן טריידים "נגד הזרם הגדול".

    ⚠️ מניעת הצצה לעתיד: משתמשים ב-shift(1) על הסדרה השבועית, כלומר תמיד
    מסתמכים על **השבוע שהסתיים**, לא על השבוע הנוכחי שעדיין באמצע.
    בלי ה-shift היינו משתמשים בסגירה של יום שישי כדי להחליט על יום שני - הצצה לעתיד.
    """
    if df.empty or len(df) < weekly_sma_weeks * 5:
        return None
    weekly_close = df['Close'].resample('W').last()
    if len(weekly_close) < weekly_sma_weeks + 2:
        return None
    weekly_sma = weekly_close.rolling(weekly_sma_weeks).mean()
    ok = (weekly_close > weekly_sma).shift(1)  # רק שבועות שהסתיימו
    return ok.reindex(df.index, method='ffill').fillna(False)


def compute_post_earnings_block(df, earnings_dates, drop_pct=5.0, wait_days=3):
    """
    ===== חוק שלושת הימים =====
    אחרי ירידה חדה בעקבות דוח, ממתינים כמה ימי מסחר לפני שקילת כניסה מחדש.
    ההיגיון: לתת לשוק לעכל את הנתונים במקום "לתפוס סכין נופלת" - המחיר אחרי
    דוח גרוע ממשיך לרוב לרדת עוד כמה ימים לפני שהוא מתייצב.

    מחזיר set של אינדקסים (מיקומים ב-df) שבהם כניסה חסומה.
    שים לב: נחסמות רק ירידות (drop), לא עליות - קפיצה חיובית אחרי דוח אינה
    "סכין נופלת" ואין סיבה להימנע ממנה.
    """
    if not earnings_dates or df.empty:
        return set()
    idx_dates = [d.date() for d in df.index]
    closes = df['Close'].values
    blocked = set()
    for ed in sorted(earnings_dates):
        pos = None
        for i in range(1, len(idx_dates)):
            if idx_dates[i] >= ed:
                pos = i
                break
        if pos is None or closes[pos-1] <= 0:
            continue
        change = ((closes[pos] / closes[pos-1]) - 1) * 100
        if change <= -abs(drop_pct):   # ירידה חדה בלבד
            for k in range(pos, min(pos + wait_days + 1, len(closes))):
                blocked.add(k)
    return blocked


def apply_weekly_trade_cap(trades, max_per_week):
    """
    ===== הגבלת מסחר יתר =====
    מגביל את מספר הכניסות החדשות בכל שבוע קלנדרי, ושומר את בעלות הציון הגבוה ביותר.
    זו בדיקה ישירה לשאלה: האם הטריידים ה"שוליים" (הנמוכים בדירוג) תורמים או גורעים?
    אם הגבלה ל-3 בשבוע משפרת את התוצאות - סימן שהמערכת מייצרת יותר מדי אותות חלשים.

    ההגבלה מופעלת ברמת **התיק** (אחרי איחוד כל המניות), כי זו הרמה שבה
    מסחר יתר קורה בפועל - לא ברמת מניה בודדת.
    """
    if not trades or max_per_week <= 0:
        return trades, 0
    by_week = {}
    for t in trades:
        wk = (t["entry_date"].isocalendar()[0], t["entry_date"].isocalendar()[1])
        by_week.setdefault(wk, []).append(t)
    kept = []
    dropped = 0
    for wk, group in by_week.items():
        if len(group) <= max_per_week:
            kept.extend(group)
        else:
            # שומרים את בעלות הציון הגבוה; אם אין ציון שמור - לפי סדר כרונולוגי
            ranked = sorted(group, key=lambda t: t.get("entry_score", 0), reverse=True)
            kept.extend(ranked[:max_per_week])
            dropped += len(group) - max_per_week
    kept.sort(key=lambda t: t["entry_date"])
    return kept, dropped




@st.cache_data(ttl=86400)
def fetch_spy_history(period="3y"):
    """ היסטוריית SPY לבקטסט של יציאת חירום מאקרו. """
    result, err = fetch_with_retry(lambda: _hist_window("SPY", period))
    if result is None or result.empty:
        return None
    return result['Close']


def compute_risk_off(spy_series, target_index, mode="sma200", confirm_days=2, dd_pct=8.0):
    """
    ===== יציאת חירום מאקרו =====
    עד היום המערכת הסתכלה רק על המניה הבודדת. כשהשוק כולו מתפרק, כל המניות
    יורדות יחד - וסטופ פר-מניה מוציא אותנו אחת-אחת, באיחור ובהפסד.

    כאן מחושבת סדרה בוליאנית "השוק במצב סיכון" לכל יום מסחר:
      - sma200:   SPY סוגר מתחת לממוצע 200
      - drawdown: SPY יורד יותר מ-X% משיא 20 הימים האחרונים

    confirm_days מונע whipsaw: נדרשים N ימים רצופים מתחת לתנאי לפני שמגיבים.
    בלי זה, נגיעה חד-יומית ב-SMA200 הייתה מוציאה מהתיק כולו ומכניסה מחדש גבוה יותר.

    ⚠️ הסתייגות מדגם: התקופה שנבדקת (3 שנים) היא שוק עולה ברובה. מנגנון כזה
    ייראה חלש בבקטסט - הערך שלו מתגלה במשברים, ואין לנו כאלה במדגם.
    """
    if spy_series is None:
        return None
    s = align_series_to_index(spy_series, target_index)
    if s is None or len(s) == 0:
        return None
    if mode == "drawdown":
        peak = s.rolling(20).max()
        raw = (s < peak * (1 - abs(dd_pct) / 100.0))
    else:
        sma = s.rolling(200).mean()
        raw = (s < sma)
    raw = raw.fillna(False).astype(int)
    if confirm_days > 1:
        ok = raw.rolling(confirm_days).sum() >= confirm_days
    else:
        ok = raw.astype(bool)
    return ok.fillna(False).values

def compute_reversal_signals(df):
    """
    ===== יציאה על היפוך מגמה =====
    עד היום המערכת יצאה משלוש סיבות בלבד: סטופ, יעד, או שעון (30 יום).
    ה"שעון" היה 41-63% מהיציאות - כלומר רוב הפוזיציות נסגרו מסיבה
    שאין לה שום קשר לשוק. זו הייתה יציאה עיוורת.

    כאן מחושבים שני איתותי היפוך אמיתיים, מראש לכל היסטוריית המניה:
      - break_sma20: סגירה מתחת ל-SMA20 (שבירת המגמה הקצרה)
      - macd_flip:   היסטוגרמת MACD עוברת מחיובי לשלילי (איבוד תאוצה)

    ⚠️ מניעת הצצה לעתיד: הערכים מחושבים על סגירת אותו יום, והיציאה
    מתבצעת במחיר הסגירה של אותו יום - בדיוק כמו יציאת "זמן" הקיימת.
    אין כאן שימוש בשום נתון עתידי.
    """
    if df.empty or len(df) < 30:
        return None, None
    close = df['Close']
    sma20 = close.rolling(20).mean()
    below = (close < sma20).fillna(False).values
    _, _, hist = calc_macd(close)
    h = hist.fillna(0)
    flip = ((h < 0) & (h.shift(1) >= 0)).fillna(False).values
    return below, flip


@st.cache_data(ttl=86400)
def fetch_returns(ticker, period="1y"):
    """ תשואות יומיות לחישוב קורלציה. מטמון 24 שעות. """
    def _f():
        return _hist_window(ticker, period)['Close']
    r, e = fetch_with_retry(_f, retries=1)
    if r is None or len(r) < 60:
        return None
    try:
        if r.index.tz is not None:
            r.index = r.index.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    return r.pct_change().dropna()


def category_fit(tickers, period="1y"):
    """
    ===== התאמה התנהגותית לקטגוריה =====
    הסיווג הרשמי (yfinance) אומר איך החברה *מוגדרת*. כאן נמדד מה שבאמת חשוב:
    האם המניה **זזה** כמו שאר חברי הקטגוריה.

    לכל מניה מחושבת קורלציית התשואות היומיות מול הממוצע של שאר המניות
    בקטגוריה (בלעדיה, כדי שלא תמדוד את עצמה). ערך גבוה = היא באמת חלק
    מהקבוצה; ערך נמוך = היא יושבת שם על סמך תווית בלבד.

    ⚠️ מגבלה: קורלציה נמוכה לא בהכרח אומרת שיוך שגוי. מניה קטנה ותנודתית
    בסקטור של ענקיות תראה קורלציה נמוכה גם כשהשיוך נכון לחלוטין.
    לכן זו אינדיקציה לבדיקה, לא פסק דין.
    """
    data = {}
    for t in tickers:
        r = fetch_returns(t, period)
        if r is not None and len(r) > 60:
            data[t] = r
    if len(data) < 3:
        return None
    df = pd.DataFrame(data).dropna(how='all')
    df = df.dropna(axis=1, thresh=int(len(df) * 0.6))
    if df.shape[1] < 3:
        return None
    df = df.fillna(0.0)
    out = {}
    for t in df.columns:
        others = df.drop(columns=[t])
        if others.shape[1] < 2:
            continue
        peer = others.mean(axis=1)
        try:
            c = float(df[t].corr(peer))
        except Exception:
            c = float('nan')
        out[t] = c
    return out

def compute_squeeze_proxy(rsi_val, vol_ratio, price_change_5d, opt_sig, iv_rv_ratio):
    """
    ⚠️⚠️ קרא את זה לפני שאתה סומך על המספר הזה ⚠️⚠️

    זהו **פרוקסי חלקי בלבד** ל-Short Squeeze, לא זיהוי אמיתי. הסיבה:
    זיהוי Squeeze אמיתי דורש שלושה נתונים שאף אחד מהם אינו זמין ב-yfinance:
      1. Short Interest % of Float - מתפרסם רק פעמיים בחודש ע"י הבורסות, ואפילו אז
         באיחור של שבוע-שבועיים. כלומר גם מקור בתשלום נותן תמונה מפגרת.
      2. Days to Cover - נגזר מ-Short Interest, אז אותה בעיה.
      3. Cost to Borrow / Short Availability - הסימן החי והמיידי ביותר ללחץ על שורטיסטים.
         זמין דרך Interactive Brokers API או ספקים בתשלום (Ortex, S3, Fintel) - לא כאן.

    מה כן נמדד כאן (כל אלה נתונים אמיתיים, אבל *עקיפים*):
      - RSI בקיצון תחתון: מניה שנמכרה בכבדות (Oversold אמיתי, מחושב מהמחיר)
      - נפח חריג: התעניינות פתאומית - לרוב מלווה מהלכים חדים
      - ירידה חדה ב-5 ימים: מה שמושך שורטיסטים להיכנס מלכתחילה
      - Put/Call OI גבוה: פוזיציונינג דובי כבד באופציות (זה כן נתון אמיתי מהבורסה)
      - IV/RV גבוה: השוק מתמחר תנועה חריגה קדימה

    השורה התחתונה: ציון גבוה כאן אומר "יש כאן תנאים שלפעמים מקדימים Squeeze",
    לא "יהיה Squeeze". אל תבנה על זה פוזיציה בלי אימות ידני של Short Interest אמיתי.
    """
    components = {}
    score = 0.0
    max_score = 0.0

    # 1. Oversold אמיתי (מבוסס RSI מחושב, לא פרוקסי מזויף)
    max_score += 30
    if rsi_val <= 25: components["oversold"] = 30
    elif rsi_val <= 32: components["oversold"] = 20
    elif rsi_val <= 40: components["oversold"] = 10
    else: components["oversold"] = 0
    score += components["oversold"]

    # 2. נפח חריג
    max_score += 20
    if vol_ratio >= 2.5: components["volume"] = 20
    elif vol_ratio >= 1.7: components["volume"] = 13
    elif vol_ratio >= 1.3: components["volume"] = 7
    else: components["volume"] = 0
    score += components["volume"]

    # 3. ירידה חדה לאחרונה (מה שמושך שורטיסטים)
    max_score += 15
    if price_change_5d <= -12: components["drop"] = 15
    elif price_change_5d <= -7: components["drop"] = 10
    elif price_change_5d <= -4: components["drop"] = 5
    else: components["drop"] = 0
    score += components["drop"]

    # 4. Put/Call OI - פוזיציונינג דובי כבד (נתון אופציות אמיתי)
    max_score += 20
    pc = opt_sig.get("pc_oi_ratio") if opt_sig else None
    if pc is None:
        components["put_call"] = None
        max_score -= 20  # לא זמין - לא מענישים, פשוט מנרמלים בלעדיו
    else:
        if pc >= 1.5: components["put_call"] = 20
        elif pc >= 1.15: components["put_call"] = 13
        elif pc >= 0.9: components["put_call"] = 6
        else: components["put_call"] = 0
        score += components["put_call"]

    # 5. IV/RV - השוק מתמחר תנועה חריגה
    max_score += 15
    if iv_rv_ratio is None:
        components["iv_rv"] = None
        max_score -= 15
    else:
        if iv_rv_ratio >= 1.6: components["iv_rv"] = 15
        elif iv_rv_ratio >= 1.25: components["iv_rv"] = 9
        elif iv_rv_ratio >= 1.0: components["iv_rv"] = 4
        else: components["iv_rv"] = 0
        score += components["iv_rv"]

    if max_score <= 0:
        return None, components, 0
    normalized = (score / max_score) * 100
    data_coverage = max_score / 100  # כמה מהרכיבים היו זמינים בפועל
    return round(normalized, 1), components, round(data_coverage * 100)

def options_sentiment_bonus(opt_sig, iv_rv_ratio):
    """
    בונוס/קנס קטן לציון הסופי מנתוני אופציות אמיתיים (טווח: -6 עד +8 נקודות).
    מכוון להיות *משני* - הציון הטכני עדיין נושא את רוב המשקל, כי נתוני האופציות
    מ-yfinance חלקיים (אין Gamma, אין Skew מלא) ולא מספיק אמינים לשאת משקל כבד.
    """
    if not opt_sig:
        return 0.0, "אין נתוני אופציות"
    bonus = 0.0
    notes = []
    pc = opt_sig.get("pc_oi_ratio")
    if pc is not None:
        if pc <= 0.6:
            bonus += 4; notes.append(f"P/C נמוך ({pc:.2f}) - פוזיציונינג שורי")
        elif pc <= 0.85:
            bonus += 2; notes.append(f"P/C מאוזן-שורי ({pc:.2f})")
        elif pc >= 1.6:
            bonus -= 4; notes.append(f"P/C גבוה מאוד ({pc:.2f}) - פוזיציונינג דובי כבד")
        elif pc >= 1.2:
            bonus -= 2; notes.append(f"P/C גבוה ({pc:.2f}) - נטייה דובית")
    if iv_rv_ratio is not None:
        if iv_rv_ratio >= 1.8:
            bonus -= 2; notes.append(f"IV/RV {iv_rv_ratio:.2f} - אופציות יקרות, ציפייה לתנודה חדה")
        elif iv_rv_ratio <= 0.8:
            bonus += 2; notes.append(f"IV/RV {iv_rv_ratio:.2f} - תנודתיות גלומה נמוכה, שוק רגוע")
    return round(max(-6, min(8, bonus)), 1), " | ".join(notes) if notes else "נייטרלי"

# ================= אינדיקטורים טכניים אמיתיים =================
def calc_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def calc_macd(close, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def calc_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def find_structural_stop(df, curr_price, lookback=15, buffer_pct=1.0):
    """
    מוצא סטופ מבוסס מבנה מחיר אמיתי (Swing Low) במקום מכפיל ATR גנרי שלא מתחשב
    במבנה הספציפי של המניה. מחפש את השפל הנמוך ביותר ב-lookback הימים האחרונים,
    ומציב את הסטופ קצת מתחתיו (buffer_pct%) כדי לא להיתפס בנגיעה מדויקת ברמה.
    זה כלל אחיד שחל על כל המניות באותו אופן - לא כיול נפרד לכל טיקר - ולכן
    לא נופל למלכודת ה-Overfitting של פרמטרים ספציפיים-למניה.
    מחזיר None אם אין מספיק נתונים, או אם הרמה שנמצאה לא הגיונית (קרובה/רחוקה מדי).
    """
    if len(df) < lookback:
        return None
    recent_low = df['Low'].iloc[-lookback:].min()
    stop = recent_low * (1 - buffer_pct / 100)
    if stop <= 0 or stop >= curr_price:
        return None
    dist_pct = (curr_price - stop) / curr_price * 100
    if dist_pct < 1.0 or dist_pct > 20.0:  # קרוב/רחוק מדי מכדי להיות סטופ שימושי - נופלים חזרה ל-ATR
        return None
    return stop

def get_trend_regime(df, curr_price):
    """
    מקור אחד ויחיד לקביעת יחס המחיר לממוצעים - קצר (SMA20) וארוך (SMA150 או מנורמל).
    נעשה שימוש בפונקציה זו הן לציון המשוקלל והן לשלב הביצוע, כדי שלא יהיו סתירות
    בין 'ציון גבוה' לבין 'שלב דובי' על אותה מניה.
    """
    total_bars = len(df)
    if total_bars < 20:
        return None
    is_normalized = total_bars < 150
    long_window = max(20, total_bars - 5) if is_normalized else 150
    sma_long = df['Close'].rolling(window=long_window).mean().iloc[-1]
    sma20 = df['Close'].rolling(20).mean().iloc[-1]
    sma50 = df['Close'].rolling(50).mean().iloc[-1]
    if pd.isna(sma20) or pd.isna(sma_long) or pd.isna(sma50):
        return None
    return {"sma20": sma20, "sma50": sma50, "sma_long": sma_long,
            "is_normalized": is_normalized, "long_window": long_window}


def vol_band(df):
    """
    ===== שיוך מניה לרמת תנודתיות =====
    אותה חלוקה שבה משתמש הבקטסט (גבולות 3.0/4.5/6.5), כדי שהסורק החי
    יציג למשתמש באיזה משטר המניה נמצאת ומה הכללים שחלים עליה.
    מחזיר (ATR%, תווית, סף, ימי החזקה).
    """
    if df.empty or len(df) < 20:
        return None, "—", 65, 30
    a = calc_atr(df).iloc[-1]
    c = df['Close'].iloc[-1]
    if pd.isna(a) or c <= 0:
        return None, "—", 65, 30
    ap = float(a / c * 100)
    if ap < 3.0:
        return ap, "🟢 שקט", 65, 30
    if ap < 4.5:
        return ap, "🟡 בינוני", 55, 20
    if ap < 6.5:
        return ap, "🟠 תנודתי", 65, 20
    return ap, "🔴 קיצוני", 75, 30

def calculate_technical_score(df, use_trend=True, use_rsi=True, use_macd=True, use_vol=True,
                               directional_vol=True):
    """
    ציון מבוסס אך ורק על אינדיקטורים טכניים אמיתיים הנגזרים ממחיר/נפח:
    - מגמה (משלב קצר מול ארוך טווח - אותו מקור כמו שלב הביצוע, למניעת סתירות)
    - RSI (מומנטום/oversold-overbought)
    - MACD (האצת מגמה)
    - נפח מסחר יחסי *מכוון* (ראה הערה למטה)
    זה איננו ניתוח פונדמנטלי (אין רווחים, P/E וכו') ואיננו נתוני אופציות.
    """
    if df.empty or len(df) < 30:
        return None, {}, "אין מספיק נתונים היסטוריים (נדרשים 30+ ימי מסחר)"

    close = df['Close']
    curr = close.iloc[-1]
    regime = get_trend_regime(df, curr)
    if regime is None:
        return None, {}, "ממוצעים נעים לא זמינים (נתונים חסרים)"

    sma20, sma_long = regime["sma20"], regime["sma_long"]

    # מגמה משולבת: קצר טווח (SMA20) מול ארוך טווח (SMA150/מנורמל) - אותה הגדרה
    # המשמשת גם את שלב הביצוע (Bullish/Pullback/Bearish), כדי שהציון לא יסתור את השלב.
    if curr > sma20 and curr > sma_long:
        trend_score = 85  # יישור מלא: קצר וארוך טווח חיוביים
    elif curr > sma20 and curr < sma_long:
        trend_score = 55  # ריבאונד בתוך מגמת ירידה ארוכה - סיכון גבוה יותר
    elif curr < sma20 and curr > sma_long:
        trend_score = 45  # תיקון בתוך מגמת עלייה ארוכה - נורמלי יחסית
    else:
        trend_score = 15  # יישור מלא כלפי מטה

    rsi_val = calc_rsi(close).iloc[-1]
    # RSI מתורגם לציון: אזור בריא (45-65) הכי גבוה, קיצוניות (oversold/overbought) מורידה ביטחון
    if 45 <= rsi_val <= 65: rsi_score = 75
    elif 65 < rsi_val <= 75: rsi_score = 60
    elif rsi_val > 75: rsi_score = 25  # overbought - סיכון לתיקון
    elif 30 <= rsi_val < 45: rsi_score = 55
    else: rsi_score = 20  # oversold עמוק

    macd_line, signal_line, hist = calc_macd(close)
    macd_hist_val = hist.iloc[-1]
    macd_hist_prev = hist.iloc[-2] if len(hist) > 1 else macd_hist_val
    if macd_hist_val > 0 and macd_hist_val > macd_hist_prev: macd_score = 85
    elif macd_hist_val > 0: macd_score = 60
    elif macd_hist_val < 0 and macd_hist_val < macd_hist_prev: macd_score = 15
    else: macd_score = 40

    # ===== נפח מכוון (שינוי מהותי מהגרסה הקודמת) =====
    # קודם: vol_ratio * 40 - נתן ציון גבוה לנפח חריג גם ביום ירידה חדה, כלומר "פאניקת מכירות"
    # נספרה כאיתות חיובי. עכשיו: נפח חריג נספר חיובית רק אם הוא מלווה תנועת מחיר חיובית.
    vol, avg_vol = df['Volume'].iloc[-1], df['Volume'].rolling(20).mean().iloc[-1]
    vol_ratio = (vol / avg_vol) if avg_vol > 0 else 1
    day_change = ((close.iloc[-1] / close.iloc[-2]) - 1) * 100 if len(close) > 1 else 0
    base_vol_score = min(100, max(10, int(vol_ratio * 40)))
    if not directional_vol:
        vol_score = base_vol_score                # התנהגות ישנה - לבידוד בבקטסט
    elif day_change > 0.3:
        vol_score = base_vol_score               # נפח בעלייה - אישור אמיתי
    elif day_change < -0.3:
        vol_score = max(10, 100 - base_vol_score)  # נפח בירידה - היפוך הסימן
    else:
        vol_score = 50                            # יום שטוח - נייטרלי

    weights = {"trend": 0.35 if use_trend else 0, "rsi": 0.25 if use_rsi else 0,
               "macd": 0.25 if use_macd else 0, "vol": 0.15 if use_vol else 0}
    tot_w = sum(weights.values())
    if tot_w == 0:
        return None, {}, "כל המנועים כבויים"

    final = ((trend_score*weights["trend"]) + (rsi_score*weights["rsi"]) +
              (macd_score*weights["macd"]) + (vol_score*weights["vol"])) / tot_w

    price_change_5d = ((close.iloc[-1] / close.iloc[-6]) - 1) * 100 if len(close) > 5 else 0

    breakdown = {
        "trend": trend_score, "rsi": rsi_score, "macd": macd_score, "vol": vol_score,
        "rsi_raw": round(rsi_val, 1), "macd_hist_raw": round(macd_hist_val, 3),
        "vol_ratio": round(vol_ratio, 2), "day_change": round(day_change, 2),
        "price_change_5d": round(price_change_5d, 2),
        "w_trend": weights["trend"]/tot_w, "w_rsi": weights["rsi"]/tot_w,
        "w_macd": weights["macd"]/tot_w, "w_vol": weights["vol"]/tot_w
    }
    return final, breakdown, None

# ================= ציון מורכב (מבנה חדש) =================
def calculate_composite_score(tech_score, macro_score, exec_p, opt_bonus=0.0):
    """
    ===== למה שינינו את מבנה הציון =====
    בגרסה הקודמת: ציון = (טכני × 0.7) + (מאקרו × 0.3).
    שתי בעיות מהותיות בשיטה הזו, *בדיוק* כשהמטרה היא לדרג מניות ולבחור את הטובה ביותר:

    בעיה 1 - דחיסת רזולוציה: המאקרו זהה לכל המניות בסריקה (אותו VIX, אותו SPY).
    לכן הוא לא מבדיל בין מניה למניה - הוא רק *מקרב את כולן לאמצע*. מניה עם 90 טכני
    ומניה עם 60 טכני, במאקרו 50, מקבלות 78 ו-57 - הפער נשחק מ-30 נקודות ל-21.
    הפתרון: מאקרו הופך ל**מכפיל** (0.80-1.00). הוא מוריד את כולן יחד כשהשוק גרוע,
    אבל *שומר על הפערים היחסיים* ביניהן. הדירוג נשאר חד.

    בעיה 2 - הציון מדד "חוזק", לא "כדאיות כניסה עכשיו": מניה במתיחת יתר קיצונית
    יכולה לקבל ציון 88 (מגמה מצוינת, MACD חזק) - למרות שהיא בדיוק המניה שלא כדאי
    להיכנס אליה כרגע. הכרטיס בממשק אמנם הציג אזהרה נפרדת, אבל ה*ציון עצמו* עדיין
    דירג אותה בראש הרשימה - וזה מה שהעין מסתכלת עליו קודם.
    הפתרון: **מכפיל איכות כניסה** שמעניש מתיחת יתר, סטופ לא-יעיל, ופאזות בעייתיות.

    התוצאה: ציון = טכני × מכפיל_מאקרו × מכפיל_כניסה + בונוס_אופציות
    זהו ציון "כדאיות כניסה משוקללת" - ולא רק "כמה המניה חזקה".
    """
    # --- מכפיל מאקרו: 0.80 (שוק גרוע) עד 1.00 (שוק מצוין) ---
    macro_mult = 0.80 + (max(0, min(100, macro_score)) / 100) * 0.20

    # --- מכפיל איכות כניסה ---
    entry_mult = 1.0
    entry_notes = []
    if exec_p is None:
        return None, {}
    if exec_p.get("is_overextended"):
        entry_mult *= 0.72
        entry_notes.append("מתיחת יתר (×0.72)")
    phase = exec_p.get("phase", "")
    if "Bear Rally" in phase:
        entry_mult *= 0.70
        entry_notes.append("ריבאונד בתוך ירידה (×0.70)")
    elif "דובי" in phase:
        entry_mult *= 0.55
        entry_notes.append("פאזה דובית (×0.55)")
    elif "פריצה" in phase:
        entry_mult *= 1.05
        entry_notes.append("פריצה מוקדמת (×1.05)")

    # ===== מכפיל יעילות סטופ - הוסר =====
    # היה כאן מכפיל שהעניש סטופים רחבים (מעל 10% → ×0.86). הבקטסט הראה שזו הייתה טעות:
    # הוא חסם ~200 טריידים רווחיים (474→275) והפיל את ה-Sharpe מ-1.93 ל-1.23.
    # הסיבה: Swing Low מייצר סטופים רחבים *בכוונה* - לפי מבנה מחיר אמיתי ולא לפי נוחות.
    # המכפיל למעשה נלחם במנגנון שהוכח כמשפר ביותר במערכת. אין החלפה - פשוט הוסר.
    # ה-cap הקיים של 12% ב-get_execution_params ממילא מטפל בסטופים באמת קיצוניים.
    sl_dist = abs(exec_p.get("sl_pct", 0))

    final = (tech_score * macro_mult * entry_mult) + opt_bonus
    final = max(0, min(100, final))

    detail = {"tech_raw": round(tech_score, 1), "macro_mult": round(macro_mult, 3),
              "entry_mult": round(entry_mult, 3), "opt_bonus": opt_bonus,
              "entry_notes": entry_notes, "final": round(final, 1)}
    return final, detail

def get_execution_params(df, curr_price, overext_threshold=8.0, stop_style="atr",
                          structural_lookback=15, structural_buffer_pct=1.0):
    """ מגדיר שלב מגמה, סטופ ויעד. משתמש באותו get_trend_regime של הציון,
    כך ששלב המגמה כאן תמיד יסכים עם ה'ציון' - לא יכולה להיות סתירה בין השניים. """
    regime = get_trend_regime(df, curr_price)
    if regime is None:
        return None

    sma20, sma50, sma_long = regime["sma20"], regime["sma50"], regime["sma_long"]
    is_normalized, long_term_window = regime["is_normalized"], regime["long_window"]
    atr = calc_atr(df).iloc[-1]

    if pd.isna(atr) or atr == 0:
        return None

    dist_20 = ((curr_price - sma20) / sma20) * 100
    is_overextended = False

    if curr_price > sma20 and curr_price > sma_long:
        if dist_20 > overext_threshold:
            phase, sl, is_overextended = "⚠️ מתיחת יתר (Overextended)", curr_price - (atr * 1.0), True
        elif sma20 > sma50 and ((sma20 - sma50) / sma50) < 0.04:
            phase, sl = "🌱 פריצה (Early Trend)", curr_price - (atr * 2.5)
        else:
            phase, sl = "🏃 מגמה בשלה (Mature)", curr_price - (atr * 1.5)
    elif curr_price < sma20 and curr_price > sma_long:
        phase, sl = "📉 תיקון (Pullback)", curr_price - (atr * 1.5)
    elif curr_price > sma20 and curr_price < sma_long:
        phase, sl = "⚠️ ריבאונד בתוך מגמת ירידה (Bear Rally)", curr_price - (atr * 1.0)
    else:
        phase, sl = "🔴 דובי (Bearish)", curr_price + (atr * 1.5)

    # סטופ מבני (Swing Low) - רק לכניסות Long (מחיר מעל SMA20, לא בפאזה דובית)
    if stop_style == "structural" and curr_price > sma20:
        struct_sl = find_structural_stop(df, curr_price, structural_lookback, structural_buffer_pct)
        if struct_sl is not None:
            sl = struct_sl

    if sl <= 0 or sl == curr_price:
        return None

    raw_risk = abs(curr_price - sl)
    max_risk = curr_price * 0.12
    was_capped = raw_risk > max_risk
    risk = min(raw_risk, max_risk)
    if was_capped:
        sl = curr_price - risk if sl < curr_price else curr_price + risk

    tp = curr_price - (risk * 2.5) if "דובי" in phase else curr_price + (risk * 2.5)
    sl_pct = ((sl - curr_price) / curr_price) * 100
    tp_pct = ((tp - curr_price) / curr_price) * 100

    return {"phase": phase, "sl": sl, "tp": tp, "sl_pct": sl_pct, "tp_pct": tp_pct,
            "is_overextended": is_overextended, "is_normalized": is_normalized,
            "is_capped": was_capped, "dist_20": dist_20,
            "norm_note": f"נורמל לחלון {long_term_window} ימים (מניה עם היסטוריה קצרה)" if is_normalized else None}

# ================= מנוע בקטסט =================

# ================= מנוע מהיר — חישוב אינדיקטורים מקדים =================
# הבעיה: הבקטסט קרא ל-calculate_technical_score על df.iloc[:i+1] בכל בר,
# כלומר חישב מחדש RSI/MACD/ממוצעים על כל ההיסטוריה — סיבוכיות ריבועית.
# הפתרון: מחשבים הכל פעם אחת וקוראים לפי אינדקס. כל האינדיקטורים סיבתיים
# (rolling/ewm מסתכלים רק אחורה), ולכן הערך בנקודה i זהה — אין הצצה לעתיד.
# השקילות נבדקה נומרית מול המסלול הישן לפני ההזרקה.

def precompute_indicator_arrays(df):
    close = df['Close']
    macd_line, signal_line, hist = calc_macd(close)
    vol = df['Volume']
    avg_vol = vol.rolling(20).mean()
    with np.errstate(divide='ignore', invalid='ignore'):
        vr = (vol / avg_vol).replace([np.inf, -np.inf], 1.0).fillna(1.0)
    return {
        "close": close.values, "high": df['High'].values, "low": df['Low'].values,
        "sma20": close.rolling(20).mean().values,
        "sma50": close.rolling(50).mean().values,
        "sma150": close.rolling(150).mean().values,
        # שיפוע ה-SMA150 באחוזים על פני 20 יום. דרישת המקור:
        # הממוצע חייב להיות שטוח או עולה, לא רק שהמחיר מעליו.
        "sma150_slope": ((close.rolling(150).mean()
                           .pct_change(20, fill_method=None)) * 100)
                        .fillna(0.0).values,
        "rsi": calc_rsi(close).values,
        "macd_hist": hist.values,
        "atr": calc_atr(df).values,
        "vol_ratio": vr.values,
        "day_change": (close.pct_change() * 100).fillna(0.0).values,
        # רצף ימים אדומים עד וכולל הבר הנוכחי. יום אדום = סגירה
        # נמוכה מהקודמת. טריגר הכניסה של המקור: הדיפ, לא המגמה.
        "red_streak": (close.diff().lt(0)
                        .groupby(close.diff().ge(0).cumsum())
                        .cumsum().fillna(0).astype(int).values),
        "pc5": (close.pct_change(5) * 100).fillna(0.0).values,
        # התנגדות: השיא הגבוה ביותר ב-N הימים שקדמו לבר הנוכחי.
        # shift(1) קריטי — בלעדיו הבר פורץ את עצמו.
        "res20": df["High"].rolling(20).max().shift(1).values,
        "res50": df["High"].rolling(50).max().shift(1).values,
        "n": len(df),
    }


def fast_technical_score(A, i, directional_vol=True):
    curr = A["close"][i]
    sma20, sma150 = A["sma20"][i], A["sma150"][i]
    if np.isnan(sma20) or np.isnan(sma150) or np.isnan(A["sma50"][i]):
        return None, None
    if curr > sma20 and curr > sma150: trend = 85
    elif curr > sma20 and curr < sma150: trend = 55
    elif curr < sma20 and curr > sma150: trend = 45
    else: trend = 15
    rsi_val = A["rsi"][i]
    if 45 <= rsi_val <= 65: rsi_s = 75
    elif 65 < rsi_val <= 75: rsi_s = 60
    elif rsi_val > 75: rsi_s = 25
    elif 30 <= rsi_val < 45: rsi_s = 55
    else: rsi_s = 20
    h = A["macd_hist"][i]
    hp = A["macd_hist"][i-1] if i > 0 else h
    if h > 0 and h > hp: macd_s = 85
    elif h > 0: macd_s = 60
    elif h < 0 and h < hp: macd_s = 15
    else: macd_s = 40
    vr, dc = A["vol_ratio"][i], A["day_change"][i]
    base_vol = min(100, max(10, int(vr * 40)))
    if not directional_vol: vol_s = base_vol
    elif dc > 0.3: vol_s = base_vol
    elif dc < -0.3: vol_s = max(10, 100 - base_vol)
    else: vol_s = 50
    score = trend * 0.35 + rsi_s * 0.25 + macd_s * 0.25 + vol_s * 0.15
    return score, {"rsi_raw": rsi_val, "vol_ratio": vr, "pc5": A["pc5"][i]}


def fast_execution_params(A, i, overext_threshold=8.0, stop_style="atr",
                           structural_lookback=15, structural_buffer_pct=1.0):
    curr = A["close"][i]
    sma20, sma50, sma150 = A["sma20"][i], A["sma50"][i], A["sma150"][i]
    atr = A["atr"][i]
    if np.isnan(sma20) or np.isnan(sma50) or np.isnan(sma150) or np.isnan(atr) or atr == 0:
        return None
    dist20 = ((curr - sma20) / sma20) * 100
    overext = False
    if curr > sma20 and curr > sma150:
        if dist20 > overext_threshold:
            phase, sl, overext = "⚠️ מתיחת יתר (Overextended)", curr - atr * 1.0, True
        elif sma20 > sma50 and ((sma20 - sma50) / sma50) < 0.04:
            phase, sl = "🌱 פריצה (Early Trend)", curr - atr * 2.5
        else:
            phase, sl = "🏃 מגמה בשלה (Mature)", curr - atr * 1.5
    elif curr < sma20 and curr > sma150:
        phase, sl = "📉 תיקון (Pullback)", curr - atr * 1.5
    elif curr > sma20 and curr < sma150:
        phase, sl = "⚠️ ריבאונד בתוך מגמת ירידה (Bear Rally)", curr - atr * 1.0
    else:
        phase, sl = "🔴 דובי (Bearish)", curr + atr * 1.5
    if stop_style == "structural" and curr > sma20 and i >= structural_lookback:
        recent_low = A["low"][i - structural_lookback + 1:i + 1].min()
        cand = recent_low * (1 - structural_buffer_pct / 100)
        if 0 < cand < curr:
            d = (curr - cand) / curr * 100
            if 1.0 <= d <= 20.0:
                sl = cand
    if sl <= 0 or sl == curr:
        return None
    raw_risk = abs(curr - sl)
    max_risk = curr * 0.12
    capped = raw_risk > max_risk
    risk = min(raw_risk, max_risk)
    if capped:
        sl = curr - risk if sl < curr else curr + risk
    tp = curr - risk * 2.5 if "דובי" in phase else curr + risk * 2.5
    return {"phase": phase, "sl": sl, "tp": tp,
            "sl_pct": ((sl - curr) / curr) * 100,
            "tp_pct": ((tp - curr) / curr) * 100,
            "is_overextended": overext, "is_capped": capped, "is_normalized": False,
            "dist_20": dist20, "norm_note": None}


def run_backtest_single(df, ticker="", score_threshold=70, max_holding_days=30,
                         earnings_mode="none", earnings_dates=None,
                         entry_buffer_days=2, exit_buffer_days=1,
                         exit_style="fixed", trailing_width_mult=2.0,
                         overext_threshold=8.0, block_overextended=True,
                         stop_style="atr", structural_lookback=15, structural_buffer_pct=1.0,
                         use_composite=True, macro_proxy=60.0, directional_vol=True,
                         cost_pct_per_side=0.0, use_earnings_move_filter=False,
                         earnings_move_mult=1.5, earnings_move_min_samples=2,
                         vix_series=None, vix_mode="ignore", vix_threshold=28.0,
                         use_weekly_trend=False, weekly_sma_weeks=30,
                         use_three_day_rule=False, three_day_drop_pct=5.0, three_day_wait=3,
                         use_reversal_exit=False, reversal_mode="sma20",
                         reversal_min_days=3,
                         entry_mode="close",
                         spy_series=None, macro_exit_mode="off",
                         macro_confirm_days=2, macro_dd_pct=8.0,
                         use_vol_norm=False, vb1=3.0, vb2=4.5, vb3=6.5,
                         require_rising_sma=False, sma_slope_min=0.0,
                         entry_trigger="three_red", red_days=3,
                         breakout_lookback=20,
                         partial_r=0.0, partial_be=False,
                         dip_pct=10.0,
                         scale_mode="off", scale_drop=5.0,
                         ladder_mode="off",
                         scale_first=0.5,
                         vol_norm_scope="thr",
                         use_cooldown=False,
                         blocked_out=None):

    """
    בקטסט מבוסס-אירועים על מניה אחת.

    ⚠️ הערה חשובה על use_composite: הבקטסט *לא* משתמש בנתוני אופציות או Fear&Greed,
    כי אלה נתונים של *היום* בלבד - אין להם היסטוריה זמינה ב-yfinance. שימוש בערך הנוכחי
    על תאריכים היסטוריים היה Look-ahead Bias חמור (הצצה לעתיד), שמייפה תוצאות באופן מזויף.
    לכן: הבקטסט בודק רק את החלק הטכני + מכפיל איכות הכניסה, עם מאקרו כערך קבוע (macro_proxy).
    זה מספיק כדי לבדוק אם *מכפיל איכות הכניסה* משפר את התוצאות - שזה השינוי המבני שנבדק.
    """
    n = len(df)
    if n < 200:
        return [], "נדרשים לפחות 200 ימי מסחר לבקטסט אמין"

    closes = df['Close'].values
    highs = df['High'].values
    lows = df['Low'].values
    opens = df['Open'].values
    sma20_arr = df['Close'].rolling(20).mean().values
    # ===== נורמליזציית תנודתיות =====
    # ATR באחוזים מהמחיר - מדד תנודתיות שמחושב מהמניה עצמה ולא מהקטגוריה שלה.
    # 11 קטגוריות הראו שאותה תצורה נותנת Sharpe 2.4 באחת ו-0.2 באחרת;
    # המשתנה המסביר הוא התנודתיות, ולכן הפרמטרים נגזרים ממנה ישירות.
    atr_pct_arr = (calc_atr(df) / df['Close'] * 100).values
    dates = df.index
    earnings_dates = earnings_dates or set()

    # היסטוריית תנועות דוחות - נבנית פעם אחת מראש, אבל בשימוש בפועל מסתכלים
    # רק על דוחות שקדמו לתאריך הטרייד (ראה avg_past_earnings_move) כדי למנוע הצצה לעתיד.
    move_history = compute_earnings_move_history(df, earnings_dates) if use_earnings_move_filter else []

    # אישור מגמה שבועי - מחושב פעם אחת, סדרה בוליאנית לכל יום (עם shift שמונע הצצה לעתיד)
    weekly_ok = compute_weekly_trend_ok(df, weekly_sma_weeks) if use_weekly_trend else None
    weekly_ok_vals = weekly_ok.values if weekly_ok is not None else None

    # חוק שלושת הימים - קבוצת אינדקסים חסומים אחרי ירידה חדה בעקבות דוח
    # POST-EARN-DIP: אותו סט משמש גם כחסימה וגם
    # כטריגר — תלוי בכיוון שנבחר.
    _need_pe = use_three_day_rule or entry_trigger in (
        "post_earn_dip", "red_or_pe")
    post_earn_blocked = (compute_post_earnings_block(
        df, earnings_dates, three_day_drop_pct, three_day_wait)
        if _need_pe else set())

    # VIX מיושר לתאריכי המניה
    vix_vals = None
    if vix_mode != "ignore" and vix_series is not None:
        aligned = align_series_to_index(vix_series, df.index)
        if aligned is not None:
            vix_vals = aligned.values

    rev_below = rev_flip = None

    if use_reversal_exit:
        rev_below, rev_flip = compute_reversal_signals(df)

    risk_off_vals = None
    if macro_exit_mode != "off":
        risk_off_vals = compute_risk_off(spy_series, df.index, macro_exit_mode,
                                          macro_confirm_days, macro_dd_pct)

    blocked_counts = {"move": 0, "vix": 0, "weekly": 0, "three_day": 0, "sma_slope": 0, "gate": 0, "macro": 0}

    trades = []
    in_trade = False
    entry_idx = entry_price = sl = tp = None
    initial_risk = trailing_stop = highest_close = None
    cooldown_until = -1
    entry_score_snapshot = 0.0
    last_exit_reason = ""
    partial_done = False
    partial_ret = 0.0
    scaled_in = False
    scale_price = 0.0
    entry_score_val = 0.0
    cur_max_days = max_holding_days
    cur_exit = exit_style
    cur_rev = use_reversal_exit
    entry_earnings_seen = False   # האם הפוזיציה הנוכחית חצתה תאריך דוח

    # ===== מבדק אמינות: מה המנוע קיבל =====
    if not _AUDIT_DONE.get("in"):
        _AUDIT_DONE["in"] = True
        try:
            import streamlit as _st
            _st.info(
                "🔬 **המנוע קיבל** — "
                f"max_days={max_holding_days} · threshold={score_threshold} · "
                f"stop={stop_style} · exit={exit_style} · earn={earnings_mode} · "
                f"vol_norm={use_vol_norm}/{vol_norm_scope} · trigger={entry_trigger} · "
                f"rising_sma={require_rising_sma} · scale={scale_mode} · "
                f"ladder={ladder_mode} · vix={vix_mode}/{vix_threshold} · "
                f"cost={cost_pct_per_side} · pos_swing={swing_lookback}/{swing_buffer_pct}"
            )
        except Exception:
            pass

    _A = precompute_indicator_arrays(df)

    for i in range(150, n - 1):
        # sub_df הוסר — המנוע המהיר קורא ממערכים מוכנים
        if not in_trade:
            tech_score, _bd = fast_technical_score(_A, i, directional_vol=directional_vol)
            if tech_score is None:
                continue
            exec_p = fast_execution_params(_A, i, overext_threshold=overext_threshold,
                                           stop_style=stop_style, structural_lookback=structural_lookback,
                                            structural_buffer_pct=structural_buffer_pct)
            if exec_p is None:
                continue

            # הציון שנבדק מול הסף: מורכב (עם מכפיל איכות כניסה) או טכני גולמי
            if use_composite:
                eval_score, _ = calculate_composite_score(tech_score, macro_proxy, exec_p, opt_bonus=0.0)
                if eval_score is None:
                    continue
            else:
                eval_score = tech_score

            # ===== גזירת פרמטרים מהתנודתיות =====
            eff_thr, eff_maxd, eff_exit, eff_rev = score_threshold, max_holding_days, exit_style, use_reversal_exit
            # ===== נרמול לפי תנודתיות =====
            # vb1/vb2/vb3 הם ספי ATR באחוזים (לא נפח - השם מטעה).
            # scope קובע מה מותר לשנות:
            #   "thr"  - סף בלבד. שאר הפרמטרים נשארים כפי שהוגדרו.
            #   "full" - גם סגנון יציאה ויציאת היפוך (ההתנהגות הישנה).
            if use_vol_norm and max_holding_days != 0 and vol_norm_scope != "off":
                _a = atr_pct_arr[i]
                if np.isnan(_a):
                    _a = 3.0
                if _a < vb1:
                    _t, _x, _r = 65, "fixed", False
                elif _a < vb2:
                    _t, _x, _r = 55, "structural_trail", False
                elif _a < vb3:
                    _t, _x, _r = 65, "fixed", True
                else:
                    _t, _x, _r = 75, "fixed", True
                eff_thr = _t
                if vol_norm_scope == "full":
                    eff_exit, eff_rev = _x, _r

            # ===== אופק לפי דוח =====
            # max_holding_days == 0 פירושו "עד הדוח הבא".
            # נמדד מהבר הנוכחי; אם אין דוח ידוע - fallback.
            if max_holding_days == 0:
                _dte = None
                if earnings_dates:
                    _today = dates[i].date()
                    _future = [d for d in earnings_dates if d > _today]
                    if _future:
                        _next_e = min(_future)
                        _dte = (_next_e - _today).days
                eff_maxd = _dte if (_dte and _dte > 0) else 120

            # ===== מבדק אמינות: מה בשימוש בפועל =====
            if not _AUDIT_DONE.get("eff"):
                _AUDIT_DONE["eff"] = True
                try:
                    import streamlit as _st
                    _st.warning(
                        "🔬 **בשימוש בפועל (אחרי דריסות)** — "
                        f"eff_maxd={eff_maxd} · eff_thr={eff_thr} · "
                        f"eff_exit={eff_exit} · eff_rev={eff_rev}"
                        + ("  ⚠️ **שונה ממה שהוגדר!**"
                           if (eff_maxd != max_holding_days or
                               eff_thr != score_threshold) else "  ✅ תואם")
                    )
                except Exception:
                    pass

            phase = exec_p["phase"]
            bad_phase = ("דובי" in phase) or ("Bear Rally" in phase) or (block_overextended and exec_p["is_overextended"])
            # ===== תנאי הכניסה =====
            # score     - הציון המשוקלל מעל הסף (ההמצאה שלנו)
            # three_red - רצף ימים אדומים (טריגר המקור)
            # either    - אחד מהשניים
            _score_ok = eval_score >= eff_thr
            _red_ok = _A["red_streak"][i] >= red_days
            _res = _A["res50"][i] if breakout_lookback >= 50 else _A["res20"][i]
            _brk_ok = (not np.isnan(_res)) and closes[i] > _res
            if entry_trigger == "three_red":
                _trigger = _red_ok
            elif entry_trigger == "either":
                _trigger = _score_ok or _red_ok
            elif entry_trigger == "breakout":
                _trigger = _brk_ok
            elif entry_trigger == "score_or_breakout":
                _trigger = _score_ok or _brk_ok
            elif entry_trigger == "dip":
                # התכנסות: ירידה של X% מהשיא של 20 יום.
                # res20 כבר כולל shift(1) - אין הצצה קדימה.
                _peak = _A["res20"][i]
                _trigger = ((not np.isnan(_peak)) and _peak > 0 and
                            (_peak - closes[i]) / _peak * 100 >= dip_pct)
            elif entry_trigger == "mom120":
                # MOM120: תנאי יחיד — המניה עלתה ב-120 ימי מסחר.
                # הפיצ׳ר היחיד ששרד סריקה של 82 עם סימן אחיד
                # בכל חמש תת-התקופות, ומתחזק דווקא ב-2024-26.
                _j = i - 120
                _trigger = (_j >= 0 and closes[_j] > 0
                            and closes[i] > closes[_j])
            elif entry_trigger == "post_earn_dip":
                # POST-EARN-DIP: כניסה דווקא בימים שהחוק חוסם.
                _trigger = i in post_earn_blocked
            elif entry_trigger == "red_or_pe":
                _trigger = _red_ok or (i in post_earn_blocked)
            else:
                _trigger = _score_ok
            # ===== זיכרון =====
            # אין כניסה חוזרת לפני שחלף ה-cooldown של הסיבה
            # שבגללה יצאנו. הכניסה עדיין חייבת לעבור את כל
            # שאר התנאים - זה שער נוסף, לא היתר.
            if use_cooldown and i < cooldown_until:
                blocked_counts["cooldown"] = blocked_counts.get("cooldown", 0) + 1
                continue
            if _trigger and not bad_phase:
                allow_entry = True
                if earnings_mode == "entry_block" and earnings_dates:
                    window_end = min(i + 1 + max_holding_days, n - 1)
                    window_dates = {d.date() for d in dates[i+1:window_end+1]}
                    if window_dates & earnings_dates:
                        allow_entry = False
                elif earnings_mode == "combined" and earnings_dates:
                    near_end = min(i + 1 + entry_buffer_days, n - 1)
                    near_dates = {d.date() for d in dates[i+1:near_end+1]}
                    if near_dates & earnings_dates:
                        allow_entry = False
                # פילטר תנועת דוחות: חוסם כניסה אם המניה נוטה לזוז בדוחות הרבה יותר
                # מרוחב הסטופ שלנו - כלומר הסטופ צפוי להיפגע על תנודתיות דוח ולא על טעות.
                # זהו כלל **מותאם למניה**, בניגוד ל"צא יומיים לפני" שהוא כלל אחיד לכולן.
                if allow_entry and use_earnings_move_filter and move_history:
                    avg_move = avg_past_earnings_move(move_history, dates[i].date(),
                                                       earnings_move_min_samples)
                    if avg_move is not None:
                        stop_dist_pct = abs(exec_p["sl_pct"])
                        if stop_dist_pct > 0 and avg_move > stop_dist_pct * earnings_move_mult:
                            allow_entry = False
                            blocked_counts["move"] += 1

                # ===== משטר VIX =====
                # "block_high" משחזר את התנהגות הסורק (חסימה בתנודתיות גבוהה).
                # "buy_dip" בודק את הטענה ההפוכה: VIX גבוה = הזדמנות, נכנסים **רק** אז.
                if allow_entry and vix_vals is not None:
                    v = vix_vals[i]
                    if not np.isnan(v):
                        if vix_mode == "block_high" and v > vix_threshold:
                            allow_entry = False
                            blocked_counts["vix"] += 1
                        elif vix_mode == "buy_dip" and v < vix_threshold:
                            allow_entry = False
                            blocked_counts["vix"] += 1

                # אישור מגמה שבועי
                if allow_entry and weekly_ok_vals is not None:
                    if not bool(weekly_ok_vals[i]):
                        allow_entry = False
                        blocked_counts["weekly"] += 1

                # מצב סיכון בשוק - לא נכנסים כלל
                if allow_entry and risk_off_vals is not None and bool(risk_off_vals[i]):
                    allow_entry = False
                    blocked_counts["macro"] += 1

                # חוק שלושת הימים אחרי ירידה בעקבות דוח
                if allow_entry and post_earn_blocked and (i + 1) in post_earn_blocked:
                    allow_entry = False
                    blocked_counts["three_day"] += 1

                # ===== שיפוע SMA150 =====
                # המקור דורש ממוצע שטוח או עולה. בלי זה נכנסים גם למניה
                # מעל ממוצע יורד - ריבאונד בתוך מגמת ירידה.
                if allow_entry and require_rising_sma:
                    _slope = _A["sma150_slope"][i]
                    if np.isnan(_slope) or _slope < sma_slope_min:
                        allow_entry = False
                        blocked_counts["sma_slope"] += 1

                # ===== שער כניסה =====
                # close   = כניסה בסגירת היום למחרת (ההתנהגות הישנה)
                # confirm = נכנסים רק אם המחיר שובר את שיא יום האיתות
                # retrace = נכנסים רק אם המחיר חוזר לגעת ב-SMA20
                entry_px = closes[i+1]
                if allow_entry and entry_mode == "confirm":
                    trig = highs[i]
                    if highs[i+1] > trig:
                        entry_px = max(trig, opens[i+1])
                    else:
                        allow_entry = False
                        blocked_counts["gate"] += 1
                elif allow_entry and entry_mode == "retrace":
                    trig = sma20_arr[i]
                    if not np.isnan(trig) and lows[i+1] <= trig < closes[i]:
                        entry_px = min(trig, opens[i+1])
                    else:
                        allow_entry = False
                        blocked_counts["gate"] += 1

                if allow_entry:
                    in_trade = True
                    entry_idx = i + 1
                    entry_price = entry_px
                    sl, tp = exec_p["sl"], exec_p["tp"]
                    initial_risk = entry_price - sl
                    entry_score_snapshot = float(eval_score)
                    partial_done = False
                    partial_ret = 0.0
                    scaled_in = False
                    scale_price = 0.0
                    trailing_stop = sl
                    highest_close = entry_price
                    entry_earnings_seen = False
                    entry_score_val = eval_score
                    cur_max_days = eff_maxd
                    cur_exit = eff_exit
                    cur_rev = eff_rev   # נשמר כדי שהגבלת מסחר-היתר תדע מה לשמור
        else:
            if cur_exit == "structural_trail":
                # ===== קידום סטופ מבני =====
                # בשונה מ-Trailing שמוותר מראש על מרחק קבוע מהשיא,
                # כאן הסטופ מטפס לשפל האמיתי האחרון בגרף.
                # במגמה מתפרצת הוא נותן מרחב; במגמה מסודרת הוא מהדק.
                # אין TP - הרעיון הוא לתת לטרייד לרוץ עד שהמבנה נשבר.
                new_sl = find_structural_stop(df.iloc[:i+1], closes[i],
                                               structural_lookback, structural_buffer_pct)
                if new_sl is not None and new_sl > trailing_stop:
                    trailing_stop = new_sl
                hit_sl = lows[i] <= trailing_stop
                hit_tp = False
                current_sl_value = trailing_stop
            elif cur_exit == "trailing":
                highest_close = max(highest_close, closes[i])
                trailing_stop = max(trailing_stop, highest_close - (initial_risk * trailing_width_mult))
                hit_sl = lows[i] <= trailing_stop
                hit_tp = False
                current_sl_value = trailing_stop
            else:
                hit_sl = lows[i] <= sl
                hit_tp = highs[i] >= tp
                current_sl_value = sl

            # ===== סטופ מדורג =====
            # הרווח נמדד לפי השיא שהושג, לא לפי הסגירה - אחרת
            # מדרגה שנגעה ונסוגה באותו יום לא הייתה נספרת.
            if ladder_mode != "off" and entry_price > 0:
                _ladder = {"tight": STOP_LADDER_TIGHT,
                           "steady": STOP_LADDER_STEADY,
                           "mid": STOP_LADDER_MID,
                           "late": STOP_LADDER_LATE,
                           "verylate": STOP_LADDER_VERYLATE}.get(
                               ladder_mode, STOP_LADDER_STEADY)
                _peak_gain = (highs[i] - entry_price) / entry_price * 100
                for _need, _lock in _ladder:
                    if _peak_gain >= _need:
                        _new_sl = entry_price * (1 + _lock / 100.0)
                        if _new_sl > sl:
                            sl = _new_sl
                        if trailing_stop is None or _new_sl > trailing_stop:
                            trailing_stop = _new_sl

            # ===== חיזוק פוזיציה =====
            # תנאי כפול: ירידה של X% מהכניסה, וגם עדיין מעל SMA150 -
            # כלומר מגמה נמשכת ולא היפוך. נבדק לפני היציאות.
            if scale_mode != "off" and not scaled_in:
                _trigger_px = entry_price * (1 - scale_drop / 100.0)
                _s150 = _A["sma150"][i]
                if (lows[i] <= _trigger_px and not np.isnan(_s150)
                        and closes[i] > _s150):
                    scale_price = _trigger_px
                    scaled_in = True

            # ===== מימוש חלקי =====
            # נבדק לפני שאר היציאות: יום שנגע ביעד החלקי וירד לסטופ
            # אינו הפסד מלא. היעד נמדד ביחידות סיכון (R).
            if partial_r > 0 and not partial_done and initial_risk > 0:
                _ptarget = entry_price + initial_risk * partial_r
                if highs[i] >= _ptarget:
                    partial_ret = (_ptarget - entry_price) / entry_price * 100
                    partial_done = True
                    if partial_be:
                        sl = max(sl, entry_price)
                        trailing_stop = max(trailing_stop, entry_price)

            # מסמנים אם הפוזיציה חצתה תאריך דוח - לצורך ניתוח "כמה עולה להחזיק דרך דוח"
            if earnings_dates and dates[i].date() in earnings_dates:
                entry_earnings_seen = True

            days_held = i - entry_idx
            # ATR-COST-FIX: מחושב פעם אחת לכל נר, לפני כל
            # הסתעפות — שלושת מסלולי היציאה משתמשים בו.
            _cps = cost_pct_per_side
            if _ATR_COST:
                try:
                    _a = _A["atr"][i]
                    if np.isfinite(_a) and closes[i] > 0:
                        _cps = cost_pct_per_side + _ATR_COST * (
                            _a / closes[i] * 100)
                except Exception:
                    pass
            # ===== יציאה על היפוך מגמה =====
            # reversal_min_days מונע יציאה מיידית ביום הראשון על רעש קצר.
            hit_reversal = False
            if cur_rev and days_held >= reversal_min_days:
                if reversal_mode == "sma150":
                    # שבירת SMA150 - יציאה גם ברווח. _A זמין כאן בוודאות.
                    _s150 = _A["sma150"][i]
                    hit_reversal = (not np.isnan(_s150)) and closes[i] < _s150
                elif reversal_mode == "sma20" and rev_below is not None:
                    hit_reversal = bool(rev_below[i])
                elif reversal_mode == "macd" and rev_flip is not None:
                    hit_reversal = bool(rev_flip[i])
                elif reversal_mode == "both" and rev_below is not None and rev_flip is not None:
                    hit_reversal = bool(rev_below[i]) and bool(rev_flip[i])
                elif reversal_mode == "either" and rev_below is not None and rev_flip is not None:
                    hit_reversal = bool(rev_below[i]) or bool(rev_flip[i])
            hit_macro = bool(risk_off_vals[i]) if risk_off_vals is not None else False
            forced_earnings_exit = False
            if earnings_mode == "combined" and earnings_dates:
                upcoming_end = min(i + 1 + exit_buffer_days, n - 1)
                upcoming_dates = {d.date() for d in dates[i+1:upcoming_end+1]}
                if upcoming_dates & earnings_dates:
                    forced_earnings_exit = True
            # NO-SAME-DAY: הכניסה היא בסגירה, ולכן יציאה באותו יום
            # אינה אפשרית במציאות. 66 טריידים כאלה נמצאו ב-20.8.
            if days_held >= 1 and (hit_sl or hit_tp or hit_reversal or hit_macro or days_held >= cur_max_days or forced_earnings_exit):
                if hit_sl:
                    exit_price = current_sl_value
                    reason = "טריילינג-SL" if cur_exit == "trailing" else "SL"
                elif hit_tp:
                    exit_price, reason = tp, "TP"
                elif hit_macro:
                    exit_price, reason = closes[i], "מאקרו"
                elif hit_reversal:
                    exit_price, reason = closes[i], "היפוך"
                elif forced_earnings_exit:
                    exit_price, reason = closes[i], "לפני-דוח"
                else:
                    exit_price, reason = closes[i], "זמן"
                _final_ret = (exit_price - entry_price) / entry_price * 100
                if scale_mode != "off":
                    # split: חצי+חצי, אותו סיכון. אם לא נורתה ההוספה -
                    #        הפוזיציה נשארה חצי, ולכן גם התשואה חצי.
                    # add:   מלא + חצי, חשיפה 150%.
                    _r2 = ((exit_price - scale_price) / scale_price * 100
                           if scaled_in and scale_price > 0 else 0.0)
                    # scale_first = חלק הכניסה הראשונה. ב-split הסכום
                    # תמיד 1.0 (אותו סיכון); ב-add מוסיפים מעל 100%.
                    if scale_mode == "split":
                        _base_w = scale_first
                        _add_w = (1.0 - scale_first) if scaled_in else 0.0
                    else:
                        _base_w = 1.0
                        _add_w = (1.0 - scale_first) if scaled_in else 0.0
                    gross_ret = _base_w * _final_ret + _add_w * _r2
                    _n_ops = 3 if scaled_in else 2
                    ret_pct = gross_ret - (_cps * _n_ops)
                elif partial_done:
                    # חצי מומש ביעד, חצי יצא בסוף. שלוש פעולות = עלות כפול 3.
                    gross_ret = 0.5 * partial_ret + 0.5 * _final_ret
                    ret_pct = gross_ret - (_cps * 3)
                else:
                    gross_ret = _final_ret
                    ret_pct = apply_trade_cost(gross_ret, _cps)
                # הזיכרון: כמה ימים להמתין לפני כניסה חוזרת למניה הזו
                last_exit_reason = reason
                cooldown_until = i + _cool_days(reason)
                trades.append({"ticker": ticker, "entry_date": dates[entry_idx], "exit_date": dates[i],
                                "entry": entry_price, "exit": exit_price,
                                "gross_return_pct": gross_ret,
                                "return_pct": ret_pct, "reason": reason, "days": days_held,
                                "held_earnings": entry_earnings_seen,
                                # תשתית להקצאת משאבים: הציון בזמן הכניסה
                                # והסקטור. בלעדיהם אין דירוג ואין ריכוזיות בדיעבד.
                                "sector": SECTOR_MAP.get(ticker) or STOCK_INFO.get(ticker, ("", ""))[1],
                                "partial": partial_done,
                                "scaled": scaled_in,
                                "entry_score": (entry_score_snapshot or entry_score_val)})
                in_trade = False

    if blocked_out is not None:
        for a,b in blocked_counts.items():
            blocked_out[a] = blocked_out.get(a,0)+b
    return trades, None

def compute_backtest_summary(trades):
    if not trades:
        return None
    rets = [t["return_pct"] for t in trades]
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    win_rate = len(wins) / len(rets) * 100
    avg_win = np.mean(wins) if wins else 0
    avg_loss = np.mean(losses) if losses else 0
    profit_factor = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else float('inf')
    equity = [100.0]
    for r in rets:
        equity.append(equity[-1] * (1 + r/100))
    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        peak = max(peak, v)
        dd = (peak - v) / peak * 100
        max_dd = max(max_dd, dd)
    return {"num_trades": len(trades), "win_rate": win_rate, "avg_win": avg_win,
            "avg_loss": avg_loss, "profit_factor": profit_factor,
            "total_return_pct": (equity[-1] - 100), "max_drawdown_pct": max_dd,
            "avg_days_held": np.mean([t["days"] for t in trades])}

def simulate_realistic_portfolio(trades, position_pct=5.0, initial_capital=100.0,
                                  price_map=None, max_positions=0):
    """
    price_map = {ticker: סדרת מחירי סגירה}.
    אם סופק — העקומה נבנית יום-יום עם שיערוך פוזיציות פתוחות (mark-to-market).
    אם לא — נשמרת ההתנהגות הישנה (דגימה באירועי יציאה בלבד), כדי שכשל
    בשרשרת ההעברה יתגלה כשינוי בתוצאה ולא יעבור בשקט.
    """
    if not trades:
        return None

    pmap = None
    if price_map:
        pmap = {}
        for _tk, _s in price_map.items():
            try:
                pmap[_tk] = {d: float(v) for d, v in zip(_s.index, _s.values)
                             if np.isfinite(v)}
            except Exception:
                pass
        pmap = pmap or None

    skipped = 0
    globals()["_VIX_EXPOSURE"] = []
    daily = pmap is not None

    if not daily:
        # ---------- המסלול הישן: אירועי יציאה בלבד ----------
        events = []
        for t in trades:
            events.append((t["entry_date"], 1, "entry", t))
            events.append((t["exit_date"], 0, "exit", t))
        events.sort(key=lambda e: (e[0], e[1]))
        cash = initial_capital
        open_positions = {}
        equity_curve = [(None, initial_capital)]
        for date, _, kind, t in events:
            if kind == "entry":
                current_equity = cash + sum(open_positions.values())
                alloc = current_equity * (position_pct / 100)
                if alloc > cash:
                    skipped += 1
                    continue
                cash -= alloc
                open_positions[id(t)] = alloc
            else:
                alloc = open_positions.pop(id(t), None)
                if alloc is None:
                    continue
                cash += alloc * (1 + t["return_pct"] / 100)
                equity_curve.append((date, cash + sum(open_positions.values())))
        timeline = sorted([(t["entry_date"], 1) for t in trades] +
                          [(t["exit_date"], -1) for t in trades])
        cur = mx = 0
        for _, delta in timeline:
            cur += delta
            mx = max(mx, cur)
    else:
        # ---------- המסלול היומי ----------
        def _value(pos):
            _t, _alloc, _ep = pos
            _px = last_px.get(_t["ticker"])
            if _px is None or not _ep:
                return _alloc
            return _alloc * (_px / _ep)

        first = min(t["entry_date"] for t in trades)
        last = max(t["exit_date"] for t in trades)
        all_dates = sorted({d for _m in pmap.values() for d in _m
                            if first <= d <= last})
        by_entry, by_exit = {}, {}
        for t in trades:
            by_entry.setdefault(t["entry_date"], []).append(t)
            by_exit.setdefault(t["exit_date"], []).append(t)

        cash = initial_capital
        open_pos = {}
        last_px = {}
        equity_curve = [(None, initial_capital)]
        mx = 0
        for d in all_dates:
            for _tk, _m in pmap.items():
                _v = _m.get(d)
                if _v is not None:
                    last_px[_tk] = _v
            # יציאות לפני כניסות — הון משוחרר זמין לאותו יום
            for t in by_exit.get(d, []):
                pos = open_pos.pop(id(t), None)
                if pos is None:
                    continue
                cash += pos[1] * (1 + t["return_pct"] / 100)
            # SCORE-ORDER: ההון מוגבל, ולכן מי שנכנס ראשון תופס
            # אותו. עד כאן הסדר היה סדר הרשימה — כלומר מיקום
            # המניה ביקום. מעכשיו הציון בזמן הכניסה מכריע.
            for t in sorted(by_entry.get(d, []),
                            key=lambda _t: -float(_t.get("entry_score") or 0)):
                # ===== תקרת פוזיציות =====
                # 0 = ללא הגבלה. אדם לא מחזיק 40 פוזיציות במקביל.
                if max_positions and len(open_pos) >= max_positions:
                    skipped += 1
                    continue
                # SECTOR-CAP: פיזור על 20 פוזיציות שכולן באותו
                # סקטור אינו פיזור. Technology לבדה היא שליש
                # מהיקום.
                if _SEC_CAP:
                    _s = t.get("sector") or ""
                    if _s:
                        _n = sum(1 for _p in open_pos.values()
                                 if (_p[0].get("sector") or "") == _s)
                        if _n >= _SEC_CAP:
                            skipped += 1
                            continue
                cur_eq = cash + sum(_value(p) for p in open_pos.values())
                _w = _vix_weight(d)
                _VIX_EXPOSURE.append(_w)
                alloc = cur_eq * (position_pct / 100) * _w
                if alloc > cash:
                    skipped += 1
                    continue
                cash -= alloc
                open_pos[id(t)] = (t, alloc, t.get("entry"))
            mx = max(mx, len(open_pos))
            equity_curve.append((d, cash + sum(_value(p) for p in open_pos.values())))

    if len(equity_curve) < 2:
        return None
    values = [v for _, v in equity_curve]
    peak = values[0]
    max_dd = 0.0
    for v in values:
        peak = max(peak, v)
        dd = (peak - v) / peak * 100 if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
    total_return_pct = values[-1] - initial_capital
    sharpe_approx = calmar_ratio = annualized_return_pct = None
    first_date = trades[0]["entry_date"] if trades else None
    last_date = equity_curve[-1][0]
    if first_date is not None and last_date is not None:
        elapsed_days = (last_date - first_date).days
        years = elapsed_days / 365.25
        if years > 0:
            annualized_return_pct = (((1 + total_return_pct / 100) ** (1 / years)) - 1) * 100
            if max_dd > 0:
                calmar_ratio = annualized_return_pct / max_dd
            period_rets = [(values[i] / values[i-1] - 1) for i in range(1, len(values))
                           if values[i-1] > 0]
            if len(period_rets) > 1:
                periods_per_year = len(period_rets) / years
                std_ret = np.std(period_rets)
                if std_ret > 0:
                    rf_per_period = (1 + RISK_FREE_ANNUAL) ** (1 / periods_per_year) - 1
                    sharpe_approx = ((np.mean(period_rets) - rf_per_period) / std_ret) * np.sqrt(periods_per_year)
    return {"final_equity": values[-1], "total_return_pct": total_return_pct,
            "max_drawdown_pct": max_dd, "skipped_trades": skipped,
            "max_concurrent_positions": mx, "closed_trades": len(trades),
            "annualized_return_pct": annualized_return_pct, "sharpe_approx": sharpe_approx,
            "daily_curve": daily, "curve_points": len(values),
            "calmar_ratio": calmar_ratio}

def max_drawdown_from_series(series):
    peak = series.iloc[0]
    max_dd = 0.0
    for v in series:
        peak = max(peak, v)
        dd = (peak - v) / peak * 100 if peak > 0 else 0
        max_dd = max(max_dd, dd)
    return max_dd

def annualized_return_from_pct(total_return_pct, num_trading_days, trading_days_per_year=252):
    years = num_trading_days / trading_days_per_year
    if years <= 0:
        return None
    return (((1 + total_return_pct / 100) ** (1 / years)) - 1) * 100

def compute_equal_weight_benchmark(price_map, start_idx=150):
    """
    תיק שווה-משקל אמיתי מאותן מניות, עם שערוך יומי משותף.
    זו ההשוואה הנכונה לתיק האסטרטגיה — בניגוד ל-bh_return שהוא
    ממוצע תשואות פר-מניה, ול-bh_dd שהוא ממוצע DD בודדים
    (ותמיד גבוה בהרבה מ-DD של תיק מגוון).
    """
    if not price_map:
        return None
    try:
        frame = pd.DataFrame({k: v for k, v in price_map.items() if v is not None})
    except Exception:
        return None
    if frame.empty or frame.shape[1] == 0 or len(frame) <= start_idx + 30:
        return None
    frame = frame.iloc[start_idx:]
    rets = frame.pct_change(fill_method=None)
    daily = rets.mean(axis=1, skipna=True).dropna()
    if len(daily) < 30:
        return None
    r = daily.values.astype(float)
    r = r[np.isfinite(r)]
    if len(r) < 30:
        return None
    equity = np.cumprod(1 + r)
    peaks = np.maximum.accumulate(equity)
    ew_dd = float(np.max((peaks - equity) / peaks)) * 100
    ew_return = float(equity[-1] - 1) * 100
    n_days = len(r)
    ew_ann = annualized_return_from_pct(ew_return, n_days)
    ew_calmar = (ew_ann / ew_dd) if ew_dd > 0 and ew_ann is not None else None
    sd = float(np.std(r, ddof=1))
    ew_sharpe = (((r.mean() - RISK_FREE_ANNUAL / 252) / sd) * np.sqrt(252)
                 if sd > 0 else None)
    return {"ew_return": ew_return, "ew_dd": ew_dd, "ew_sharpe": ew_sharpe,
            "ew_calmar": ew_calmar, "ew_n": frame.shape[1], "ew_days": n_days}


def compute_price_based_benchmarks(df, start_idx=150):
    if len(df) <= start_idx + 30:
        return None
    sub_close = df['Close'].iloc[start_idx:].dropna()
    n_days = len(sub_close)
    bh_return = (sub_close.iloc[-1] / sub_close.iloc[0] - 1) * 100
    bh_dd = max_drawdown_from_series(sub_close)
    bh_daily_ret = sub_close.pct_change().dropna()
    bh_sharpe = ((bh_daily_ret.mean() - RISK_FREE_ANNUAL / 252) / bh_daily_ret.std() * np.sqrt(252)) if bh_daily_ret.std() > 0 else None
    bh_ann_return = annualized_return_from_pct(bh_return, n_days)
    bh_calmar = (bh_ann_return / bh_dd) if bh_dd > 0 and bh_ann_return is not None else None
    sma50 = df['Close'].rolling(50).mean()
    sma200 = df['Close'].rolling(200).mean()
    in_regime = (sma50 > sma200).astype(int).shift(1).fillna(0)
    daily_ret = df['Close'].pct_change().fillna(0)
    strat_daily_ret = (daily_ret * in_regime).iloc[start_idx:]
    equity = (1 + strat_daily_ret).cumprod() * 100
    sma_return = equity.iloc[-1] - 100
    sma_dd = max_drawdown_from_series(equity)
    sma_sharpe = ((strat_daily_ret.mean() - RISK_FREE_ANNUAL / 252) / strat_daily_ret.std() * np.sqrt(252)) if strat_daily_ret.std() > 0 else None
    sma_ann_return = annualized_return_from_pct(sma_return, n_days)
    sma_calmar = (sma_ann_return / sma_dd) if sma_dd > 0 and sma_ann_return is not None else None
    return {"bh_return": bh_return, "bh_dd": bh_dd, "bh_sharpe": bh_sharpe, "bh_calmar": bh_calmar,
            "sma_return": sma_return, "sma_dd": sma_dd, "sma_sharpe": sma_sharpe, "sma_calmar": sma_calmar,
            "n_days": n_days}

def run_aggregate(tickers, earnings_mode, bt_period, bt_threshold, bt_max_days,
                   entry_buffer_days, exit_buffer_days, progress_label="", exit_style="fixed",
                   trailing_width_mult=2.0, overext_threshold=8.0, block_overextended=True,
                   stop_style="atr", structural_lookback=15, structural_buffer_pct=1.0,
                   use_composite=True, directional_vol=True,
                   cost_pct_per_side=0.0, use_earnings_move_filter=False,
                   earnings_move_mult=1.5, earnings_move_min_samples=2,
                   vix_mode="ignore", vix_threshold=28.0,
                   use_weekly_trend=False, weekly_sma_weeks=30,
                   use_three_day_rule=False, three_day_drop_pct=5.0, three_day_wait=3,
                   use_reversal_exit=False, reversal_mode="sma20", reversal_min_days=3,
                   entry_mode="close", macro_exit_mode="off",
                   macro_confirm_days=2, macro_dd_pct=8.0,
                   use_vol_norm=False, vb1=3.0, vb2=4.5, vb3=6.5,
                   require_rising_sma=False, sma_slope_min=0.0,
                   entry_trigger="three_red", red_days=3,
                   breakout_lookback=20,
                   partial_r=0.0, partial_be=False,
                   dip_pct=10.0,
                   scale_mode="off", scale_drop=5.0,
                   ladder_mode="off",
                   scale_first=0.5,
                   vol_norm_scope="thr",
                   use_cooldown=False,
                   max_trades_per_week=0):
    _AUDIT_DONE.clear()
    all_trades, per_ticker_stats, failed = [], [], []
    price_map = {}
    agg_blocked = {}
    # VIX נשלף פעם אחת לכל הריצה (לא פר-מניה) - חוסך קריאות רשת מיותרות
    vix_series = fetch_vix_history(bt_period) if vix_mode != "ignore" else None
    # VIX-SIZING: נשלף בנפרד לצורך גודל חשיפה, ללא תלות בפילטר.
    try:
        _vx = vix_series if vix_series is not None else fetch_vix_history(bt_period)
        if _vx is not None:
            _mp = {}
            for _d, _v in _vx.items():
                _k = _vix_key(_d)
                if _k is not None and np.isfinite(_v):
                    _mp[_k] = float(_v)
            globals()["_VIX_MAP"] = _mp or None
        else:
            globals()["_VIX_MAP"] = None
    except Exception:
        globals()["_VIX_MAP"] = None
    spy_series = fetch_spy_history(bt_period) if macro_exit_mode != "off" else None
    if vix_mode != "ignore" and vix_series is None:
        st.markdown("<div class='unknown-box'>⚠️ לא ניתן לשלוף היסטוריית VIX - מסנן ה-VIX לא יופעל בריצה הזו.</div>", unsafe_allow_html=True)
    bh_returns, bh_dds, sma_returns, sma_dds = [], [], [], []
    bh_sharpes, bh_calmars, sma_sharpes, sma_calmars = [], [], [], []
    progress_bar = st.progress(0, text="מאתחל...")
    for i, t in enumerate(tickers):
        progress_bar.progress(i / len(tickers), text=f"🔍 {progress_label}{t} ({i+1}/{len(tickers)})...")
        df, fetch_err = fetch_stock_data_backtest(t, bt_period)
        if df.empty:
            failed.append(f"{t} ({fetch_err or 'אין נתונים'})")
            continue
        try:
            price_map[t] = df['Close']
        except Exception:
            pass

        bench = compute_price_based_benchmarks(df)
        if bench and np.isfinite(bench["bh_return"]) and np.isfinite(bench["sma_return"]):
            bh_returns.append(bench["bh_return"]); bh_dds.append(bench["bh_dd"])
            sma_returns.append(bench["sma_return"]); sma_dds.append(bench["sma_dd"])
            if bench["bh_sharpe"] is not None and np.isfinite(bench["bh_sharpe"]): bh_sharpes.append(bench["bh_sharpe"])
            if bench["bh_calmar"] is not None and np.isfinite(bench["bh_calmar"]): bh_calmars.append(bench["bh_calmar"])
            if bench["sma_sharpe"] is not None and np.isfinite(bench["sma_sharpe"]): sma_sharpes.append(bench["sma_sharpe"])
            if bench["sma_calmar"] is not None and np.isfinite(bench["sma_calmar"]): sma_calmars.append(bench["sma_calmar"])
        # תאריכי דוחות נדרשים גם למדיניות הדוחות, גם לפילטר תנועת הדוחות,
        # וגם לניתוח "החזקה דרך דוח" - אז שולפים אותם כמעט תמיד.
        e_dates = fetch_earnings_dates_backtest(t) if (earnings_mode != "none" or use_earnings_move_filter) else set()
        trades, err = run_backtest_single(df, t, bt_threshold, bt_max_days,
                                           earnings_mode=earnings_mode, earnings_dates=e_dates,
                                           entry_buffer_days=entry_buffer_days, exit_buffer_days=exit_buffer_days,
                                           exit_style=exit_style, trailing_width_mult=trailing_width_mult,
                                           overext_threshold=overext_threshold, block_overextended=block_overextended,
                                           stop_style=stop_style, structural_lookback=structural_lookback,
                                           structural_buffer_pct=structural_buffer_pct,
                                           use_composite=use_composite,
                                           directional_vol=directional_vol,
                                           cost_pct_per_side=cost_pct_per_side,
                                           use_earnings_move_filter=use_earnings_move_filter,
                                           earnings_move_mult=earnings_move_mult,
                                           earnings_move_min_samples=earnings_move_min_samples,
                                           vix_series=vix_series, vix_mode=vix_mode,
                                           vix_threshold=vix_threshold,
                                           use_weekly_trend=use_weekly_trend,
                                           weekly_sma_weeks=weekly_sma_weeks,
                                           use_three_day_rule=use_three_day_rule,
                                           three_day_drop_pct=three_day_drop_pct,
                                           three_day_wait=three_day_wait,
                                           use_reversal_exit=use_reversal_exit,
                                           reversal_mode=reversal_mode,
                                           reversal_min_days=reversal_min_days,
                                           entry_mode=entry_mode,
                                           spy_series=spy_series,
                                           macro_exit_mode=macro_exit_mode,
                                           macro_confirm_days=macro_confirm_days,
                                           macro_dd_pct=macro_dd_pct,
                                           use_vol_norm=use_vol_norm,
                                           vb1=vb1, vb2=vb2, vb3=vb3,
                                           require_rising_sma=require_rising_sma,
                                           entry_trigger=entry_trigger,
                                           breakout_lookback=breakout_lookback,
                                           partial_r=partial_r, partial_be=partial_be,
                                           dip_pct=dip_pct,
                                           scale_mode=scale_mode, scale_drop=scale_drop,
                                           ladder_mode=ladder_mode,
                                           scale_first=scale_first,
                                           vol_norm_scope=vol_norm_scope,
                                           use_cooldown=use_cooldown,
                                           sma_slope_min=sma_slope_min,
                                           blocked_out=agg_blocked)
        if err:
            failed.append(f"{t} ({err})")
            continue
        all_trades.extend(trades)
        if trades:
            t_summary = compute_backtest_summary(trades)
            per_ticker_stats.append({"טיקר": t, "טריידים": t_summary["num_trades"],
                                      "הצלחה %": round(t_summary["win_rate"], 0),
                                      "תשואה מצטברת %": round(t_summary["total_return_pct"], 1)})
    progress_bar.progress(1.0, text="✅ הושלם")
    time.sleep(0.2)
    progress_bar.empty()
    all_trades.sort(key=lambda t: t["entry_date"])

    # הגבלת מסחר יתר מופעלת כאן - אחרי איחוד כל המניות - כי זו רמת התיק,
    # שבה מסחר יתר קורה בפועל. הגבלה פר-מניה לא הייתה תופסת את התופעה.
    capped_out = 0
    if max_trades_per_week > 0:
        all_trades, capped_out = apply_weekly_trade_cap(all_trades, max_trades_per_week)
        if capped_out:
            st.caption(f"🚦 הגבלת מסחר יתר: {capped_out} טריידים סוננו (נשמרו {max_trades_per_week} בעלי הציון הגבוה בכל שבוע).")

    benchmarks = None
    if bh_returns:
        benchmarks = {
            "bh_return": float(np.mean(bh_returns)), "bh_dd": float(np.mean(bh_dds)),
            "sma_return": float(np.mean(sma_returns)), "sma_dd": float(np.mean(sma_dds)),
            "bh_sharpe": float(np.mean(bh_sharpes)) if bh_sharpes else None,
            "bh_calmar": float(np.mean(bh_calmars)) if bh_calmars else None,
            "sma_sharpe": float(np.mean(sma_sharpes)) if sma_sharpes else None,
            "sma_calmar": float(np.mean(sma_calmars)) if sma_calmars else None,
            "n": len(bh_returns)
        }
        _ew = compute_equal_weight_benchmark(price_map)
        if _ew:
            benchmarks.update(_ew)
    st.session_state["last_blocked"] = {k:v for k,v in agg_blocked.items() if v>0}
    return all_trades, per_ticker_stats, failed, benchmarks, price_map

def render_aggregate(all_trades, per_ticker_stats, failed, cat_tickers, label, bt_position_pct,
                      show_details=True, benchmarks=None, show_earnings_split=False,
                      cost_applied=0.0, price_map=None, max_positions=0):
    if failed:
        with st.expander(f"⚠️ {len(failed)} טיקרים נכשלו", expanded=False):
            for f in failed: st.write(f"- {f}")
    if not all_trades:
        st.info(f"{label}: לא נמצאו טריידים תואמים (נסה סף ציון נמוך יותר).")
        return None
    s = compute_backtest_summary(all_trades)
    st.markdown(f"#### {label}")
    if cost_applied > 0:
        gross = [t.get("gross_return_pct", t["return_pct"]) for t in all_trades]
        net = [t["return_pct"] for t in all_trades]
        st.caption(f"💰 עלויות פעילות: {cost_applied*2:.3f}% לסבב. תשואה ממוצעת לטרייד: {np.mean(gross):+.2f}% לפני עלויות → {np.mean(net):+.2f}% אחרי.")
    st.markdown(f"""
    <div class="metric-row">
        <div class="metric-item"><div class="metric-title">סה"כ טריידים</div><div class="metric-value">{s['num_trades']}</div></div>
        <div class="metric-item"><div class="metric-title">אחוז הצלחה</div><div class="metric-value">{s['win_rate']:.0f}%</div></div>
        <div class="metric-item"><div class="metric-title">רווח מצטבר (ריבית דריבית)</div><div class="metric-value">{s['total_return_pct']:+.1f}%</div></div>
        <div class="metric-item"><div class="metric-title">Drawdown מקס'</div><div class="metric-value">-{s['max_drawdown_pct']:.1f}%</div></div>
    </div>
    """, unsafe_allow_html=True)
    col_x, col_y, col_z = st.columns(3)
    col_x.metric("רווח ממוצע (זכייה)", f"+{s['avg_win']:.1f}%")
    col_y.metric("הפסד ממוצע (הפסד)", f"{s['avg_loss']:.1f}%")
    pf_disp = "∞" if s['profit_factor'] == float('inf') else f"{s['profit_factor']:.2f}"
    col_z.metric("Profit Factor", pf_disp)
    st.caption(f"ממוצע ימי החזקה לטרייד: {s['avg_days_held']:.1f} | מניות עם טריידים: {len(per_ticker_stats)}/{len(cat_tickers)}")

    port = simulate_realistic_portfolio(all_trades, position_pct=bt_position_pct,
                                        price_map=price_map,
                                        max_positions=max_positions)
    if port:
        st.markdown(f"""
        <div class="metric-row">
            <div class="metric-item"><div class="metric-title">💼 תשואה (תיק ריאלי)</div><div class="metric-value">{port['total_return_pct']:+.1f}%</div></div>
            <div class="metric-item"><div class="metric-title">Drawdown (תיק ריאלי)</div><div class="metric-value">-{port['max_drawdown_pct']:.1f}%</div></div>
            <div class="metric-item"><div class="metric-title">פוזיציות מקביליות (שיא)</div><div class="metric-value">{port['max_concurrent_positions']}</div></div>
        </div>
        """, unsafe_allow_html=True)
        s["realistic_return_pct"] = port["total_return_pct"]
        s["realistic_dd_pct"] = port["max_drawdown_pct"]
        # CAPITAL-PRESSURE: כמה נדחו מחוסר הון, ומה שיא
        # הפוזיציות במקביל. בלי אלה אי אפשר לדעת אם הדוח
        # מתאר את כל הטריידים או רק את הממומנים.
        s["skipped_trades"] = port.get("skipped_trades")
        s["max_concurrent"] = port.get("max_concurrent_positions")
        s["realistic_sharpe"] = port.get("sharpe_approx")
        s["realistic_calmar"] = port.get("calmar_ratio")

    if benchmarks:
        strat_ret = s.get("realistic_return_pct", s["total_return_pct"])
        strat_dd = s.get("realistic_dd_pct", s["max_drawdown_pct"])
        strat_sharpe = s.get("realistic_sharpe")
        strat_calmar = s.get("realistic_calmar")
        beats_bh = strat_ret > benchmarks["bh_return"]
        beats_sma = strat_ret > benchmarks["sma_return"]

        def fmt_ratio(v):
            return round(v, 2) if v is not None else "—"

        st.markdown("##### 🥊 השוואה מול שיטות נפוצות (אותה תקופה, אותן מניות)")
        comp_bench_df = pd.DataFrame([
            {"שיטה": "🎯 השיטה שלנו (תיק ריאלי)", "תשואה %": round(strat_ret, 1), "Drawdown %": round(strat_dd, 1),
             "Sharpe": fmt_ratio(strat_sharpe), "Calmar": fmt_ratio(strat_calmar)},
            {"שיטה": "💰 Buy & Hold", "תשואה %": round(benchmarks["bh_return"], 1), "Drawdown %": round(benchmarks["bh_dd"], 1),
             "Sharpe": fmt_ratio(benchmarks.get("bh_sharpe")), "Calmar": fmt_ratio(benchmarks.get("bh_calmar"))},
            {"שיטה": "📈 SMA 50/200 Crossover", "תשואה %": round(benchmarks["sma_return"], 1), "Drawdown %": round(benchmarks["sma_dd"], 1),
             "Sharpe": fmt_ratio(benchmarks.get("sma_sharpe")), "Calmar": fmt_ratio(benchmarks.get("sma_calmar"))},
        ])
        st.dataframe(comp_bench_df, use_container_width=True)
        st.caption("📐 Sharpe = תשואה עודפת ליחידת תנודתיות (גבוה יותר = טוב יותר, ~1 סביר, 2+ טוב מאוד). Calmar = תשואה שנתית חלקי Drawdown מקס' (גבוה יותר = טוב יותר).")
        if beats_bh and beats_sma:
            st.success("✅ השיטה ניצחה גם את Buy & Hold וגם את SMA Crossover בתשואה.")
        elif not beats_bh:
            st.markdown("<div class='unknown-box'>⚠️ Buy & Hold הפשוט נתן תשואה גבוהה יותר מהשיטה כאן. שווה לבדוק אם המורכבות שווה את זה - אבל בדוק גם Sharpe/Calmar, לא רק תשואה גולמית.</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='unknown-box'>⚠️ SMA Crossover (שיטה סטנדרטית פשוטה) נתן תשואה גבוהה יותר כאן.</div>", unsafe_allow_html=True)
        if strat_sharpe is not None and benchmarks.get("bh_sharpe") is not None and strat_sharpe > benchmarks["bh_sharpe"]:
            st.info("💡 עם זאת, ה-Sharpe של השיטה שלנו גבוה יותר מ-Buy & Hold - כלומר תשואה טובה יותר ביחס לסיכון שנלקח, גם אם התשואה הגולמית נמוכה יותר.")
        st.caption(f"Benchmarks מבוססים על ממוצע פשוט (equal-weight) בין {benchmarks['n']} מניות עם נתונים, לא על תיק עם ניהול סיכון - זו השוואה גסה.")

    # ===== ניתוח: כמה עולה להחזיק דרך דוח =====
    if show_earnings_split:
        ee = analyze_earnings_exposure(all_trades)
        if ee:
            st.markdown("##### 📊 החזקה דרך דוח - כמה זה עולה?")
            ee_df = pd.DataFrame([
                {"קבוצה": "🎲 חצו תאריך דוח", "טריידים": ee["held"]["n"],
                 "תשואה ממוצעת %": round(ee["held"]["avg"], 2), "הצלחה %": round(ee["held"]["win_rate"], 0),
                 "הכי גרוע %": round(ee["held"]["worst"], 1), "סטיית תקן": round(ee["held"]["std"], 1)},
                {"קבוצה": "✅ לא חצו דוח", "טריידים": ee["clean"]["n"],
                 "תשואה ממוצעת %": round(ee["clean"]["avg"], 2), "הצלחה %": round(ee["clean"]["win_rate"], 0),
                 "הכי גרוע %": round(ee["clean"]["worst"], 1), "סטיית תקן": round(ee["clean"]["std"], 1)},
            ])
            st.dataframe(ee_df, use_container_width=True)
            edge = ee["edge"]
            if edge > 0.5:
                st.success(f"✅ הימנעות מדוחות שווה **{edge:+.2f}%** לטרייד בממוצע — הצדקה כמותית למדיניות 'משולב'.")
            elif edge < -0.5:
                st.markdown(f"<div class='unknown-box'>⚠️ דווקא הטריידים שחצו דוח היו טובים ב-{abs(edge):.2f}% בממוצע. במדגם הזה היציאה המוקדמת <b>עולה</b> כסף - שווה לבדוק שוב לפני שנועלים את המדיניות.</div>", unsafe_allow_html=True)
            else:
                st.info(f"ההפרש זניח ({edge:+.2f}% לטרייד) — במדגם הזה מדיניות הדוחות לא מוסיפה הרבה, ורק מקטינה הזדמנויות.")
            if min(ee["held"]["n"], ee["clean"]["n"]) < 15:
                st.caption("⚠️ אחת הקבוצות קטנה מ-15 טריידים — ההשוואה לא מובהקת סטטיסטית.")
        elif all_trades:
            st.caption("📊 ניתוח דוחות: אין פיצול לשתי קבוצות (או שכל הטריידים חצו דוח, או שאף אחד לא). במדיניות 'משולב' זה צפוי — הרץ במצב 'רגיל' כדי לראות השוואה.")

    if s['num_trades'] < 30:
        st.markdown("<div class='unknown-box'>⚠️ מדגם קטן יחסית (פחות מ-30).</div>", unsafe_allow_html=True)
    if show_details:
        with st.expander(f"פירוט לפי מניה ({label})", expanded=False):
            st.dataframe(pd.DataFrame(per_ticker_stats).sort_values("תשואה מצטברת %", ascending=False),
                         use_container_width=True)
    return s

# ================= דשבורד ראשי =================
st.markdown("""
<div class="disclaimer">
⚠️ <b>הבהרה:</b> כלי זה מציג <b>אינדיקציות טכניות</b> (מגמה, RSI, MACD, נפח) + <b>נתוני אופציות אמיתיים</b> (Put/Call, IV)
+ <b>סנטימנט שוק</b> (VIX, Fear&Greed). זה <b>לא ייעוץ השקעות</b> ולא ניתוח פונדמנטלי.
מדד ה-Squeeze הוא <b>פרוקסי חלקי בלבד</b> - אין כאן Short Interest אמיתי. קבלת החלטות מסחר באחריותך בלבד.
</div>
""", unsafe_allow_html=True)





















































# ===== כרטיסי שיתוף =====





















































with st.expander("\U0001F5C2\uFE0F יצור כרטיסים מרובה", expanded=False):


























    st.caption("בוחרים מניות, מקבלים קובץ ZIP עם כל התמונות וקובץ כותרות.")








































st.markdown(f"""
<div style="background:linear-gradient(90deg,#1a3a2a,#0d2818);color:#7ee2a8;
padding:10px 14px;border-radius:6px;border-left:5px solid #28a745;
margin-bottom:10px;font-size:0.85rem;">
<b style="font-size:1.05rem;">🟢 {APP_VERSION}</b><br>
<span style="color:#aaa;">👁️ רשימת מעקב · 🔬 קטגוריות מתמחות · 📸 כרטיס שיתוף</span>
</div>
""", unsafe_allow_html=True)
st.sidebar.title("🌐 מקורות נתונים")
use_fear_greed = st.sidebar.toggle("Fear & Greed (CNN)", True,
    help="מדד סנטימנט שוק כללי. נשלף מ-endpoint לא-רשמי של CNN - אם ייכשל, המערכת תחזור אוטומטית לחישוב מאקרו ללא סנטימנט.")
use_options = st.sidebar.toggle("נתוני אופציות (Put/Call, IV)", True,
    help="שולף option_chain אמיתי מ-yfinance. מאט את הסריקה משמעותית (קריאת רשת נוספת לכל מניה) - כבה אם רק רוצה סריקה מהירה.")

st.markdown("""
<div class="real-tag">
🔒 <b>תצורה פעילה:</b> 🏗️ סטופ Swing Low · 🔀 מדיניות דוחות משולבת · 📏 נורמליזציית תנודתיות (3.0/4.5/6.5)<br>
הסף, ימי ההחזקה וסגנון היציאה נגזרים מ-ATR% של כל מניה בנפרד.<br>
<span style="color:#999;font-size:0.9em;">סדרת 22 בדיקות על 11 קטגוריות הראתה שהציון המורכב, הנפח המכוון וחסימת מתיחת היתר היו מזיקים — והוסרו.</span></div>
""", unsafe_allow_html=True)

live_macro = fetch_live_macro(use_fear_greed)

if live_macro["error"]:
    st.markdown(f"<div class='unknown-box'>⚠️ לא ניתן לשלוף נתוני מאקרו כרגע ({live_macro['error']}). הציונים מוצגים ללא רכיב מאקרו.</div>", unsafe_allow_html=True)
    macro_score = 50.0
    macro_danger = False
else:
    macro_score = live_macro['macro_score']
    macro_danger = live_macro['vix'] > 28
    fg_disp = live_macro.get('fg_value')
    fg_txt = f"{fg_disp:.0f}" if fg_disp is not None else "—"
    fg_rating = live_macro.get('fg_rating') or ""

    st.markdown(f"""
    <div class="metric-row">
        <div class="metric-item"><div class="metric-title">📊 VIX</div><div class="metric-value">{live_macro['vix']}</div></div>
        <div class="metric-item"><div class="metric-title">😱 Fear & Greed</div><div class="metric-value">{fg_txt}</div></div>
        <div class="metric-item"><div class="metric-title">⚖️ ציון מאקרו</div><div class="metric-value">{macro_score}</div></div>
        <div class="metric-item"><div class="metric-title">📐 קנס SMA20</div><div class="metric-value">-{live_macro['spy_penalty']}</div></div>
    </div>
    """, unsafe_allow_html=True)
    if fg_disp is not None and fg_rating:
        st.caption(f"סנטימנט נוכחי: **{fg_rating}** ({fg_disp:.0f}/100). הפירוש שלנו הוא *קונטרה מתון*: חמדנות קיצונית = אזהרה, פחד = לרוב הזדמנות.")
    elif use_fear_greed and live_macro.get('fg_err'):
        st.markdown(f"<div class='unknown-box'>⚠️ Fear & Greed לא נשלף ({live_macro['fg_err'][:80]}) - ה-endpoint לא רשמי ולעיתים נשבר. המאקרו מחושב בלעדיו.</div>", unsafe_allow_html=True)

if macro_danger: st.error("🛑 VIX גבוה מ-28: תנודתיות שוק חריגה. שקול משנה זהירות.")

tab_scanner, tab_deep_dive, tab_backtest = st.tabs(["🚀 סורק", "🔬 פירוק אינדיקטורים", "🧪 בקטסט"])

# ================= ניהול סיכון / גודל פוזיציה =================

# ===== קטלוג וסיווג אוטומטי =====
with st.sidebar.expander("🔎 הוסף מניה חדשה (סיווג אוטומטי)", expanded=False):
    st.caption("הסימול ייקטלג, ישויך לקטגוריה שלו, וייכנס לתיק האישי. "
               "הסיווג נשמר בנפרד ולכן שורד הסרה מהתיק.")
    _t_new = st.text_input("סימול:", key="cat_t").strip().upper()
    if st.button("🔎 בדוק וסווג", key="cat_go") and _t_new:
        _nm, _ind, _cat, _conf, _e = fetch_ticker_meta(_t_new)
        if _e or not _nm:
            st.error(f"לא נמצאו נתונים ל-{_t_new} ({_e})")
        else:
            st.session_state["cat_pending"] = {"t": _t_new, "name": _nm,
                                                "sector": _ind, "cat": _cat, "conf": _conf}
    _p = st.session_state.get("cat_pending")
    if _p:
        _lbl = {"high": "🟢 סיווג ודאי", "med": "🟡 סיווג לפי סקטור בלבד",
                "low": "🔴 סיווג לא ודאי - בדוק"}.get(_p["conf"], "")
        st.markdown(f"**{_p['t']} · {_p['name']}**")
        st.caption(f"ענף: {_p['sector'] or '—'} · {_lbl}")
        _opts = ALL_CAT_KEYS
        _idx = _opts.index(_p["cat"]) if _p["cat"] in _opts else 0
        _chosen = st.selectbox("קטגוריה:", _opts, index=_idx, key="cat_pick")
        _c1, _c2 = st.columns(2)
        if _c1.button("✅ שמור", key="cat_save"):
            _cl = load_catalog()
            _cl[_p["t"]] = {"name": _p["name"], "sector": _p["sector"], "cat": _chosen}
            _ok1, _er1 = save_catalog(_cl)
            _ok2, _er2 = save_portfolio(load_portfolio() + [_p["t"]])
            st.session_state.pop("cat_pending", None)
            if _ok1 and _ok2:
                st.success(f"{_p['t']} נוסף לתיק ול-{_chosen}")
                st.rerun()
            else:
                st.error(f"שמירה נכשלה: {_er1 or _er2}")
        if _c2.button("✖️ בטל", key="cat_cancel"):
            st.session_state.pop("cat_pending", None)
            st.rerun()

with st.sidebar.expander("📚 מניות שקוטלגו", expanded=False):
    _cl = load_catalog()
    if not _cl:
        st.caption("עדיין לא קוטלגו מניות.")
    else:
        st.caption(f"{len(_cl)} מניות בקטלוג. שינוי כאן משפיע על הקטגוריות.")
        for _tk in sorted(_cl):
            _v = _cl[_tk]
            st.markdown(f"**{_tk}** · {_v.get('name','')}")
            _new_cat = st.selectbox("קטגוריה", ALL_CAT_KEYS,
                index=ALL_CAT_KEYS.index(_v.get("cat")) if _v.get("cat") in ALL_CAT_KEYS else 0,
                key=f"cf_{_tk}", label_visibility="collapsed")
            _b1, _b2 = st.columns(2)
            if _b1.button("שנה", key=f"cu_{_tk}"):
                _cl[_tk]["cat"] = _new_cat; save_catalog(_cl); st.rerun()
            if _b2.button("מחק", key=f"cd_{_tk}"):
                _cl.pop(_tk, None); save_catalog(_cl); st.rerun()




with st.sidebar.expander("👁️ ערוך רשימת מעקב", expanded=False):
    _wcur = load_watchlist()
    st.caption("ברשימה: " + str(len(_wcur)) + " מניות")
    _wadd = st.text_input("הוסף (פסיקים/רווחים):", key="wl_add")
    if st.button("➕ הוסף למעקב", key="wl_add_btn") and _wadd.strip():
        _wnew = [x.strip().upper() for x in re.split(r'[,\s]+', _wadd) if x.strip()]
        _wok, _werr = save_watchlist(_wcur + _wnew)
        if _wok:
            _cl = load_catalog()
            _added = []
            for _t in _wnew:
                if _t not in _cl:
                    _nm, _ind, _cat, _cf, _e = fetch_ticker_meta(_t)
                    if _nm and _cat:
                        _cl[_t] = {"name": _nm, "sector": _ind, "cat": _cat}
                        _added.append(_t + " -> " + _cat)
            if _added:
                save_catalog(_cl)
                st.success("נוסף וסווג: " + " | ".join(_added))
            else:
                st.success("נוסף: " + ", ".join(_wnew))
            st.rerun()
        else:
            st.error(str(_werr))
    _wrm = st.multiselect("הסר:", _wcur, key="wl_rm")
    if st.button("🗑️ הסר", key="wl_rm_btn") and _wrm:
        _wok, _werr = save_watchlist([x for x in _wcur if x not in _wrm])
        if _wok:
            st.success("הוסר"); st.rerun()
        else:
            st.error(str(_werr))
    _wbk = load_wl_backups()
    if _wbk:
        st.caption("↩️ שחזור")
        _wo = [b["ts"] + " (" + str(len(b["list"])) + ")" for b in _wbk]
        _wp = st.selectbox("שחזר:", _wo, key="wl_bk", label_visibility="collapsed")
        if st.button("↩️ שחזר", key="wl_bk_go"):
            save_watchlist(_wbk[_wo.index(_wp)]["list"]); st.rerun()

with st.sidebar.expander("\U0001F4DD ערוך רשימת בקשות", expanded=False):
    _rcur = load_requests()
    st.caption("ברשימה: " + str(len(_rcur)) + " מניות")
    _radd = st.text_input("הוסף (פסיקים/רווחים):", key="rq_add")
    if st.button("➕ הוסף לבקשות", key="rq_add_btn") and _radd.strip():
        _rnew = [x.strip().upper() for x in re.split(r'[,\s]+', _radd) if x.strip()]
        _rok, _rerr = save_requests(_rcur + _rnew)
        if _rok:
            try:
                _cl = load_catalog()
                for _t in _rnew:
                    if _t not in _cl:
                        catalog_ticker(_t)
            except Exception:
                pass
            st.success("נוסף"); st.rerun()
        else:
            st.error("שגיאה: " + str(_rerr))
    _rrm = st.multiselect("הסר:", _rcur, key="rq_rm")
    if st.button("🗑️ הסר", key="rq_rm_btn") and _rrm:
        _rok, _rerr = save_requests([x for x in _rcur if x not in _rrm])
        if _rok:
            st.success("הוסר"); st.rerun()
        else:
            st.error("שגיאה: " + str(_rerr))
    _rbk = load_rq_backups()
    if _rbk:
        _ro = [b["ts"] + " (" + str(len(b["list"])) + ")" for b in _rbk]
        _rp = st.selectbox("שחזר:", _ro, key="rq_bk", label_visibility="collapsed")
        if st.button("↩️ שחזר", key="rq_bk_go"):
            save_requests(_rbk[_ro.index(_rp)]["list"]); st.rerun()

st.sidebar.title("💰 ניהול סיכון")
portfolio_size = st.sidebar.number_input("גודל תיק ($):", min_value=100, value=10000, step=500)
risk_pct = st.sidebar.number_input("% סיכון לטרייד בודד:", min_value=0.25, max_value=5.0, value=1.0, step=0.25)
st.sidebar.caption(f"סיכון מקסימלי לטרייד: ${portfolio_size * risk_pct / 100:.0f}")


# ================= כרטיס שיתוף - מנוע מחודש =================
# PNG אנכי 1080x1920 (9:16) לטיקטוק/ריל/סטורי, עם ווטרמארק, גרף מחיר,
# מד ציון, ורמות מסחר. כל הטקסט באנגלית.
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io as _io
import zipfile as _zip

BRAND = "MONKEY BUSINESS"
BRAND_EMOJI = "\U0001F649\U0001F648\U0001F64A"   # 🙉🙈🙊
BOT_EMOJI = "\U0001F916"                          # 🤖

_FB = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
       "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
_FR = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
       "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]
_FE = ["/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
       "/usr/share/fonts/truetype/noto/NotoEmoji-Regular.ttf"]

def _font(size, bold=True):
    for p in (_FB if bold else _FR):
        try:
            if Path(p).exists():
                return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()

def _emoji_ok():
    """ בודק אם מותקן פונט אמוג'י. בלעדיו הווטרמארק יהיה טקסט בלבד. """
    return any(Path(p).exists() for p in _FE)

def _draw_emoji(img, text, xy, size):
    """ מצייר אמוג'י אם יש פונט מתאים. מחזיר True בהצלחה. """
    for p in _FE:
        if not Path(p).exists():
            continue
        try:
            f = ImageFont.truetype(p, 109 if "Color" in p else size)
            layer = Image.new("RGBA", (len(text) * 130, 140), (0, 0, 0, 0))
            ImageDraw.Draw(layer).text((0, 0), text, font=f, embedded_color=True)
            layer = layer.crop(layer.getbbox() or (0, 0, 1, 1))
            r = size / max(1, layer.height)
            layer = layer.resize((max(1, int(layer.width * r)), size), Image.LANCZOS)
            img.paste(layer, xy, layer)
            return layer.width
        except Exception:
            continue
    return 0

def _sector_en(tk):
    """ הענף באנגלית מ-yfinance (מטומן). המאגר הפנימי בעברית ו-PIL
    לא מרנדר RTL, לכן לכרטיס משמש הענף הרשמי באנגלית. """
    try:
        _n, ind, _c, _cf, _e = fetch_ticker_meta(tk)
        if ind and all(ord(c) < 128 for c in ind):
            return ind
    except Exception:
        pass
    return ""

def _phase_en(phase):
    m = re.search(r'\(([A-Za-z ]+)\)', phase or "")
    return m.group(1).strip().upper() if m else "TREND"

def _band_en(a):
    if a is None:
        return "N/A", (150, 150, 150)
    if a < 3.0:
        return "CALM", (46, 204, 113)
    if a < 4.5:
        return "MODERATE", (241, 196, 15)
    if a < 6.5:
        return "VOLATILE", (230, 126, 34)
    return "EXTREME", (231, 76, 60)

def _ctr(d, y, txt, f, fill, W=1080):
    w = d.textlength(txt, font=f)
    d.text(((W - w) / 2, y), txt, font=f, fill=fill)

def _watermark(img, center_emoji=True, emoji_size=300, emoji_alpha=0.17,
               tile_alpha=9):
    """ ווטרמארק דו-שכבתי:
        1. תבנית אלכסונית חוזרת של שם המותג (עדינה מאוד)
        2. אמוג'י גדול ממורכז + שם המותג מתחתיו
    שתי השכבות מצוירות כרקע - התוכן של הכרטיס נצבע מעליהן ולכן שום דבר לא מוסתר. """
    W, H = img.size

    # ----- שכבה 1: תבנית אלכסונית -----
    layer = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
    dd = ImageDraw.Draw(layer)
    f = _font(40)
    for yy in range(0, H * 2, 200):
        off = 260 if (yy // 200) % 2 else 0
        for xx in range(-200, W * 2, 560):
            dd.text((xx + off, yy), BRAND, font=f,
                    fill=(255, 255, 255, tile_alpha))
    layer = layer.rotate(28, resample=Image.BICUBIC, center=(W, H))
    layer = layer.crop((W // 2, H // 2, W // 2 + W, H // 2 + H))
    base = Image.alpha_composite(img.convert("RGBA"), layer)

    if not center_emoji:
        return base.convert("RGB")

    # ----- שכבה 2: אמוג'י ממורכז -----
    mid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    scratch = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    drawn = 0
    try:
        drawn = _draw_emoji(scratch, BRAND_EMOJI, (0, 0), emoji_size)
    except Exception:
        drawn = 0

    cy = H // 2
    if drawn:
        bb = scratch.getbbox()
        if bb:
            art = scratch.crop(bb)
            px = (W - art.width) // 2
            py = cy - art.height // 2 - 40
            mid.paste(art, (px, py), art)

    # שם המותג מתחת לאמוג'י
    dm = ImageDraw.Draw(mid)
    fb = _font(56)
    tw = dm.textlength(BRAND, font=fb)
    ty = cy + (emoji_size // 2) - 10 if drawn else cy - 28
    dm.text(((W - tw) / 2, ty), BRAND, font=fb, fill=(255, 255, 255, 255))

    # החלשת השכבה כולה לרמת ווטרמארק
    a = mid.split()[3].point(lambda v: int(v * emoji_alpha))
    mid.putalpha(a)

    return Image.alpha_composite(base, mid).convert("RGB")

def _sparkline(d, df, x, y, w, h, entry, sl, tp):
    """ גרף מחיר 6 חודשים עם קווי כניסה, סטופ ויעד. """
    try:
        ser = df['Close'].tail(126)
        if len(ser) < 20:
            return False
        vals = list(ser.values)
        lo = min(min(vals), sl if sl else min(vals))
        hi = max(max(vals), tp if tp else max(vals))
        rng = (hi - lo) or 1
        def py(v):
            return y + h - (v - lo) / rng * h
        d.rounded_rectangle([x, y, x + w, y + h], radius=14, fill=(13, 22, 29))
        for lvl, col, lbl in [(sl, (231, 76, 60), "STOP"),
                               (entry, (0, 230, 210), "ENTRY"),
                               (tp, (46, 204, 113), "TARGET")]:
            if not lvl:
                continue
            yy = py(lvl)
            if not (y <= yy <= y + h):
                continue
            for xx in range(x + 6, x + w - 6, 16):
                d.line([(xx, yy), (xx + 8, yy)], fill=col, width=2)
            f = _font(20, False)
            ly2 = min(max(yy - 24, y + 4), y + h - 26)
            d.text((x + w - 8 - d.textlength(lbl, font=f), ly2), lbl, font=f, fill=col)
        n = len(vals)
        pts = [(x + 10 + i * (w - 20) / (n - 1), py(v)) for i, v in enumerate(vals)]
        up = vals[-1] >= vals[0]
        col = (46, 204, 113) if up else (231, 76, 60)
        area = pts + [(pts[-1][0], y + h - 2), (pts[0][0], y + h - 2)]
        d.polygon(area, fill=(col[0] // 8, col[1] // 8, col[2] // 8))
        d.line(pts, fill=col, width=4, joint="curve")
        d.ellipse([pts[-1][0] - 7, pts[-1][1] - 7, pts[-1][0] + 7, pts[-1][1] + 7], fill=col)
        f = _font(20, False)
        d.text((x + 12, y + 8), "6 MONTHS", font=f, fill=(110, 130, 140))
        return True
    except Exception:
        return False

def make_infographic(card, sigd):
    W, H = 1080, 1920
    BG, CYAN, WHITE, GREY = (7, 12, 18), (0, 230, 210), (240, 245, 245), (125, 142, 150)
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for x in range(0, W, 54):
        d.line([(x, 0), (x, H)], fill=(12, 20, 27), width=1)
    for y in range(0, H, 54):
        d.line([(0, y), (W, y)], fill=(12, 20, 27), width=1)
    glow = Image.new("RGB", (W, H), BG)
    ImageDraw.Draw(glow).ellipse([-260, -560, W + 260, 460], fill=(0, 66, 76))
    img = Image.blend(img, glow.filter(ImageFilter.GaussianBlur(140)), 0.55)
    img = _watermark(img)
    d = ImageDraw.Draw(img)

    ex = card.get("exec") or {}
    tk = card["ticker"]
    name = stock_label(tk)
    sect = _sector_en(tk)
    score = card.get("score", 0)
    thr = card.get("band_thr", 65)
    passed = score >= thr
    atr = card.get("atr_pct")
    bt, bc = _band_en(atr)

    # ===== כותרת מותג =====
    y = 46
    f_b = _font(34)
    ew = _draw_emoji(img, BRAND_EMOJI, (0, 0), 1) and 0
    bw = d.textlength(BRAND, font=f_b)
    d.text(((W - bw) / 2, y), BRAND, font=f_b, fill=(0, 200, 185))
    y += 52
    d.line([(W / 2 - 90, y), (W / 2 + 90, y)], fill=(0, 120, 112), width=3)
    y += 40

    # ===== טיקר =====
    f_tk = _font(146)
    _ctr(d, y, tk, f_tk, WHITE); y += 158
    _ctr(d, y, name[:26], _font(44, False), CYAN); y += 58
    if sect:
        chip = sect.upper()[:32]
        cw = d.textlength(chip, font=_font(28, False))
        d.rounded_rectangle([(W - cw) / 2 - 20, y - 6, (W + cw) / 2 + 20, y + 40],
                            radius=20, fill=(18, 30, 38))
        _ctr(d, y + 4, chip, _font(28, False), GREY)
        y += 62

    y += 16
    # ===== פסק דין + מד ציון =====
    vc = (46, 204, 113) if passed else (241, 196, 15)
    vt = "SETUP QUALIFIED" if passed else "WATCHING - NOT YET"
    d.rounded_rectangle([80, y, W - 80, y + 196], radius=24,
                        fill=(vc[0] // 8, vc[1] // 8, vc[2] // 8), outline=vc, width=4)
    _ctr(d, y + 20, vt, _font(50), vc)
    gx, gy, gw = 130, y + 96, W - 260
    d.rounded_rectangle([gx, gy, gx + gw, gy + 26], radius=13, fill=(24, 36, 44))
    fill_w = max(10, min(gw, gw * score / 100))
    d.rounded_rectangle([gx, gy, gx + fill_w, gy + 26], radius=13, fill=vc)
    tx = gx + gw * thr / 100
    d.line([(tx, gy - 8), (tx, gy + 34)], fill=WHITE, width=3)
    f_s = _font(24, False)
    d.text((gx, gy + 36), f"SCORE {score:.0f}", font=f_s, fill=WHITE)
    lbl = f"THRESHOLD {thr}"
    d.text((gx + gw - d.textlength(lbl, font=f_s), gy + 36), lbl, font=f_s, fill=GREY)
    y += 250

    # ===== גרף =====
    try:
        _df, _ = fetch_stock_data(tk)
    except Exception:
        _df = None
    if _df is not None and not _df.empty:
        if _sparkline(d, _df, 80, y, W - 160, 300, card.get("curr"),
                      ex.get("sl"), ex.get("tp")):
            y += 330

    # ===== רמות =====
    def row(lbl, val, col=WHITE, sub=""):
        nonlocal y
        d.rounded_rectangle([80, y, W - 80, y + 92], radius=16, fill=(15, 25, 33))
        d.text((112, y + 26), lbl, font=_font(36, False), fill=GREY)
        vw = d.textlength(val, font=_font(44))
        d.text((W - 112 - vw, y + 20), val, font=_font(44), fill=col)
        if sub:
            sw = d.textlength(sub, font=_font(24, False))
            d.text((W - 112 - sw, y + 62), sub, font=_font(24, False), fill=GREY)
        y += 102

    row("ENTRY", f"${card['curr']:.2f}", CYAN)
    if ex:
        row("STOP LOSS", f"${ex['sl']:.2f}", (231, 76, 60), f"{ex['sl_pct']:+.1f}%")
        row("TARGET", f"${ex['tp']:.2f}", (46, 204, 113), f"{ex['tp_pct']:+.1f}%")
        rr = abs(ex['tp_pct'] / ex['sl_pct']) if ex.get('sl_pct') else 0
        row("RISK / REWARD", f"1 : {rr:.1f}")

    y += 8
    # ===== נתונים =====
    d.rounded_rectangle([80, y, W - 80, y + 200], radius=16, fill=(15, 25, 33))
    try:
        rsi_v = f"{sigd['breakdown']['rsi_raw']:.0f}"
    except Exception:
        rsi_v = "-"
    cells = [("VOLATILITY", bt, bc), ("ATR", f"{atr:.1f}%" if atr else "-", WHITE),
             ("PHASE", _phase_en(ex.get("phase", "")), WHITE),
             ("RSI", rsi_v, WHITE), ("MAX HOLD", f"{card.get('band_days', 30)}d", WHITE),
             ("EARNINGS", f"{card.get('e_days', '?')}d", WHITE)]
    for i, (lb, vl, cl) in enumerate(cells):
        cx = 80 + (W - 160) * (i % 3) / 3 + (W - 160) / 6
        cy = y + 28 + (i // 3) * 94
        lw = d.textlength(lb, font=_font(24, False))
        d.text((cx - lw / 2, cy), lb, font=_font(24, False), fill=GREY)
        vw = d.textlength(str(vl), font=_font(38))
        d.text((cx - vw / 2, cy + 32), str(vl), font=_font(38), fill=cl)
    y += 224

    _ctr(d, y, datetime.now().strftime("%d %b %Y").upper(), _font(30, False), GREY)

    # ===== דיסקליימר =====
    disc = ("NOT FINANCIAL ADVICE. Automated technical screen based on price data only. "
            "Not a recommendation to buy or sell. Past performance does not guarantee "
            "future results. Trading involves substantial risk of loss.")
    by = H - 236
    d.rounded_rectangle([64, by, W - 64, H - 96], radius=16,
                        fill=(26, 20, 10), outline=(120, 92, 22), width=2)
    f_d = _font(24, False)
    line, ly = "", by + 22
    for wd in disc.split():
        t = (line + " " + wd).strip()
        if d.textlength(t, font=f_d) > W - 190:
            d.text((94, ly), line, font=f_d, fill=(202, 180, 118)); ly += 30
            line = wd
        else:
            line = t
    if line:
        d.text((94, ly), line, font=f_d, fill=(202, 180, 118))

    # ===== מותג תחתון =====
    f_f = _font(28)
    fw = d.textlength(BRAND, font=f_f)
    gap = 130
    x0 = (W - (fw + gap * 2)) / 2
    _draw_emoji(img, BRAND_EMOJI, (int(x0), H - 76), 32)
    d.text((x0 + gap, H - 68), BRAND, font=f_f, fill=(74, 96, 104))
    _draw_emoji(img, BOT_EMOJI, (int(x0 + gap + fw + 24), H - 76), 32)

    buf = _io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ================= כותרת לטיקטוק =================
# נבנית לפי מצב הסטאפ בפועל, כדי שלא תחזור על עצמה בין מניות.
_HOOKS_GO = [
    "This one just lit up my scanner \U0001F6A8",
    "I don't chase. I wait for THIS \U0001F440",
    "Setup confirmed. Levels below \U0001F447",
    "My screener flagged this at the close \U0001F4CA",
    "This is what a clean setup looks like \U0001F9F5",
]
_HOOKS_WAIT = [
    "Not a buy yet. Here's what I need to see \u23F3",
    "On the watchlist, not in the portfolio \U0001F440",
    "Close, but it hasn't earned it yet \u270B",
    "Everyone's talking about this one. I'm waiting \U0001F914",
]
_SECTOR_TAGS = {
    "semiconductor": ["#semiconductors", "#chipstocks"],
    "aerospace": ["#defensestocks", "#aerospace"],
    "uranium": ["#uranium", "#nuclearenergy"],
    "solar": ["#solarstocks", "#cleanenergy"],
    "oil": ["#oilstocks", "#energystocks"],
    "gas": ["#energystocks"],
    "utilities": ["#utilities", "#powerstocks"],
    "biotech": ["#biotech", "#pharmastocks"],
    "drug": ["#pharmastocks"],
    "medical": ["#healthcarestocks"],
    "bank": ["#bankstocks", "#financialstocks"],
    "capital markets": ["#financialstocks"],
    "credit": ["#fintech"],
    "software": ["#techstocks", "#softwarestocks"],
    "computer": ["#techstocks"],
    "communication": ["#techstocks"],
    "gold": ["#goldstocks", "#preciousmetals"],
    "copper": ["#copper", "#commodities"],
    "steel": ["#commodities"],
    "metals": ["#commodities", "#mining"],
    "railroad": ["#industrials"],
    "airline": ["#airlinestocks"],
    "retail": ["#retailstocks"],
    "reit": ["#reits", "#realestate"],
    "insurance": ["#insurancestocks"],
    "auto": ["#evstocks"],
}

def make_caption(card, sigd):
    ex = card.get("exec") or {}
    tk = card["ticker"]
    name = stock_label(tk)
    sect = _sector_en(tk)
    score = card.get("score", 0)
    thr = card.get("band_thr", 65)
    passed = score >= thr
    atr = card.get("atr_pct")
    bt, _ = _band_en(atr)
    phase = _phase_en(ex.get("phase", "")).title()
    seed = sum(ord(c) for c in tk) + datetime.now().day
    hook = (_HOOKS_GO if passed else _HOOKS_WAIT)[seed % len(_HOOKS_GO if passed else _HOOKS_WAIT)]

    L = [hook, ""]
    L.append(f"${tk} \u2014 {name}")
    if passed:
        L.append(f"Score {score:.0f}/100 vs a {thr} bar for a {bt.lower()} mover. It cleared it.")
    else:
        L.append(f"Score {score:.0f}/100. It needs {thr} to qualify. Not there yet.")
    L.append("")
    if ex:
        rr = abs(ex['tp_pct'] / ex['sl_pct']) if ex.get('sl_pct') else 0
        L.append("\U0001F4CD THE PLAN")
        L.append(f"Entry {card['curr']:.2f}")
        L.append(f"Stop {ex['sl']:.2f} ({ex['sl_pct']:+.1f}%)")
        L.append(f"Target {ex['tp']:.2f} ({ex['tp_pct']:+.1f}%)")
        L.append(f"Risk/reward 1:{rr:.1f}")
        L.append("")
    L.append(f"\u26A1 Phase: {phase} \u00b7 Volatility: {bt.title()} \u00b7 Max hold {card.get('band_days', 30)} days")
    if card.get("e_days") not in (None, "?", ""):
        L.append(f"\U0001F4C5 Earnings in {card.get('e_days')} days \u2014 factor that in.")
    L.append("")
    L.append("The stop is the whole strategy. Without it this is gambling.")
    L.append("")
    L.append("Follow for daily setups from an automated scanner \u2014 no hype, just levels. \U0001F916")
    L.append("")
    L.append("\u26A0\uFE0F Not financial advice. Technical screen only. Do your own research.")
    L.append("")

    tags = ["#stocks", "#stockmarket", "#trading", "#investing", "#swingtrading",
            "#stockstowatch", "#technicalanalysis", "#fintok", "#stocktok",
            "#investingtips", "#moneytok", "#wallstreet", "#daytrading",
            "#tradingsetup", "#riskmanagement", f"#{tk.lower()}", "#monkeybusiness"]
    for k, v in _SECTOR_TAGS.items():
        if sect and k.lower() in sect.lower():
            tags = v + tags
            break
    seen, out = set(), []
    for t in tags:
        if t not in seen:
            seen.add(t); out.append(t)
    L.append(" ".join(out[:20]))
    return "\n".join(L)
def calc_position_size(entry_price, sl_price, portfolio, risk_percent):
    risk_per_share = abs(entry_price - sl_price)
    if risk_per_share <= 0:
        return None
    max_loss = portfolio * (risk_percent / 100)
    shares = int(max_loss / risk_per_share)
    position_value = shares * entry_price
    if shares <= 0 or position_value > portfolio:
        shares = int(portfolio / entry_price) if entry_price > 0 else 0
        position_value = shares * entry_price
    return {"shares": shares, "position_value": position_value, "max_loss": max_loss}

def gather_stock_signals(ticker, df, curr, macro_score, want_options=True,
                          stop_style=DEFAULTS["stop_style"],
                          structural_lookback=DEFAULTS["structural_lookback"],
                          structural_buffer_pct=DEFAULTS["structural_buffer_pct"],
                          overext_threshold=DEFAULTS["overext_threshold"],
                          directional_vol=DEFAULTS["directional_vol"],
                          use_composite=DEFAULTS["use_composite"]):
    """ אוסף את כל האותות למניה אחת: טכני, ביצוע, אופציות, תנועה צפויה, squeeze, וציון מורכב.
    ברירות המחדל מגיעות מ-DEFAULTS - התצורה שאומתה בבקטסט על מספר קטגוריות. """
    tech_score, bd, tech_err = calculate_technical_score(df, directional_vol=directional_vol)
    if tech_score is None:
        return None, tech_err
    exec_p = get_execution_params(df, curr, overext_threshold=overext_threshold,
                                   stop_style=stop_style, structural_lookback=structural_lookback,
                                   structural_buffer_pct=structural_buffer_pct)
    opt_sig = opt_err = None
    iv_rv_ratio = realized_vol = exp_move = None
    if want_options:
        opt_sig, opt_err = fetch_options_signals(ticker, curr)
        if opt_sig:
            realized_vol, iv_rv_ratio = compute_iv_percentile(df, opt_sig.get("atm_iv"))
            exp_move = compute_expected_move(opt_sig, curr)
    opt_bonus, opt_note = options_sentiment_bonus(opt_sig, iv_rv_ratio)
    squeeze_score, squeeze_parts, squeeze_coverage = compute_squeeze_proxy(
        bd["rsi_raw"], bd["vol_ratio"], bd["price_change_5d"], opt_sig, iv_rv_ratio)
    composite, comp_detail = (None, {})
    if exec_p is not None and use_composite:
        composite, comp_detail = calculate_composite_score(tech_score, macro_score, exec_p, opt_bonus)
    em_risk = em_note = em_ratio = None
    if exp_move and exec_p:
        em_risk, em_note, em_ratio = assess_stop_vs_expected_move(exp_move, exec_p.get("sl_pct"))
    return {"tech_score": tech_score, "breakdown": bd, "exec": exec_p,
            "opt_sig": opt_sig, "opt_err": opt_err, "opt_bonus": opt_bonus, "opt_note": opt_note,
            "iv_rv_ratio": iv_rv_ratio, "realized_vol": realized_vol,
            "exp_move": exp_move, "em_risk": em_risk, "em_note": em_note, "em_ratio": em_ratio,
            "squeeze_score": squeeze_score, "squeeze_parts": squeeze_parts,
            "squeeze_coverage": squeeze_coverage,
            "composite": composite, "comp_detail": comp_detail}, None

with tab_scanner:
    st.sidebar.title("🔍 הגדרות סריקה")
    selected_cat = st.sidebar.selectbox("בחר קטגוריה:", list(CATEGORIES.keys()))
    cat_len = len(CATEGORIES[selected_cat])
    with st.sidebar.expander(f"מניות בקטגוריה ({cat_len})", expanded=False):
        st.write(", ".join(CATEGORIES[selected_cat]))

    # ===== עריכת התיק האישי =====
    # התיק נשמר כקובץ JSON ב-Drive ולא בזיכרון, כדי שישרוד איפוס רנטיים.
    with st.sidebar.expander("✏️ ערוך את התיק האישי", expanded=False):
        _cur = load_portfolio()
        st.caption(f"כרגע בתיק: {len(_cur)} מניות")
        _add = st.text_input("הוסף (פסיקים/רווחים):", key="pf_add")
        if st.button("➕ הוסף", key="pf_add_btn") and _add.strip():
            _new = [x.strip().upper() for x in re.split(r'[,\s]+', _add) if x.strip()]
            okp, err = save_portfolio(_cur + _new)
            if okp:
                st.success(f"נוספו: {', '.join(_new)}")
                st.rerun()
            else:
                st.error(f"שמירה נכשלה: {err}")
        _rm = st.multiselect("הסר מניות:", _cur, key="pf_rm")
        if st.button("🗑️ הסר", key="pf_rm_btn") and _rm:
            okp, err = save_portfolio([x for x in _cur if x not in _rm])
            if okp:
                st.success(f"הוסרו: {', '.join(_rm)}")
                st.rerun()
            else:
                st.error(f"שמירה נכשלה: {err}")
            st.rerun()
        st.caption("השינויים נשמרים ב-Drive ושורדים איפוס של הרנטיים.")
        _bk = load_backups()
        if _bk:
            st.markdown("---")
            st.caption("\u21A9\uFE0F שחזור: 10 המצבים האחרונים נשמרים אוטומטית")
            _opts = [f"{b['ts']} ({len(b['list'])} מניות)" for b in _bk]
            _pick = st.selectbox("שחזר למצב:", _opts, key="pf_bk_pick",
                                  label_visibility="collapsed")
            _bi = _opts.index(_pick)
            st.caption(", ".join(_bk[_bi]["list"][:12]) +
                       (" ..." if len(_bk[_bi]["list"]) > 12 else ""))
            if st.button("\u21A9\uFE0F שחזר", key="pf_bk_go"):
                _okb, _erb = save_portfolio(_bk[_bi]["list"])
                if _okb:
                    st.success("שוחזר"); st.rerun()
                else:
                    st.error(str(_erb))

    custom_t = st.sidebar.text_input("חיפוש חופשי (פסיקים/רווחים):", "")

    st.sidebar.markdown("---")
    use_locked = st.sidebar.toggle("🔒 תצורה מאומתת (מומלץ)", True,
        help="מפעיל את התצורה שנבחרה על סמך סדרת 22 בדיקות על 11 קטגוריות: Swing Low + מדיניות דוחות משולבת + נורמליזציית תנודתיות.")

    if use_locked:
        sc_stop_style = DEFAULTS["stop_style"]
        sc_lookback = DEFAULTS["structural_lookback"]
        sc_buffer = DEFAULTS["structural_buffer_pct"]
        sc_overext = DEFAULTS["overext_threshold"]
        sc_dir_vol = DEFAULTS["directional_vol"]
        sc_composite = DEFAULTS["use_composite"]
        sc_entry_buf = DEFAULTS["entry_buffer_days"]
        sc_exit_buf = DEFAULTS["exit_buffer_days"]
        st.sidebar.caption("🏗️ Swing Low · 🔀 דוחות משולב · 📏 נורמליזציה אוטומטית לפי ATR")
    else:
        st.sidebar.warning("⚠️ מצב ניסוי - התצורה לא מאומתת")
        sc_stop_style = "structural" if st.sidebar.toggle("🏗️ סטופ Swing Low", True) else "atr"
        sc_lookback = st.sidebar.number_input("חלון Swing Low (ימים):", 5, 40, DEFAULTS["structural_lookback"], 5)
        sc_buffer = st.sidebar.number_input("Buffer מתחת לשפל (%):", 0.0, 5.0, DEFAULTS["structural_buffer_pct"], 0.5)
        sc_overext = st.sidebar.number_input("סף מתיחת יתר (% מעל SMA20):", 3.0, 25.0, DEFAULTS["overext_threshold"], 1.0)
        sc_dir_vol = st.sidebar.toggle("נפח מכוון", DEFAULTS["directional_vol"])
        sc_composite = st.sidebar.toggle("ציון מורכב", DEFAULTS["use_composite"])
        sc_entry_buf = st.sidebar.number_input("ימים לפני דוח לחסימת כניסה:", 1, 10, DEFAULTS["entry_buffer_days"], 1)
        sc_exit_buf = st.sidebar.number_input("ימים לפני דוח ליציאה:", 1, 5, DEFAULTS["exit_buffer_days"], 1)

    min_score_filter = st.sidebar.slider("הצג רק מניות מעל ציון:", 0, 90, 0, 5,
        help="0 = הצג הכל. העלה כדי לסנן רק את המועמדות החזקות.")

    sort_mode = st.radio("מיון התוצאות לפי:", ["🎯 ציון כדאיות כניסה (מומלץ)", "💪 חוזק טכני גולמי", "🚀 פוטנציאל Squeeze"],
                          horizontal=False,
                          help="'ציון כדאיות' לוקח בחשבון גם איכות הכניסה (מתיחת יתר, פאזת מגמה) - הכי שימושי לבחירת מניה מתוך רשימה. 'חוזק טכני' הוא הציון הגולמי בלי הפילטרים.")

    # הכפתור מדליק דגל במקום להריץ ישירות -
    # אחרת כל לחיצה על כפתור אחר מוחקת את תוצאות הסריקה.
    if st.sidebar.button("הרץ סורק", use_container_width=True, type="primary"):
        st.session_state["scan_on"] = True
    if st.session_state.get("scan_on"):
        targets = [t.strip().upper() for t in re.split(r'[,\s]+', custom_t) if t.strip()] if custom_t else CATEGORIES[selected_cat]
        total_targets = len(targets)
        progress_bar = st.progress(0, text="מאתחל סריקה...")
        cards_data, failed_tickers = [], []

        for i, t in enumerate(targets):
            progress_bar.progress(i / total_targets, text=f"🔍 מעבד: {t} ({i+1}/{total_targets})...")
            df, fetch_err = fetch_stock_data(t)
            if df.empty:
                failed_tickers.append(f"{t} ({fetch_err or 'אין נתונים'})")
                continue

            curr = df['Close'].iloc[-1]
            sig, sig_err = gather_stock_signals(t, df, curr, macro_score, want_options=use_options,
                                                 stop_style=sc_stop_style, structural_lookback=sc_lookback,
                                                 structural_buffer_pct=sc_buffer, overext_threshold=sc_overext,
                                                 directional_vol=sc_dir_vol, use_composite=sc_composite)
            if sig is None:
                failed_tickers.append(f"{t} ({sig_err})")
                continue

            exec_params = sig["exec"]
            final_sc = sig["composite"] if sig["composite"] is not None else sig["tech_score"]

            e_days, e_err = get_earnings_days(t)
            if e_err or e_days is None:
                e_alert = "❓ לא אומת (שגיאת API)"
            elif e_days <= sc_exit_buf:
                e_alert = "🚨 צא עכשיו"
            elif e_days <= sc_entry_buf:
                e_alert = "🛑 אל תיכנס"
            elif e_days <= 7:
                e_alert = "⚠️ דוח השבוע"
            elif e_days <= 14:
                e_alert = "🟡 דוח בשבועיים"
            else:
                e_alert = "🟢 נקי"

            if exec_params is None:
                act, color = "❌ שגיאת חישוב נתונים", "#dc3545"
            elif macro_danger:
                act, color = "🛑 BLOCKED (VIX גבוה)", "#dc3545"
            elif e_days is not None and e_days <= sc_entry_buf:
                act, color = f"🛑 BLOCKED (דוח בעוד {e_days} ימים)", "#dc3545"
            elif e_days is None:
                act, color = "⚠️ בדוק דוח ידנית", "#ffc107"
            elif exec_params["is_overextended"]:
                act, color = "⚠️ מתיחת יתר - המתן", "#ffc107"
            elif "דובי" in exec_params["phase"]:
                act, color = "🔴 מגמה שלילית / הימנע", "#dc3545"
            elif "Bear Rally" in exec_params["phase"]:
                act, color = "⚠️ ריבאונד בתוך ירידה - סיכון גבוה", "#ffc107"
            elif final_sc >= 70:
                act, color = "🟢 כדאיות כניסה גבוהה", "#28a745"
            elif final_sc >= 50:
                act, color = "🔵 כדאיות בינונית", "#17a2b8"
            else:
                act, color = "⚪ נטרלי / עקוב", "#6c757d"

            if e_days is None:
                e_days_disp = "?"
            elif e_days >= 999:
                e_days_disp = "לא ידוע בטווח"
            else:
                e_days_disp = str(e_days)

            _ap, _blabel, _bthr, _bdays = vol_band(df)
            cards_data.append({"atr_pct": _ap, "band": _blabel,
                                "band_thr": _bthr, "band_days": _bdays,
                                "ticker": t, "act": act, "color": color, "e_alert": e_alert,
                                "e_days": e_days_disp, "e_days_raw": e_days, "score": final_sc,
                                "curr": curr, "exec": exec_params, "sig": sig})

        progress_bar.progress(1.0, text="✅ הושלם")
        time.sleep(0.4)
        progress_bar.empty()

        if failed_tickers:
            with st.expander(f"⚠️ {len(failed_tickers)} טיקרים נכשלו בשליפה", expanded=False):
                for f in failed_tickers: st.write(f"- {f}")

        if cards_data:
            # ===== לוח התראות דוחות =====
            # מוצג לפני כל השאר כי זו פעולה דחופה בזמן: מי שכבר בפוזיציה צריך לצאת,
            # ומי ששוקל כניסה צריך לדעת שהחלון נסגר. סדר לפי דחיפות, לא לפי ציון.
            urgent = [c for c in cards_data if c.get("e_days_raw") is not None and c["e_days_raw"] <= sc_exit_buf]
            soon = [c for c in cards_data if c.get("e_days_raw") is not None and sc_exit_buf < c["e_days_raw"] <= 7]
            two_wk = [c for c in cards_data if c.get("e_days_raw") is not None and 7 < c["e_days_raw"] <= 14]
            if urgent or soon or two_wk:
                st.markdown("### 📅 התראות דוחות")
                if urgent:
                    names = ", ".join(f"{c['ticker']} ({c['e_days_raw']}י)" for c in urgent)
                    st.error(f"🚨 **צא מפוזיציה עכשיו:** {names} — הדוח בתוך {sc_exit_buf} ימים או פחות. לפי מדיניות 'משולב' יוצאים לפני הדוח וחוזרים אחריו.")
                if soon:
                    names = ", ".join(f"{c['ticker']} ({c['e_days_raw']}י)" for c in soon)
                    st.warning(f"⚠️ **דוח השבוע:** {names} — אל תפתח פוזיציות חדשות, והתכונן לצאת.")
                if two_wk:
                    names = ", ".join(f"{c['ticker']} ({c['e_days_raw']}י)" for c in two_wk)
                    st.info(f"🟡 **דוח בשבועיים הקרובים:** {names}")
                unknown = [c for c in cards_data if c.get("e_days_raw") is None]
                if unknown:
                    st.caption(f"❓ לא הצלחתי לאמת תאריך דוח ל: {', '.join(c['ticker'] for c in unknown)} — בדוק ידנית לפני כניסה.")
                st.markdown("---")

            total_before = len(cards_data)
            if min_score_filter > 0:
                cards_data = [c for c in cards_data if c["score"] >= min_score_filter]
                st.caption(f"מסונן: {len(cards_data)} מתוך {total_before} מניות עם ציון ≥ {min_score_filter}")
            if not cards_data:
                st.info(f"אף מניה לא עברה את סף הציון {min_score_filter}. הורד את הסף בסרגל הצד.")
                st.stop()

            if sort_mode.startswith("💪"):
                cards_data.sort(key=lambda x: x['sig']['tech_score'], reverse=True)
            elif sort_mode.startswith("🚀"):
                cards_data.sort(key=lambda x: (x['sig']['squeeze_score'] or 0), reverse=True)
            else:
                cards_data.sort(key=lambda x: x['score'], reverse=True)

            # טבלת דירוג מרוכזת - הדרך המהירה לבחור מניה מתוך רשימה
            st.markdown("### 🏆 דירוג מרוכז")
            rank_rows = []
            for c in cards_data:
                s = c['sig']
                rank_rows.append({
                    "טיקר": c['ticker'],
                    "שם": stock_label(c['ticker']),
                    "תחום": stock_sector(c['ticker']),
                    "🎯 ציון": round(c['score'], 1),
                    "סף": c.get('band_thr', 65),
                    "עובר?": "✅" if c['score'] >= c.get('band_thr', 65) else "❌",
                    "💲 מחיר": round(c['curr'], 2),
                    "🛑 סטופ": round(c['exec']['sl'], 2) if c['exec'] else "—",
                    "SL %": round(c['exec']['sl_pct'], 1) if c['exec'] else "—",
                    "🎯 יעד": round(c['exec']['tp'], 2) if c['exec'] else "—",
                    "TP %": round(c['exec']['tp_pct'], 1) if c['exec'] else "—",
                    "📦 מניות": (calc_position_size(c['curr'], c['exec']['sl'], portfolio_size, risk_pct) or {}).get('shares', "—") if c['exec'] else "—",
                    "📏 תנודתיות": c.get('band', "—"),
                    "ATR%": round(c['atr_pct'], 1) if c.get('atr_pct') else "—",
                    "RSI": s['breakdown']['rsi_raw'],
                    "דוח (ימים)": c['e_days'],
                    "שלב": c['exec']['phase'].split(' ')[0] if c['exec'] else "—",
                    "🚀 Squeeze": s['squeeze_score'] if s['squeeze_score'] is not None else "—",
                })
            st.dataframe(pd.DataFrame(rank_rows), use_container_width=True)
            st.caption("📏 הסף המומלץ נגזר מתנודתיות המניה (ATR%) — אותה נוסחה שבבקטסט. מניה קיצונית דורשת סף 75; מניה בינונית מסתפקת ב-55.")
            st.markdown("---")

            # last generated share card - rendered at top of results because

            # Streamlit scrolls to the top of the page on every rerun

            if st.session_state.get("ig_err"):

                st.error("Card generation failed:")

                st.code(st.session_state["ig_err"], language="text")

                if st.button("Dismiss", key="ig_err_x"):

                    st.session_state.pop("ig_err", None)

                    st.rerun()

            _lt = st.session_state.get("ig_last")

            if _lt and st.session_state.get("igimg_" + _lt):

                _limg = st.session_state["igimg_" + _lt]

                with st.container(border=True):

                    st.markdown("#### 📸 Share card: " + _lt)

                    st.image(_limg, width=260)

                    st.download_button("⬇️ Download PNG", _limg,

                        file_name=_lt + "_" + datetime.now().strftime("%Y%m%d") + ".png",

                        mime="image/png", key="igdl_top")

                    if st.button("✖️ Close", key="igx_top"):

                        st.session_state.pop("igimg_" + _lt, None)

                        st.session_state.pop("ig_last", None)

                        st.rerun()


            with st.expander("🗂️ Bulk share cards", expanded=False):


                _opts = [c["ticker"] for c in cards_data]


                _pass = [c["ticker"] for c in cards_data if c["score"] >= c.get("band_thr", 65)]


                _sel = st.multiselect("Tickers:", _opts, default=(_pass[:10] or _opts[:10]), key="bulk_sel")


                if st.button("🗂️ Generate " + str(len(_sel)) + " cards", key="bulk_go", type="primary") and _sel:


                    _byt = {c["ticker"]: c for c in cards_data}


                    _pb = st.progress(0.0, text="starting...")


                    _buf = _io.BytesIO()


                    _caps, _fails = [], []


                    with _zip.ZipFile(_buf, "w", _zip.ZIP_DEFLATED) as _z:


                        for _i, _t in enumerate(_sel):


                            _pb.progress(_i / max(1, len(_sel)), text=_t)


                            _c = _byt.get(_t)


                            if not _c:


                                continue


                            try:


                                _z.writestr(_t + ".png", make_infographic(_c, _c["sig"]))


                                _cp = make_caption(_c, _c["sig"])


                                _z.writestr("captions/" + _t + ".txt", _cp)


                                _caps.append("=" * 40 + chr(10) + _t + chr(10) + "=" * 40 + chr(10) + _cp)


                            except Exception as _e:


                                _fails.append(_t + ": " + str(_e))


                        _z.writestr("ALL_CAPTIONS.txt", (chr(10) * 2).join(_caps))


                    _pb.empty()


                    st.session_state["bulk_zip"] = _buf.getvalue()


                    st.session_state["bulk_caps"] = (chr(10) * 2).join(_caps)


                    st.session_state["bulk_n"] = len(_caps)


                    if _fails:


                        st.warning("failed: " + ", ".join(_fails))


                if st.session_state.get("bulk_zip"):


                    st.success(str(st.session_state.get("bulk_n", 0)) + " cards ready")


                    st.download_button("⬇️ Download ZIP", st.session_state["bulk_zip"],


                        file_name="cards_" + datetime.now().strftime("%Y%m%d_%H%M") + ".zip",


                        mime="application/zip", key="bulk_dl")


                    with st.expander("All captions", expanded=False):


                        st.code(st.session_state["bulk_caps"], language="text")



            for card in cards_data:
                s = card["sig"]
                with st.container(border=True):
                    st.markdown(f"<h4 style='color: {card['color']}; margin-bottom: 0;'>{card['ticker']} · <span style='font-size:0.8em;color:#ccc;'>{stock_label(card['ticker'])}</span> | {card['act']}</h4>", unsafe_allow_html=True)
                    if stock_sector(card['ticker']):
                        st.caption(f"🏷️ {stock_sector(card['ticker'])}")
                    exec_p = card["exec"]
                    phase_txt = exec_p["phase"] if exec_p else "לא זמין"
                    st.markdown(f"**מגמה:** {phase_txt} | **דוח:** {card['e_alert']} ({card['e_days']} ימים) | **🎯 כדאיות:** {card['score']:.1f} | **💪 טכני:** {s['tech_score']:.1f}")
                    _igk = "igimg_" + card["ticker"]
                    if st.button("\U0001F4F8 Share card", key="ig_" + card["ticker"]):
                        try:
                            st.session_state[_igk] = make_infographic(card, s)
                            st.session_state["igcap_" + card["ticker"]] = make_caption(card, s)
                            st.session_state["ig_last"] = card["ticker"]
                            st.session_state.pop("ig_err", None)
                        except Exception as _e:
                            import traceback
                            st.session_state.pop(_igk, None)
                            st.session_state["ig_err"] = traceback.format_exc()
                        st.rerun()
        else:
            st.warning("לא נמצאו מניות עם נתונים תקינים לניתוח.")

with tab_deep_dive:

    # ===== בדיקת סיווג הקטגוריות =====
    # הקטגוריות סווגו ידנית ולכן ייתכנו בהן טעויות. הבדיקה מושכת מ-yfinance
    # את הענף האמיתי של כל מניה, ומשווה אותו לקטגוריה שהיא יושבת בה בפועל.
    # זו בדיקה של **הסיווג**, לא של הביצועים - היא לא נוגעת בבקטסט.
    with st.expander("\U0001F50D בדיקת סיווג הקטגוריות (רמזור)", expanded=False):
        st.markdown("""
        <div class='unknown-box'>
        \U0001F6A6 <b>מה הבדיקה עושה:</b> לכל מניה נשלף הענף האמיתי מ-yfinance
        ומושווה לקטגוריה שהיא משויכת אליה.<br>
        \U0001F7E2 תואם &nbsp;·&nbsp; \U0001F7E1 שיוך כפול (ייתכן שבכוונה) &nbsp;·&nbsp;
        \U0001F534 לא תואם - כדאי לבדוק &nbsp;·&nbsp; \u26AA אין נתוני ענף (בעיקר תעודות סל)<br>
        \u26A0\uFE0F כל מניה דורשת קריאת רשת. קטגוריה בודדת = כדקה; הכל = כמה דקות.
        </div>
        """, unsafe_allow_html=True)

        _aud_opts = ["\u05db\u05dc \u05d4\u05e7\u05d8\u05d2\u05d5\u05e8\u05d9\u05d5\u05ea"] + list(CATEGORIES.keys())
        _aud_pick = st.selectbox("מה לבדוק:", _aud_opts, index=1, key="aud_pick")

        if st.button("\U0001F50D הרץ בדיקת סיווג", key="aud_run"):
            _targets = list(CATEGORIES.keys()) if _aud_pick == _aud_opts[0] else [_aud_pick]
            # מפת שיוך: לכל טיקר, באילו קטגוריות הוא נמצא
            _where = {}
            for _k in CATEGORIES:
                for _t in CATEGORIES[_k]:
                    _where.setdefault(_t, []).append(_k)

            _tks = sorted({t for k in _targets for t in CATEGORIES[k]})
            _pb = st.progress(0, text="מאתחל...")
            _rows, _cnt = [], {"ok": 0, "dup": 0, "bad": 0, "none": 0}
            for _i, _t in enumerate(_tks):
                _pb.progress(_i / max(1, len(_tks)), text=f"בודק {_t} ({_i+1}/{len(_tks)})")
                _nm, _ind, _exp, _conf, _e = fetch_ticker_meta(_t)
                _mine = [k for k in _where.get(_t, []) if k in _targets]
                _mine_s = " + ".join(_mine) if _mine else "—"
                if _e or not _nm:
                    _st, _note = "\u26AA", "אין נתונים"
                    _cnt["none"] += 1
                elif _exp is None:
                    _st, _note = "\u26AA", "ענף לא ממופה"
                    _cnt["none"] += 1
                elif any(_exp == k for k in _mine):
                    if len(_mine) > 1:
                        _st, _note = "\U0001F7E1", "שיוך כפול"
                        _cnt["dup"] += 1
                    else:
                        _st, _note = "\U0001F7E2", "תואם"
                        _cnt["ok"] += 1
                else:
                    _st, _note = "\U0001F534", "לא תואם"
                    _cnt["bad"] += 1
                _rows.append({"": _st, "טיקר": _t, "שם": _nm or _t,
                               "ענף אמיתי": _ind or "—",
                               "אצלנו": _mine_s,
                               "צפוי": _exp or "—",
                               "הערה": _note})
            _pb.progress(1.0, text="הושלם"); time.sleep(0.2); _pb.empty()

            st.markdown(f"""
            <div class="metric-row">
                <div class="metric-item"><div class="metric-title">\U0001F7E2 תואם</div><div class="metric-value">{_cnt['ok']}</div></div>
                <div class="metric-item"><div class="metric-title">\U0001F7E1 כפול</div><div class="metric-value">{_cnt['dup']}</div></div>
                <div class="metric-item"><div class="metric-title">\U0001F534 לא תואם</div><div class="metric-value">{_cnt['bad']}</div></div>
                <div class="metric-item"><div class="metric-title">\u26AA אין נתונים</div><div class="metric-value">{_cnt['none']}</div></div>
            </div>
            """, unsafe_allow_html=True)

            _bad_rows = [r for r in _rows if r[""] == "\U0001F534"]
            if _bad_rows:
                st.markdown("##### \U0001F534 דורשים בדיקה")
                st.dataframe(pd.DataFrame(_bad_rows), use_container_width=True)
            else:
                st.success("אין אי-התאמות בקטגוריות שנבדקו.")

            with st.expander(f"כל התוצאות ({len(_rows)})", expanded=False):
                st.dataframe(pd.DataFrame(_rows), use_container_width=True)

            _L = ["=" * 54, "בדיקת סיווג: " + str(_aud_pick),
                  datetime.now().strftime("%Y-%m-%d %H:%M"), "=" * 54,
                  f"תואם {_cnt['ok']} | כפול {_cnt['dup']} | לא תואם {_cnt['bad']} | אין נתונים {_cnt['none']}",
                  "", "--- לא תואם ---"]
            for _r in _bad_rows:
                _L.append(f"  {_r['טיקר']} ({_r['שם']}) | ענף: {_r['ענף אמיתי']} | אצלנו: {_r['אצלנו']} | צפוי: {_r['צפוי']}")
            _dups = [r for r in _rows if r[""] == "\U0001F7E1"]
            if _dups:
                _L += ["", "--- שיוך כפול ---"]
                for _r in _dups:
                    _L.append(f"  {_r['טיקר']}: {_r['אצלנו']}")
            _nones = [r for r in _rows if r[""] == "\u26AA"]
            if _nones:
                _L += ["", "--- אין נתוני ענף ---",
                       "  " + ", ".join(r["טיקר"] for r in _nones)]
            _txt = "\n".join(_L)
            st.markdown("##### \U0001F4CB דוח להעתקה")
            st.code(_txt, language="text")
            st.download_button("\u2B07\uFE0F הורד", _txt,
                file_name=f"audit_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain", key="aud_dl")


    # ===== בדיקת התאמה התנהגותית =====
    with st.expander("\U0001F4C8 בדיקת התאמה התנהגותית לקטגוריה", expanded=False):
        st.markdown("""
        <div class='unknown-box'>
        \U0001F9EA <b>למה זה שונה מבדיקת הסיווג:</b> הסיווג הרשמי אומר איך החברה
        <b>מוגדרת</b>. כאן נמדד מה שבאמת משנה - האם היא <b>זזה</b> כמו שאר הקבוצה.<br>
        \U0001F7E2 מעל 0.60 מתנהגת כמו הקבוצה &nbsp;·&nbsp;
        \U0001F7E1 0.35-0.60 חלקית &nbsp;·&nbsp;
        \U0001F534 מתחת ל-0.35 מתנהגת אחרת<br>
        \u26A0\uFE0F קורלציה נמוכה \u2260 שיוך שגוי. מניה קטנה בסקטור של ענקיות
        תראה ערך נמוך גם כששיוכה נכון. זו אינדיקציה לבדיקה, לא פסק דין.
        </div>
        """, unsafe_allow_html=True)

        _fit_cats = st.multiselect("קטגוריות לבדיקה:", list(CATEGORIES.keys()),
                                    default=[list(CATEGORIES.keys())[0]], key="fit_cats")
        _fit_per = st.selectbox("טווח:", ["6mo", "1y", "2y"], index=1, key="fit_per")

        if st.button("\U0001F4C8 הרץ בדיקת התאמה", key="fit_run") and _fit_cats:
            _all_rows, _txt_parts = [], []
            _multi = {}
            for _k in CATEGORIES:
                for _t in CATEGORIES[_k]:
                    _multi.setdefault(_t, []).append(_k)

            for _ci, _k in enumerate(_fit_cats):
                _pb = st.progress(0, text=f"{_k}: מושך נתונים...")
                _fit = category_fit(CATEGORIES[_k], _fit_per)
                _pb.progress(1.0); time.sleep(0.1); _pb.empty()
                if not _fit:
                    st.warning(f"{_k}: אין מספיק נתונים")
                    continue
                _rows = []
                for _t, _c in sorted(_fit.items(), key=lambda x: -(x[1] if x[1] == x[1] else -9)):
                    if _c != _c:
                        _st = "\u26AA"
                    elif _c >= 0.60:
                        _st = "\U0001F7E2"
                    elif _c >= 0.35:
                        _st = "\U0001F7E1"
                    else:
                        _st = "\U0001F534"
                    _others = [x for x in _multi.get(_t, []) if x != _k]
                    _rows.append({"": _st, "טיקר": _t, "שם": stock_label(_t),
                                   "קורלציה": round(_c, 2) if _c == _c else "—",
                                   "גם ב-": " + ".join(_others) if _others else "—"})
                _vals = [v for v in _fit.values() if v == v]
                _avg = sum(_vals) / len(_vals) if _vals else float('nan')
                st.markdown(f"##### {_k} — קורלציה ממוצעת {_avg:.2f}")
                st.dataframe(pd.DataFrame(_rows), use_container_width=True)
                _weak = [r for r in _rows if r[""] == "\U0001F534"]
                if _weak:
                    st.caption("\U0001F534 " + ", ".join(f"{r['טיקר']} ({r['קורלציה']})" for r in _weak))
                _all_rows += _rows
                _txt_parts.append(f"--- {_k} (ממוצע {_avg:.2f}) ---")
                for _r in _rows:
                    _txt_parts.append(f"  {_r['']} {_r['טיקר']:<6} {_r['קורלציה']}  {_r['שם']}"
                                       + (f"  | גם ב: {_r['גם ב-']}" if _r['גם ב-'] != "—" else ""))
                _txt_parts.append("")

            if _all_rows:
                _txt = "\n".join(["=" * 54, "בדיקת התאמה התנהגותית",
                                   datetime.now().strftime("%Y-%m-%d %H:%M"),
                                   f"טווח: {_fit_per}", "=" * 54] + _txt_parts)
                st.markdown("##### \U0001F4CB דוח להעתקה")
                st.code(_txt, language="text")
                st.download_button("\u2B07\uFE0F הורד", _txt,
                    file_name=f"fit_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                    mime="text/plain", key="fit_dl")

    st.markdown("### 🔬 פירוק אינדיקטורים לטיקר בודד")
    calc_ticker = st.text_input("הזן סימול:", "NVDA").upper()
    if st.button("הצג פירוק"):
        df, fetch_err = fetch_stock_data(calc_ticker)
        if df.empty:
            st.markdown(f"<div class='fail-box'>🚨 שגיאת שליפה: {fetch_err}</div>", unsafe_allow_html=True)
        else:
            curr = df['Close'].iloc[-1]
            sig, sig_err = gather_stock_signals(calc_ticker, df, curr, macro_score, want_options=use_options,
                                                 stop_style=DEFAULTS["stop_style"],
                                                 structural_lookback=DEFAULTS["structural_lookback"],
                                                 structural_buffer_pct=DEFAULTS["structural_buffer_pct"],
                                                 overext_threshold=DEFAULTS["overext_threshold"],
                                                 directional_vol=DEFAULTS["directional_vol"],
                                                 use_composite=DEFAULTS["use_composite"])
            if sig is None:
                st.markdown(f"<div class='fail-box'>🚨 {sig_err}</div>", unsafe_allow_html=True)
            else:
                bd = sig["breakdown"]
                exec_p = sig["exec"]
                st.markdown("#### ⚙️ פרמטרי ביצוע")
                if exec_p is None:
                    st.markdown("<div class='fail-box'>🚨 לא ניתן לחשב סטופ/יעד - נתונים חסרים</div>", unsafe_allow_html=True)
                else:
                    st.info(f"**שלב מגמה:** {exec_p['phase']} (מרחק מ-SMA20: {exec_p['dist_20']:+.1f}%)")
                    if exec_p["norm_note"]: st.warning(exec_p["norm_note"])
                    if exec_p.get("is_capped"):
                        st.markdown("<div class='unknown-box'>⚠️ ATR קיצוני - הסטופ מוגבל ל-12% מהמחיר במקום המרחק הגולמי הגדול יותר.</div>", unsafe_allow_html=True)
                    col_a, col_b = st.columns(2)
                    col_a.metric("סטופ (SL)", f"${exec_p['sl']:.2f}", f"{exec_p['sl_pct']:.1f}%", delta_color="inverse")
                    col_b.metric("יעד (TP)", f"${exec_p['tp']:.2f}", f"{exec_p['tp_pct']:+.1f}%", delta_color="normal")
                    pos = calc_position_size(curr, exec_p['sl'], portfolio_size, risk_pct)
                    if pos and pos["shares"] > 0:
                        st.info(f"💰 **גודל פוזיציה מוצע:** {pos['shares']} מניות (שווי {pos['position_value']:.0f}\\$ מתוך תיק {portfolio_size:.0f}\\$) | הפסד מקסימלי אם SL נפגע: {pos['max_loss']:.0f}\\$")

                st.markdown("#### 1️⃣ פירוק ציון טכני")
                st.table(pd.DataFrame([
                    {"אינדיקטור": "מגמה (SMA)", "גולמי": bd["trend"], "משקל": f"{bd['w_trend']*100:.0f}%"},
                    {"אינדיקטור": f"RSI ({bd['rsi_raw']})", "גולמי": bd["rsi"], "משקל": f"{bd['w_rsi']*100:.0f}%"},
                    {"אינדיקטור": f"MACD Hist ({bd['macd_hist_raw']})", "גולמי": bd["macd"], "משקל": f"{bd['w_macd']*100:.0f}%"},
                    {"אינדיקטור": f"נפח מכוון (יחס {bd['vol_ratio']}x, יום {bd['day_change']:+.1f}%)", "גולמי": bd["vol"], "משקל": f"{bd['w_vol']*100:.0f}%"}
                ]))
                st.caption("ℹ️ 'נפח מכוון': נפח חריג נספר חיובית רק ביום עלייה. בירידה חדה נפח גבוה הוא פאניקת מכירות - הסימן מתהפך.")

                # ===== סעיף 2: הכללים שחלים על המניה =====
                # החליף את טבלת המכפילים. הציון המורכב הוסר אחרי שנמצא מזיק,
                # ובמקומו מוצג מה שבאמת קובע את הכללים: תנודתיות.
                st.markdown("#### 2️⃣ הכללים שחלים על המניה הזו")
                tech_val = sig["tech_score"]
                _ap, _bl, _bthr, _bdays = vol_band(df)
                if _ap is not None:
                    _bexit = "TP קבוע" if _ap < 3.0 else ("קידום סטופ מבני" if _ap < 4.5 else "TP קבוע")
                    _brev = "לא" if _ap < 4.5 else "כן"
                    st.table(pd.DataFrame([
                        {"פרמטר": "ATR% (תנודתיות יומית)", "ערך": f"{_ap:.2f}%"},
                        {"פרמטר": "רמה", "ערך": _bl},
                        {"פרמטר": "סף כניסה מומלץ", "ערך": _bthr},
                        {"פרמטר": "מקסימום ימי החזקה", "ערך": _bdays},
                        {"פרמטר": "סגנון יציאה", "ערך": _bexit},
                        {"פרמטר": "יציאה על היפוך", "ערך": _brev},
                    ]))
                    _pass = "✅ עובר" if tech_val >= _bthr else "❌ לא עובר"
                    st.markdown(f"**הציון הטכני של המניה: {tech_val:.1f}** · מול סף {_bthr} ← {_pass}")
                    st.caption("📏 הכללים נגזרים מתנודתיות המניה עצמה (גבולות 3.0/4.5/6.5) — אותה נוסחה שבבקטסט.")
                else:
                    st.caption("לא ניתן לחשב ATR — נתונים חסרים.")


                st.markdown("#### 3️⃣ אופציות ו-Squeeze")
                if sig["opt_sig"]:
                    o = sig["opt_sig"]
                    st.markdown(f"<span class='real-tag'>📊 נתוני אופציות אמיתיים | פקיעות שנבדקו: {', '.join(o['expirations_used'])} | סה\"כ OI: {o['total_oi']:,.0f}</span>", unsafe_allow_html=True)
                    rows = []
                    if o.get("pc_oi_ratio") is not None: rows.append({"מדד": "Put/Call (Open Interest)", "ערך": round(o["pc_oi_ratio"], 3)})
                    if o.get("pc_vol_ratio") is not None: rows.append({"מדד": "Put/Call (נפח יומי)", "ערך": round(o["pc_vol_ratio"], 3)})
                    if o.get("atm_iv") is not None: rows.append({"מדד": "IV סביב הכסף", "ערך": f"{o['atm_iv']*100:.1f}%"})
                    if sig["realized_vol"] is not None: rows.append({"מדד": "תנודתיות בפועל (שנתית)", "ערך": f"{sig['realized_vol']*100:.1f}%"})
                    if sig["iv_rv_ratio"] is not None: rows.append({"מדד": "יחס IV/RV", "ערך": round(sig["iv_rv_ratio"], 2)})
                    if o.get("atm_call_px") is not None: rows.append({"מדד": "Call בכסף (ATM)", "ערך": f"${o['atm_call_px']:.2f}"})
                    if o.get("atm_put_px") is not None: rows.append({"מדד": "Put בכסף (ATM)", "ערך": f"${o['atm_put_px']:.2f}"})
                    st.table(pd.DataFrame(rows))
                    if sig.get("exp_move"):
                        em = sig["exp_move"]
                        st.markdown(f"""
                        <div class='real-tag'>
                        📏 <b>תנועה צפויה: ±{em['move_pct']:.1f}%</b> (${em['lower']:.2f} – ${em['upper']:.2f}) עד פקיעת {em['expiration']}<br>
                        <b>החישוב:</b> (Call בכסף ${o.get('atm_call_px', 0):.2f} + Put בכסף ${o.get('atm_put_px', 0):.2f}) ÷ מחיר ${curr:.2f} = {em['move_pct']:.1f}%<br>
                        ⚠️ זהו <b>גודל</b> התנועה הצפויה, לא הכיוון. שוק האופציות לא מנבא כיוון.
                        </div>
                        """, unsafe_allow_html=True)
                        if sig.get("em_note"):
                            st.caption(f"מול הסטופ שלנו: {sig['em_note']}")
                        st.caption("ℹ️ סביב דוחות ה-IV מתנפח ואז קורס מיד אחרי הפרסום (IV Crush) - זו הסיבה שה-IV הגבוה לפני דוח אינו 'איתות', אלא תמחור אי-ודאות. אנחנו סוחרים מניות ולא אופציות, אז ה-IV Crush לא פוגע בנו ישירות - אבל התנועה החדה כן.")
                    st.caption(f"השפעה על הציון: {sig['opt_bonus']:+.1f} נקודות — {sig['opt_note']}")
                else:
                    st.caption(f"אופציות לא זמינות: {sig['opt_err'] or 'לא נשלף / נזילות נמוכה'}")

                if sig["squeeze_score"] is not None:
                    p = sig["squeeze_parts"]
                    st.markdown(f"**🚀 פוטנציאל Squeeze (פרוקסי): {sig['squeeze_score']}/100** — כיסוי נתונים {sig['squeeze_coverage']}%")
                    sq_rows = [
                        {"רכיב": "Oversold (RSI)", "ניקוד": p.get("oversold"), "מקס": 30},
                        {"רכיב": "נפח חריג", "ניקוד": p.get("volume"), "מקס": 20},
                        {"רכיב": "ירידה חדה (5 ימים)", "ניקוד": p.get("drop"), "מקס": 15},
                        {"רכיב": "Put/Call OI", "ניקוד": p.get("put_call") if p.get("put_call") is not None else "לא זמין", "מקס": 20},
                        {"רכיב": "IV/RV", "ניקוד": p.get("iv_rv") if p.get("iv_rv") is not None else "לא זמין", "מקס": 15},
                    ]
                    st.table(pd.DataFrame(sq_rows))
                    st.markdown("""
                    <div class='proxy-tag'>
                    ⚠️ <b>מגבלה מהותית שחייבים להכיר:</b> זה <b>לא</b> זיהוי Short Squeeze אמיתי.
                    זיהוי אמיתי דורש שלושה נתונים שאינם קיימים ב-yfinance:<br>
                    • <b>Short Interest % of Float</b> — מתפרסם פעמיים בחודש בלבד, ובאיחור של שבוע-שבועיים<br>
                    • <b>Days to Cover</b> — נגזר מהראשון, אותה בעיה<br>
                    • <b>Cost to Borrow / Short Availability</b> — הסימן החי ביותר. זמין דרך <b>Interactive Brokers API</b>
                    או ספקים בתשלום (Ortex, S3, Fintel)<br><br>
                    מה שנמדד כאן הוא <b>תנאים שלפעמים מקדימים</b> Squeeze — לא תחזית. אמת ידנית לפני פעולה.
                    </div>
                    """, unsafe_allow_html=True)

with tab_backtest:
    st.markdown("### 🧪 בקטסט - בדיקת השיטה על נתונים היסטוריים")
    st.markdown("""
    <div class="disclaimer">
    ⚠️ בקטסט מבוסס על נתוני מחיר בלבד (ללא עמלות, ספרד, או פערי מחיר תוך-יומיים).
    ביצועים היסטוריים <b>אינם מבטיחים</b> תוצאות עתידיות. מדגם קטן (פחות מ-30 טריידים) אינו מובהק סטטיסטית -
    <b>השתמש במצב "קטגוריה שלמה" לקבלת מדגם אמין</b>, לא בבדיקת מניה בודדת בלבד.
    </div>
    """, unsafe_allow_html=True)
    st.markdown("""
    <div class="proxy-tag">
    ℹ️ <b>למה הבקטסט לא כולל אופציות ו-Fear&Greed:</b> לשני אלה אין היסטוריה זמינה ב-yfinance -
    יש רק את הערך של <b>היום</b>. החלת הערך הנוכחי על תאריכים היסטוריים הייתה
    <b>Look-ahead Bias</b> (הצצה לעתיד) - שמייפה תוצאות באופן מזויף לחלוטין.
    לכן הבקטסט בודק רק את החלק הטכני + מכפיל איכות הכניסה, שהם הרכיבים שכן ניתן לשחזר היסטורית.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class='unknown-box'>
    📌 <b>ציפייה ריאלית:</b> התוצאה משתנה מאוד לפי סקטור.
    עם נורמליזציית תנודתיות: שבבים ~2.4 · תיק בדיקות ~2.6 ·
    פיננסים ~1.0 · AI ~0.9 · בריאות ~0.5.<br>
    בסקטורים מחזוריים (אנרגיה) השיטה כמעט לא עובדת — וגם Buy&amp;Hold שם חלש.<br>
    היתרון האמיתי הוא <b>ניהול סיכון</b>: DD של 3-6% מול 30-60% ב-Buy&amp;Hold.
    התשואה הגולמית לרוב נמוכה מ-Buy&amp;Hold.
    </div>
    """, unsafe_allow_html=True)

    with st.expander("📖 מקרא - מה כל מתג עושה", expanded=False):
        st.markdown("""
| מתג | מה זה עושה | למה זה שם |
|---|---|---|
| **ציון מורכב** | הסף נבדק מול `טכני × מכפיל מאקרו × מכפיל פאזה + בונוס אופציות` במקום הציון הטכני הגולמי | ❌ נמצא מזיק בסדרת הבדיקות (בדיקה 02): Sharpe 2.28 כבוי מול 2.06 דלוק |
| **נפח מכוון** | נפח חריג נספר חיובית רק ביום עלייה; ביום ירידה הסימן מתהפך | בלי זה, פאניקת מכירות בנפח גבוה נספרה כאיתות חיובי |
| **סגנון סטופ** | ATR = מכפיל תנודתיות גנרי · Swing Low = השפל האמיתי האחרון בגרף | Swing Low ניצח ב-6/6 קטגוריות — הרכיב היחיד מהתצורה הישנה שעמד במבחן |
| **מדיניות דוחות** | רגיל = מתעלם · חסימת כניסה = לא נכנס אם דוח בטווח · משולב = נכנס רגיל אבל יוצא לפני הדוח | "משולב" שיפר את אחוז ההצלחה בכל הקטגוריות |
| **סגנון יציאה** | TP קבוע = יעד 2.5x הסיכון · Trailing = סטופ נגרר בלי יעד | Trailing תופס מגמות ארוכות אבל יוצא בתיקונים |
| **מתיחת יתר** | סף המרחק מ-SMA20 שמעליו המניה "מתוחה", ואם לחסום כניסה | חסימה = פחות טריידים אבל כניסות נקיות יותר |
| **💰 עלויות מסחר** | מנכה עמלה+ספרד מכל טרייד (כפול 2: כניסה ויציאה) | **הפער הגדול ביותר בין בקטסט למציאות.** בלי זה כל התוצאות אופטימיות מדי |
| **📏 פילטר תנועת דוחות** | חוסם כניסה אם המניה נוטה לזוז בדוחות יותר מ-X× רוחב הסטופ | כלל *מותאם למניה* במקום "צא יומיים לפני" לכולן |
| **📊 ניתוח החזקה דרך דוח** | מפצל את הטריידים ל"חצו דוח" מול "לא חצו" ומשווה | נותן **מספר** לשאלה כמה עולה להחזיק דרך דוח |
| **🌪️ משטר VIX** | התעלם · חסום כניסה ב-VIX גבוה · או להפך: היכנס **רק** ב-VIX גבוה | **בודק סתירה אמיתית:** הסורק חוסם ב-VIX>28, ו"כללי הדיפ" טוענים ש-VIX>30 הוא איתות כניסה |
| **📅 אישור מגמה שבועי** | דורש שגם הסגירה השבועית תהיה מעל ממוצע שבועי, לא רק היומי | רעיון ה"Zoom Out" - לא להיכנס נגד התמונה הגדולה |
| **🔪 חוק שלושת הימים** | אחרי ירידה חדה בעקבות דוח, ממתין N ימים לפני כניסה | מונע "תפיסת סכין נופלת" - המחיר לרוב ממשיך לרדת עוד כמה ימים |
| **🚦 הגבלת מסחר יתר** | תקרת כניסות חדשות בשבוע, שומר את בעלות הציון הגבוה | בודק ישירות: האם הטריידים השוליים תורמים או גורעים? |
        """)
        st.caption("💡 שיטת עבודה: שנה **מתג אחד בכל פעם**. אם תשנה שלושה יחד ותקבל תוצאה שונה, לא תדע מי אחראי - זו בדיוק הטעות שעשינו קודם עם הציון המורכב.")


    # ================= סדרת בדיקות אוטומטית =================
    # במקום לכבות ולהדליק מתגים ידנית (מקור עיקרי לטעויות ולבלבול),
    # כל בדיקה כאן מגדירה בעצמה את *כל* הצירופים שהיא צריכה.
    # בסיס אחיד לכל הבדיקות = התצורה שנקבעה כקו בסיס רשמי,
    # כך שכל תוצאה ניתנת להשוואה ישירה מול Sharpe 2.23 / Calmar 2.59.
    SUITE_BASE = {
        # ⚠️ נגזר מ-DEFAULTS — התצורה החיה. אין ערכים כתובים ביד.
        # כל שינוי בתצורה החיה מגיע לבדיקות אוטומטית.
        "composite":     DEFAULTS["use_composite"],
        "dir_vol":       DEFAULTS["directional_vol"],
        "block_overext": DEFAULTS["block_overextended"],
        "earn":          DEFAULTS["earnings_mode"],
        "exit":          DEFAULTS["exit_style"],
        "stop":          DEFAULTS["stop_style"],
        "threshold":     DEFAULTS["score_threshold"],
        "max_days":      DEFAULTS["max_holding_days"],
        "vol_norm":      DEFAULTS["use_vol_norm"],
        "rising_sma":    False,   # שיפוע SMA150 - כבוי בקו הבסיס
        # THREE-RED-DEFAULT: נמדד ראשון בשני החלונות ובכל מדד
    # (בדיקה 51). הציון נשאר מחושב ומוצג — רק תפקידו
    # כשער כניסה מתבטל.
    "trigger":       "three_red",
        "brk_lb":        20,       # חלון פריצת התנגדות
        "part_r": 2.0,      # מימוש חלקי ביעד R (0 = כבוי)
        "part_be":       False,    # סטופ לנקודת כניסה אחרי מימוש
        "dip_pct":       10.0,     # ירידה מהשיא לטריגר התכנסות
        "scale":         "off",   # חיזוק פוזיציה: off/split/add
        "scale_drop":    5.0,     # אחוז ירידה להוספה
        "ladder":        "off",   # סטופ מדורג: off/steady/tight
        "scale_first":   0.5,      # חלק הכניסה הראשונה
        "vn_scope":      "thr",   # off/thr/full
        "cooldown":      False,    # זיכרון: אין כניסה חוזרת מיידית
        "max_pos":       0,       # תקרת פוזיציות (0=ללא)
        "vb1":           DEFAULTS["vb1"],
        "vb2":           DEFAULTS["vb2"],
        "vb3":           DEFAULTS["vb3"],
        # מתגי בדיקה שאין להם מקבילה ב-DEFAULTS — כבויים
        "cost": 0.05, "vix_size": "off", "cool_mode": "off", "sec_cap": 0, "atr_cost": 0.0,
        # TRAIL-CAL: רוחב הטריילינג לא זרם מהחבילה עד כה.
        "trail": 2.0,  # COOLDOWN-OFF: נמדד כמזיק בבדיקה 47 "use_reversal": False, "weekly": False, "three_day": False,
        "em_filter": False, "max_wk": 0,
        "vix": "ignore", "rev": "sma20", "entry": "close", "macro": "off",
    }
    TEST_SUITE = {
        "\u2699\uFE0F \u05d9\u05d3\u05e0\u05d9 (\u05d1\u05d7\u05d9\u05e8\u05d4 \u05d7\u05d5\u05e4\u05e9\u05d9\u05ea \u05d1\u05de\u05ea\u05d2\u05d9\u05dd)": None,
        "01 \u05e7\u05d5 \u05d1\u05e1\u05d9\u05e1": [("\u05d1\u05e1\u05d9\u05e1", {})],
        "02 \u05e6\u05d9\u05d5\u05df \u05de\u05d5\u05e8\u05db\u05d1": [("\u05db\u05d1\u05d5\u05d9", {"composite": False}), ("\u05d3\u05dc\u05d5\u05e7", {"composite": True})],
        "03 \u05e0\u05e4\u05d7 \u05de\u05db\u05d5\u05d5\u05df": [("\u05de\u05db\u05d5\u05d5\u05df", {"dir_vol": True}), ("\u05e8\u05d2\u05d9\u05dc", {"dir_vol": False})],
        "04 \u05d7\u05e1\u05d9\u05de\u05ea \u05de\u05ea\u05d9\u05d7\u05ea \u05d9\u05ea\u05e8": [("\u05d7\u05d5\u05e1\u05dd", {"block_overext": True}), ("\u05dc\u05d0 \u05d7\u05d5\u05e1\u05dd", {"block_overext": False})],
        "05 \u05de\u05d3\u05d9\u05e0\u05d9\u05d5\u05ea \u05d3\u05d5\u05d7\u05d5\u05ea": [("\u05e8\u05d2\u05d9\u05dc", {"earn": "none"}), ("\u05d7\u05e1\u05d9\u05de\u05ea \u05db\u05e0\u05d9\u05e1\u05d4", {"earn": "entry_block"}), ("\u05de\u05e9\u05d5\u05dc\u05d1", {"earn": "combined"})],
        "06 \u05e1\u05d2\u05e0\u05d5\u05df \u05e1\u05d8\u05d5\u05e4": [("ATR", {"stop": "atr"}), ("Swing Low", {"stop": "structural"})],
        "07 \u05e1\u05d2\u05e0\u05d5\u05df \u05d9\u05e6\u05d9\u05d0\u05d4": [("TP \u05e7\u05d1\u05d5\u05e2", {"exit": "fixed"}), ("Trailing", {"exit": "trailing"}), ("\u05e7\u05d9\u05d3\u05d5\u05dd \u05de\u05d1\u05e0\u05d9", {"exit": "structural_trail"})],
        "08 \u05e9\u05e2\u05e8 \u05db\u05e0\u05d9\u05e1\u05d4": [("\u05e1\u05d2\u05d9\u05e8\u05d4", {"entry": "close"}), ("\u05d0\u05d9\u05e9\u05d5\u05e8", {"entry": "confirm"}), ("\u05e8\u05d9\u05d8\u05e8\u05d9\u05d9\u05e1\u05de\u05e0\u05d8", {"entry": "retrace"})],
        "09 \u05d9\u05e6\u05d9\u05d0\u05ea \u05d7\u05d9\u05e8\u05d5\u05dd \u05de\u05d0\u05e7\u05e8\u05d5": [("\u05db\u05d1\u05d5\u05d9", {"macro": "off"}), ("SMA200", {"macro": "sma200"}), ("\u05d9\u05e8\u05d9\u05d3\u05d4 \u05de\u05e9\u05d9\u05d0", {"macro": "drawdown"})],
        "10 \u05d9\u05e6\u05d9\u05d0\u05d4 \u05e2\u05dc \u05d4\u05d9\u05e4\u05d5\u05da": [("\u05db\u05d1\u05d5\u05d9", {}), ("SMA20", {"use_reversal": True, "rev": "sma20"}), ("MACD", {"use_reversal": True, "rev": "macd"}), ("\u05d0\u05d7\u05d3", {"use_reversal": True, "rev": "either"}), ("\u05e9\u05e0\u05d9\u05d4\u05dd", {"use_reversal": True, "rev": "both"})],
        "11 \u05de\u05e9\u05d8\u05e8 VIX": [("\u05d4\u05ea\u05e2\u05dc\u05dd", {"vix": "ignore"}), ("\u05d7\u05e1\u05d5\u05dd \u05d2\u05d1\u05d5\u05d4", {"vix": "block_high"}), ("\u05db\u05e0\u05d9\u05e1\u05d4 \u05d1\u05d2\u05d1\u05d5\u05d4", {"vix": "buy_dip"})],
        "12 \u05d0\u05d9\u05e9\u05d5\u05e8 \u05de\u05d2\u05de\u05d4 \u05e9\u05d1\u05d5\u05e2\u05d9": [("\u05db\u05d1\u05d5\u05d9", {"weekly": False}), ("\u05d3\u05dc\u05d5\u05e7", {"weekly": True})],
        "13 \u05d7\u05d5\u05e7 3 \u05d4\u05d9\u05de\u05d9\u05dd": [("\u05db\u05d1\u05d5\u05d9", {"three_day": False}), ("\u05d3\u05dc\u05d5\u05e7", {"three_day": True})],
        "14 \u05e4\u05d9\u05dc\u05d8\u05e8 \u05ea\u05e0\u05d5\u05e2\u05ea \u05d3\u05d5\u05d7\u05d5\u05ea": [("\u05db\u05d1\u05d5\u05d9", {"em_filter": False}), ("\u05d3\u05dc\u05d5\u05e7", {"em_filter": True})],
        "15 \u05d4\u05d2\u05d1\u05dc\u05ea \u05de\u05e1\u05d7\u05e8 \u05d9\u05ea\u05e8": [("\u05dc\u05dc\u05d0", {"max_wk": 0}), ("3 \u05d1\u05e9\u05d1\u05d5\u05e2", {"max_wk": 3}), ("5 \u05d1\u05e9\u05d1\u05d5\u05e2", {"max_wk": 5})],
        "16 \u05e1\u05e3 \u05e6\u05d9\u05d5\u05df": [("55", {"threshold": 55}), ("65", {"threshold": 65}), ("75", {"threshold": 75})],
        "17 \u05d9\u05de\u05d9 \u05d4\u05d7\u05d6\u05e7\u05d4 \u05de\u05e7\u05e1": [("20", {"max_days": 20}), ("30", {"max_days": 30}), ("60", {"max_days": 60})],
        "18 \u05e2\u05dc\u05d5\u05d9\u05d5\u05ea \u05de\u05e1\u05d7\u05e8": [("0%", {"cost": 0.0}), ("0.05%", {"cost": 0.05}), ("0.10%", {"cost": 0.10})],
        "21 \u05e0\u05d5\u05e8\u05de\u05dc\u05d9\u05d6\u05e6\u05d9\u05d9\u05ea \u05ea\u05e0\u05d5\u05d3\u05ea\u05d9\u05d5\u05ea": [("\u05db\u05d1\u05d5\u05d9", {}), ("\u05d3\u05dc\u05d5\u05e7", {"vol_norm": True})],
        "22 \u05db\u05d9\u05d5\u05dc \u05d2\u05d1\u05d5\u05dc\u05d5\u05ea": [
            ("\u05db\u05d1\u05d5\u05d9", {}),
            ("2.0/3.5/5.5", {"vol_norm": True}),
            ("2.5/4.0/6.0", {"vol_norm": True, "vb1": 2.5, "vb2": 4.0, "vb3": 6.0}),
            ("3.0/4.5/6.5", {"vol_norm": True, "vb1": 3.0, "vb2": 4.5, "vb3": 6.5}),
            ("1.5/3.0/5.0", {"vol_norm": True, "vb1": 1.5, "vb2": 3.0, "vb3": 5.0}),
        ],
        "19 \u05e9\u05d9\u05dc\u05d5\u05d1 \u05de\u05e6\u05d8\u05d1\u05e8": [
            ("0 \u05d1\u05e1\u05d9\u05e1", {}),
            ("1 +\u05e0\u05e4\u05d7 \u05e8\u05d2\u05d9\u05dc", {"dir_vol": False}),
            ("2 +\u05d1\u05dc\u05d9 \u05de\u05ea\u05d9\u05d7\u05d4", {"dir_vol": False, "block_overext": False}),
            ("3 +\u05e1\u05e3 55", {"dir_vol": False, "block_overext": False, "threshold": 55}),
            ("4 +20 \u05d9\u05de\u05d9\u05dd", {"dir_vol": False, "block_overext": False, "threshold": 55, "max_days": 20}),
            ("5 +\u05e9\u05d1\u05d5\u05e2\u05d9", {"dir_vol": False, "block_overext": False, "threshold": 55, "max_days": 20, "weekly": True}),
            ("6 +\u05d4\u05d9\u05e4\u05d5\u05da", {"dir_vol": False, "block_overext": False, "threshold": 55, "max_days": 20, "weekly": True, "use_reversal": True, "rev": "both"}),
            ("7 +\u05e7\u05d9\u05d3\u05d5\u05dd \u05de\u05d1\u05e0\u05d9", {"dir_vol": False, "block_overext": False, "threshold": 55, "max_days": 20, "weekly": True, "use_reversal": True, "rev": "both", "exit": "structural_trail"}),
        ],
        # EXIT-SUITE: הזנב הימני נחתך. איזה כלל אחראי?
        # MOM120: הכניסה הנוכחית נמדדה כמזיקה. זו החלופה.
        # SHOWDOWN: כל הטריגרים תחת אותה תצורה בדיוק —
        # רק "trigger" משתנה. עד כה כל אחד נמדד באופק אחר,
        # ולכן הדירוג ביניהם לא היה תקף.
        # TURNOVER-SUITE: 5,255 טריידים ⇒ רגישות קיצונית
        # לעלויות. האם אפשר לקצץ בלי לאבד את היתרון?
        # FACTORIAL: צירופים, לא גורם-גורם. כך נמדדות
        # גם אינטראקציות ולא רק השפעות ראשיות.
        # POST-EARN-DIP: הטענה של המקור, בבדיקה ישירה.
        # ATR-COST: האם היתרון שורד תמחור ריאלי?
        "58 עלות ריאלית לפי תנודתיות": [
            ("קבוע 0.05% (הבסיס)", {}),
            ("קבוע 0.10%", {"cost": 0.10}),
            ("0.03% + 0.01×ATR", {"cost": 0.03, "atr_cost": 0.01}),
            ("0.03% + 0.02×ATR", {"cost": 0.03, "atr_cost": 0.02}),
            ("0.05% + 0.02×ATR", {"cost": 0.05, "atr_cost": 0.02}),
        ],
        "57 ירידה אחרי דוח": [
            ("3 אדומים (בסיס)", {}),
            ("רק ירידת דוח", {"trigger": "post_earn_dip"}),
            ("3 אדומים או ירידת דוח", {"trigger": "red_or_pe"}),
        ],
        "56 תקרת ריכוזיות סקטוריאלית": [
            ("ללא תקרה", {"sec_cap": 0}),
            ("עד 3 בסקטור", {"sec_cap": 3}),
            ("עד 5 בסקטור", {"sec_cap": 5}),
            ("עד 8 בסקטור", {"sec_cap": 8}),
        ],
        "55 שילוב משולב": [
            ("בסיס", {}),
            ("T · trailing", {"exit": "trailing"}),
            ("P · מימוש 2R", {"part_r": 2.0}),
            ("T+P", {"exit": "trailing", "part_r": 2.0}),
            ("T+P · מימוש 1R", {"exit": "trailing", "part_r": 1.0}),
            ("T+P+סולם", {"exit": "trailing", "part_r": 2.0,
                          "ladder": "steady"}),
        ],
        "53 צמצום תחלופה": [
            ("בסיס · 3 אדומים", {}),
            ("+ שיפוע SMA150 עולה", {"rising_sma": True}),
            ("+ רצף 4 ימים", {"red_days": 4}),
            ("שניהם יחד", {"rising_sma": True, "red_days": 4}),
        ],
        # ⭐ משפחת הניהול — כאן הוכח שיש השפעה גדולה,
        # וכל הפרמטרים קיימים ומעולם לא נבדקו.
        "54 ניהול פוזיציה": [
            ("בסיס", {}),
            ("מימוש חלקי ב-1R", {"part_r": 1.0}),
            ("מימוש 1R + סטופ לכניסה", {"part_r": 1.0, "part_be": True}),
            ("מימוש חלקי ב-2R", {"part_r": 2.0}),
            ("סטופ מדורג · steady", {"ladder": "steady"}),
            ("סטופ מדורג · tight", {"ladder": "tight"}),
            ("חיזוק פוזיציה · split", {"scale": "split"}),
            ("חיזוק פוזיציה · add", {"scale": "add"}),
        ],
        "52 כיול אורך הרצף האדום": [
            ("2 ימים", {"red_days": 2}),
            ("3 ימים (הנוכחי)", {"red_days": 3}),
            ("4 ימים", {"red_days": 4}),
            ("5 ימים", {"red_days": 5}),
        ],
        "51 כל הטריגרים · תצורה זהה": [
            ("ציון (הנוכחי)", {}),
            ("3 ימים אדומים", {"trigger": "three_red"}),
            ("פריצה 20", {"trigger": "breakout"}),
            ("מומנטום 120", {"trigger": "mom120"}),
            ("ציון או 3 אדומים", {"trigger": "either"}),
        ],
        "50 כניסה: ציון מול מומנטום": [
            ("ציון (הנוכחי)", {}),
            ("מומנטום 120", {"trigger": "mom120"}),
            ("מומנטום 120 · בלי חסימת מתיחה",
             {"trigger": "mom120", "block_overext": False}),
            ("ציון · בלי חסימת מתיחה", {"block_overext": False}),
        ],
        "49 כיול רוחב טריילינג": [
            ("TP קבוע (בסיס)", {"exit": "fixed"}),
            ("trailing 1.5", {"exit": "trailing", "trail": 1.5}),
            ("trailing 2.0", {"exit": "trailing", "trail": 2.0}),
            ("trailing 3.0", {"exit": "trailing", "trail": 3.0}),
            ("trailing 4.0", {"exit": "trailing", "trail": 4.0}),
        ],
        "48 ניהול יציאה": [
            ("בסיס נוכחי", {}),
            ("trailing במקום TP", {"exit": "trailing"}),
            ("אופק 90 יום", {"max_days": 90}),
            ("בלי יציאת דוחות", {"earn": "entry_block"}),
            ("שלושתם יחד", {"exit": "trailing", "max_days": 90,
                            "earn": "entry_block"}),
        ],
        "47 מדיניות המתנה": [
            ("כבוי", {"cooldown": False}),
            ("נוכחי", {"cool_mode": "current"}),
            ("רק אחרי סטופ", {"cool_mode": "sl_only"}),
            ("קצר · 3 ימים", {"cool_mode": "short"}),
        ],
        "46 חשיפה לפי VIX": [
            ("קבוע", {"vix_size": "off"}),
            ("מדורג לפי VIX", {"vix_size": "tiered"}),
        ],
        "45 תקרת פוזיציות": [
            ("ללא הגבלה", {"max_pos": 0}),
            ("עד 10", {"max_pos": 10}),
            ("עד 15", {"max_pos": 15}),
            ("עד 20", {"max_pos": 20}),
            ("עד 30", {"max_pos": 30}),
        ],
        "44 זיכרון (cooldown)": [
            ("ללא זיכרון (הישן)", {"cooldown": False}),
            ("עם זיכרון לפי סיבה", {"cooldown": True}),
        ],
        "43 היקף נרמול התנודתיות": [
            ("כבוי לגמרי", {"vn_scope": "off"}),
            ("סף בלבד", {"vn_scope": "thr"}),
            ("מלא (הישן)", {"vn_scope": "full"}),
        ],
        "42 אופק לפי דוח": [
            ("30 יום (הבסיס)", {"max_days": 30}),
            ("עד הדוח הבא", {"max_days": 0}),
            ("45 יום", {"max_days": 45}),
            ("60 יום", {"max_days": 60}),
        ],
        "40 אופק ללא vol_norm": [
            ("30 יום", {"vol_norm": False, "max_days": 30}),
            ("45 יום", {"vol_norm": False, "max_days": 45}),
            ("60 יום", {"vol_norm": False, "max_days": 60}),
            ("90 יום", {"vol_norm": False, "max_days": 90}),
            ("120 יום", {"vol_norm": False, "max_days": 120}),
            ("150 יום", {"vol_norm": False, "max_days": 150}),
            ("200 יום", {"vol_norm": False, "max_days": 200}),
        ],
        "41 השפעת הדריסה עצמה": [
            ("vol_norm דלוק, 30 יום", {"vol_norm": True, "max_days": 30}),
            ("vol_norm דלוק, 120 יום", {"vol_norm": True, "max_days": 120}),
            ("vol_norm כבוי, 30 יום", {"vol_norm": False, "max_days": 30}),
            ("vol_norm כבוי, 120 יום", {"vol_norm": False, "max_days": 120}),
        ],
        "38 רגישות אופק ההחזקה": [
            ("30 יום (הקיים)", {"max_days": 30}),
            ("45 יום", {"max_days": 45}),
            ("60 יום", {"max_days": 60}),
            ("90 יום", {"max_days": 90}),
            ("120 יום", {"max_days": 120}),
            ("150 יום", {"max_days": 150}),
            ("200 יום", {"max_days": 200}),
        ],
        "39 אופק + ללא סטופ מבני": [
            ("30 יום + Swing Low", {"max_days": 30}),
            ("90 יום + Swing Low", {"max_days": 90}),
            ("90 יום + ATR", {"max_days": 90, "stop": "atr"}),
            ("150 יום + ATR", {"max_days": 150, "stop": "atr"}),
            ("200 יום + ATR", {"max_days": 200, "stop": "atr"}),
        ],
        "37 ניהול מדדים": [
            ("תצורה חיה", {}),
            ("ללא סטופ מבני (זמן בלבד)", {"stop": "atr", "max_days": 60}),
            ("חיזוק 75/25 בירידה 8%", {"scale": "split", "scale_first": 0.75, "scale_drop": 8.0}),
            ("סטופ מדורג מאוחר", {"ladder": "late"}),
            ("החזקה ארוכה (90 יום)", {"max_days": 90}),
        ],
        "36 חיזוק 75/25": [
            ("מלא (בסיס)", {"max_days": 120}),
            ("75/25 בירידה 5%", {"max_days": 120, "scale": "split", "scale_first": 0.75, "scale_drop": 5.0}),
            ("75/25 בירידה 7%", {"max_days": 120, "scale": "split", "scale_first": 0.75, "scale_drop": 7.0}),
            ("75/25 בירידה 8%", {"max_days": 120, "scale": "split", "scale_first": 0.75, "scale_drop": 8.0}),
            ("75/25 בירידה 10%", {"max_days": 120, "scale": "split", "scale_first": 0.75, "scale_drop": 10.0}),
            ("75/25 בירידה 12%", {"max_days": 120, "scale": "split", "scale_first": 0.75, "scale_drop": 12.0}),
        ],
        "35 סטופ מדורג - מדרגות מאוחרות": [
            ("Swing Low (הקיים)", {"max_days": 120}),
            ("ראשונה ב-8%", {"max_days": 120, "ladder": "mid"}),
            ("ראשונה ב-10%", {"max_days": 120, "ladder": "late"}),
            ("ראשונה ב-15%", {"max_days": 120, "ladder": "verylate"}),
        ],
        "34 סטופ מדורג": [
            ("Swing Low (הקיים)", {"max_days": 120}),
            ("מדורג שמרני", {"max_days": 120, "ladder": "steady"}),
            ("מדורג מצטמצם", {"max_days": 120, "ladder": "tight"}),
        ],
        "32 רגישות סף החיזוק (split)": [
            ("מלא (בסיס)", {}),
            ("6%", {"scale": "split", "scale_drop": 6.0}),
            ("7%", {"scale": "split", "scale_drop": 7.0}),
            ("8%", {"scale": "split", "scale_drop": 8.0}),
            ("9%", {"scale": "split", "scale_drop": 9.0}),
            ("10%", {"scale": "split", "scale_drop": 10.0}),
            ("12%", {"scale": "split", "scale_drop": 12.0}),
            ("15%", {"scale": "split", "scale_drop": 15.0}),
        ],
        "33 רגישות סף החיזוק (add)": [
            ("מלא (בסיס)", {}),
            ("3%", {"scale": "add", "scale_drop": 3.0}),
            ("5%", {"scale": "add", "scale_drop": 5.0}),
            ("7%", {"scale": "add", "scale_drop": 7.0}),
            ("8%", {"scale": "add", "scale_drop": 8.0}),
            ("10%", {"scale": "add", "scale_drop": 10.0}),
            ("12%", {"scale": "add", "scale_drop": 12.0}),
        ],
        "31 חיזוק פוזיציה": [
            ("מלא בכניסה (הקיים)", {"max_days": 120}),
            ("חצי+חצי בירידה 3%", {"max_days": 120, "scale": "split", "scale_drop": 3.0}),
            ("חצי+חצי בירידה 5%", {"max_days": 120, "scale": "split", "scale_drop": 5.0}),
            ("חצי+חצי בירידה 8%", {"max_days": 120, "scale": "split", "scale_drop": 8.0}),
            ("מלא+חצי בירידה 5% (סיכון גדל)", {"max_days": 120, "scale": "add", "scale_drop": 5.0}),
        ],
        "30 התכנסות - ירידה מהשיא": [
            ("ציון (הקיים)", {"max_days": 120}),
            ("ירידה 5% מהשיא", {"max_days": 120, "trigger": "dip", "dip_pct": 5.0}),
            ("ירידה 10% מהשיא", {"max_days": 120, "trigger": "dip", "dip_pct": 10.0}),
            ("ירידה 15% מהשיא", {"max_days": 120, "trigger": "dip", "dip_pct": 15.0}),
        ],
        "29 מצב שוק (VIX)": [
            ("ללא VIX (הקיים)", {"max_days": 120}),
            ("חסום מעל 25", {"max_days": 120, "vix": "block_high", "vix_th": 25.0}),
            ("חסום מעל 28", {"max_days": 120, "vix": "block_high", "vix_th": 28.0}),
            ("חסום מעל 32", {"max_days": 120, "vix": "block_high", "vix_th": 32.0}),
        ],
        "28 יציאה על שבירת SMA150": [
            ("ללא יציאת היפוך (הקיים)", {}),
            ("שבירת SMA150", {"use_reversal": True, "rev": "sma150"}),
            ("שבירת SMA20 (להשוואה)", {"use_reversal": True, "rev": "sma20"}),
        ],
        "27 מימוש חלקי 50%": [
            ("הכל-או-כלום (הקיים)", {"max_days": 120}),
            ("חצי ב-1R", {"max_days": 120, "part_r": 1.0}),
            ("חצי ב-1R + סטופ לכניסה", {"max_days": 120, "part_r": 1.0, "part_be": True}),
            ("חצי ב-1.5R", {"max_days": 120, "part_r": 1.5}),
        ],
        "26 פריצת התנגדות": [
            ("ציון (הקיים)", {"max_days": 120}),
            ("פריצה 20 בלבד", {"max_days": 120, "trigger": "breakout"}),
            ("פריצה 50 בלבד", {"max_days": 120, "trigger": "breakout", "brk_lb": 50}),
            ("ציון או פריצה", {"max_days": 120, "trigger": "score_or_breakout"}),
        ],
        "25 מדיניות דוחות (שער מלא)": [
            ("ללא מדיניות", {"max_days": 120, "earn": "none"}),
            ("מניעת כניסה בלבד", {"max_days": 120, "earn": "entry_block"}),
            ("משולב (הקיים)", {"max_days": 120}),
        ],
        "24 טריגר כניסה": [
            ("ציון (הקיים)", {"max_days": 120}),
            ("3 ימים אדומים בלבד", {"max_days": 120, "trigger": "three_red"}),
            ("ציון או 3 אדומים", {"max_days": 120, "trigger": "either"}),
        ],
        "23 שיפוע SMA150": [
            ("כבוי", {"max_days": 120}),
            ("דורש שטוח או עולה", {"max_days": 120, "rising_sma": True}),
        ],
        "20 \u05ea\u05e6\u05d5\u05e8\u05d5\u05ea \u05de\u05d5\u05e2\u05de\u05d3\u05d5\u05ea": [
            ("\u05d1\u05e1\u05d9\u05e1", {}),
            ("\u05ea\u05e9\u05d5\u05d0\u05d4", {"dir_vol": False, "block_overext": False, "threshold": 55, "max_days": 20, "exit": "structural_trail"}),
            ("\u05de\u05d0\u05d5\u05d6\u05df", {"dir_vol": False, "block_overext": False, "threshold": 55, "max_days": 20, "weekly": True, "use_reversal": True, "rev": "both"}),
            ("\u05e9\u05de\u05e8\u05e0\u05d9", {"threshold": 75, "earn": "entry_block", "weekly": True, "use_reversal": True, "rev": "both", "exit": "structural_trail"}),
        ],
    }
    st.markdown("### \U0001F9ED \u05e1\u05d3\u05e8\u05ea \u05d1\u05d3\u05d9\u05e7\u05d5\u05ea")
    _suite_label = st.selectbox("\u05d1\u05d7\u05e8 \u05d1\u05d3\u05d9\u05e7\u05d4:", list(TEST_SUITE.keys()), index=0,
        help="\u05db\u05dc \u05d1\u05d3\u05d9\u05e7\u05d4 \u05de\u05e8\u05d9\u05e6\u05d4 \u05d0\u05ea \u05db\u05dc \u05d4\u05e6\u05d9\u05e8\u05d5\u05e4\u05d9\u05dd \u05e9\u05dc\u05d4 \u05dc\u05d1\u05d3, \u05e2\u05dc \u05d1\u05e1\u05d9\u05e1 \u05d0\u05d7\u05d9\u05d3. \u05d4\u05de\u05ea\u05d2\u05d9\u05dd \u05dc\u05de\u05d8\u05d4 \u05de\u05ea\u05e2\u05dc\u05de\u05d9\u05dd \u05db\u05e9\u05d1\u05d3\u05d9\u05e7\u05d4 \u05e0\u05d1\u05d7\u05e8\u05ea.")
    _suite_specs = TEST_SUITE[_suite_label]
    if _suite_specs is not None:
        st.success(f"\u05d1\u05d3\u05d9\u05e7\u05d4 \u05e4\u05e2\u05d9\u05dc\u05d4: **{_suite_label}** \u2014 {len(_suite_specs)} \u05e8\u05d9\u05e6\u05d5\u05ea. \u05db\u05dc \u05d4\u05de\u05ea\u05d2\u05d9\u05dd \u05dc\u05de\u05d8\u05d4 \u05de\u05d5\u05d2\u05d3\u05e8\u05d9\u05dd \u05d0\u05d5\u05d8\u05d5\u05de\u05d8\u05d9\u05ea.")
        st.caption("\u05e7\u05d5 \u05d1\u05e1\u05d9\u05e1 \u05dc\u05d4\u05e9\u05d5\u05d5\u05d0\u05d4: Sharpe 2.23 \u00b7 Calmar 2.59 \u00b7 211 \u05d8\u05e8\u05d9\u05d9\u05d3\u05d9\u05dd (\u05ea\u05d9\u05e7 \u05d1\u05d3\u05d9\u05e7\u05d5\u05ea, 3y, \u05e2\u05dc\u05d5\u05d9\u05d5\u05ea 0.05%)")
    st.markdown("---")

    st.markdown("**💰 עלויות מסחר:**")
    col_c1, col_c2 = st.columns(2)
    apply_costs = col_c1.checkbox("הפעל עלויות מסחר", value=True,
        help="מנכה עמלה + ספרד מכל טרייד. כבוי = תוצאות 'נקיות' (אופטימיות מדי). דלוק = קרוב יותר למציאות.")
    cost_pct_per_side = col_c2.number_input("עלות לכל כיוון (%):", min_value=0.0, max_value=1.0,
        value=0.05, step=0.01, format="%.3f", disabled=not apply_costs,
        help="עמלה + מחצית הספרד. ברוקר זול על מניות אמריקאיות: ~0.02-0.05%. מניות קטנות/לא נזילות: 0.1-0.3%. המספר מוכפל ב-2 (כניסה + יציאה).")
    effective_cost = cost_pct_per_side if apply_costs else 0.0
    if apply_costs:
        st.caption(f"כל טרייד יספוג {effective_cost*2:.3f}% עלות סבב מלא. עם ~400 טריידים זה מצטבר משמעותית.")

    st.markdown("**📏 פילטר תנועת דוחות (תחליף בר-בדיקה ל-Expected Move):**")
    use_em_filter = st.checkbox("חסום כניסה למניות שזזות חזק בדוחות", value=False,
        help="מחשב מהדוחות ההיסטוריים של כל מניה את התנועה הממוצעת שלה ביום שאחרי דוח, וחוסם כניסה אם היא גדולה מדי ביחס לסטופ. משתמש רק בדוחות שקדמו לתאריך הטרייד - בלי הצצה לעתיד.")
    em_mult, em_min_samples = 1.5, 2
    if use_em_filter:
        col_m1, col_m2 = st.columns(2)
        em_mult = col_m1.number_input("חסום אם תנועת הדוח > X× רוחב הסטופ:", min_value=0.5, max_value=4.0,
            value=1.5, step=0.25,
            help="1.5 = חוסם מניה שזזה בדוחות פי 1.5 מהסטופ. נמוך יותר = מחמיר יותר (פחות טריידים).")
        em_min_samples = col_m2.number_input("מינימום דוחות היסטוריים נדרשים:", min_value=1, max_value=8, value=2, step=1,
            help="אם למניה יש פחות דוחות מזה בהיסטוריה שלפני הטרייד, הפילטר לא מופעל עליה (אין מספיק מידע).")
        st.markdown("<div class='unknown-box'>ℹ️ הפילטר לא מחליף את מדיניות הדוחות - הוא פועל <b>בנוסף</b> לה. מדיניות הדוחות מטפלת בתזמון (מתי לצאת); הפילטר מטפל בבחירה (על אילו מניות בכלל לסחור).</div>", unsafe_allow_html=True)

    st.markdown("**🌪️ משטר VIX (בדיקת הסתירה):**")
    st.markdown("""
    <div class='unknown-box'>
    ⚔️ <b>סתירה שצריך להכריע:</b> הסורק שלנו חוסם כניסות כש-VIX &gt; 28 (תנודתיות = סכנה).
    "כללי קניית הדיפ" טוענים בדיוק ההפך: VIX &gt; 30 הוא <b>איתות כניסה</b> (פאניקה = הזדמנות).
    שניהם לא יכולים להיות נכונים. הרץ את שלושת המצבים ותן לנתונים להכריע.
    </div>
    """, unsafe_allow_html=True)
    VIX_MODE_MAP = {
        "🚫 התעלם מ-VIX (ברירת מחדל בבקטסט עד היום)": "ignore",
        "🛑 חסום כניסה כש-VIX גבוה (התנהגות הסורק)": "block_high",
        "🎯 היכנס רק כש-VIX גבוה (טענת 'קניית הדיפ')": "buy_dip",
        "🔬 השווה את כל השלושה": "compare",
    }
    vix_label = st.radio("מצב VIX:", list(VIX_MODE_MAP.keys()), index=0, horizontal=False)
    vix_mode_sel = VIX_MODE_MAP[vix_label]
    vix_threshold = 28.0
    if vix_mode_sel != "ignore":
        vix_threshold = st.number_input("סף VIX:", min_value=12.0, max_value=45.0, value=28.0, step=1.0,
            help="הסורק משתמש ב-28. 'כללי הדיפ' מדברים על 30. שים לב: ב'היכנס רק כש-VIX גבוה' סף גבוה יקטין דרמטית את מספר הטריידים.")
        if vix_mode_sel == "buy_dip":
            st.markdown("<div class='unknown-box'>⚠️ במצב הזה נכנסים <b>רק</b> בתקופות תנודתיות גבוהה - צפה למספר טריידים קטן מאוד, שעלול להיות לא מובהק סטטיסטית. בדוק את מספר הטריידים לפני שאתה מסיק מסקנה.</div>", unsafe_allow_html=True)
    if vix_mode_sel == "compare":
        vix_modes_to_run = [("ignore", "🚫 בלי VIX"), ("block_high", "🛑 חסימה ב-VIX גבוה"), ("buy_dip", "🎯 כניסה ב-VIX גבוה")]
    else:
        vix_modes_to_run = [(vix_mode_sel, "")]

    st.markdown("**📅 אישור מגמה שבועי + 🔪 חוק שלושת הימים + 🚦 מסחר יתר:**")
    col_n1, col_n2 = st.columns(2)
    use_weekly_trend = col_n1.checkbox("אישור מגמה שבועי", value=False,
        help="דורש שהסגירה השבועית האחרונה תהיה מעל ממוצע נע שבועי. משתמש רק בשבועות שהסתיימו - בלי הצצה לעתיד.")
    weekly_sma_weeks = col_n2.number_input("ממוצע שבועי (שבועות):", min_value=10, max_value=60, value=30, step=5,
        disabled=not use_weekly_trend, help="30 שבועות ≈ 150 ימי מסחר - מקביל ל-SMA150 היומי שאנחנו כבר משתמשים בו.")

    col_t1, col_t2, col_t3 = st.columns(3)
    use_three_day = col_t1.checkbox("🔪 חוק 3 הימים", value=False,
        help="אחרי ירידה חדה בעקבות דוח, לא נכנסים למשך N ימי מסחר.")
    three_day_drop = col_t2.number_input("ירידה שמפעילה (%):", min_value=2.0, max_value=20.0, value=5.0, step=1.0,
        disabled=not use_three_day, help="רק ירידות חוסמות. קפיצה חיובית אחרי דוח אינה 'סכין נופלת'.")
    three_day_wait = col_t3.number_input("ימי המתנה:", min_value=1, max_value=10, value=3, step=1,
        disabled=not use_three_day)

    max_trades_per_week = st.number_input("🚦 מקסימום כניסות חדשות בשבוע (0 = ללא הגבלה):",
        min_value=0, max_value=30, value=0, step=1,
        help="מופעל ברמת התיק אחרי איחוד כל המניות. שומר את בעלות הציון הגבוה. זמין במצב 'קטגוריה שלמה' ו'מספר קטגוריות' בלבד.")


    st.markdown("**\U0001F504 \u05d9\u05e6\u05d9\u05d0\u05d4 \u05e2\u05dc \u05d4\u05d9\u05e4\u05d5\u05da \u05de\u05d2\u05de\u05d4:**")
    st.markdown("""
    <div class='unknown-box'>
    \U0001F4CC <b>\u05dc\u05de\u05d4 \u05d6\u05d4 \u05d7\u05e9\u05d5\u05d1:</b> \u05d1\u05ea\u05e6\u05d5\u05e8\u05d4 \u05d4\u05e0\u05d5\u05db\u05d7\u05d9\u05ea, 41-63% \u05de\u05d4\u05d9\u05e6\u05d9\u05d0\u05d5\u05ea \u05d4\u05df "\u05d6\u05de\u05df"
    (\u05d7\u05dc\u05e4\u05d5 30 \u05d9\u05d5\u05dd) \u05d5\u05e8\u05e7 8-12% \u05d4\u05df TP. \u05db\u05dc\u05d5\u05de\u05e8 \u05e8\u05d5\u05d1 \u05d4\u05e4\u05d5\u05d6\u05d9\u05e6\u05d9\u05d5\u05ea \u05e0\u05e1\u05d2\u05e8\u05d5\u05ea
    \u05e2\u05dc \u05e9\u05e2\u05d5\u05df \u05e2\u05e6\u05e8 - \u05dc\u05dc\u05d0 \u05e9\u05d5\u05dd \u05e7\u05e9\u05e8 \u05dc\u05de\u05d4 \u05e9\u05e7\u05d5\u05e8\u05d4 \u05d1\u05e9\u05d5\u05e7. \u05d4\u05de\u05ea\u05d2 \u05d4\u05d6\u05d4 \u05de\u05d7\u05dc\u05d9\u05e3
    \u05d9\u05e6\u05d9\u05d0\u05d4 \u05e2\u05d9\u05d5\u05d5\u05e8\u05ea \u05d1\u05d9\u05e6\u05d9\u05d0\u05d4 \u05de\u05e0\u05d5\u05de\u05e7\u05ea.
    </div>
    """, unsafe_allow_html=True)
    use_reversal_exit = st.checkbox("\u05e6\u05d0 \u05db\u05e9\u05de\u05d6\u05d5\u05d4\u05d4 \u05d4\u05d9\u05e4\u05d5\u05da \u05de\u05d2\u05de\u05d4", value=False,
        help="\u05de\u05d7\u05dc\u05d9\u05e3 \u05d9\u05e6\u05d9\u05d0\u05d5\u05ea '\u05d6\u05de\u05df' \u05d1\u05d9\u05e6\u05d9\u05d0\u05d4 \u05e2\u05dc \u05d0\u05d9\u05ea\u05d5\u05ea \u05d8\u05db\u05e0\u05d9 \u05d0\u05de\u05d9\u05ea\u05d9.")
    REV_MODE_MAP = {
        "\U0001F4C9 \u05e9\u05d1\u05d9\u05e8\u05ea SMA20 (\u05de\u05d4\u05d9\u05e8)": "sma20",
        "\u3030\uFE0F \u05d4\u05d9\u05e4\u05d5\u05da MACD (\u05d0\u05d9\u05d8\u05d9)": "macd",
        "\u26A1 \u05d0\u05d7\u05d3 \u05de\u05d4\u05e9\u05e0\u05d9\u05d9\u05dd (\u05e8\u05d2\u05d9\u05e9 \u05de\u05d0\u05d5\u05d3)": "either",
        "\U0001F512 \u05e9\u05e0\u05d9\u05d4\u05dd \u05d9\u05d7\u05d3 (\u05e9\u05de\u05e8\u05e0\u05d9)": "both",
        "\U0001F52C \u05d4\u05e9\u05d5\u05d5\u05d4 \u05d0\u05ea \u05db\u05d5\u05dc\u05dd": "compare",
    }
    reversal_mode = "sma20"; reversal_min_days = 3
    if use_reversal_exit:
        col_r1, col_r2 = st.columns(2)
        rev_label = col_r1.selectbox("\u05d0\u05d9\u05ea\u05d5\u05ea \u05d4\u05d9\u05e4\u05d5\u05da:", list(REV_MODE_MAP.keys()), index=0)
        reversal_mode = REV_MODE_MAP[rev_label]
        reversal_min_days = col_r2.number_input("\u05de\u05d9\u05e0\u05d9\u05de\u05d5\u05dd \u05d9\u05de\u05d9 \u05d4\u05d7\u05d6\u05e7\u05d4 \u05dc\u05e4\u05e0\u05d9 \u05d1\u05d3\u05d9\u05e7\u05d4:",
            min_value=0, max_value=15, value=3, step=1,
            help="\u05de\u05d5\u05e0\u05e2 \u05d9\u05e6\u05d9\u05d0\u05d4 \u05de\u05d9\u05d9\u05d3\u05d9\u05ea \u05e2\u05dc \u05e8\u05e2\u05e9 \u05d1\u05d9\u05de\u05d9\u05dd \u05d4\u05e8\u05d0\u05e9\u05d5\u05e0\u05d9\u05dd.")
    if reversal_mode == "compare":
        rev_modes_to_run = [("sma20", "\U0001F4C9 SMA20"), ("macd", "\u3030\uFE0F MACD"),
                            ("either", "\u26A1 \u05d0\u05d7\u05d3"), ("both", "\U0001F512 \u05e9\u05e0\u05d9\u05d4\u05dd")]
    else:
        rev_modes_to_run = [(reversal_mode, "")]


    st.markdown("**\U0001F6AA \u05e9\u05e2\u05e8 \u05db\u05e0\u05d9\u05e1\u05d4:**")

    st.markdown("**\U0001F4CF \u05e0\u05d5\u05e8\u05de\u05dc\u05d9\u05d6\u05e6\u05d9\u05d9\u05ea \u05ea\u05e0\u05d5\u05d3\u05ea\u05d9\u05d5\u05ea:**")
    st.markdown("""
    <div class='unknown-box'>
    \U0001F4CA 11 \u05e7\u05d8\u05d2\u05d5\u05e8\u05d9\u05d5\u05ea \u05d4\u05e8\u05d0\u05d5 \u05e9\u05d0\u05d5\u05ea\u05d4 \u05ea\u05e6\u05d5\u05e8\u05d4 \u05e0\u05d5\u05ea\u05e0\u05ea Sharpe 2.4 \u05d1\u05d0\u05d7\u05ea \u05d5-0.2 \u05d1\u05d0\u05d7\u05e8\u05ea.
    \u05d4\u05de\u05e9\u05ea\u05e0\u05d4 \u05d4\u05de\u05e1\u05d1\u05d9\u05e8 \u05d4\u05d5\u05d0 <b>\u05ea\u05e0\u05d5\u05d3\u05ea\u05d9\u05d5\u05ea</b>. \u05db\u05d0\u05df \u05d4\u05e4\u05e8\u05de\u05d8\u05e8\u05d9\u05dd \u05e0\u05d2\u05d6\u05e8\u05d9\u05dd \u05de-ATR%
    \u05e9\u05dc \u05db\u05dc \u05de\u05e0\u05d9\u05d4 \u05d1\u05e0\u05e4\u05e8\u05d3 - <b>\u05e0\u05d5\u05e1\u05d7\u05d4 \u05d0\u05d7\u05ea</b>, \u05dc\u05d0 \u05db\u05d9\u05d5\u05dc \u05e4\u05e8-\u05e7\u05d8\u05d2\u05d5\u05e8\u05d9\u05d4.<br>
    &lt;2%: \u05e1\u05e3 65 \u00b7 30 \u05d9\u05de\u05d9\u05dd \u00b7 TP \u05e7\u05d1\u05d5\u05e2<br>
    2-3.5%: \u05e1\u05e3 55 \u00b7 20 \u05d9\u05de\u05d9\u05dd \u00b7 \u05e7\u05d9\u05d3\u05d5\u05dd \u05de\u05d1\u05e0\u05d9<br>
    3.5-5.5%: \u05e1\u05e3 65 \u00b7 20 \u05d9\u05de\u05d9\u05dd \u00b7 \u05d4\u05d9\u05e4\u05d5\u05da<br>
    &gt;5.5%: \u05e1\u05e3 75 \u00b7 30 \u05d9\u05de\u05d9\u05dd \u00b7 \u05d4\u05d9\u05e4\u05d5\u05da
    </div>
    """, unsafe_allow_html=True)
    use_vol_norm = st.checkbox("\u05d4\u05e4\u05e2\u05dc \u05e0\u05d5\u05e8\u05de\u05dc\u05d9\u05d6\u05e6\u05d9\u05d9\u05ea \u05ea\u05e0\u05d5\u05d3\u05ea\u05d9\u05d5\u05ea", value=True,
        help="\u05de\u05ea\u05e2\u05dc\u05dd \u05de\u05e1\u05e3 \u05d4\u05e6\u05d9\u05d5\u05df, \u05d9\u05de\u05d9 \u05d4\u05d4\u05d7\u05d6\u05e7\u05d4 \u05d5\u05e1\u05d2\u05e0\u05d5\u05df \u05d4\u05d9\u05e6\u05d9\u05d0\u05d4 - \u05d4\u05db\u05dc \u05e0\u05d2\u05d6\u05e8 \u05de-ATR%.")
    vb1, vb2, vb3 = 2.0, 3.5, 5.5
    if use_vol_norm:
        col_v1, col_v2, col_v3 = st.columns(3)
        vb1 = col_v1.number_input("\u05d2\u05d1\u05d5\u05dc 1 (%)", min_value=0.5, max_value=5.0, value=3.0, step=0.5)
        vb2 = col_v2.number_input("\u05d2\u05d1\u05d5\u05dc 2 (%)", min_value=1.0, max_value=8.0, value=4.5, step=0.5)
        vb3 = col_v3.number_input("\u05d2\u05d1\u05d5\u05dc 3 (%)", min_value=2.0, max_value=12.0, value=6.5, step=0.5)

    ENTRY_MODE_MAP = {
        "\U0001F4CD \u05e1\u05d2\u05d9\u05e8\u05d4 (\u05d1\u05e8\u05d9\u05e8\u05ea \u05de\u05d7\u05d3\u05dc)": "close",
        "\u2705 \u05d0\u05d9\u05e9\u05d5\u05e8 - \u05e8\u05e7 \u05de\u05e2\u05dc \u05e9\u05d9\u05d0 \u05d9\u05d5\u05dd \u05d4\u05d0\u05d9\u05ea\u05d5\u05ea": "confirm",
        "\u21A9\uFE0F \u05e8\u05d9\u05d8\u05e8\u05d9\u05d9\u05e1\u05de\u05e0\u05d8 - \u05e8\u05e7 \u05d1\u05d7\u05d6\u05e8\u05d4 \u05dc-SMA20": "retrace",
        "\U0001F52C \u05d4\u05e9\u05d5\u05d5\u05d4 \u05d0\u05ea \u05db\u05d5\u05dc\u05dd": "compare",
    }
    entry_label = st.selectbox("\u05d0\u05d9\u05da \u05e0\u05db\u05e0\u05e1\u05d9\u05dd:", list(ENTRY_MODE_MAP.keys()), index=0,
        help="\u05d4\u05d9\u05d5\u05dd \u05e0\u05db\u05e0\u05e1\u05d9\u05dd \u05d1\u05db\u05dc \u05de\u05d7\u05d9\u05e8. '\u05d0\u05d9\u05e9\u05d5\u05e8' \u05d3\u05d5\u05e8\u05e9 \u05e9\u05d4\u05de\u05d7\u05d9\u05e8 \u05d9\u05de\u05e9\u05d9\u05da \u05dc\u05e2\u05dc\u05d5\u05ea; '\u05e8\u05d9\u05d8\u05e8\u05d9\u05d9\u05e1\u05de\u05e0\u05d8' \u05de\u05d7\u05db\u05d4 \u05dc\u05de\u05d7\u05d9\u05e8 \u05d8\u05d5\u05d1 \u05d9\u05d5\u05ea\u05e8.")
    entry_mode = ENTRY_MODE_MAP[entry_label]
    if entry_mode == "compare":
        entry_modes_to_run = [("close", "\U0001F4CD \u05e1\u05d2\u05d9\u05e8\u05d4"), ("confirm", "\u2705 \u05d0\u05d9\u05e9\u05d5\u05e8"), ("retrace", "\u21A9\uFE0F \u05e8\u05d9\u05d8\u05e8\u05d9\u05d9\u05e1\u05de\u05e0\u05d8")]
    else:
        entry_modes_to_run = [(entry_mode, "")]

    st.markdown("**\U0001F6A8 \u05d9\u05e6\u05d9\u05d0\u05ea \u05d7\u05d9\u05e8\u05d5\u05dd \u05de\u05d0\u05e7\u05e8\u05d5:**")
    st.markdown("""
    <div class='unknown-box'>
    \U0001F30A \u05e1\u05d5\u05d2\u05e8 \u05d0\u05ea <b>\u05db\u05dc</b> \u05d4\u05e4\u05d5\u05d6\u05d9\u05e6\u05d9\u05d5\u05ea \u05db\u05e9\u05d4\u05e9\u05d5\u05e7 \u05e9\u05d5\u05d1\u05e8, \u05d5\u05d7\u05d5\u05e1\u05dd \u05db\u05e0\u05d9\u05e1\u05d5\u05ea \u05e2\u05d3 \u05e9\u05d4\u05ea\u05e0\u05d0\u05d9 \u05de\u05ea\u05d1\u05d8\u05dc.<br>
    \u26A0\uFE0F \u05d4\u05ea\u05e7\u05d5\u05e4\u05d4 \u05e9\u05e0\u05d1\u05d3\u05e7\u05ea \u05d4\u05d9\u05d0 \u05e9\u05d5\u05e7 \u05e2\u05d5\u05dc\u05d4 \u05d1\u05e8\u05d5\u05d1\u05d4 - \u05e6\u05e4\u05d4 \u05e9\u05d4\u05de\u05e0\u05d2\u05e0\u05d5\u05df \u05d9\u05d9\u05e8\u05d0\u05d4 \u05d7\u05dc\u05e9 \u05db\u05d0\u05df.
    \u05d4\u05e2\u05e8\u05da \u05e9\u05dc\u05d5 \u05de\u05ea\u05d2\u05dc\u05d4 \u05d1\u05de\u05e9\u05d1\u05e8\u05d9\u05dd. \u05e9\u05e7\u05d5\u05dc \u05dc\u05d4\u05e8\u05d9\u05e5 \u05e2\u05dc 5y.
    </div>
    """, unsafe_allow_html=True)
    MACRO_MODE_MAP = {
        "\U0001F6AB \u05db\u05d1\u05d5\u05d9": "off",
        "\U0001F4C9 SPY \u05de\u05ea\u05d7\u05ea \u05dc-SMA200": "sma200",
        "\U0001F53B SPY \u05d9\u05d5\u05e8\u05d3 \u05de\u05e9\u05d9\u05d0 20 \u05d9\u05d5\u05dd": "drawdown",
        "\U0001F52C \u05d4\u05e9\u05d5\u05d5\u05d4 \u05d0\u05ea \u05db\u05d5\u05dc\u05dd": "compare",
    }
    macro_label = st.selectbox("\u05de\u05e6\u05d1 \u05d9\u05e6\u05d9\u05d0\u05ea \u05d7\u05d9\u05e8\u05d5\u05dd:", list(MACRO_MODE_MAP.keys()), index=0)
    macro_exit_mode = MACRO_MODE_MAP[macro_label]
    macro_confirm_days, macro_dd_pct = 2, 8.0
    if macro_exit_mode != "off":
        col_g1, col_g2 = st.columns(2)
        macro_confirm_days = col_g1.number_input("\u05d9\u05de\u05d9 \u05d0\u05d9\u05e9\u05d5\u05e8 \u05e8\u05e6\u05d5\u05e4\u05d9\u05dd:", min_value=1, max_value=10, value=2, step=1,
            help="\u05de\u05d5\u05e0\u05e2 \u05ea\u05d2\u05d5\u05d1\u05d4 \u05dc\u05e0\u05d2\u05d9\u05e2\u05d4 \u05d7\u05d3-\u05d9\u05d5\u05de\u05d9\u05ea (whipsaw).")
        macro_dd_pct = col_g2.number_input("\u05d0\u05d7\u05d5\u05d6 \u05d9\u05e8\u05d9\u05d3\u05d4 \u05de\u05e9\u05d9\u05d0:", min_value=3.0, max_value=25.0, value=8.0, step=1.0,
            help="\u05e8\u05dc\u05d5\u05d5\u05e0\u05d8\u05d9 \u05e8\u05e7 \u05d1\u05de\u05e6\u05d1 '\u05d9\u05d5\u05e8\u05d3 \u05de\u05e9\u05d9\u05d0'.")
    if macro_exit_mode == "compare":
        macro_modes_to_run = [("off", "\U0001F6AB \u05d1\u05dc\u05d9 \u05de\u05d0\u05e7\u05e8\u05d5"), ("sma200", "\U0001F4C9 SMA200"), ("drawdown", "\U0001F53B \u05d9\u05e8\u05d9\u05d3\u05d4 \u05de\u05e9\u05d9\u05d0")]
    else:
        macro_modes_to_run = [(macro_exit_mode, "")]

    st.markdown("---")
    show_earnings_analysis = st.checkbox("📊 הצג ניתוח 'כמה עולה להחזיק דרך דוח'", value=True,
        help="מפצל את הטריידים לשתי קבוצות ומשווה תוחלת. שים לב: במדיניות 'משולב' כמעט אין טריידים שחוצים דוח, אז הניתוח יהיה ריק - הרץ אותו במצב 'רגיל' כדי לראות תוצאה.")

    st.markdown("---")
    use_composite_bt = st.checkbox("השתמש בציון המורכב החדש (עם מכפיל איכות כניסה)", value=DEFAULTS["use_composite"],
        help="מסומן = הסף נבדק מול הציון החדש (מכפיל מאקרו + ענישת מתיחת יתר). לא מסומן = הציון הטכני הגולמי הישן.")
    directional_vol_bt = st.checkbox("נפח מכוון (נפח חריג נספר שלילית ביום ירידה)", value=DEFAULTS["directional_vol"],
        help="השינוי השני שהוכנס יחד עם הציון המורכב. בטל אותו כדי לבודד: אם הביצועים משתפרים בלעדיו - הוא האשם, לא הציון.")
    st.markdown("""
    <div class='unknown-box'>
    📌 <b>מה השתנה:</b> סדרת 22 בדיקות על 11 קטגוריות הראתה שחמישה מששה
    רכיבים שהיו נעולים היו <b>מזיקים</b>: הציון המורכב, הנפח המכוון,
    חסימת מתיחת יתר, סף 65 ו-30 ימי החזקה. רק Swing Low עמד במבחן.<br>
    המשתנה המסביר הוא <b>תנודתיות</b> — ולכן הפרמטרים נגזרים מ-ATR%
    של כל מניה בנפרד (בדיקה 21). המתגים למטה נשמרים לבדיקות חוזרות.
    </div>
    """, unsafe_allow_html=True)

    st.caption(f"📌 גרסה {APP_VERSION}")

    bt_mode = st.radio("מצב בקטסט:", ["🎯 טיקר בודד", "📊 קטגוריה שלמה (אגרגטיבי)", "🌍 מספר קטגוריות (מחוץ למדגם)"], index=1, horizontal=False)
    col_bt1, col_bt2 = st.columns(2)
    bt_threshold = col_bt1.number_input("סף ציון כניסה:", min_value=40, max_value=90, value=DEFAULTS["score_threshold"], step=5,
        help="שים לב: הציון המורכב נמוך יותר בממוצע מהטכני הגולמי (בגלל המכפילים) - לכן סף 65 כאן שקול בערך ל-70 בציון הישן.")
    bt_max_days = col_bt2.number_input("מקסימום ימי החזקה (0=עד הדוח):", min_value=0, max_value=250, value=DEFAULTS["max_holding_days"], step=5)
    bt_period = st.selectbox("טווח נתונים היסטורי:", ["2y", "3y", "5y"], index=1,
                              help="טווח ארוך יותר = יותר טריידים = מדגם אמין יותר, אך שליפה איטית יותר")
    bt_earnings_mode_label = st.radio("מדיניות דוחות בבקטסט:", [
        "רגיל (ללא הגבלה)",
        "🚫 חסימת כניסה בלבד",
        "🔀 משולב: מניעת כניסה + יציאה מוקדמת (מומלץ)",
        "🔬 השווה את כל השלוש"
    ], index=2, horizontal=False,
       help="'חסימת כניסה בלבד' לא נכנס אם יש דוח בכל טווח ההחזקה. 'משולב' נכנס כרגיל, אבל יוצא ביזמה כמה ימים לפני דוח.")
    EARNINGS_MODE_MAP = {
        "רגיל (ללא הגבלה)": "none",
        "🚫 חסימת כניסה בלבד": "entry_block",
        "🔀 משולב: מניעת כניסה + יציאה מוקדמת (מומלץ)": "combined",
    }
    entry_buffer_days, exit_buffer_days = 2, 1
    if bt_earnings_mode_label in ["🔀 משולב: מניעת כניסה + יציאה מוקדמת (מומלץ)", "🔬 השווה את כל השלוש"]:
        col_e1, col_e2 = st.columns(2)
        entry_buffer_days = col_e1.number_input("ימים לפני דוח לחסום כניסה חדשה:", min_value=1, max_value=10, value=2, step=1)
        exit_buffer_days = col_e2.number_input("ימים לפני דוח לצאת מפוזיציה קיימת:", min_value=1, max_value=5, value=1, step=1)

    if bt_earnings_mode_label == "🔬 השווה את כל השלוש":
        bt_modes_to_run = [("none", "📊 רגיל (ללא הגבלה)"),
                            ("entry_block", "🚫 חסימת כניסה בלבד"),
                            ("combined", "🔀 משולב (כניסה + יציאה מוקדמת)")]
    else:
        bt_modes_to_run = [(EARNINGS_MODE_MAP[bt_earnings_mode_label], "תוצאות")]

    bt_exit_style_label = st.radio("סגנון יציאה:", [
        "🎯 TP קבוע (ברירת מחדל)",
        "📈 Trailing Stop (לתת לרווחים לרוץ)",
        "🔬 השווה בין השניים"
    ], horizontal=False)
    EXIT_STYLE_MAP = {"🎯 TP קבוע (ברירת מחדל)": "fixed", "📈 Trailing Stop (לתת לרווחים לרוץ)": "trailing", "🏗️ קידום סטופ מבני (Swing Low נגרר)": "structural_trail"}
    trailing_width_mult = 2.0
    # trailing_width_mult נדרש רק ל-Trailing הרגיל
    if bt_exit_style_label in ["📈 Trailing Stop (לתת לרווחים לרוץ)", "🔬 השווה את כולם"]:
        trailing_width_mult = st.number_input(
            "רוחב Trailing Stop (מכפיל הסיכון המקורי):", min_value=1.0, max_value=5.0, value=2.0, step=0.5)
    if bt_exit_style_label == "🔬 השווה את כולם":
        bt_exit_styles_to_run = [("fixed", "🎯 TP קבוע"), ("trailing", "📈 Trailing Stop"), ("structural_trail", "🏗️ קידום מבני")]
    else:
        bt_exit_styles_to_run = [(EXIT_STYLE_MAP[bt_exit_style_label], "")]

    st.markdown("**מדיניות מתיחת יתר (Overextended):**")
    col_ov1, col_ov2 = st.columns(2)
    overext_threshold = col_ov1.number_input("סף מתיחת יתר (% מעל SMA20):", min_value=3.0, max_value=25.0, value=8.0, step=1.0)
    block_overextended = col_ov2.checkbox("חסום כניסה על מתיחת יתר", value=True)
    if not block_overextended:
        st.markdown("<div class='unknown-box'>⚠️ ביטלת את חסימת מתיחת היתר - המערכת תיכנס גם למניות שכבר עלו הרבה.</div>", unsafe_allow_html=True)

    bt_stop_style_label = st.radio("סגנון סטופ:", [
        "📐 ATR קבוע",
        "🏗️ מבנה מחיר (Swing Low) - מומלץ",
        "🔬 השווה בין השניים"
    ], index=1, horizontal=False,
       help="בבדיקות שהרצנו על 3 קטגוריות, Swing Low ניצח את ATR בכל אחת מהן בתשואה, Sharpe ו-Calmar.")
    STOP_STYLE_MAP = {"📐 ATR קבוע": "atr", "🏗️ מבנה מחיר (Swing Low) - מומלץ": "structural"}
    structural_lookback, structural_buffer_pct = 15, 1.0
    if bt_stop_style_label in ["🏗️ מבנה מחיר (Swing Low) - מומלץ", "🔬 השווה בין השניים"]:
        col_s1, col_s2 = st.columns(2)
        structural_lookback = col_s1.number_input("חלון חיפוש Swing Low (ימים):", min_value=5, max_value=40, value=15, step=5)
        structural_buffer_pct = col_s2.number_input("Buffer מתחת לשפל (%):", min_value=0.0, max_value=5.0, value=1.0, step=0.5)
    if bt_stop_style_label == "🔬 השווה בין השניים":
        bt_stop_styles_to_run = [("atr", "📐 ATR"), ("structural", "🏗️ Swing Low")]
    else:
        bt_stop_styles_to_run = [(STOP_STYLE_MAP[bt_stop_style_label], "")]

    bt_runs_to_execute = []
    _BASE = {"composite": use_composite_bt, "dir_vol": directional_vol_bt,
             "block_overext": block_overextended, "use_reversal": use_reversal_exit,
             "weekly": use_weekly_trend, "three_day": use_three_day,
             "em_filter": use_em_filter, "max_wk": max_trades_per_week,
             "cost": effective_cost, "threshold": bt_threshold, "max_days": bt_max_days,
             "vol_norm": use_vol_norm, "vb1": vb1, "vb2": vb2, "vb3": vb3,
             "rising_sma": False, "trigger": "score", "brk_lb": 20,
             "part_r": 2.0, "part_be": False, "dip_pct": 10.0,
             "scale": "off", "scale_drop": 5.0, "ladder": "off",
             "scale_first": 0.5, "vn_scope": "thr", "cooldown": False,
             "max_pos": 0, "cool_mode": "off"}
    if _suite_specs is not None:
        _BASE.update({k: v for k, v in SUITE_BASE.items() if k in _BASE})
        for _lbl, _ov in _suite_specs:
            bt_runs_to_execute.append((
                _ov.get("earn", SUITE_BASE["earn"]),
                _ov.get("exit", SUITE_BASE["exit"]),
                _ov.get("stop", SUITE_BASE["stop"]),
                _lbl,
                _ov.get("vix", SUITE_BASE["vix"]),
                _ov.get("rev", SUITE_BASE["rev"]),
                _ov.get("entry", SUITE_BASE["entry"]),
                _ov.get("macro", SUITE_BASE["macro"]),
                _ov))
    for mode_code, mode_label in (bt_modes_to_run if _suite_specs is None else []):
        for exit_code, exit_label in bt_exit_styles_to_run:
            for stop_code, stop_label in bt_stop_styles_to_run:
                for vmode_code, vmode_label in vix_modes_to_run:
                  for rmode_code, rmode_label in rev_modes_to_run:
                   for emode_code, emode_label in entry_modes_to_run:
                    for gmode_code, gmode_label in macro_modes_to_run:
                     parts = [p for p in [mode_label if mode_label != "תוצאות" else "", exit_label, stop_label, vmode_label, rmode_label, emode_label, gmode_label] if p]
                     combined_label = " | ".join(parts) if parts else "תוצאות"
                     bt_runs_to_execute.append((mode_code, exit_code, stop_code, combined_label, vmode_code, rmode_code, emode_code, gmode_code, {}))

    if len(bt_runs_to_execute) > 2:
        st.caption(f"ℹ️ יורצו {len(bt_runs_to_execute)} שילובים - זמן ריצה יתארך בהתאם.")
    if len(bt_runs_to_execute) > 6:
        st.markdown("<div class='unknown-box'>⚠️ שילוב גדול של אפשרויות - עלול לקחת זמן רב מאוד. שקול לצמצם.</div>", unsafe_allow_html=True)

    # DATE-RANGE: חלון מפורש. בלי זה אין out-of-sample.
    import datetime as _dt
    _use_range = st.checkbox("📅 טווח תאריכים מדויק (במקום תקופה יחסית)",
                             value=False, key="bt_use_range")
    if _use_range:
        _c1, _c2 = st.columns(2)
        _s = _c1.date_input("מתאריך", value=_dt.date(2022, 1, 1),
                            key="bt_start")
        _e = _c2.date_input("עד תאריך", value=_dt.date(2023, 12, 31),
                            key="bt_end")
        if _s and _e and _s < _e:
            bt_period = f"{_s}:{_e}"
            st.caption("⚠️ חימום אינדיקטורים נאכל מתחילת החלון — "
                       "כ-150 ימי מסחר ראשונים ללא כניסות. "
                       "לחלון קצר הוסף מרווח לפני תאריך ההתחלה.")
        else:
            st.error("טווח תאריכים לא תקין — מריץ לפי התקופה היחסית")
    bt_cfg = {"period": bt_period, "threshold": bt_threshold, "max_days": bt_max_days,
        "composite": use_composite_bt, "dir_vol": directional_vol_bt,
        "stop": bt_stop_style_label, "swing_lb": structural_lookback,
        "swing_buf": structural_buffer_pct, "earnings": bt_earnings_mode_label,
        "entry_buf": entry_buffer_days, "exit_buf": exit_buffer_days,
        "exit_style": bt_exit_style_label, "trail_mult": trailing_width_mult,
        "overext": overext_threshold, "block_overext": block_overextended,
        "cost_side": effective_cost,
        "em_filter": f"{em_mult}x/min{em_min_samples}" if use_em_filter else False,
        "vix": vix_label, "vix_th": vix_threshold,
        "weekly": f"{weekly_sma_weeks}w" if use_weekly_trend else False,
        "three_day": f"{three_day_drop}%/{three_day_wait}d" if use_three_day else False,
        "max_wk": max_trades_per_week or "none",
        "reversal": f"{reversal_mode}/min{reversal_min_days}d" if use_reversal_exit else False,
        "suite": _suite_label if _suite_specs is not None else "manual",
        "vol_norm": f"{vb1}/{vb2}/{vb3}" if use_vol_norm else False,
        "entry_gate": entry_mode,
        "macro_exit": f"{macro_exit_mode}/{macro_confirm_days}d" if macro_exit_mode != "off" else False}


    if bt_mode == "🎯 טיקר בודד":
        bt_ticker = st.text_input("סימול לבקטסט:", "NVDA", key="bt_ticker").upper()
        if st.button("הרץ בקטסט", type="primary"):
            df, fetch_err = fetch_stock_data_backtest(bt_ticker, bt_period)
            if df.empty:
                st.markdown(f"<div class='fail-box'>🚨 שגיאת שליפה: {fetch_err}</div>", unsafe_allow_html=True)
            else:
                needs_earnings = any(m != "none" for m, _, _, _, _, _, _, _, _ in bt_runs_to_execute) or use_em_filter or use_three_day
                earnings_dates = fetch_earnings_dates_backtest(bt_ticker) if needs_earnings else set()
                if needs_earnings and not earnings_dates:
                    st.markdown(f"<div class='unknown-box'>⚠️ לא נמצאו תאריכי דוחות ל-{bt_ticker} (ייתכן שזו ETF) - כל המצבים ייצאו זהים.</div>", unsafe_allow_html=True)

                with st.spinner(f"מריץ בקטסט על {bt_period} אחורה..."):
                    mode_results = {}
                    single_blocked = {}
                    vix_hist_single = fetch_vix_history(bt_period) if any(v != "ignore" for _, _, _, _, v, _, _, _, _ in bt_runs_to_execute) else None
                    spy_hist_single = fetch_spy_history(bt_period) if any(g != "off" for _, _, _, _, _, _, _, g, _ in bt_runs_to_execute) else None
                    for mode_code, exit_code, stop_code, combined_label, vmode_code, rmode_code, emode_code, gmode_code, ovr in bt_runs_to_execute:
                        use_composite_bt = ovr.get("composite", _BASE["composite"])
                        directional_vol_bt = ovr.get("dir_vol", _BASE["dir_vol"])
                        block_overextended = ovr.get("block_overext", _BASE["block_overext"])
                        use_reversal_exit = ovr.get("use_reversal", _BASE["use_reversal"])
                        use_weekly_trend = ovr.get("weekly", _BASE["weekly"])
                        use_three_day = ovr.get("three_day", _BASE["three_day"])
                        use_em_filter = ovr.get("em_filter", _BASE["em_filter"])
                        max_trades_per_week = ovr.get("max_wk", _BASE["max_wk"])
                        effective_cost = ovr.get("cost", _BASE["cost"])
                        _eff_trail = float(ovr.get("trail", _BASE.get("trail", 2.0)))
                        globals()["_SEC_CAP"] = int(ovr.get("sec_cap", _BASE.get("sec_cap", 0)))
                        globals()["_ATR_COST"] = float(ovr.get("atr_cost", _BASE.get("atr_cost", 0.0)))
                        # VIX-SIZING: הסכמה נקבעת כאן, יחד עם שאר הדריסות.
                        globals()["_VIX_SIZING"] = ovr.get("vix_size", _BASE.get("vix_size", "off"))
                        globals()["_COOL_MODE"] = ovr.get("cool_mode", _BASE.get("cool_mode", "current"))
                        # AUDIT-EVERY-RUN: הערך נדרס כאן. הפלט חייב לדווח את מה
                        # שהמנוע קיבל בפועל, והמבדק חייב לרוץ בכל תצורה.
                        try:
                            bt_cfg["cost_side"] = effective_cost
                            # eff_engine: מה שהמנוע קיבל בפועל, אחרי הדריסות.
                            # בלי זה הדוח מציג את מה שבוקש בממשק ונזרק.
                            bt_cfg["eff_engine"] = " · ".join(
                                f"{_k}={ovr.get(_k, _BASE[_k])}" for _k in sorted(_BASE))
                        except Exception: pass
                        _AUDIT_DONE.clear()
                        bt_threshold = ovr.get("threshold", _BASE["threshold"])
                        bt_max_days = ovr.get("max_days", _BASE["max_days"])
                        use_vol_norm = ovr.get("vol_norm", _BASE["vol_norm"])
                        require_rising_sma = ovr.get("rising_sma", _BASE["rising_sma"])
                        entry_trigger = ovr.get("trigger", _BASE["trigger"])
                        breakout_lookback = ovr.get("brk_lb", _BASE["brk_lb"])
                        partial_r = ovr.get("part_r", _BASE["part_r"])
                        partial_be = ovr.get("part_be", _BASE["part_be"])
                        dip_pct = ovr.get("dip_pct", _BASE["dip_pct"])
                        scale_mode = ovr.get("scale", _BASE["scale"])
                        scale_drop = ovr.get("scale_drop", _BASE["scale_drop"])
                        ladder_mode = ovr.get("ladder", _BASE["ladder"])
                        scale_first = ovr.get("scale_first", _BASE["scale_first"])
                        vol_norm_scope = ovr.get("vn_scope", _BASE["vn_scope"])
                        use_cooldown = ovr.get("cooldown", _BASE["cooldown"])
                        max_positions = ovr.get("max_pos", _BASE["max_pos"])
                        vb1 = ovr.get("vb1", _BASE["vb1"])
                        vb2 = ovr.get("vb2", _BASE["vb2"])
                        vb3 = ovr.get("vb3", _BASE["vb3"])
                        trades, err = run_backtest_single(df, bt_ticker, bt_threshold, bt_max_days,
                                                           earnings_mode=mode_code, earnings_dates=earnings_dates,
                                                           entry_buffer_days=entry_buffer_days, exit_buffer_days=exit_buffer_days,
                                                           exit_style=exit_code, trailing_width_mult=_eff_trail,
                                                           overext_threshold=overext_threshold, block_overextended=block_overextended,
                                                           stop_style=stop_code, structural_lookback=structural_lookback,
                                                           structural_buffer_pct=structural_buffer_pct,
                                                           use_composite=use_composite_bt,
                                                           directional_vol=directional_vol_bt,
                                                           cost_pct_per_side=effective_cost,
                                                           use_earnings_move_filter=use_em_filter,
                                                           earnings_move_mult=em_mult,
                                                           earnings_move_min_samples=em_min_samples,
                                                           vix_series=vix_hist_single, vix_mode=vmode_code,
                                                           vix_threshold=vix_threshold,
                                                           use_weekly_trend=use_weekly_trend,
                                                           weekly_sma_weeks=weekly_sma_weeks,
                                                           use_three_day_rule=use_three_day,
                                                           three_day_drop_pct=three_day_drop,
                                                           three_day_wait=three_day_wait,
                                                           use_reversal_exit=use_reversal_exit,
                                                           reversal_mode=rmode_code,
                                                           reversal_min_days=reversal_min_days,
                                                           entry_mode=emode_code,
                                                           spy_series=spy_hist_single,
                                                           macro_exit_mode=gmode_code,
                                                           macro_confirm_days=macro_confirm_days,
                                                           macro_dd_pct=macro_dd_pct,
                                                           use_vol_norm=use_vol_norm,
                                                           vb1=vb1, vb2=vb2, vb3=vb3,
                                                           blocked_out=single_blocked)
                        mode_results[combined_label] = (trades, err)

                first_label = bt_runs_to_execute[0][3]
                base_trades, base_err = mode_results[first_label]
                if base_err:
                    st.warning(base_err)
                elif not base_trades:
                    st.info("לא נמצאו טריידים תואמים (נסה סף ציון נמוך יותר או טווח ארוך יותר).")
                else:
                    def render_summary(trades, label):
                        s = compute_backtest_summary(trades)
                        if s is None:
                            st.info(f"{label}: אין טריידים תואמים.")
                            return None
                        st.markdown(f"**{label}**")
                        st.markdown(f"""
                        <div class="metric-row">
                            <div class="metric-item"><div class="metric-title">מספר טריידים</div><div class="metric-value">{s['num_trades']}</div></div>
                            <div class="metric-item"><div class="metric-title">אחוז הצלחה</div><div class="metric-value">{s['win_rate']:.0f}%</div></div>
                            <div class="metric-item"><div class="metric-title">תשואה מצטברת</div><div class="metric-value">{s['total_return_pct']:+.1f}%</div></div>
                            <div class="metric-item"><div class="metric-title">Drawdown מקס'</div><div class="metric-value">-{s['max_drawdown_pct']:.1f}%</div></div>
                        </div>
                        """, unsafe_allow_html=True)
                        col_x, col_y, col_z = st.columns(3)
                        col_x.metric("רווח ממוצע (זכייה)", f"+{s['avg_win']:.1f}%")
                        col_y.metric("הפסד ממוצע (הפסד)", f"{s['avg_loss']:.1f}%")
                        pf_disp = "∞" if s['profit_factor'] == float('inf') else f"{s['profit_factor']:.2f}"
                        col_z.metric("Profit Factor", pf_disp)
                        st.caption(f"ממוצע ימי החזקה לטרייד: {s['avg_days_held']:.1f}")
                        if effective_cost > 0:
                            g = np.mean([t.get("gross_return_pct", t["return_pct"]) for t in trades])
                            nt = np.mean([t["return_pct"] for t in trades])
                            st.caption(f"💰 לפני עלויות: {g:+.2f}% לטרייד → אחרי: {nt:+.2f}%")
                        if show_earnings_analysis:
                            ee = analyze_earnings_exposure(trades)
                            if ee:
                                st.caption(f"📊 חצו דוח: {ee['held']['n']} טריידים, ממוצע {ee['held']['avg']:+.2f}% | לא חצו: {ee['clean']['n']} טריידים, ממוצע {ee['clean']['avg']:+.2f}% | הפרש: {ee['edge']:+.2f}%")
                        if s['num_trades'] < 15:
                            st.markdown("<div class='unknown-box'>⚠️ מדגם קטן מדי (מניה בודדת) - התוצאות עלולות להיות מקריות.</div>", unsafe_allow_html=True)
                        return s

                    summaries = {}
                    text_reports = []
                    for idx, (mode_label, (trades, err)) in enumerate(mode_results.items()):
                        if err:
                            st.warning(f"{mode_label}: {err}")
                            continue
                        summaries[mode_label] = render_summary(trades, mode_label)
                        text_reports.append(build_text_report(
                            f"{bt_ticker} | {mode_label}",
                            {**bt_cfg, "ticker": bt_ticker, "scope": "single"},
                            summaries[mode_label], None, trades, [],
                            single_blocked, []))
                        if idx < len(mode_results) - 1:
                            st.markdown("---")

                    if len(bt_runs_to_execute) > 1 and all(summaries.values()):
                        st.markdown("---")
                        st.markdown("#### 📈 טבלת השוואה")
                        comp_rows = []
                        for mode_label, s in summaries.items():
                            comp_rows.append({"מצב": mode_label, "טריידים": s['num_trades'],
                                               "הצלחה %": round(s['win_rate'], 0),
                                               "PF": round(s['profit_factor'], 2) if s['profit_factor'] != float('inf') else "∞",
                                               "תשואה מצטברת %": round(s['total_return_pct'], 1)})
                        st.dataframe(pd.DataFrame(comp_rows), use_container_width=True)

                    with st.expander(f"פירוט טריידים ({first_label}, {len(base_trades)})", expanded=False):
                        trades_df = pd.DataFrame(base_trades)
                        trades_df["entry_date"] = trades_df["entry_date"].dt.strftime("%Y-%m-%d")
                        trades_df["exit_date"] = trades_df["exit_date"].dt.strftime("%Y-%m-%d")
                        trades_df["return_pct"] = trades_df["return_pct"].round(2)
                        st.dataframe(trades_df[["entry_date", "exit_date", "entry", "exit", "return_pct", "reason", "days"]],
                                     use_container_width=True)

                    render_report_export(text_reports, "single")

    elif bt_mode == "📊 קטגוריה שלמה (אגרגטיבי)":
        _cat_keys = list(CATEGORIES.keys())
        _def_cat = _cat_keys.index("💰 יקום סחיר (159)") if "💰 יקום סחיר (159)" in _cat_keys else 0
        # STANDING-DEFAULTS: היקום הנקי כברירת מחדל.
        # לפי שם ולא לפי אינדקס — אינדקס נשבר כשמוסיפים
        # קטגוריה, וזה שקט ומסוכן.
        _keys = list(CATEGORIES.keys())
        _def_cat = next((i for i, k in enumerate(_keys)
                         if "יקום 2023 · נקי" in k), _def_cat)
        bt_cat = st.selectbox("בחר קטגוריה לבקטסט אגרגטיבי:", _keys, index=_def_cat, key="bt_cat")
        cat_tickers = CATEGORIES[bt_cat]
        st.caption(f"יורצו {len(cat_tickers)} מניות, הטריידים מכולן יאוחדו למדגם סטטיסטי אחד.")
        bt_position_pct = st.number_input("הקצאת הון לכל פוזיציה (% מהתיק):", min_value=1, max_value=20, value=5, step=1)

        if st.button("הרץ בקטסט אגרגטיבי", type="primary"):
            st.markdown("""
            <div class="unknown-box">
            ⚠️ <b>הבהרה:</b> "תשואה מצטברת (ריבית דריבית)" מניחה כל ההון בטרייד אחד ברצף - לא ריאלי.
            סעיף "💼 תיק ריאלי" למטה מדמה פוזיציות מקבילות עם הקצאת הון קבועה - אמין יותר.
            המספרים הכי אמינים תמיד: <b>אחוז הצלחה, רווח/הפסד ממוצע, Profit Factor</b>.
            </div>
            """, unsafe_allow_html=True)

            mode_summaries = {}
            mode_trades = {}
            text_reports = []
            for idx, (mode_code, exit_code, stop_code, combined_label, vmode_code, rmode_code, emode_code, gmode_code, ovr) in enumerate(bt_runs_to_execute):
                use_composite_bt = ovr.get("composite", _BASE["composite"])
                directional_vol_bt = ovr.get("dir_vol", _BASE["dir_vol"])
                block_overextended = ovr.get("block_overext", _BASE["block_overext"])
                use_reversal_exit = ovr.get("use_reversal", _BASE["use_reversal"])
                use_weekly_trend = ovr.get("weekly", _BASE["weekly"])
                use_three_day = ovr.get("three_day", _BASE["three_day"])
                use_em_filter = ovr.get("em_filter", _BASE["em_filter"])
                max_trades_per_week = ovr.get("max_wk", _BASE["max_wk"])
                effective_cost = ovr.get("cost", _BASE["cost"])
                _eff_trail = float(ovr.get("trail", _BASE.get("trail", 2.0)))
                globals()["_SEC_CAP"] = int(ovr.get("sec_cap", _BASE.get("sec_cap", 0)))
                globals()["_ATR_COST"] = float(ovr.get("atr_cost", _BASE.get("atr_cost", 0.0)))
                # VIX-SIZING: הסכמה נקבעת כאן, יחד עם שאר הדריסות.
                globals()["_VIX_SIZING"] = ovr.get("vix_size", _BASE.get("vix_size", "off"))
                globals()["_COOL_MODE"] = ovr.get("cool_mode", _BASE.get("cool_mode", "current"))
                # AUDIT-EVERY-RUN: הערך נדרס כאן. הפלט חייב לדווח את מה
                # שהמנוע קיבל בפועל, והמבדק חייב לרוץ בכל תצורה.
                try:
                    bt_cfg["cost_side"] = effective_cost
                    # eff_engine: מה שהמנוע קיבל בפועל, אחרי הדריסות.
                    # בלי זה הדוח מציג את מה שבוקש בממשק ונזרק.
                    bt_cfg["eff_engine"] = " · ".join(
                        f"{_k}={ovr.get(_k, _BASE[_k])}" for _k in sorted(_BASE))
                except Exception: pass
                _AUDIT_DONE.clear()
                bt_threshold = ovr.get("threshold", _BASE["threshold"])
                bt_max_days = ovr.get("max_days", _BASE["max_days"])
                use_vol_norm = ovr.get("vol_norm", _BASE["vol_norm"])
                require_rising_sma = ovr.get("rising_sma", _BASE["rising_sma"])
                entry_trigger = ovr.get("trigger", _BASE["trigger"])
                breakout_lookback = ovr.get("brk_lb", _BASE["brk_lb"])
                partial_r = ovr.get("part_r", _BASE["part_r"])
                partial_be = ovr.get("part_be", _BASE["part_be"])
                dip_pct = ovr.get("dip_pct", _BASE["dip_pct"])
                scale_mode = ovr.get("scale", _BASE["scale"])
                scale_drop = ovr.get("scale_drop", _BASE["scale_drop"])
                ladder_mode = ovr.get("ladder", _BASE["ladder"])
                scale_first = ovr.get("scale_first", _BASE["scale_first"])
                vol_norm_scope = ovr.get("vn_scope", _BASE["vn_scope"])
                use_cooldown = ovr.get("cooldown", _BASE["cooldown"])
                max_positions = ovr.get("max_pos", _BASE["max_pos"])
                vb1 = ovr.get("vb1", _BASE["vb1"])
                vb2 = ovr.get("vb2", _BASE["vb2"])
                vb3 = ovr.get("vb3", _BASE["vb3"])
                all_trades, per_ticker_stats, failed, benchmarks, price_map = run_aggregate(cat_tickers, mode_code, bt_period, bt_threshold,
                                                                      bt_max_days, entry_buffer_days, exit_buffer_days, f"{combined_label}: ",
                                                                      exit_style=exit_code, trailing_width_mult=_eff_trail,
                                                                      overext_threshold=overext_threshold, block_overextended=block_overextended,
                                                                      stop_style=stop_code, structural_lookback=structural_lookback,
                                                                      structural_buffer_pct=structural_buffer_pct,
                                                                      use_composite=use_composite_bt,
                                                                      directional_vol=directional_vol_bt,
                                                                      cost_pct_per_side=effective_cost,
                                                                      use_earnings_move_filter=use_em_filter,
                                                                      earnings_move_mult=em_mult,
                                                                      earnings_move_min_samples=em_min_samples,
                                                                      vix_mode=vmode_code, vix_threshold=vix_threshold,
                                                                      use_weekly_trend=use_weekly_trend,
                                                                      weekly_sma_weeks=weekly_sma_weeks,
                                                                      use_three_day_rule=use_three_day,
                                                                      three_day_drop_pct=three_day_drop,
                                                                      three_day_wait=three_day_wait,
                                                                      use_reversal_exit=use_reversal_exit,
                                                                      reversal_mode=rmode_code,
                                                                      reversal_min_days=reversal_min_days,
                                                                      entry_mode=emode_code,
                                                                      macro_exit_mode=gmode_code,
                                                                      macro_confirm_days=macro_confirm_days,
                                                                      macro_dd_pct=macro_dd_pct,
                                                                      use_vol_norm=use_vol_norm,
                                                                      require_rising_sma=require_rising_sma,
                                                                      entry_trigger=entry_trigger,
                                                                      breakout_lookback=breakout_lookback,
                                                                      partial_r=partial_r, partial_be=partial_be,
                                                                      dip_pct=dip_pct,
                                                                      scale_mode=scale_mode, scale_drop=scale_drop,
                                                                      ladder_mode=ladder_mode,
                                                                      scale_first=scale_first,
                                                                      vol_norm_scope=vol_norm_scope,
                                                                      use_cooldown=use_cooldown,
                                                                      vb1=vb1, vb2=vb2, vb3=vb3,
                                                                      max_trades_per_week=max_trades_per_week)
                s = render_aggregate(all_trades, per_ticker_stats, failed, cat_tickers, combined_label, bt_position_pct,
                                      benchmarks=benchmarks, show_earnings_split=show_earnings_analysis,
                                      cost_applied=effective_cost, price_map=price_map,
                                    max_positions=max_positions)
                mode_summaries[combined_label] = s
                mode_trades[combined_label] = all_trades
                text_reports.append(build_text_report(
                    f"{bt_cat} | {combined_label}", {**bt_cfg, "cat": bt_cat, "pos_pct": bt_position_pct},
                    s, benchmarks, all_trades, per_ticker_stats,
                    st.session_state.get("last_blocked", {}), failed))
                if idx < len(bt_runs_to_execute) - 1:
                    st.markdown("---")

            if len(bt_runs_to_execute) > 1 and all(mode_summaries.values()):
                st.markdown("---")
                st.markdown("#### 📈 טבלת השוואה")
                comp_rows = []
                for mode_label, s in mode_summaries.items():
                    comp_rows.append({"מצב": mode_label, "טריידים": s['num_trades'],
                                       "הצלחה %": round(s['win_rate'], 0),
                                       "PF": round(s['profit_factor'], 2) if s['profit_factor'] != float('inf') else "∞",
                                       "תשואה מצטברת %": round(s['total_return_pct'], 1)})
                st.dataframe(pd.DataFrame(comp_rows), use_container_width=True)

            first_label = bt_runs_to_execute[0][3]
            with st.expander(f"כל טריידים - {first_label} ({len(mode_trades[first_label])})", expanded=False):
                trades_df = pd.DataFrame(mode_trades[first_label])
                if not trades_df.empty:
                    trades_df["entry_date"] = trades_df["entry_date"].dt.strftime("%Y-%m-%d")
                    trades_df["exit_date"] = trades_df["exit_date"].dt.strftime("%Y-%m-%d")
                    trades_df["return_pct"] = trades_df["return_pct"].round(2)
                    st.dataframe(trades_df[["ticker", "entry_date", "exit_date", "entry", "exit", "return_pct", "reason", "days"]],
                                 use_container_width=True)

            render_report_export(text_reports, "agg")

    else:  # 🌍 מספר קטגוריות
        st.markdown("""
        <div class="disclaimer">
        🌍 <b>בדיקה מחוץ למדגם:</b> מריץ את אותם פרמטרים בדיוק על מספר קטגוריות ומראה טבלת השוואה מרוכזת.
        אם התוצאות נשארות דומות בין קטגוריות - חיזוק שהשיטה כללית. אם הן קורסות בקטגוריה מסוימת - סימן לזהירות.
        </div>
        """, unsafe_allow_html=True)
        selected_cats = st.multiselect("בחר קטגוריות להשוואה (מומלץ 2-4):", list(CATEGORIES.keys()),
                                        default=list(CATEGORIES.keys())[:2])
        bt_position_pct_multi = st.number_input("הקצאת הון לכל פוזיציה (% מהתיק):", min_value=1, max_value=20, value=5, step=1, key="pos_pct_multi")

        if len(bt_runs_to_execute) > 1 and len(selected_cats) > 2:
            st.markdown("<div class='unknown-box'>⚠️ שילוב של כמה מצבים עם יותר מ-2 קטגוריות ייקח זמן רב. שקול לצמצם.</div>", unsafe_allow_html=True)

        if st.button("הרץ בדיקה מחוץ למדגם", type="primary"):
            if not selected_cats:
                st.warning("בחר לפחות קטגוריה אחת.")
            else:
                cross_rows = []
                text_reports = []
                for cat_name in selected_cats:
                    st.markdown(f"## 📂 {cat_name}")
                    cat_tickers_multi = CATEGORIES[cat_name]
                    for mode_code, exit_code, stop_code, combined_label, vmode_code, rmode_code, emode_code, gmode_code, ovr in bt_runs_to_execute:
                        use_composite_bt = ovr.get("composite", _BASE["composite"])
                        directional_vol_bt = ovr.get("dir_vol", _BASE["dir_vol"])
                        block_overextended = ovr.get("block_overext", _BASE["block_overext"])
                        use_reversal_exit = ovr.get("use_reversal", _BASE["use_reversal"])
                        use_weekly_trend = ovr.get("weekly", _BASE["weekly"])
                        use_three_day = ovr.get("three_day", _BASE["three_day"])
                        use_em_filter = ovr.get("em_filter", _BASE["em_filter"])
                        max_trades_per_week = ovr.get("max_wk", _BASE["max_wk"])
                        effective_cost = ovr.get("cost", _BASE["cost"])
                        _eff_trail = float(ovr.get("trail", _BASE.get("trail", 2.0)))
                        globals()["_SEC_CAP"] = int(ovr.get("sec_cap", _BASE.get("sec_cap", 0)))
                        globals()["_ATR_COST"] = float(ovr.get("atr_cost", _BASE.get("atr_cost", 0.0)))
                        # VIX-SIZING: הסכמה נקבעת כאן, יחד עם שאר הדריסות.
                        globals()["_VIX_SIZING"] = ovr.get("vix_size", _BASE.get("vix_size", "off"))
                        globals()["_COOL_MODE"] = ovr.get("cool_mode", _BASE.get("cool_mode", "current"))
                        # AUDIT-EVERY-RUN: הערך נדרס כאן. הפלט חייב לדווח את מה
                        # שהמנוע קיבל בפועל, והמבדק חייב לרוץ בכל תצורה.
                        try:
                            bt_cfg["cost_side"] = effective_cost
                            # eff_engine: מה שהמנוע קיבל בפועל, אחרי הדריסות.
                            # בלי זה הדוח מציג את מה שבוקש בממשק ונזרק.
                            bt_cfg["eff_engine"] = " · ".join(
                                f"{_k}={ovr.get(_k, _BASE[_k])}" for _k in sorted(_BASE))
                        except Exception: pass
                        _AUDIT_DONE.clear()
                        bt_threshold = ovr.get("threshold", _BASE["threshold"])
                        bt_max_days = ovr.get("max_days", _BASE["max_days"])
                        use_vol_norm = ovr.get("vol_norm", _BASE["vol_norm"])
                        require_rising_sma = ovr.get("rising_sma", _BASE["rising_sma"])
                        entry_trigger = ovr.get("trigger", _BASE["trigger"])
                        breakout_lookback = ovr.get("brk_lb", _BASE["brk_lb"])
                        partial_r = ovr.get("part_r", _BASE["part_r"])
                        partial_be = ovr.get("part_be", _BASE["part_be"])
                        dip_pct = ovr.get("dip_pct", _BASE["dip_pct"])
                        scale_mode = ovr.get("scale", _BASE["scale"])
                        scale_drop = ovr.get("scale_drop", _BASE["scale_drop"])
                        ladder_mode = ovr.get("ladder", _BASE["ladder"])
                        scale_first = ovr.get("scale_first", _BASE["scale_first"])
                        vol_norm_scope = ovr.get("vn_scope", _BASE["vn_scope"])
                        use_cooldown = ovr.get("cooldown", _BASE["cooldown"])
                        max_positions = ovr.get("max_pos", _BASE["max_pos"])
                        vb1 = ovr.get("vb1", _BASE["vb1"])
                        vb2 = ovr.get("vb2", _BASE["vb2"])
                        vb3 = ovr.get("vb3", _BASE["vb3"])
                        all_trades, per_ticker_stats, failed, benchmarks, price_map = run_aggregate(
                            cat_tickers_multi, mode_code, bt_period, bt_threshold, bt_max_days,
                            entry_buffer_days, exit_buffer_days, f"{cat_name} | {combined_label}: ",
                            exit_style=exit_code, trailing_width_mult=_eff_trail,
                            overext_threshold=overext_threshold, block_overextended=block_overextended,
                            stop_style=stop_code, structural_lookback=structural_lookback,
                            structural_buffer_pct=structural_buffer_pct,
                            use_composite=use_composite_bt,
                            directional_vol=directional_vol_bt,
                            cost_pct_per_side=effective_cost,
                            use_earnings_move_filter=use_em_filter,
                            earnings_move_mult=em_mult,
                            earnings_move_min_samples=em_min_samples,
                            vix_mode=vmode_code, vix_threshold=vix_threshold,
                            use_weekly_trend=use_weekly_trend, weekly_sma_weeks=weekly_sma_weeks,
                            use_three_day_rule=use_three_day, three_day_drop_pct=three_day_drop,
                            three_day_wait=three_day_wait,
                            use_reversal_exit=use_reversal_exit, reversal_mode=rmode_code,
                            reversal_min_days=reversal_min_days,
                            entry_mode=emode_code, macro_exit_mode=gmode_code,
                            macro_confirm_days=macro_confirm_days, macro_dd_pct=macro_dd_pct,
                            use_vol_norm=use_vol_norm, vb1=vb1, vb2=vb2, vb3=vb3,
                            require_rising_sma=require_rising_sma,
                            entry_trigger=entry_trigger,
                            breakout_lookback=breakout_lookback,
                            partial_r=partial_r, partial_be=partial_be,
                            dip_pct=dip_pct,
                            scale_mode=scale_mode, scale_drop=scale_drop,
                            ladder_mode=ladder_mode,
                            scale_first=scale_first,
                            vol_norm_scope=vol_norm_scope,
                            use_cooldown=use_cooldown,
                            max_trades_per_week=max_trades_per_week)
                        with st.expander(f"{combined_label} - פירוט מלא", expanded=(len(bt_runs_to_execute) == 1)):
                            s = render_aggregate(all_trades, per_ticker_stats, failed, cat_tickers_multi,
                                                  combined_label, bt_position_pct_multi, show_details=True, benchmarks=benchmarks,
                                                  show_earnings_split=show_earnings_analysis, cost_applied=effective_cost, price_map=price_map,
                                    max_positions=max_positions)
                        if s:
                            text_reports.append(build_text_report(
                                f"{cat_name} | {combined_label}",
                                {**bt_cfg, "cat": cat_name,
                                 "pos_pct": bt_position_pct_multi},
                                s, benchmarks, all_trades, per_ticker_stats,
                                st.session_state.get("last_blocked", {}), failed))
                            cross_rows.append({
                                "קטגוריה": cat_name, "מצב": combined_label, "טריידים": s['num_trades'],
                                "הצלחה %": round(s['win_rate'], 0),
                                "PF": round(s['profit_factor'], 2) if s['profit_factor'] != float('inf') else "∞",
                                "תשואה (תיק ריאלי) %": round(s.get('realistic_return_pct', float('nan')), 1),
                                "DD (תיק ריאלי) %": round(s.get('realistic_dd_pct', float('nan')), 1),
                                "Sharpe": round(s.get('realistic_sharpe'), 2) if s.get('realistic_sharpe') else None,
                                "Calmar": round(s.get('realistic_calmar'), 2) if s.get('realistic_calmar') else None,
                                "Buy&Hold %": round(benchmarks['bh_return'], 1) if benchmarks else None,
                                "SMA Crossover %": round(benchmarks['sma_return'], 1) if benchmarks else None,
                            })
                    st.markdown("---")

                if text_reports:
                    render_report_export(text_reports)

                if cross_rows:
                    st.markdown("## 📊 טבלת השוואה מרוכזת (כל הקטגוריות)")
                    cross_df = pd.DataFrame(cross_rows)
                    st.dataframe(cross_df, use_container_width=True)
                    win_rates = cross_df["הצלחה %"].astype(float)
                    if win_rates.max() - win_rates.min() > 20:
                        st.markdown("<div class='unknown-box'>⚠️ פער גדול (מעל 20 נק') באחוז ההצלחה בין קטגוריות - השיטה כנראה רגישה לסקטור.</div>", unsafe_allow_html=True)
                    else:
                        st.success("✅ אחוזי ההצלחה בין הקטגוריות קרובים יחסית - חיזוק לכך שהשיטה לא מכוונת רק לקטגוריה אחת.")
                else:
                    st.info("לא נאספו תוצאות תקפות מאף קטגוריה.")

                render_report_export(text_reports, "multi")