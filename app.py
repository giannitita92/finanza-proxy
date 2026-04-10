from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from datetime import timezone, timedelta

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
    # Tassi di interesse - formato Yahoo Finance
    'EURIBOR1M.INDEX': 'EURIBOR1MD=X',
    'EURSW30Y.INDEX':  'EURSW30Y=X',
    'BMPS.MI': 'BMPS.MI',
    'ISP.MI':  'ISP.MI',
    'LDO.MI':  'LDO.MI',
    'BAMI.MI': 'BAMI.MI',
    'G.MI':    'G.MI',
    'UCG.MI':  'UCG.MI',
    'PST.MI':  'PST.MI',
    'ENEL.MI': 'ENEL.MI',
    'MB.MI':   'MB.MI',
    '1EL.MI':  '1EL.MI',
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

    # Converti timestamp UTC → ora di Roma (CET=UTC+1, CEST=UTC+2)
    # Usiamo offset fisso +1 (invernale); per semplicità aggiungiamo 1h e lasciamo
    # che il frontend mostri l'ora locale del server (già ok per Milano)
    # In realtà passiamo il ts originale e formattiamo lato JS con timeZone:'Europe/Rome'
    candles = []
    for i, ts in enumerate(timestamps):
        if i >= len(closes) or closes[i] is None:
            continue
        candles.append({
            't': ts,  # Unix timestamp UTC — il frontend converte con timeZone Europe/Rome
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

@app.route('/portfolio_history')
def portfolio_history():
    """
    Calcola il valore storico del portafoglio giorno per giorno.
    Riceve: positions = lista di {symbol, qty, avgPrice, startDate}
    Ritorna: serie temporale di {date, value, invested, pl, plPct}
    """
    import json
    from datetime import datetime, timedelta

    try:
        positions_raw = request.args.get('positions', '')
        if not positions_raw:
            return jsonify({'error': 'positions required'}), 400
        positions = json.loads(positions_raw)
    except Exception as e:
        return jsonify({'error': f'invalid positions: {e}'}), 400

    # Scarica storico per ogni titolo dal 2025-08-26 (primo acquisto)
    all_closes = {}  # symbol -> {date_str -> close}

    for pos in positions:
        sym = pos['symbol']  # es. BMPS.MI
        try:
            hist = fetch_yahoo_history(sym, '1d', '1y')
            closes = {}
            for c in hist['candles']:
                from datetime import timezone
                dt = datetime.fromtimestamp(c['t'], tz=timezone.utc)
                date_str = dt.strftime('%Y-%m-%d')
                closes[date_str] = c['c']
            all_closes[sym] = closes
        except Exception as e:
            all_closes[sym] = {}

    # Costruisci serie giornaliera dal 2025-08-26 ad oggi
    start = datetime(2025, 8, 26)
    end   = datetime.now()
    series = []
    current = start

    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        # Skip weekend
        if current.weekday() < 5:
            total_value    = 0.0
            total_invested = 0.0
            has_data       = False

            for pos in positions:
                sym       = pos['symbol']
                qty       = pos['qty']
                avg_price = pos['avgPrice']
                start_date= pos['startDate']  # 'YYYY-MM-DD'

                # Prima dell'acquisto questo titolo non è in portafoglio
                if date_str < start_date:
                    continue

                invested = qty * avg_price
                closes   = all_closes.get(sym, {})

                # Cerca il prezzo del giorno (o il più recente disponibile)
                price = closes.get(date_str)
                if price is None:
                    # Cerca il giorno lavorativo precedente più vicino
                    for days_back in range(1, 8):
                        prev_date = (current - timedelta(days=days_back)).strftime('%Y-%m-%d')
                        if prev_date in closes:
                            price = closes[prev_date]
                            break

                if price is not None:
                    total_value    += qty * price
                    total_invested += invested
                    has_data        = True

            if has_data and total_invested > 0:
                pl     = total_value - total_invested
                pl_pct = (pl / total_invested) * 100
                series.append({
                    'date':     date_str,
                    'value':    round(total_value, 2),
                    'invested': round(total_invested, 2),
                    'pl':       round(pl, 2),
                    'plPct':    round(pl_pct, 4),
                })

        current += timedelta(days=1)

    # Calcola min/max P&L
    if series:
        pl_values = [s['pl'] for s in series]
        pct_values = [s['plPct'] for s in series]
        stats = {
            'maxPl':    max(pl_values),
            'minPl':    min(pl_values),
            'maxPct':   max(pct_values),
            'minPct':   min(pct_values),
            'maxDate':  series[pl_values.index(max(pl_values))]['date'],
            'minDate':  series[pl_values.index(min(pl_values))]['date'],
        }
    else:
        stats = {}

    return jsonify({'series': series, 'stats': stats})


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
