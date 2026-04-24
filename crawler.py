import requests
import json
import os
from datetime import datetime

# 設定目標
ETFS = [
    {"name": "00981A", "fundCode": "49YTW", "provider": "unified"},
    {"name": "00982A", "fundId": "399", "provider": "capital"}
]

def get_tw_prices():
    """抓取上市、上櫃、興櫃當日收盤價"""
    prices = {}
    print("--- 正在抓取全市場股價 ---")
    try:
        # 1. 上市
        res = requests.get("https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=json", timeout=15)
        for row in res.json()['data']:
            prices[row[0].strip()] = float(row[7].replace(',', '')) if row[7] != 'null' else 0
        # 2. 上櫃
        res = requests.get("https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_quotes_result.php?l=zh-tw&o=json", timeout=15)
        for row in res.json()['aaData']:
            prices[row[0].strip()] = float(row[2].replace(',', '')) if row[2] != 'null' else 0
        # 3. 興櫃 (參考價)
        res = requests.get("https://www.tpex.org.tw/web/emergingstock/latest_quotes/stk_quotes_result.php?l=zh-tw&o=json", timeout=15)
        for row in res.json()['aaData']:
            prices[row[0].strip()] = float(row[2].replace(',', '')) if row[2] != 'null' else 0
        print(f"✅ 股價抓取完成，共 {len(prices)} 筆標的。")
    except Exception as e:
        print(f"⚠️ 股價抓取部分失敗: {e}")
    return prices

def fetch_unified(fund_code):
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}
    # 先拿 Session
    session.get("https://www.ezmoney.com.tw/ETF/Transaction/PCF", headers=headers)
    # 民國日期
    now = datetime.now()
    m_date = f"{now.year-1911}/{now.strftime('%m/%d')}"
    api_url = "https://www.ezmoney.com.tw/ETF/Transaction/GetPCF"
    payload = {"fundCode": fund_code, "date": m_date, "specificDate": False}
    res = session.post(api_url, json=payload, headers=headers)
    data = res.json()
    stocks = []
    for item in data.get('asset', []):
        if item.get('AssetCode') == 'ST':
            for d in item.get('Details', []):
                stocks.append({"id": d['DetailCode'].strip(), "name": d['DetailName'], "share": d['Share']})
    return stocks

def fetch_capital(fund_id):
    url = "https://www.capitalfund.com.tw/CFWeb/api/etf/buyback"
    res = requests.post(url, json={"fundId": fund_id, "date": None}, headers={"User-Agent": "Mozilla/5.0"})
    data = res.json()
    stocks = []
    for s in data.get('data', {}).get('stocks', []):
        stocks.append({"id": s['stocNo'].strip(), "name": s['stocName'], "share": s['share']})
    return stocks

def main():
    all_data = {"date": datetime.now().strftime("%Y-%m-%d"), "etfs": {}, "market_prices": {}}
    
    # 執行抓取
    all_data["market_prices"] = get_tw_prices()
    all_data["etfs"]["00981A"] = fetch_unified("49YTW")
    all_data["etfs"]["00982A"] = fetch_capital("399")
    
    # 確保目錄存在並存檔
    os.makedirs('data', exist_ok=True)
    file_path = f"data/{all_data['date']}.json"
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=4)
    print(f"🎉 數據已成功存檔至: {file_path}")

if __name__ == "__main__":
    main()
