import requests
import json
import os
import yfinance as yf
from datetime import datetime, timedelta
import time

def get_dates(target_date_str):
    dt = datetime.strptime(target_date_str, "%Y-%m-%d")
    return dt.strftime("%Y-%m-%d"), f"{dt.year - 1911}/{dt.strftime('%m/%d')}"

def get_single_price(sid):
    """針對 0 股價標的進行 30 天追溯抓取"""
    for suffix in ['.TW', '.TWO']:
        ticker = f"{sid}{suffix}"
        try:
            stock = yf.Ticker(ticker)
            # 抓取最近一個月，確保拿得到價格
            hist = stock.history(period="1mo")
            if not hist.empty:
                val = hist['Close'].dropna().iloc[-1]
                if val > 0: return round(float(val), 2)
        except: continue
    return "Yahoo無資料"

def get_yahoo_prices(stock_ids, target_date_str):
    prices = {}
    if not stock_ids: return {}
    
    clean_ids = list(set([str(sid).strip() for sid in stock_ids if sid]))
    print(f"--- 執行全域股價暴力補完 (共 {len(clean_ids)} 檔) ---")
    
    # 第一輪：批量抓取最近 7 天
    all_tickers = [f"{sid}.TW" for sid in clean_ids] + [f"{sid}.TWO" for sid in clean_ids]
    try:
        end_dt = datetime.strptime(target_date_str, "%Y-%m-%d") + timedelta(days=1)
        start_dt = end_dt - timedelta(days=7)
        data = yf.download(all_tickers, start=start_dt.strftime("%Y-%m-%d"), 
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
            prices[sid] = p
    except: pass

    # 第二輪：防呆檢查，如果是 0 或空值，就暴力單點追溯
    for sid in clean_ids:
        if prices.get(sid, 0) == 0:
            print(f"🕵️ 偵測到 {sid} 價格缺失，執行 30 天追溯...")
            prices[sid] = get_single_price(sid)
            
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
    
    result["etfs"]["00981A"] = fetch_unified(m_date)
    result["etfs"]["00982A"] = fetch_capital(ad_date)
    
    # 掃描歷史檔案，建立「標的全宇宙」
    ids = set()
    for etf in result["etfs"].values():
        for s in etf: ids.add(s['id'])
    if os.path.exists('data'):
        for f in os.listdir('data'):
            if f.endswith('.json'):
                try:
                    with open(f'data/{f}', 'r') as j:
                        past = json.load(j)
                        for e_data in past.get('etfs', {}).values():
                            for s in e_data: ids.add(s['id'])
                except: continue

    result["market_prices"] = get_yahoo_prices(list(ids), ad_date)
    
    os.makedirs('data', exist_ok=True)
    with open(f"data/{ad_date}.json", 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
