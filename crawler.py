import requests
import json
import os
import yfinance as yf
from datetime import datetime, timedelta

def get_yahoo_prices(stock_ids, target_date_str):
    prices = {}
    if not stock_ids: return {}
    clean_ids = list(set([str(sid).strip() for sid in stock_ids if sid]))
    print(f"--- 抓取 {target_date_str} 價格 (共 {len(clean_ids)} 檔) ---")
    tickers = [f"{sid}.TW" for sid in clean_ids] + [f"{sid}.TWO" for sid in clean_ids]
    try:
        dt = datetime.strptime(target_date_str, "%Y-%m-%d")
        data = yf.download(tickers, start=(dt - timedelta(days=10)).strftime("%Y-%m-%d"), 
                           end=(dt + timedelta(days=1)).strftime("%Y-%m-%d"), group_by='ticker', progress=False)
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
    return prices

def fetch_etf_holdings(m_date, ad_date):
    results = {"00981A": [], "00982A": []}
    # 統一
    try:
        r1 = requests.post("https://www.ezmoney.com.tw/ETF/Transaction/GetPCF", 
                           json={"fundCode": "49YTW", "date": m_date, "specificDate": True}, timeout=15)
        results["00981A"] = [{"id": d['DetailCode'].strip(), "name": d['DetailName'], "share": d['Share']} 
                             for item in r1.json().get('asset', []) if item.get('AssetCode') == 'ST' for d in item.get('Details', [])]
    except: print("⚠️ 00981A 抓取失敗")

    # 群益 (回歸最簡化 POST)
    try:
        slash_date = ad_date.replace("-", "/")
        r2 = requests.post("https://www.capitalfund.com.tw/CFWeb/api/etf/buyback", 
                           json={"fundId": "399", "date": slash_date}, timeout=15)
        stocks = r2.json().get('data', {}).get('stocks', [])
        results["00982A"] = [{"id": s['stocNo'].strip(), "name": s['stocName'], "share": s['share']} for s in stocks]
    except: print("⚠️ 00982A 抓取失敗")
    
    return results

if __name__ == "__main__":
    target_date = os.environ.get("TARGET_DATE", datetime.now().strftime("%Y-%m-%d"))
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    m_date = f"{dt.year - 1911}/{dt.strftime('%m/%d')}"
    
    holdings = fetch_etf_holdings(m_date, target_date)
    all_ids = set()
    for stocks in holdings.values():
        for s in stocks: all_ids.add(s['id'])
    
    # 掃描歷史
    if os.path.exists('data'):
        for f in os.listdir('data'):
            if f.endswith('.json'):
                try:
                    with open(f'data/{f}', 'r') as j:
                        old = json.load(j)
                        for stocks in old.get('etfs', {}).values():
                            for s in stocks: all_ids.add(s['id'])
                except: continue

    prices = get_yahoo_prices(list(all_ids), target_date)
    res = {"date": target_date, "etfs": holdings, "market_prices": prices}
    os.makedirs('data', exist_ok=True)
    with open(f"data/{target_date}.json", 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=4)
