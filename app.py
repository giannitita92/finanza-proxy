from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

EODHD_KEY = '69d622b9205744.40064343'
EODHD_BASE = 'https://eodhd.com/api/real-time'

@app.route('/quote')
def quote():
    symbol = request.args.get('symbol', '')
    extra  = request.args.get('s', '')
    if not symbol:
        return jsonify({'error': 'symbol required'}), 400
    params = {'api_token': EODHD_KEY, 'fmt': 'json'}
    if extra:
        params['s'] = extra
    try:
        r = requests.get(f'{EODHD_BASE}/{symbol}', params=params, timeout=10)
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
