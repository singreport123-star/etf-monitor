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
    print(f"--- 啟動全歷史標的追蹤 (數量: {len(stock_ids)}) ---")
    
    # 建立台股代碼池
    all_tickers = [f"{sid}.TW" for sid in stock_ids] + [f"{sid}.TWO" for sid in stock_ids]
    
    try:
        # 抓取最近 7 天，確保遇到連假也能拿到最後一個有效收盤價
        end_dt = datetime.strptime(target_date_str, "%Y-%m-%d") + timedelta(days=1)
        start_dt = end_dt - timedelta(days=7)
        
        data = yf.download(all_tickers, start=start_dt.strftime("%Y-%m-%d"), 
                           end=end_dt.strftime("%Y-%m-%d"), group_by='ticker', progress=False)
        
        for sid in stock_ids:
            price = 0
            for suffix in ['.TW', '.TWO']:
                ticker = f"{sid}{suffix}"
                if ticker in data.columns.levels[0]:
                    try:
                        series = data[ticker]['Close'].dropna()
                        if not series.empty:
                            price = round(float(series.iloc[-1]), 2)
                            break
                    except: continue
            prices[sid] = price
            if price == 0: print(f"⚠️ 警告：標的 {sid} 抓不到價格")
    except Exception as e:
        print(f"❌ Yahoo 引擎異常: {e}")
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
    
    # 1. 抓取今天的成分股
    result["etfs"]["00981A"] = fetch_unified(m_date)
    result["etfs"]["00982A"] = fetch_capital(ad_date)
    
    # 2. 獲取股價清單 (今日有的 + 歷史出現過的)
    all_known_ids = set()
    # 加入今日名單
    for etf in result["etfs"].values():
        for s in etf: all_known_ids.add(s['id'])
    
    # 掃描歷史檔案，把以前出現過、但今天被賣掉的股票也找回來抓價
    data_dir = 'data'
    if os.path.exists(data_dir):
        for filename in os.listdir(data_dir):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(data_dir, filename), 'r') as f:
                        past_data = json.load(f)
                        for e_name in ["00981A", "00982A"]:
                            for s in past_data.get('etfs', {}).get(e_name, []):
                                all_known_ids.add(s['id'])
                except: continue

    # 3. 抓取這份全歷史名單的股價
    result["market_prices"] = get_yahoo_prices(list(all_known_ids), ad_date)
    
    os.makedirs('data', exist_ok=True)
    with open(f"data/{ad_date}.json", 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
