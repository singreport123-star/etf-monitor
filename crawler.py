import requests
import json
import os
import yfinance as yf
from datetime import datetime, timedelta

def get_price_on_date(stock_ids, target_date_str):
    """精準抓取該日期當天的收盤價"""
    prices = {}
    if not stock_ids: return {}
    print(f"--- 抓取 {target_date_str} 當日收盤價 (共 {len(stock_ids)} 檔) ---")
    
    tickers = [f"{sid}.TW" for sid in stock_ids] + [f"{sid}.TWO" for sid in stock_ids]
    try:
        # 抓取目標日前後資料，確保能定位到那一天的最後一筆成交
        target_dt = datetime.strptime(target_date_str, "%Y-%m-%d")
        start_dt = target_dt - timedelta(days=10) # 往回找10天確保遇到假日有備案
        end_dt = target_dt + timedelta(days=1)
        data = yf.download(tickers, start=start_dt.strftime("%Y-%m-%d"), 
                           end=end_dt.strftime("%Y-%m-%d"), group_by='ticker', progress=False)
        
        for sid in stock_ids:
            p = 0
            for suffix in ['.TW', '.TWO']:
                t = f"{sid}{suffix}"
                if t in data.columns.levels[0]:
                    series = data[t]['Close'].dropna()
                    if not series.empty:
                        p = round(float(series.iloc[-1]), 2) # 拿該日期當天(或最近一天)的價格
                        break
            prices[sid] = p
    except Exception as e: print(f"Yahoo 錯誤: {e}")
    return prices

def fetch_etf_holdings(m_date, ad_date):
    # 統一 00981A
    try:
        s = requests.Session()
        s.get("https://www.ezmoney.com.tw/ETF/Transaction/PCF")
        r1 = s.post("https://www.ezmoney.com.tw/ETF/Transaction/GetPCF", 
                    json={"fundCode": "49YTW", "date": m_date, "specificDate": True})
        u_list = [{"id": d['DetailCode'].strip(), "name": d['DetailName'], "share": d['Share']} 
                  for item in r1.json().get('asset', []) if item.get('AssetCode') == 'ST' for d in item.get('Details', [])]
    except: u_list = []
    
    # 群益 00982A
    try:
        r2 = requests.post("https://www.capitalfund.com.tw/CFWeb/api/etf/buyback", 
                           json={"fundId": "399", "date": ad_date})
        c_list = [{"id": s['stocNo'].strip(), "name": s['stocName'], "share": s['share']} 
                  for s in r2.json().get('data', {}).get('stocks', [])]
    except: c_list = []
    
    return {"00981A": u_list, "00982A": c_list}

if __name__ == "__main__":
    target_date = os.environ.get("TARGET_DATE", datetime.now().strftime("%Y-%m-%d"))
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    m_date = f"{dt.year - 1911}/{dt.strftime('%m/%d')}"
    
    # 1. 抓取持股
    holdings = fetch_etf_holdings(m_date, target_date)
    
    # 2. 聯集所有歷史代號 (確保消失的股票也有今天的價格)
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

    # 3. 抓取這批標在「這一天」的價格
    prices = get_price_on_date(list(all_ids), target_date)
    
    # 4. 存成當天的獨立檔案
    res = {"date": target_date, "etfs": holdings, "market_prices": prices}
    os.makedirs('data', exist_ok=True)
    with open(f"data/{target_date}.json", 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=4)
