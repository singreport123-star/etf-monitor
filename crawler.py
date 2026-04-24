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
    print(f"--- 啟動 Yahoo 報價引擎，目標標的數: {len(stock_ids)} ---")
    
    all_tickers = [f"{sid}.TW" for sid in stock_ids] + [f"{sid}.TWO" for sid in stock_ids]
    
    try:
        # 抓取最近 1 個月的歷史資料，確保絕對能拿到「最後一個有效收盤價」
        data = yf.download(all_tickers, period="1mo", interval="1d", group_by='ticker', progress=False)
        
        for sid in stock_ids:
            price = 0
            for suffix in ['.TW', '.TWO']:
                ticker = f"{sid}{suffix}"
                if ticker in data.columns.levels[0]:
                    try:
                        # 抓取最後一筆非空值的收盤價
                        series = data[ticker]['Close'].dropna()
                        if not series.empty:
                            price = round(float(series.iloc[-1]), 2)
                            break
                    except: continue
            prices[sid] = price
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
    
    # 1. 抓取今日成分股
    result["etfs"]["00981A"] = fetch_unified(m_date)
    result["etfs"]["00982A"] = fetch_capital(ad_date)
    
    # 2. 獲取股價清單 (今日有的 + 昨天存檔裡有的)
    price_target_ids = set()
    for etf in result["etfs"].values():
        for s in etf: price_target_ids.add(s['id'])
    
    # 讀取 list.json 找上一個存檔，把昨天有但今天被賣掉的 ID 加進來抓價
    if os.path.exists('list.json'):
        with open('list.json', 'r') as f:
            history = json.load(f)
            if history:
                last_file = f"data/{history[0]}.json" # 注意：此時 list.json 還沒被 Actions 更新，所以 history[0] 是上一次的日期
                if os.path.exists(last_file):
                    with open(last_file, 'r') as lf:
                        past_data = json.load(lf)
                        for e_name in ["00981A", "00982A"]:
                            for s in past_data.get('etfs', {}).get(e_name, []):
                                price_target_ids.add(s['id'])

    # 3. 抓取所有相關股價
    result["market_prices"] = get_yahoo_prices(list(price_target_ids), ad_date)
    
    os.makedirs('data', exist_ok=True)
    with open(f"data/{ad_date}.json", 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
