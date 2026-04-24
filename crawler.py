import requests
import json
import os
import yfinance as yf
from datetime import datetime, timedelta

def get_yahoo_prices(stock_ids, target_date_str):
    """抓取該日期當天的收盤價"""
    prices = {}
    if not stock_ids: return {}
    clean_ids = list(set([str(sid).strip() for sid in stock_ids if sid]))
    print(f"--- 抓取 {target_date_str} 收盤價 (共 {len(clean_ids)} 檔) ---")
    
    tickers = [f"{sid}.TW" for sid in clean_ids] + [f"{sid}.TWO" for sid in clean_ids]
    try:
        dt = datetime.strptime(target_date_str, "%Y-%m-%d")
        # 抓取最近 10 天，確保能定位到最後一個有效成交價
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

def fetch_holdings(m_date, ad_date):
    results = {"00981A": [], "00982A": []}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    # 統一 00981A
    try:
        r1 = requests.post("https://www.ezmoney.com.tw/ETF/Transaction/GetPCF", 
                           json={"fundCode": "49YTW", "date": m_date, "specificDate": True}, headers=headers, timeout=15)
        results["00981A"] = [{"id": d['DetailCode'].strip(), "name": d['DetailName'], "share": d['Share']} 
                             for item in r1.json().get('asset', []) if item.get('AssetCode') == 'ST' for d in item.get('Details', [])]
        print(f"✅ 00981A 成功: {len(results['00981A'])} 檔")
    except: print("❌ 00981A 失敗")

    # 群益 00982A (修正模擬)
    try:
        slash_date = ad_date.replace("-", "/")
        capital_headers = {
            **headers,
            "Referer": "https://www.capitalfund.com.tw/etf/product/detail/399/buyback",
            "Content-Type": "application/json"
        }
        r2 = requests.post("https://www.capitalfund.com.tw/CFWeb/api/etf/buyback", 
                           json={"fundId": "399", "date": slash_date}, headers=capital_headers, timeout=15)
        stocks = r2.json().get('data', {}).get('stocks', [])
        results["00982A"] = [{"id": s['stocNo'].strip(), "name": s['stocName'], "share": s['share']} for s in stocks]
        print(f"✅ 00982A 成功: {len(results['00982A'])} 檔")
    except: print("❌ 00982A 失敗")
    
    return results

if __name__ == "__main__":
    target_date = os.environ.get("TARGET_DATE", datetime.now().strftime("%Y-%m-%d"))
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    m_date = f"{dt.year - 1911}/{dt.strftime('%m/%d')}"
    
    # 1. 抓持股
    holdings = fetch_holdings(m_date, target_date)
    
    # 2. 聯集 ID (確保出清股也有今天的價)
    all_ids = set()
    for stocks in holdings.values():
        for s in stocks: all_ids.add(s['id'])
    if os.path.exists('data'):
        for f in os.listdir('data'):
            if f.endswith('.json'):
                with open(f'data/{f}', 'r') as j:
                    old_data = json.load(j)
                    for stocks in old_data.get('etfs', {}).values():
                        for s in stocks: all_ids.add(s['id'])

    # 3. 抓取這天的價格
    prices = get_yahoo_prices(list(all_ids), target_date)
    
    # 4. 存檔
    res = {"date": target_date, "etfs": holdings, "market_prices": prices}
    os.makedirs('data', exist_ok=True)
    with open(f"data/{target_date}.json", 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=4)
