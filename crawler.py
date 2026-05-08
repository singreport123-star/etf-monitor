import requests
import json
import os
import yfinance as yf
from datetime import datetime, timedelta

# --- 核心邏輯：股價對齊 (聯集歷史標的) ---
def get_yahoo_prices(etf_id, stock_ids, target_date_str):
    prices = {}
    if not stock_ids: return {}
    clean_ids = list(set([str(sid).strip() for sid in stock_ids if sid]))
    print(f"--- [{etf_id}] 抓取 {target_date_str} 價格 (共 {len(clean_ids)} 檔) ---")
    
    tickers = [f"{sid}.TW" for sid in clean_ids] + [f"{sid}.TWO" for sid in clean_ids]
    try:
        dt = datetime.strptime(target_date_str, "%Y-%m-%d")
        data = yf.download(tickers, start=(dt - timedelta(days=10)).strftime("%Y-%m-%d"), 
                           end=(dt + timedelta(days=1)).strftime("%Y-%m-%d"), group_by='ticker', progress=False)
        for sid in clean_ids:
            p = 0
            for suffix in ['.TW', '.TWO']:
                t = f"{sid}{suffix}"
                if t in data.columns.levels[0]:
                    series = data[t]['Close'].dropna()
                    if not series.empty: p = round(float(series.iloc[-1]), 2); break
            prices[sid] = p
    except: pass
    return prices

# --- 標準化存檔流程 ---
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
    print(f"✅ {etf_id} 數據存檔成功：{folder}/{target_date}.json")

# --- ETF 爬蟲：統一 00981A ---
def run_00981A(target_date):
    print("📡 啟動 00981A (統一) 採集...")
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    m_date = f"{dt.year - 1911}/{dt.strftime('%m/%d')}"
    try:
        r = requests.post("https://www.ezmoney.com.tw/ETF/Transaction/GetPCF", 
                          json={"fundCode": "49YTW", "date": m_date, "specificDate": True}, timeout=15)
        h = [{"id": d['DetailCode'].strip(), "name": d['DetailName'], "share": d['Share']} 
             for item in r.json().get('asset', []) if item.get('AssetCode') == 'ST' for d in item.get('Details', [])]
        process_and_save("00981A", h, target_date)
    except Exception as e: print(f"❌ 00981A 失敗: {e}")

# --- ETF 爬蟲：群益 00982A ---
def run_00982A(target_date):
    print("📡 啟動 00982A (群益) 採集...")
    formats = [target_date, target_date.replace("-", "/")]
    for fmt in formats:
        try:
            r = requests.post("https://www.capitalfund.com.tw/CFWeb/api/etf/buyback", 
                              json={"fundId": "399", "date": fmt}, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            data = r.json()
            stocks = data.get('data', {}).get('stocks', [])
            if stocks:
                h = [{"id": s['stocNo'].strip(), "name": s['stocName'], "share": s['share']} for s in stocks]
                process_and_save("00982A", h, target_date)
                return 
        except: continue
    print("❌ 00982A 採集失敗")

# --- ETF 爬蟲：中信 00995A (POST 修正版) ---
def run_00995A(target_date):
    print("📡 啟動 00995A (中信) 採集...")
    session = requests.Session()
    base_url = "https://www.ctbcinvestments.com.tw/API"
    std_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.ctbcinvestments.com.tw/Etf/00653201/Combination"
    }
    try:
        # 1. 取得 AuthToken (修正為 POST)
        auth_url = f"{base_url}/home/AuthToken"
        auth_res = session.post(auth_url, params={"token": "www.ctbcinvestments.com"}, json={"token": "www.ctbcinvestments.com"}, headers=std_headers, timeout=15)
        
        if auth_res.status_code != 200:
            print(f"❌ AuthToken 請求失敗，狀態碼: {auth_res.status_code}")
            return
            
        dynamic_token = auth_res.json().get('Data', {}).get('token', '')
        if not dynamic_token:
            print("❌ 無法獲取有效 Token")
            return

        # 2. 取得持股權重 (token 同時放 URL query string 與 JSON body，StartDate 用當下 UTC 時間)
        api_url = f"{base_url}/etf/ETFHoldingWeight"
        now = datetime.utcnow()
        iso_date = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
        payload = {"FID": "E0036", "StartDate": iso_date, "token": dynamic_token}
        
        r = session.post(api_url, params={"token": dynamic_token}, json=payload, headers=std_headers, timeout=20)
        res_json = r.json()
        
        details = res_json.get('Data', {}).get('FundAssetsDetail', [])
        stock_section = next((i for i in details if i.get('Code') == 'STOCK'), None)
        
        if stock_section and stock_section.get('Data'):
            h = [{"id": s['code_'].strip(), "name": s['name_'], "share": float(s['qty_'].replace(',', ''))} 
                 for s in stock_section.get('Data', [])]
            process_and_save("00995A", h, target_date)
        else:
            print(f"⚠️ 00995A 在 {target_date} 查無持股數據")
            
    except Exception as e:
        print(f"❌ 00995A 執行異常: {e}")

if __name__ == "__main__":
    t_date = os.environ.get("TARGET_DATE", datetime.now().strftime("%Y-%m-%d"))
    run_00981A(t_date)
    run_00982A(t_date)
    run_00995A(t_date)
