import requests
import json
import os
import yfinance as yf
from datetime import datetime, timedelta

def get_dates(target_date_str):
    dt = datetime.strptime(target_date_str, "%Y-%m-%d")
    return dt.strftime("%Y-%m-%d"), f"{dt.year - 1911}/{dt.strftime('%m/%d')}"

def force_fetch_price(sid, target_date_str):
    """針對 0 股價的標的進行單點暴力重抓"""
    for suffix in ['.TW', '.TWO']:
        ticker = f"{sid}{suffix}"
        try:
            # 抓取最近 10 天的歷史紀錄，確保拿得到最新的有效收盤價
            stock = yf.Ticker(ticker)
            hist = stock.history(period="10d")
            if not hist.empty:
                last_price = hist['Close'].dropna().iloc[-1]
                if last_price > 0:
                    return round(float(last_price), 2)
        except: continue
    return "Yahoo 無資料" # 如果連單點抓取都失敗，直接回傳文字

def get_yahoo_prices(stock_ids, target_date_str):
    prices = {}
    if not stock_ids: return {}
    print(f"--- 啟動 Yahoo 全域價格引擎 (標的數: {len(stock_ids)}) ---")
    
    # 第一輪：批量抓取
    all_tickers = [f"{sid}.TW" for sid in stock_ids] + [f"{sid}.TWO" for sid in stock_ids]
    try:
        target_dt = datetime.strptime(target_date_str, "%Y-%m-%d")
        data = yf.download(all_tickers, period="5d", group_by='ticker', progress=False)
        for sid in stock_ids:
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

    # 第二輪：防呆檢查，如果是 0 就暴力單點重抓
    for sid in stock_ids:
        if prices.get(sid, 0) == 0:
            print(f"🕵️ 偵測到 {sid} 股價異常，執行暴力重抓...")
            prices[sid] = force_fetch_price(sid, target_date_str)
            
    return prices

# fetch_unified 與 fetch_capital 維持正常抓取
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
    
    # 掃描歷史與今日 ID
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
