import requests
import json
import os
import yfinance as yf
from datetime import datetime, timedelta

def get_dates(target_date_str):
    dt = datetime.strptime(target_date_str, "%Y-%m-%d")
    return dt.strftime("%Y-%m-%d"), f"{dt.year - 1911}/{dt.strftime('%m/%d')}"

def get_yahoo_prices(stock_ids, target_date_str):
    prices = {}
    if not stock_ids: return {}
    
    # 確保代碼是純數字且不重複
    clean_ids = list(set([str(sid).strip() for sid in stock_ids if str(sid).strip().isdigit()]))
    print(f"--- 執行全域股價補完計畫 (共 {len(clean_ids)} 檔) ---")
    
    all_tickers = [f"{sid}.TW" for sid in clean_ids] + [f"{sid}.TWO" for sid in clean_ids]
    
    try:
        # 抓取最近一個月的歷史紀錄，確保拿得到最後一個收盤價
        end_dt = datetime.strptime(target_date_str, "%Y-%m-%d") + timedelta(days=1)
        start_dt = end_dt - timedelta(days=30)
        data = yf.download(all_tickers, start=start_dt.strftime("%Y-%m-%d"), 
                           end=end_dt.strftime("%Y-%m-%d"), group_by='ticker', progress=False)
        
        for sid in clean_ids:
            price = 0
            for suffix in ['.TW', '.TWO']:
                ticker = f"{sid}{suffix}"
                if ticker in data.columns.levels[0]:
                    series = data[ticker]['Close'].dropna()
                    if not series.empty:
                        price = round(float(series.iloc[-1]), 2)
                        break
            # 如果還是 0，就回傳一個識別字串
            prices[sid] = price if price > 0 else "Yahoo無資料"
    except Exception as e:
        print(f"Yahoo 引擎異常: {e}")
    return prices

def fetch_unified(m_date):
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}
    session.get("https://www.ezmoney.com.tw/ETF/Transaction/PCF", headers=headers)
    res = session.post("https://www.ezmoney.com.tw/ETF/Transaction/GetPCF", 
                       json={"fundCode": "49YTW", "date": m_date, "specificDate": True}, headers=headers)
    return [{"id": d['DetailCode'].strip(), "name": d['DetailName'], "share": d['Share']} 
            for item in res.json().get('asset', []) if item.get('AssetCode') == 'ST' 
            for d in item.get('Details', [])]

def fetch_capital(ad_date):
    res = requests.post("https://www.capitalfund.com.tw/CFWeb/api/etf/buyback", 
                        json={"fundId": "399", "date": ad_date}, headers={"User-Agent": "Mozilla/5.0"})
    return [{"id": s['stocNo'].strip(), "name": s['stocName'], "share": s['share']} 
            for s in res.json().get('data', {}).get('stocks', [])]

if __name__ == "__main__":
    target_date = os.environ.get("TARGET_DATE", datetime.now().strftime("%Y-%m-%d"))
    ad_date, m_date = get_dates(target_date)
    result = {"date": ad_date, "etfs": {}, "market_prices": {}}
    
    # 1. 抓取今日標的
    result["etfs"]["00981A"] = fetch_unified(m_date)
    result["etfs"]["00982A"] = fetch_capital(ad_date)

    # 2. 暴力掃描所有歷史數據，建立「標的全宇宙」
    universe_ids = set()
    # 加入今天的新名單
    for etf in result["etfs"].values():
        for s in etf: universe_ids.add(s['id'])
    
    # 加入資料夾內所有舊標的
    if os.path.exists('data'):
        for file in os.listdir('data'):
            if file.endswith('.json'):
                try:
                    with open(f'data/{file}', 'r') as f:
                        old = json.load(f)
                        for e_data in old.get('etfs', {}).values():
                            for s in e_data: universe_ids.add(s['id'])
                except: continue

    # 3. 抓取這份全宇宙清單的價格
    result["market_prices"] = get_yahoo_prices(list(universe_ids), ad_date)
    
    os.makedirs('data', exist_ok=True)
    with open(f"data/{ad_date}.json", 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
