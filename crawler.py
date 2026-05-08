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
        # 抓取最近 10 天，確保能定位到最後一個有效收盤價
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
    
    # 建立聯集名單：今日有的 + 該 ETF 歷史出現過的 (確保出清股也有當天價)
    universe_ids = set([s['id'] for s in holdings])
    if os.path.exists(folder):
        for f in os.listdir(folder):
            if f.endswith('.json'):
                try:
                    with open(os.path.join(folder, f), 'r') as j:
                        old = json.load(j)
                        for s in old.get('holdings', []): universe_ids.add(s['id'])
                except: continue
    
    # 抓取該日期當天的價格
    prices = get_yahoo_prices(etf_id, list(universe_ids), target_date)
    
    final_data = {
        "etf_id": etf_id,
        "date": target_date,
        "holdings": holdings,
        "market_prices": prices
    }
    
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

# --- ETF 爬蟲：群益 00982A (回歸原始穩定版) ---
def run_00982A(target_date):
    print("📡 啟動 00982A (群益) 採集...")
    # 嘗試兩種日期格式，因為群益 API 對格式很挑剔
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
                return # 成功就跳出
        except: continue
    print("❌ 00982A 採集失敗 (所有格式均無效)")

# --- ETF 爬蟲：中信 00995A ---
def run_00995A(target_date):
    print("📡 啟動 00995A (中信) 採集...")
    try:
        api_url = "https://www.ctbcinvestments.com/api/Etf/ETFHoldingWeight"
        params = {"token": "www.ctbcinvestments.com", "fundCode": "00653201"}
        r = requests.get(api_url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        details = r.json().get('Data', {}).get('FundAssetsDetail', [])
        stock_section = next((i for i in details if i.get('Code') == 'STOCK'), None)
        if stock_section:
            h = [{"id": s['code_'].strip(), "name": s['name_'], "share": float(s['qty_'].replace(',', ''))} 
                 for s in stock_section.get('Data', [])]
            process_and_save("00995A", h, target_date)
    except Exception as e: print(f"❌ 00995A 失敗: {e}")

if __name__ == "__main__":
    t_date = os.environ.get("TARGET_DATE", datetime.now().strftime("%Y-%m-%d"))
    run_00981A(t_date)
    run_00982A(t_date)
    run_00995A(t_date)
