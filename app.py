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

# Mappa simboli interni → Yahoo Finance
SYMBOL_MAP = {
    'FTSEMIB.INDX':  '^FTSEMIB',
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

def fetch_yahoo(yf_symbol):
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(yf_symbol)}?interval=1d&range=2d'
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    data = r.json()
    meta = data['chart']['result'][0]['meta']
    price  = meta.get('regularMarketPrice') or meta.get('chartPreviousClose', 0)
    prev   = meta.get('previousClose') or meta.get('chartPreviousClose', price)
    change   = round(price - prev, 4)
    change_p = round((change / prev * 100) if prev else 0, 4)
    return {
        'code':          yf_symbol,
        'close':         price,
        'previousClose': prev,
        'change':        change,
        'change_p':      change_p,
        'timestamp':     meta.get('regularMarketTime', 0),
        'currency':      meta.get('currency', 'EUR'),
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
            results.append(fetch_yahoo(yf_sym))
        except Exception as e:
            results.append({'code': sym, 'error': str(e)})

    return jsonify(results if len(results) > 1 else results[0])

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
