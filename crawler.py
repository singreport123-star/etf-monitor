import requests
import json
import os
import yfinance as yf
from datetime import datetime, timedelta

# --- 核心邏輯：確保價格絕對有抓到 ---
def get_yahoo_prices(stock_ids, target_date_str):
    prices = {}
    if not stock_ids: return {}
    clean_ids = list(set([str(sid).strip() for sid in stock_ids if sid]))
    print(f"--- 抓取 {target_date_str} 價格 (共 {len(clean_ids)} 檔) ---")
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

# --- 標準化存檔：分資料夾存放 ---
def save_etf_isolated(etf_id, holdings, target_date):
    folder = f"data/{etf_id}"
    os.makedirs(folder, exist_ok=True)
    
    # 聯集邏輯：今日 + 歷史 (確保出清股也有當天價)
    union_ids = set([s['id'] for s in holdings])
    if os.path.exists(folder):
        for f in os.listdir(folder):
            if f.endswith('.json'):
                try:
                    with open(os.path.join(folder, f), 'r') as j:
                        old = json.load(j)
                        for s in old.get('holdings', []): union_ids.add(s['id'])
                except: continue
    
    prices = get_yahoo_prices(list(union_ids), target_date)
    
    final_json = {
        "etf_id": etf_id,
        "date": target_date,
        "holdings": holdings,
        "market_prices": prices
    }
    
    with open(f"{folder}/{target_date}.json", 'w', encoding='utf-8') as f:
        json.dump(final_json, f, ensure_ascii=False, indent=4)
    print(f"🚀 {etf_id} 存檔完成：{folder}/{target_date}.json")

# --- 執行 00981A (統一) ---
def run_00981A(target_date):
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    m_date = f"{dt.year - 1911}/{dt.strftime('%m/%d')}"
    try:
        r = requests.post("https://www.ezmoney.com.tw/ETF/Transaction/GetPCF", 
                          json={"fundCode": "49YTW", "date": m_date, "specificDate": True}, timeout=15)
        h = [{"id": d['DetailCode'].strip(), "name": d['DetailName'], "share": d['Share']} 
             for item in r.json().get('asset', []) if item.get('AssetCode') == 'ST' for d in item.get('Details', [])]
        save_etf_isolated("00981A", h, target_date)
    except: print("❌ 00981A 採集失敗")

# --- 執行 00982A (群益) - 回歸最原始成功 POST 方式 ---
def run_00982A(target_date):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.post("https://www.capitalfund.com.tw/CFWeb/api/etf/buyback", 
                          json={"fundId": "399", "date": target_date}, headers=headers, timeout=15)
        stocks = r.json().get('data', {}).get('stocks', [])
        h = [{"id": s['stocNo'].strip(), "name": s['stocName'], "share": s['share']} for s in stocks]
        save_etf_isolated("00982A", h, target_date)
    except: print("❌ 00982A 採集失敗")

if __name__ == "__main__":
    t_date = os.environ.get("TARGET_DATE", datetime.now().strftime("%Y-%m-%d"))
    run_00981A(t_date)
    run_00982A(t_date)
