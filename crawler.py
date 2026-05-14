import requests
import json
import os
import yfinance as yf
from datetime import datetime, timedelta

# --- 輔助工具：匯率引擎 ---
def get_fx_rate(target_date_dt):
    """抓取指定日期的美金對台幣收盤匯率"""
    try:
        fx_code = "USDTWD=X"
        data = yf.download(fx_code, 
                           start=(target_date_dt - timedelta(days=7)).strftime("%Y-%m-%d"),
                           end=(target_date_dt + timedelta(days=1)).strftime("%Y-%m-%d"), 
                           auto_adjust=False, progress=False)
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except: pass
    return 31.5  # 萬一失敗的保底匯率

# --- 核心邏輯：股價對齊 (支持美股自動換匯) ---
def get_yahoo_prices(etf_id, stock_ids, target_date_str):
    prices = {}
    if not stock_ids: return {}
    clean_ids = list(set([str(sid).strip() for sid in stock_ids if sid]))
    dt = datetime.strptime(target_date_str, "%Y-%m-%d")
    
    # 判斷是否需要換匯 (只有 00988A 需要)
    fx_rate = get_fx_rate(dt) if etf_id == "00988A" else 1.0
    print(f"--- [{etf_id}] 抓取 {target_date_str} 價格 (基準匯率: {fx_rate:.2f}) ---")
    
    # 建立 Yahoo Ticker 映射表
    ticker_map = {}
    for sid in clean_ids:
        if " US" in sid:
            yahoo_ticker = sid.split(" ")[0]
            ticker_map[yahoo_ticker] = {"id": sid, "is_us": True}
        else:
            # 台股嘗試兩種後綴
            ticker_map[f"{sid}.TW"] = {"id": sid, "is_us": False}
            ticker_map[f"{sid}.TWO"] = {"id": sid, "is_us": False}

    tickers = list(ticker_map.keys())
    try:
        data = yf.download(tickers, 
                           start=(dt - timedelta(days=10)).strftime("%Y-%m-%d"), 
                           end=(dt + timedelta(days=1)).strftime("%Y-%m-%d"), 
                           group_by='ticker', auto_adjust=False, progress=False)
        
        for yt, info in ticker_map.items():
            sid = info["id"]
            if yt in data.columns.levels[0]:
                series = data[yt]['Close'].dropna()
                if not series.empty:
                    # 如果已經有值(例如 .TW 抓到了)就跳過 .TWO
                    if sid in prices and prices[sid] > 0: continue
                    
                    raw_price = float(series.iloc[-1])
                    # 美股自動乘以匯率
                    final_price = round(raw_price * fx_rate, 2) if info["is_us"] else round(raw_price, 2)
                    prices[sid] = final_price
    except Exception as e:
        print(f"⚠️ Yahoo 抓取異常: {e}")
        
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
    print(f"✅ {etf_id} 數據存檔成功")

# --- ETF 爬蟲：統一系列 (00981A, 00988A) ---
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

# --- ETF 爬蟲：群益 00982A ---
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

# --- ETF 爬蟲：中信 00995A ---
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
    run_uni_etf("00988A", "61YTW", t_date) # 支援美股換匯的新爬蟲
    run_00982A(t_date)
    run_00995A(t_date)
