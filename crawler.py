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
    
    clean_ids = list(set([str(sid).strip() for sid in stock_ids if str(sid).strip().isdigit()]))
    print(f"--- 執行全宇宙標的價格補完 (共 {len(clean_ids)} 檔) ---")
    
    tickers = [f"{sid}.TW" for sid in clean_ids] + [f"{sid}.TWO" for sid in clean_ids]
    
    try:
        # 抓取最近 14 天的歷史紀錄，確保遇到長假也能拿到收盤價
        end_dt = datetime.strptime(target_date_str, "%Y-%m-%d") + timedelta(days=1)
        start_dt = end_dt - timedelta(days=14)
        data = yf.download(tickers, start=start_dt.strftime("%Y-%m-%d"), 
                           end=end_dt.strftime("%Y-%m-%d"), group_by='ticker', progress=False)
        
        for sid in clean_ids:
            p = 0
            for suffix in ['.TW', '.TWO']:
                t = f"{sid}{suffix}"
                if t in data.columns.levels[0]:
                    series = data[t]['Close'].dropna()
                    if not series.empty:
                        p = round(float(series.iloc[-1]), 2)
                        break
            prices[sid] = p if p > 0 else "Yahoo無資料"
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
    
    # 1. 抓取今日標的名單
    try:
        result["etfs"]["00981A"] = fetch_unified(m_date)
        result["etfs"]["00982A"] = fetch_capital(ad_date)
    except: pass

    # 2. 暴力聯集：確保「歷史出現過的標的」也必須在今天的價格名單中
    universe_ids = set()
    for etf_data in result["etfs"].values():
        for s in etf_data: universe_ids.add(s['id'])
    
    if os.path.exists('data'):
        for f in os.listdir('data'):
            if f.endswith('.json'):
                try:
                    with open(os.path.join('data', f), 'r') as j:
                        old_data = json.load(j)
                        for e_data in old_data.get('etfs', {}).values():
                            for s in e_data: universe_ids.add(s['id'])
                except: continue

    # 3. 抓取這大包名單的所有價格
    result["market_prices"] = get_yahoo_prices(list(universe_ids), ad_date)
    
    os.makedirs('data', exist_ok=True)
    with open(f"data/{ad_date}.json", 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
