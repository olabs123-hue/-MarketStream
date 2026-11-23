from fastapi.testclient import TestClient
from backend.app import app, generate_path, snapshot


def test_health_and_markets():
    with TestClient(app) as c:
        assert c.get('/health').json() == {'status': 'ok', 'mode': 'simulation'}
        markets = c.get('/api/markets').json()
        assert len(markets) == 3
        assert all('reference_price' in x for x in markets)


def test_history_is_deterministic():
    assert generate_path('BTC-USD') == generate_path('BTC-USD')
    with TestClient(app) as c:
        assert len(c.get('/api/history/ETH-USD').json()['prices']) == 36
        assert c.get('/api/history/UNKNOWN').status_code == 404


def test_depth_ordering_and_spread():
    book = snapshot('BTC-USD', 68000, 3)
    assert book['simulated'] is True
    assert book['sequence'] == 3
    assert all(book['bids'][i][0] > book['bids'][i+1][0] for i in range(7))
    assert all(book['asks'][i][0] < book['asks'][i+1][0] for i in range(7))
    assert book['bids'][0][0] < book['asks'][0][0]


def test_websocket_first_message():
    with TestClient(app) as c:
        with c.websocket_connect('/ws/SOL-USD') as ws:
            data = ws.receive_json()
            assert data['symbol'] == 'SOL-USD'
            assert data['sequence'] == 0
            assert data['simulated'] is True
