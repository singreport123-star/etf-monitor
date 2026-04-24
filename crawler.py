import requests
import json
import os
import yfinance as yf
from datetime import datetime, timedelta
import time

def get_dates(target_date_str):
    dt = datetime.strptime(target_date_str, "%Y-%m-%d")
    ad_date = dt.strftime("%Y-%m-%d")
    m_year = dt.year - 1911
    m_date = f"{m_year}/{dt.strftime('%m/%d')}"
    return ad_date, m_date

def get_yahoo_prices(stock_ids, target_date_str):
    prices = {}
    print(f"--- 正在透過 Yahoo Finance 抓取 {target_date_str} 股價 ---")
    
    tickers_tw = [f"{sid}.TW" for sid in stock_ids]
    tickers_two = [f"{sid}.TWO" for sid in stock_ids]
    all_tickers = tickers_tw + tickers_two
    
    try:
        start_dt = datetime.strptime(target_date_str, "%Y-%m-%d")
        end_dt = start_dt + timedelta(days=1)
        
        # 批量下載 (不印出進度條)
        data = yf.download(all_tickers, start=start_dt.strftime("%Y-%m-%d"), 
                           end=end_dt.strftime("%Y-%m-%d"), group_by='ticker', progress=False)
        
        for sid in stock_ids:
            price = 0
            for suffix in ['.TW', '.TWO']:
                ticker = f"{sid}{suffix}"
                if ticker in data.columns.levels[0]:
                    try:
                        day_data = data[ticker]
                        if not day_data.empty:
                            val = day_data['Close'].iloc[0]
                            if str(val) != 'nan':
                                price = round(float(val), 2)
                                break
                    except:
                        continue
            prices[sid] = price
        print(f"✅ 股價抓取完成")
    except Exception as e:
        print(f"⚠️ Yahoo 抓取異常: {e}")
    return prices

def fetch_unified(m_date):
    print(f"正在抓取 00981A (統一) - 日期: {m_date}")
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }
    session.get("https://www.ezmoney.com.tw/ETF/Transaction/PCF", headers=headers)
    api_url = "https://www.ezmoney.com.tw/ETF/Transaction/GetPCF"
    payload = {"fundCode": "49YTW", "date": m_date, "specificDate": True}
    res = session.post(api_url, json=payload, headers=headers)
    data = res.json()
    stocks = []
    for item in data.get('asset', []):
        if item.get('AssetCode') == 'ST':
            for d in item.get('Details', []):
                stocks.append({"id": d['DetailCode'].strip(), "name": d['DetailName'], "share": d['Share']})
    return stocks

def fetch_capital(ad_date):
    print(f"正在抓取 00982A (群益) - 日期: {ad_date}")
    url = "https://www.capitalfund.com.tw/CFWeb/api/etf/buyback"
    payload = {"fundId": "399", "date": ad_date}
    res = requests.post(url, json=payload, headers={"User-Agent": "Mozilla/5.0"})
    data = res.json()
    stocks = []
    for s in data.get('data', {}).get('stocks', []):
        stocks.append({"id": s['stocNo'].strip(), "name": s['stocName'], "share": s['share']})
    return stocks

if __name__ == "__main__":
    target_date = os.environ.get("TARGET_DATE", datetime.now().strftime("%Y-%m-%d"))
    ad_date, m_date = get_dates(target_date)
    
    result = {"date": ad_date, "etfs": {}, "market_prices": {}}
    
    # 執行採集
    try:
        result["etfs"]["00981A"] = fetch_unified(m_date)
        result["etfs"]["00982A"] = fetch_capital(ad_date)
        
        unique_ids = set()
        for etf in result["etfs"].values():
            for s in etf: unique_ids.add(s['id'])
        
        result["market_prices"] = get_yahoo_prices(list(unique_ids), ad_date)
        
        os.makedirs('data', exist_ok=True)
        with open(f"data/{ad_date}.json", 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=4)
        print(f"🎉 {ad_date} 採集存檔成功")
    except Exception as e:
        print(f"❌ 採集失敗: {e}")
