import ccxt
import pandas as pd
import time
from datetime import datetime, UTC
print(datetime.now(UTC))

# ---------------- CONFIG ----------------
symbol = 'BTC/USDT:USDT'
timeframe = '5m'
sl_pct = 0.004
risk_per_trade = 0.02

# ---------------- API ----------------
exchange = ccxt.bybit({
    'apiKey': 'Lf5fqi9HfapfKMuqRc',
    'secret': 'C4Xz4rD2O1IMeu87etTKx44Q2uEGD2KbIEbc',
    'enableRateLimit': True,
    'options': {
        'defaultType': 'swap',
        'defaultSubType': 'linear'
    }
})

exchange.set_sandbox_mode(True)

# ---------------- HELPERS ----------------

def is_strong_candle(row):
    body = abs(row['close'] - row['open'])
    rng = row['high'] - row['low']
    return body / rng > 0.6 if rng > 0 else False

def swing_high(df, i, lookback=10):
    return df['high'][i] == max(df['high'][i-lookback:i+1])

def swing_low(df, i, lookback=10):
    return df['low'][i] == min(df['low'][i-lookback:i+1])

def volatility_ok(df, i):
    recent = df['high'][i-20:i].max() - df['low'][i-20:i].min()
    return recent > df['close'][i] * 0.0015

def session_ok(hour):
    return (7 <= hour <= 16) or (13 <= hour <= 22)

def fetch_data():
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=100)
    df = pd.DataFrame(bars, columns=['time','open','high','low','close','volume'])
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    df['hour'] = df['time'].dt.hour
    return df

# ---------------- POSITION CHECK ----------------

def get_position():
    try:
        positions = exchange.fetch_positions([symbol])
        for p in positions:
            if float(p['contracts']) > 0:
                return p
    except:
        return None
    return None

# ---------------- SIGNAL ----------------

def check_signal(df):
    i = len(df) - 3
    row = df.iloc[i]

    if not session_ok(row['hour']):
        return None

    if not volatility_ok(df, i):
        return None

    # LONG
    if swing_high(df, i-2):
        level = df['high'][i-2]

        if df['high'][i-1] > level and df['close'][i-1] < level:
            if is_strong_candle(df.iloc[i]) and is_strong_candle(df.iloc[i+1]):

                entry = df['close'][i+1]
                sl = entry * (1 - sl_pct)
                tp = max(df['high'][i-20:i])

                rr = (tp - entry) / (entry - sl)

                if rr >= 1.3:
                    return 'buy', entry, sl, tp

    # SHORT
    elif swing_low(df, i-2):
        level = df['low'][i-2]

        if df['low'][i-1] < level and df['close'][i-1] > level:
            if is_strong_candle(df.iloc[i]) and is_strong_candle(df.iloc[i+1]):

                entry = df['close'][i+1]
                sl = entry * (1 + sl_pct)
                tp = min(df['low'][i-20:i])

                rr = (entry - tp) / (sl - entry)

                if rr >= 1.3:
                    return 'sell', entry, sl, tp

    return None

# ---------------- EXECUTION ----------------

def place_trade(side, entry, sl, tp):
    balance = exchange.fetch_balance()
    usdt = balance['USDT']['free']

    risk_amount = usdt * risk_per_trade
    qty = risk_amount / abs(entry - sl)

    qty = round(qty, 3)

    print(f"\n🚀 TRADE: {side.upper()}")
    print("Entry:", entry)
    print("SL:", sl)
    print("TP:", tp)

    exchange.create_market_order(symbol, side, qty)

    opposite = 'sell' if side == 'buy' else 'buy'

    # SL
    exchange.create_order(
        symbol,
        'STOP_MARKET',
        opposite,
        qty,
        params={'stopPrice': sl, 'reduceOnly': True}
    )

    # TP
    exchange.create_order(
        symbol,
        'TAKE_PROFIT_MARKET',
        opposite,
        qty,
        params={'stopPrice': tp, 'reduceOnly': True}
    )

# ---------------- MAIN LOOP ----------------

print("🤖 BOT RUNNING ON BYBIT TESTNET...")

while True:
    try:
        df = fetch_data()
        pos = get_position()

        if pos:
            print("📊 Position active...")
        else:
            signal = check_signal(df)

            if signal:
                side, entry, sl, tp = signal
                place_trade(side, entry, sl, tp)
            else:
                print(f"No signal... {datetime.now(UTC)}")

    except Exception as e:
        print("Error:", e)

    time.sleep(60)
