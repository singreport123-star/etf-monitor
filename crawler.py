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
    print(f"--- 正在透過 Yahoo Finance 抓取 {target_date_str} 股價 ---")
    all_tickers = [f"{sid}.TW" for sid in stock_ids] + [f"{sid}.TWO" for sid in stock_ids]
    try:
        start_dt = datetime.strptime(target_date_str, "%Y-%m-%d")
        end_dt = start_dt + timedelta(days=1)
        data = yf.download(all_tickers, start=start_dt.strftime("%Y-%m-%d"), 
                           end=end_dt.strftime("%Y-%m-%d"), group_by='ticker', progress=False)
        for sid in stock_ids:
            price = 0
            for suffix in ['.TW', '.TWO']:
                ticker = f"{sid}{suffix}"
                if ticker in data.columns.levels[0]:
                    try:
                        val = data[ticker]['Close'].iloc[0]
                        if str(val) != 'nan':
                            price = round(float(val), 2)
                            break
                    except: continue
            prices[sid] = price
    except Exception as e: print(f"⚠️ Yahoo 抓取異常: {e}")
    return prices

def fetch_unified(m_date):
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}
    session.get("https://www.ezmoney.com.tw/ETF/Transaction/PCF", headers=headers)
    res = session.post("https://www.ezmoney.com.tw/ETF/Transaction/GetPCF", 
                       json={"fundCode": "49YTW", "date": m_date, "specificDate": True}, headers=headers)
    stocks = []
    for item in res.json().get('asset', []):
        if item.get('AssetCode') == 'ST':
            for d in item.get('Details', []):
                stocks.append({"id": d['DetailCode'].strip(), "name": d['DetailName'], "share": d['Share']})
    return stocks

def fetch_capital(ad_date):
    res = requests.post("https://www.capitalfund.com.tw/CFWeb/api/etf/buyback", 
                        json={"fundId": "399", "date": ad_date}, headers={"User-Agent": "Mozilla/5.0"})
    return [{"id": s['stocNo'].strip(), "name": s['stocName'], "share": s['share']} for s in res.json().get('data', {}).get('stocks', [])]

if __name__ == "__main__":
    target_date = os.environ.get("TARGET_DATE", datetime.now().strftime("%Y-%m-%d"))
    ad_date, m_date = get_dates(target_date)
    result = {"date": ad_date, "etfs": {}, "market_prices": {}}
    
    # 核心修正：抓取「今天有」+「上次有」的所有 ID
    current_ids = set()
    result["etfs"]["00981A"] = fetch_unified(m_date)
    result["etfs"]["00982A"] = fetch_capital(ad_date)
    for etf in result["etfs"].values():
        for s in etf: current_ids.add(s['id'])
    
    # 嘗試讀取上一次的存檔來補齊 ID (避免出清股沒價格)
    if os.path.exists('list.json'):
        with open('list.json', 'r') as f:
            past_dates = json.load(f)
            if past_dates:
                last_file = f"data/{past_dates[0]}.json"
                if os.path.exists(last_file):
                    with open(last_file, 'r') as lf:
                        past_data = json.load(lf)
                        for etf_data in past_data.get('etfs', {}).values():
                            for s in etf_data: current_ids.add(s['id'])

    result["market_prices"] = get_yahoo_prices(list(current_ids), ad_date)
    os.makedirs('data', exist_ok=True)
    with open(f"data/{ad_date}.json", 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
