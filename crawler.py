import requests
import json
import os
import yfinance as yf
from datetime import datetime, timedelta

# --- 核心配置：全球市場對齊矩陣 ---
MARKET_MAP = {
    "US": {"suffix": "",     "fx": "USDTWD=X"},
    "JP": {"suffix": ".T",   "fx": "JPYTWD=X"},
    "KS": {"suffix": ".KS",  "fx": "KRWTWD=X"},
    "GY": {"suffix": ".DE",  "fx": "EURTWD=X"},
    "FP": {"suffix": ".PA",  "fx": "EURTWD=X"},
    "HK": {"suffix": ".HK",  "fx": "HKDTWD=X"},
    "CH": {"suffix": ".SS",  "fx": "CNYTWD=X"}, # 預設上海，代碼判斷在 resolver 處理
}

# --- 輔助工具：全球匯率引擎 ---
def get_global_fx_rates(target_date_dt):
    """批次獲取所有必要匯率"""
    fx_tickers = list(set([m["fx"] for m in MARKET_MAP.values()]))
    rates = {"TWD": 1.0}
    try:
        data = yf.download(fx_tickers, 
                           start=(target_date_dt - timedelta(days=7)).strftime("%Y-%m-%d"),
                           end=(target_date_dt + timedelta(days=1)).strftime("%Y-%m-%d"), 
                           auto_adjust=False, progress=False)
        if not data.empty:
            for fx in fx_tickers:
                # 取得該匯率最新收盤價
                if fx in data['Close']:
                    val = data['Close'][fx].dropna()
                    if not val.empty:
                        rates[fx] = float(val.iloc[-1])
    except: pass
    # 保底匯率，防止網路波動導致數據歸零
    return rates

# --- 核心邏輯：股價對齊 (支持八國聯軍標的) ---
def get_yahoo_prices(etf_id, stock_ids, target_date_str):
    prices = {}
    if not stock_ids: return {}
    clean_ids = list(set([str(sid).strip() for sid in stock_ids if sid]))
    dt = datetime.strptime(target_date_str, "%Y-%m-%d")
    
    # 獲取全球匯率矩陣
    fx_matrix = get_global_fx_rates(dt)
    print(f"--- [{etf_id}] 啟動全球價格對齊 (日期: {target_date_str}) ---")
    
    # 建立 Yahoo Ticker 映射表與匯率關聯
    ticker_map = {}
    for sid in clean_ids:
        # 1. 識別市場
        parts = sid.split(" ")
        ticker_base = parts[0]
        market_code = parts[1] if len(parts) > 1 else "TWD"
        
        if market_code in MARKET_MAP:
            # 全球標的處理
            m_cfg = MARKET_MAP[market_code]
            suffix = m_cfg["suffix"]
            # 中國市場特殊判斷: 60xxxx 為上海(.SS), 其餘為深圳(.SZ)
            if market_code == "CH" and not ticker_base.startswith("60"):
                suffix = ".SZ"
            
            yahoo_ticker = f"{ticker_base}{suffix}"
            ticker_map[yahoo_ticker] = {"id": sid, "fx_key": m_cfg["fx"]}
        else:
            # 台灣標的處理 (保留原有的雙後綴嘗試邏輯)
            ticker_map[f"{sid}.TW"] = {"id": sid, "fx_key": "TWD"}
            ticker_map[f"{sid}.TWO"] = {"id": sid, "fx_key": "TWD"}

    tickers = list(ticker_map.keys())
    try:
        data = yf.download(tickers, 
                           start=(dt - timedelta(days=10)).strftime("%Y-%m-%d"), 
                           end=(dt + timedelta(days=1)).strftime("%Y-%m-%d"), 
                           group_by='ticker', auto_adjust=False, progress=False)
        
        for yt, info in ticker_map.items():
            sid = info["id"]
            fx_val = fx_matrix.get(info["fx_key"], 1.0)
            
            # yfinance 多標的結構處理
            df = data[yt] if len(tickers) > 1 else data
            if 'Close' in df:
                series = df['Close'].dropna()
                if not series.empty:
                    if sid in prices and prices[sid] > 0: continue # 避免 .TW/.TWO 重複
                    raw_p = float(series.iloc[-1])
                    prices[sid] = round(raw_p * fx_val, 2)
                    
    except Exception as e:
        print(f"⚠️ Yahoo 全球抓取異常: {e}")
        
    return prices

