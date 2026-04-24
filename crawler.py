import requests
import json
import os
import yfinance as yf
from datetime import datetime, timedelta
import time

def get_dates(target_date_str):
    dt = datetime.strptime(target_date_str, "%Y-%m-%d")
    return dt.strftime("%Y-%m-%d"), f"{dt.year - 1911}/{dt.strftime('%m/%d')}"

def get_yahoo_prices(stock_ids, target_date_str):
    prices = {}
    if not stock_ids: return {}
    
    # 確保代碼唯一且不為空
    stock_ids = list(set([str(sid).strip() for sid in stock_ids if sid]))
    print(f"--- 暴力抓取清單 (共 {len(stock_ids)} 檔): {stock_ids} ---")
    
    all_tickers = [f"{sid}.TW" for sid in stock_ids] + [f"{sid}.TWO" for sid in stock_ids]
    
    try:
        # 抓取最近 10 天的歷史紀錄
        data = yf.download(all_tickers, period="10d", group_by='ticker', progress=False)
        
        for sid in stock_ids:
            price = 0
            for suffix in ['.TW', '.TWO']:
                ticker = f"{sid}{suffix}"
                if ticker in data.columns.levels[0]:
                    series = data[ticker]['Close'].dropna()
                    if not series.empty:
                        price = round(float(series.iloc[-1]), 2)
                        break
            # 存入結果，如果真的抓不到就給 0
            prices[sid] = price
            if price == 0: print(f"❌ 無法從 Yahoo 獲取價格: {sid}")
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
    try:
        result["etfs"]["00981A"] = fetch_unified(m_date)
        result["etfs"]["00982A"] = fetch_capital(ad_date)
    except: pass

    # 2. 暴力掃描：把所有的標的代號全部挖出來
    all_known_ids = set()
    for etf_data in result["etfs"].values():
        for s in etf_data: all_known_ids.add(s['id'])
    
    # 從現有的 data/ 資料夾內找標的
    if os.path.exists('data'):
        for file in os.listdir('data'):
            if file.endswith('.json'):
                try:
                    with open(f'data/{file}', 'r') as f:
                        old_data = json.load(f)
                        for e_data in old_data.get('etfs', {}).values():
                            for s in e_data: all_known_ids.add(s['id'])
                except: continue

    # 3. 執行抓取
    result["market_prices"] = get_yahoo_prices(list(all_known_ids), ad_date)
    
    # 4. 存檔
    os.makedirs('data', exist_ok=True)
    with open(f"data/{ad_date}.json", 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
