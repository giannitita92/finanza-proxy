from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'it-IT,it;q=0.9,en;q=0.8',
}

SYMBOL_MAP = {
    'FTSEMIB.INDX':  'FTSEMIB.MI',
    'GDAXI.INDX':    '^GDAXI',
    'FCHI.INDX':     '^FCHI',
    'FTSE.INDX':     '^FTSE',
    'IBEX.INDX':     '^IBEX',
    'STOXX50E.INDX': '^STOXX50E',
    'GSPC.INDX':     '^GSPC',
    'NDX.INDX':      '^NDX',
    'BMPS.MI': 'BMPS.MI',
    'ISP.MI':  'ISP.MI',
    'LDO.MI':  'LDO.MI',
    'BAMI.MI': 'BAMI.MI',
    'G.MI':    'G.MI',
    'UCG.MI':  'UCG.MI',
    'PST.MI':  'PST.MI',
    'ENEL.MI': 'ENEL.MI',
    'MB.MI':   'MB.MI',
}

def fetch_yahoo_quote(yf_symbol):
    # Usiamo range=5d per avere sia chartPreviousClose che regularMarketPreviousClose
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(yf_symbol)}?interval=1d&range=5d'
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    data = r.json()
    result = data['chart']['result'][0]
    meta   = result['meta']

    price = meta.get('regularMarketPrice', 0)

    # Calcoliamo prev dalla serie storica: penultimo close = chiusura di ieri
    closes = result.get('indicators', {}).get('quote', [{}])[0].get('close', [])
    closes_clean = [c for c in closes if c is not None]

    if len(closes_clean) >= 2:
        # ultimo = oggi (potrebbe essere intraday), penultimo = chiusura ieri
        prev = closes_clean[-2]
    elif len(closes_clean) == 1:
        prev = closes_clean[0]
    else:
        prev = meta.get('chartPreviousClose', price)

    change   = round(price - prev, 6)
    change_p = round((change / prev * 100) if prev else 0, 4)
    return {
        'code':          yf_symbol,
        'close':         round(price, 4),
        'previousClose': round(prev, 4),
        'change':        change,
        'change_p':      change_p,
        'timestamp':     meta.get('regularMarketTime', 0),
        'currency':      meta.get('currency', 'EUR'),
        'marketState':   meta.get('marketState', 'CLOSED'),
    }

def fetch_yahoo_history(yf_symbol, interval, range_str):
    """
    interval: 1m, 5m, 15m, 30m, 60m, 1d, 1wk
    range_str: 1d, 5d, 1mo, 3mo, 6mo, 1y, 5y
    """
    # Yahoo Finance interval/range compatibility
    valid = {
        '1m':  ['1d', '5d'],
        '5m':  ['1d', '5d'],
        '15m': ['1d', '5d'],
        '30m': ['1d', '5d', '1mo'],
        '60m': ['1d', '5d', '1mo', '3mo'],
        '1d':  ['1mo', '3mo', '6mo', '1y', '5y'],
        '1wk': ['3mo', '6mo', '1y', '5y'],
    }
    allowed_ranges = valid.get(interval, ['1mo'])
    if range_str not in allowed_ranges:
        range_str = allowed_ranges[-1]

    url = (f'https://query1.finance.yahoo.com/v8/finance/chart/'
           f'{requests.utils.quote(yf_symbol)}'
           f'?interval={interval}&range={range_str}')
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    result = data['chart']['result'][0]
    meta   = result['meta']
    timestamps = result.get('timestamp', [])
    closes     = result['indicators']['quote'][0].get('close', [])
    opens      = result['indicators']['quote'][0].get('open', [])
    highs      = result['indicators']['quote'][0].get('high', [])
    lows       = result['indicators']['quote'][0].get('low', [])

    candles = []
    for i, ts in enumerate(timestamps):
        if i >= len(closes) or closes[i] is None:
            continue
        candles.append({
            't': ts,
            'o': round(opens[i], 4)  if opens[i]  is not None else None,
            'h': round(highs[i], 4)  if highs[i]  is not None else None,
            'l': round(lows[i], 4)   if lows[i]   is not None else None,
            'c': round(closes[i], 4),
        })

    return {
        'symbol':   yf_symbol,
        'interval': interval,
        'range':    range_str,
        'currency': meta.get('currency', 'EUR'),
        'prev':     meta.get('chartPreviousClose', 0),
        'candles':  candles,
    }

@app.route('/quote')
def quote():
    symbol = request.args.get('symbol', '').strip()
    extra  = request.args.get('s', '').strip()
    if not symbol:
        return jsonify({'error': 'symbol required'}), 400
    symbols = [symbol]
    if extra:
        symbols += [s.strip() for s in extra.split(',') if s.strip()]
    results = []
    for sym in symbols:
        yf_sym = SYMBOL_MAP.get(sym, sym)
        try:
            results.append(fetch_yahoo_quote(yf_sym))
        except Exception as e:
            results.append({'code': sym, 'error': str(e), 'close': 0, 'change': 0, 'change_p': 0})
    return jsonify(results if len(results) > 1 else results[0])

@app.route('/history')
def history():
    symbol   = request.args.get('symbol', '').strip()
    interval = request.args.get('interval', '1d').strip()
    range_s  = request.args.get('range', '1mo').strip()
    if not symbol:
        return jsonify({'error': 'symbol required'}), 400
    yf_sym = SYMBOL_MAP.get(symbol, symbol)
    try:
        return jsonify(fetch_yahoo_history(yf_sym, interval, range_s))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