# --- 標準化存檔流程 (維持標的隔離) ---
def process_and_save(etf_id, holdings, target_date):
    folder = f"data/{etf_id}"
    os.makedirs(folder, exist_ok=True)
    
    universe_ids = set([s['id'] for s in holdings])
    if os.path.exists(folder):
        for f in os.listdir(folder):
            if f.endswith('.json'):
                try:
                    with open(os.path.join(folder, f), 'r') as j:
                        old = json.load(j)
                        for s in old.get('holdings', []): universe_ids.add(s['id'])
                except: continue
    
    prices = get_yahoo_prices(etf_id, list(universe_ids), target_date)
    final_data = {"etf_id": etf_id, "date": target_date, "holdings": holdings, "market_prices": prices}
    
    with open(f"{folder}/{target_date}.json", 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=4)
    print(f"✅ {etf_id} 全球數據存檔成功：{folder}/{target_date}.json")

# --- ETF 爬蟲模組 ---
def run_uni_etf(etf_id, fund_code, target_date):
    print(f"📡 啟動 {etf_id} 採集...")
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    m_date = f"{dt.year - 1911}/{dt.strftime('%m/%d')}"
    try:
        r = requests.post("https://www.ezmoney.com.tw/ETF/Transaction/GetPCF", 
                          json={"fundCode": fund_code, "date": m_date, "specificDate": True}, timeout=15)
        h = [{"id": d['DetailCode'].strip(), "name": d['DetailName'], "share": d['Share']} 
             for item in r.json().get('asset', []) if item.get('AssetCode') == 'ST' for d in item.get('Details', [])]
        if h: process_and_save(etf_id, h, target_date)
    except Exception as e: print(f"❌ {etf_id} 失敗: {e}")

def run_00982A(target_date):
    print("📡 啟動 00982A 採集...")
    formats = [target_date, target_date.replace("-", "/")]
    for fmt in formats:
        try:
            r = requests.post("https://www.capitalfund.com.tw/CFWeb/api/etf/buyback", 
                              json={"fundId": "399", "date": fmt}, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            stocks = r.json().get('data', {}).get('stocks', [])
            if stocks:
                h = [{"id": s['stocNo'].strip(), "name": s['stocName'], "share": s['share']} for s in stocks]
                process_and_save("00982A", h, target_date)
                return 
        except: continue

def run_00995A(target_date):
    print("📡 啟動 00995A 採集...")
    session = requests.Session()
    std_headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.ctbcinvestments.com.tw/"}
    try:
        auth_res = session.post("https://www.ctbcinvestments.com.tw/API/home/AuthToken", params={"token": "www.ctbcinvestments.com"}, json={"token": "www.ctbcinvestments.com"}, headers=std_headers, timeout=15)
        token = auth_res.json().get('Data', {}).get('token', '')
        if not token: return
        now = datetime.utcnow()
        iso_date = f"{target_date}T{now.strftime('%H:%M:%S.%f')[:-3]}Z"
        r = session.post("https://www.ctbcinvestments.com.tw/API/etf/ETFHoldingWeight", params={"token": token}, json={"FID": "E0036", "StartDate": iso_date, "token": token}, headers=std_headers, timeout=20)
        details = r.json().get('Data', {}).get('FundAssetsDetail', [])
        stock_section = next((i for i in details if i.get('Code') == 'STOCK'), None)
        if stock_section:
            h = [{"id": s['code_'].strip(), "name": s['name_'], "share": float(s['qty_'].replace(',', ''))} for s in stock_section.get('Data', [])]
            process_and_save("00995A", h, target_date)
    except Exception as e: print(f"❌ 00995A 失敗: {e}")

if __name__ == "__main__":
    t_date = os.environ.get("TARGET_DATE", datetime.now().strftime("%Y-%m-%d"))
    run_uni_etf("00981A", "49YTW", t_date)
    run_uni_etf("00988A", "61YTW", t_date) # 支援全球標的與自動換匯
    run_00982A(t_date)
    run_00995A(t_date)
