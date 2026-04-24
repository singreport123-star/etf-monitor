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
        # 抓取最近 10 天，確保能對齊
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
    final_holdings = {"00981A": [], "00982A": []}
    
    # 統一 (00981A)
    print("📡 正在嘗試抓取 00981A (統一)...")
    try:
        r1 = requests.post("https://www.ezmoney.com.tw/ETF/Transaction/GetPCF", 
                           json={"fundCode": "49YTW", "date": m_date, "specificDate": True}, timeout=15)
        res1 = r1.json()
        final_holdings["00981A"] = [{"id": d['DetailCode'].strip(), "name": d['DetailName'], "share": d['Share']} 
                                   for item in res1.get('asset', []) if item.get('AssetCode') == 'ST' 
                                   for d in item.get('Details', [])]
        print(f"✅ 00981A 成功，抓到 {len(final_holdings['00981A'])} 檔")
    except Exception as e:
        print(f"❌ 00981A 抓取崩潰: {e}")

    # 群益 (00982A)
    print("📡 正在嘗試抓取 00982A (群益)...")
    try:
        slash_date = ad_date.replace("-", "/")
        # 群益 API 有時候很挑 User-Agent，我們模擬一下
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r2 = requests.post("https://www.capitalfund.com.tw/CFWeb/api/etf/buyback", 
                           json={"fundId": "399", "date": slash_date}, headers=headers, timeout=15)
        res2 = r2.json()
        stocks = res2.get('data', {}).get('stocks', [])
        if not stocks:
            print("⚠️ 群益 API 回傳成功，但持股名單是空的！")
        final_holdings["00982A"] = [{"id": s['stocNo'].strip(), "name": s['stocName'], "share": s['share']} for s in stocks]
        print(f"✅ 00982A 成功，抓到 {len(final_holdings['00982A'])} 檔")
    except Exception as e:
        print(f"❌ 00982A 抓取崩潰: {e}")
    
    return final_holdings

if __name__ == "__main__":
    target_date = os.environ.get("TARGET_DATE", datetime.now().strftime("%Y-%m-%d"))
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    m_date = f"{dt.year - 1911}/{dt.strftime('%m/%d')}"
    
    # 1. 抓取持股名單
    holdings = fetch_etf_holdings(m_date, target_date)
    
    # 2. 聯集所有 ID，確保價格包完整
    all_ids = set()
    for stocks in holdings.values():
        for s in stocks: all_ids.add(s['id'])
    
    # 掃描歷史檔案，補齊出清股的價格
    if os.path.exists('data'):
        for f in os.listdir('data'):
            if f.endswith('.json'):
                try:
                    with open(f'data/{f}', 'r') as j:
                        old = json.load(j)
                        for stocks in old.get('etfs', {}).values():
                            for s in stocks: all_ids.add(s['id'])
                except: continue

    # 3. 抓取這份全清單的「當日」價格
    prices = get_yahoo_prices(list(all_ids), target_date)
    
    # 4. 存檔 (確保結構絕對正確)
    res = {
        "date": target_date,
        "etfs": {
            "00981A": holdings["00981A"],
            "00982A": holdings["00982A"]
        },
        "market_prices": prices
    }
    
    os.makedirs('data', exist_ok=True)
    with open(f"data/{target_date}.json", 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=4)
    print(f"🚀 {target_date} 資料包存檔完成！")
