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
    # Usiamo v8 con range=1d interval=1m per avere i dati intraday di oggi
    # e chartPreviousClose che è la chiusura di ieri (dato corretto per la %)
    url = (
        f'https://query1.finance.yahoo.com/v8/finance/chart/'
        f'{requests.utils.quote(yf_symbol)}'
        f'?interval=1m&range=1d'
    )
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    data = r.json()
    result = data['chart']['result'][0]
    meta   = result['meta']

    # regularMarketPrice = prezzo corrente (o ultima chiusura se mercato chiuso)
    price = meta.get('regularMarketPrice', 0)

    # chartPreviousClose = chiusura di IERI — questo è il riferimento corretto
    prev  = meta.get('chartPreviousClose', price)

    # Se non disponibile usa previousClose
    if not prev:
        prev = meta.get('previousClose', price)

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
            results.append({'code': sym, 'error': str(e), 'close': 0, 'change': 0, 'change_p': 0})

    return jsonify(results if len(results) > 1 else results[0])

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
