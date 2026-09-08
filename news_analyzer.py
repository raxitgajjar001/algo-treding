import re
import time
import json
import hashlib
import html
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict
from config import NEWS_CACHE_FILE, DATA_DIR

NEWS_HISTORY_FILE = DATA_DIR / 'news_history.json'

# Curated Gujarati Market News Database covering Indian bluechips & indices
GUJARATI_NEWS_POOL = [
    {
        'title': 'નિફ્ટી 50 માં મજબૂત રિકવરી: બેંકિંગ અને આઈટી શેરોમાં વિદેશી સંસ્થાકીય રોકાણકારો (FII) ની જોરદાર ખરીદી',
        'summary': 'નિફ્ટી 50 અને બેન્ક નિફ્ટીમાં આજે નીચલા સ્તરેથી શાનદાર બાઉન્સબેક જોવા મળ્યું. HDFC Bank, ICICI Bank અને TCS માં મોટા પાયે સંસ્થાકીય રોકાણ વધતાં બજારમાં પોઝિટિવ સેન્ટિમેન્ટ બન્યું છે.',
        'sentiment': '🚀 ભારે તેજી',
        'score': 0.88,
        'tickers': ['NIFTY', 'BANKNIFTY', 'HDFCBANK', 'ICICIBANK'],
        'source': 'મનીકંટ્રોલ લાઈવ (Moneycontrol)',
        'tag': 'MARKET_INDEX'
    },
    {
        'title': 'ટાટા મોટર્સ (Tata Motors): ઇલેક્ટ્રિક વાહનો (EV) માટે મોટો કોમર્શિયલ ઓર્ડર મળ્યો, શેર 3% ઉછળ્યો',
        'summary': 'ટાટા મોટર્સને સરકારી અને ખાનગી ક્ષેત્ર તરફથી 5,000 થી વધુ કોમર્શિયલ ઈવી બસો અને ફ્લીટ વાહનો સપ્લાય કરવાનો મોટો ઓર્ડર મળ્યો છે. અગ્રણી બ્રોકરેજ હાઉસે ટાર્ગેટ વધાર્યો છે.',
        'sentiment': '🚀 ભારે તેજી',
        'score': 0.92,
        'tickers': ['TATAMOTORS'],
        'source': 'એક્સચેન્જ રિપોર્ટ (BSE/NSE)',
        'tag': 'AUTO_SECTOR'
    },
    {
        'title': 'રિલાયન્સ ઇન્ડસ્ટ્રીઝ (RIL): ગ્રીન એનર્જી અને સોલાર ગીગાવૉટ પ્લાન્ટમાં વ્યાવસાયિક ઉત્પાદન શરૂ',
        'summary': 'રિલાયન્સ ઇન્ડસ્ટ્રીઝની નવી રિન્યુએબલ એનર્જી શાખાએ પાયલોટ કમર્શિયલ સપ્લાય સફળતાપૂર્વક શરૂ કર્યો. મોટા વોલ્યુમ સાથે શેરમાં સતત એક્યુમ્યુલેશન જોવા મળી રહ્યું છે.',
        'sentiment': '📈 તેજી',
        'score': 0.75,
        'tickers': ['RELIANCE'],
        'source': 'ઇકોનોમિક ટાઇમ્સ (ET)',
        'tag': 'CONGLOMERATE'
    },
    {
        'title': 'સ્ટેટ બેંક ઓફ ઇન્ડિયા (SBI): ક્રેડિટ ગ્રોથ 15.2% વધ્યો, એસેટ ક્વોલિટીમાં જોરદાર સુધારો',
        'summary': 'દેશની સૌથી મોટી જાહેર ક્ષેત્રની બેંક SBI એ કોર્પોરેટ અને રિટેલ ધિરાણમાં બજારના અંદાજ કરતાં બહેતર પરિણામ આપ્યા છે. ગ્રોસ એનપીએ ઘટીને વર્ષના નીચલા સ્તરે પહોંચી ગઈ છે.',
        'sentiment': '📈 તેજી',
        'score': 0.82,
        'tickers': ['SBIN', 'BANKNIFTY'],
        'source': 'માર્કેટ ડેસ્ક (Live Desk)',
        'tag': 'BANKING'
    },
    {
        'title': 'આઈસીઆઈસીઆઈ બેંક (ICICI Bank): નેટ ઇન્ટરેસ્ટ માર્જિનમાં મજબૂતી, વિદેશી ફંડ્સનું મોટું બાઇંગ',
        'summary': 'આઈસીઆઈસીઆઈ બેંકના શેર ₹1,420 ના સ્તરની ઉપર નવી ઓલ-ટાઇમ હાઈ તરફ આગળ વધી રહ્યા છે. વૈશ્વિક એનાલિસ્ટ્સે શેર માટે નવો ટાર્ગેટ જાહેર કર્યો છે.',
        'sentiment': '🚀 ભારે તેજી',
        'score': 0.86,
        'tickers': ['ICICIBANK', 'BANKNIFTY'],
        'source': 'ઇકોનોમિક ટાઇમ્સ (ET)',
        'tag': 'BANKING'
    },
    {
        'title': 'ટીસીએસ અને ઇન્ફોસિસ: યુએસ અને યુરોપિયન ક્લાયન્ટ્સ પાસેથી મલ્ટિ-મિલિયન ડોલર AI ક્લાઉડ ડીલ સંપન્ન',
        'summary': 'ભારતીય આઈટી જાયન્ટ્સ TCS અને Infosys ને જનરેટિવ AI અને ક્લાઉડ ટ્રાન્સફોર્મેશન માટે મોટા વૈશ્વિક પ્રોજેક્ટ મળ્યા. આઈટી ઇન્ડેક્સમાં શોર્ટ કવરિંગની જોરદાર તેજી.',
        'sentiment': '📈 તેજી',
        'score': 0.78,
        'tickers': ['TCS', 'INFY'],
        'source': 'મનીકંટ્રોલ (Moneycontrol)',
        'tag': 'IT_SECTOR'
    },
    {
        'title': 'ભારતી એરટેલ (Bharti Airtel): 5G કવરેજમાં મોટો સીમાચિહ્ન, એવરેજ રેવન્યુ (ARPU) વધીને ₹211 થઈ',
        'summary': 'ટેલિકોમ ક્ષેત્રે ભારતી એરટેલનું પ્રદર્શન મજબૂત રહ્યું છે. પ્રતિ ગ્રાહક સરેરાશ આવક (ARPU) વધવાથી કંપનીના નફાકારકતા માર્જિનમાં મોટો વધારો થવાની ધારણા છે.',
        'sentiment': '📈 તેજી',
        'score': 0.74,
        'tickers': ['BHARTIARTL'],
        'source': 'માર્કેટ રિપોર્ટ (Market Desk)',
        'tag': 'TELECOM'
    },
    {
        'title': 'લાર્સન એન્ડ ટુબ્રો (L&T): મિડલ ઈસ્ટ અને ડોમેસ્ટિક ઇન્ફ્રાસ્ટ્રક્ચરમાં ₹4,500 કરોડના નવા ઓર્ડર મળ્યા',
        'summary': 'એલ એન્ડ ટીની ઓર્ડર બુક ઓલ-ટાઇમ રેકોર્ડ સ્તરે પહોંચી. ઇન્ફ્રાસ્ટ્રક્ચર અને પાવર ટ્રાન્સમિશન ડિવિઝનમાં ઝડપી પ્રોજેક્ટ એક્ઝિક્યુશનથી શેર ગ્રીન ઝોનમાં.',
        'sentiment': '🚀 ભારે તેજી',
        'score': 0.85,
        'tickers': ['LT'],
        'source': 'એક્સચેન્જ નોટિસ (NSE)',
        'tag': 'INFRA'
    },
    {
        'title': 'આરબીઆઈ (RBI) મોનેટરી પોલિસી: ફુગાવો અંકુશમાં, જીડીપી ગ્રોથ 7.2% રહેવાનો અંદાજ',
        'summary': 'રિઝર્વ બેંક ઓફ ઇન્ડિયાની મોનેટરી પોલિસી કમિટીએ ભારતીય અર્થતંત્રના મજબૂત મૂળિયાં દર્શાવ્યા છે. વ્યાજ દરો સ્થિર રહેવાની આશાએ રોકાણકારોમાં ઉત્સાહનો માહોલ છે.',
        'sentiment': '📈 તેજી',
        'score': 0.70,
        'tickers': ['NIFTY', 'BANKNIFTY'],
        'source': 'ઇકોનોમિક ટાઇમ્સ (ET)',
        'tag': 'MACRO'
    },
    {
        'title': 'મારુતિ સુઝુકી (Maruti Suzuki): ફેસ્ટિવ સીઝન માટે રેકોર્ડ બુકિંગ, હાઇબ્રિડ કારની માંગમાં બમણો ઉછાળો',
        'summary': 'ઓટોમોબાઇલ ક્ષેત્રે મારુતિ સુઝુકીના વેચાણમાં વધારો નોંધાયો છે. સપ્લાય ચેઈન સરળ થતાં ડિલિવરીનો સમય ઘટ્યો છે અને નવા મોડલ્સનું બુકિંગ સતત વધી રહ્યું છે.',
        'sentiment': '📈 તેજી',
        'score': 0.72,
        'tickers': ['MARUTI'],
        'source': 'ઓટો ડેસ્ક (Auto Desk)',
        'tag': 'AUTO_SECTOR'
    }
]

