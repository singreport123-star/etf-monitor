import requests
import json
import os
import yfinance as yf
from datetime import datetime, timedelta

def get_yahoo_prices(stock_ids, target_date_str):
    prices = {}
    if not stock_ids: return {}
    clean_ids = list(set([str(sid).strip() for sid in stock_ids if sid]))
    print(f"--- 抓取 {target_date_str} 收盤價 (共 {len(clean_ids)} 檔) ---")
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
    except Exception as e: print(f"Yahoo 錯誤: {e}")
    return prices

def fetch_etf_holdings(m_date, ad_date):
    # 統一 (00981A)
    u_list = []
    try:
        s1 = requests.Session()
        s1.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        s1.get("https://www.ezmoney.com.tw/ETF/Transaction/PCF")
        r1 = s1.post("https://www.ezmoney.com.tw/ETF/Transaction/GetPCF", 
                     json={"fundCode": "49YTW", "date": m_date, "specificDate": True}, timeout=15)
        u_list = [{"id": d['DetailCode'].strip(), "name": d['DetailName'], "share": d['Share']} 
                  for item in r1.json().get('asset', []) if item.get('AssetCode') == 'ST' for d in item.get('Details', [])]
        print(f"✅ 00981A 抓取成功: {len(u_list)} 檔")
    except Exception as e: print(f"❌ 00981A 失敗: {e}")

    # 群益 (00982A) - 確定方案
    c_list = []
    try:
        s2 = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json",
            "Referer": "https://www.capitalfund.com.tw/etf/product/detail/399/buyback",
            "X-Requested-With": "XMLHttpRequest"
        }
        # 必須先拿 Cookie
        s2.get("https://www.capitalfund.com.tw/etf/product/detail/399/buyback", headers=headers)
        # 群益 API 絕對要斜線日期
        slash_date = ad_date.replace("-", "/")
        r2 = s2.post("https://www.capitalfund.com.tw/CFWeb/api/etf/buyback", 
                     json={"fundId": "399", "date": slash_date}, headers=headers, timeout=15)
        
        raw_data = r2.json()
        stocks = raw_data.get('data', {}).get('stocks', [])
        c_list = [{"id": s['stocNo'].strip(), "name": s['stocName'], "share": s['share']} for s in stocks]
        print(f"✅ 00982A 抓取成功: {len(c_list)} 檔")
    except Exception as e: print(f"❌ 00982A 失敗: {e}")
    
    return {"00981A": u_list, "00982A": c_list}

if __name__ == "__main__":
    target_date = os.environ.get("TARGET_DATE", datetime.now().strftime("%Y-%m-%d"))
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    m_date = f"{dt.year - 1911}/{dt.strftime('%m/%d')}"
    
    holdings = fetch_etf_holdings(m_date, target_date)
    
    # 聯集所有 ID，確保 A/B 日價格都有存進當天的 JSON
    all_ids = set()
    for stocks in holdings.values():
        for s in stocks: all_ids.add(s['id'])
    
    if os.path.exists('data'):
        for f in os.listdir('data'):
            if f.endswith('.json'):
                with open(f'data/{f}', 'r') as j:
                    old = json.load(j)
                    for stocks in old.get('etfs', {}).values():
                        for s in stocks: all_ids.add(s['id'])

    prices = get_yahoo_prices(list(all_ids), target_date)
    res = {"date": target_date, "etfs": holdings, "market_prices": prices}
    
    os.makedirs('data', exist_ok=True)
    with open(f"data/{target_date}.json", 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=4)