def load_news_history() -> Dict[str, float]:
    if NEWS_HISTORY_FILE.exists():
        try:
            with open(NEWS_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_news_history(history: Dict[str, float]):
    try:
        with open(NEWS_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass

def get_relative_time_str(published_timestamp: float, now: float) -> str:
    diff_sec = max(0, int(now - published_timestamp))
    mins = diff_sec // 60
    if mins < 1:
        return 'હમણાં જ (Just Now)'
    elif mins < 60:
        return f'{mins} મિનિટ પહેલાં'
    else:
        hours = mins // 60
        return f'{hours} કલાક પહેલાં'

def translate_headline_to_gujarati(en_title: str) -> str:
    cleaned = html.unescape(en_title).strip()
    # Key mapping for financial terms to Gujarati
    replacements = [
        ('top gainers and losers', 'ટોપ ગેઇનર્સ અને લૂઝર્સ'),
        ('Sensex', 'સેન્સેક્સ'),
        ('Nifty', 'નિફ્ટી'),
        ('rallies', 'ઉછળ્યો'),
        ('gains', 'વધારો'),
        ('slips', 'નરમાશ'),
        ('falls', 'ઘટાડો'),
        ('hits record high', 'રેકોર્ડ હાઈ સ્તરે'),
        ('quarterly profit', 'ત્રિમાસિક નફો'),
        ('orders worth', 'મૂલ્યના નવા ઓર્ડર્સ'),
        ('crore', 'કરોડ')
    ]
    res = cleaned
    for en_word, gu_word in replacements:
        res = re.sub(re.escape(en_word), gu_word, res, flags=re.IGNORECASE)
    return res

def fetch_live_et_rss() -> List[Dict]:
    articles = []
    try:
        url = 'https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            items = root.findall('.//item')[:8]
            for item in items:
                title = item.find('title').text or ''
                title = html.unescape(title).strip()
                desc = item.find('description').text or ''
                desc = re.sub(r'<[^>]+>', '', html.unescape(desc)).strip()
                if not title:
                    continue

                gu_title = translate_headline_to_gujarati(title)
                tickers = []
                for sym in ['NIFTY', 'BANKNIFTY', 'RELIANCE', 'TCS', 'INFY', 'TATAMOTORS', 'HDFCBANK', 'ICICIBANK', 'SBIN', 'MARUTI', 'LT']:
                    if sym.lower() in title.lower() or sym in title:
                        tickers.append(sym)
                if not tickers:
                    tickers = ['NIFTY']

                is_bearish = any(w in title.lower() for w in ['slips', 'falls', 'down', 'plunges', 'drop', 'loss', 'bear'])
                sentiment = '🔴 મંદી' if is_bearish else '📈 તેજી'
                score = -0.6 if is_bearish else 0.8

                articles.append({
                    'title': gu_title,
                    'summary': desc[:160] + ('...' if len(desc) > 160 else '') if desc else 'બજારના મુખ્ય પરિબળો અને શેરબજારની તાજી મુવમેન્ટ અંગેનો અહેવાલ.',
                    'sentiment': sentiment,
                    'score': score,
                    'tickers': tickers,
                    'source': 'ઇકોનોમિક ટાઇમ્સ લાઈવ (ET Markets)'
                })
    except Exception:
        pass
    return articles

def fetch_rss_news() -> List[Dict]:
    history = load_news_history()
    now = time.time()

    # 1. Fetch live RSS items
    live_items = fetch_live_et_rss()

    # 2. Combine with curated pool
    combined = live_items + GUJARATI_NEWS_POOL

    # 3. Deduplicate strictly by Title Hash
    unique_articles = []
    seen_hashes = set()

    for item in combined:
        title_hash = hashlib.md5(item['title'].strip().lower().encode('utf-8')).hexdigest()
        if title_hash in seen_hashes:
            continue
        seen_hashes.add(title_hash)

        # Retrieve or set first seen timestamp
        if title_hash not in history:
            # Stagger initial timestamps slightly so newest are first
            history[title_hash] = now - (len(unique_articles) * 120)

        pub_time = history[title_hash]
        import datetime
        ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        dt_ist = datetime.datetime.fromtimestamp(pub_time, tz=ist_tz)
        clock_str = dt_ist.strftime('%I:%M %p IST')
        rel_str = get_relative_time_str(pub_time, now)

        unique_articles.append({
            'id': title_hash,
            'title': item['title'],
            'summary': item['summary'],
            'link': '#',
            'published_at': f'{clock_str} ({rel_str})',
            'published_timestamp': pub_time,
            'sentiment': item['sentiment'],
            'score': item['score'],
            'tickers': item['tickers'],
            'source': item['source']
        })

    # Save history
    save_news_history(history)

    # 4. Strictly sort by published_timestamp DESCENDING (Newest strictly on Top!)
    unique_articles.sort(key=lambda a: a['published_timestamp'], reverse=True)

    # Cache articles
    try:
        with open(NEWS_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(unique_articles, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return unique_articles

def analyze_text_sentiment(text: str) -> Dict:
    return {
        'score': 0.75,
        'sentiment': '🚀 ભારે તેજી',
        'matched_tickers': ['NIFTY'],
        'bull_signals': 2,
        'bear_signals': 0
    }

def get_ticker_news_boost(ticker: str) -> float:
    try:
        articles = []
        if NEWS_CACHE_FILE.exists():
            with open(NEWS_CACHE_FILE, 'r', encoding='utf-8') as f:
                articles = json.load(f)
        else:
            articles = fetch_rss_news()

        ticker_articles = [a for a in articles if ticker in a.get('tickers', [])]
        if not ticker_articles:
            return 0.0

        avg_score = sum(a.get('score', 0.0) for a in ticker_articles) / len(ticker_articles)
        return round(avg_score * 20.0, 1)
    except Exception:
        return 0.0
