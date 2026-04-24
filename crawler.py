import requests
import json
import os
import sys
from datetime import datetime

def get_dates(target_date_str):
    # 解析輸入日期 (YYYY-MM-DD)
    dt = datetime.strptime(target_date_str, "%Y-%m-%d")
    ad_date = dt.strftime("%Y-%m-%d")
    m_year = dt.year - 1911
    m_date = f"{m_year}/{dt.strftime('%m/%d')}"
    return ad_date, m_date, dt.strftime("%Y%m%d")

def get_tw_prices(date_yyyymmdd):
    """抓取指定日期的上市、上櫃、興櫃收盤價"""
    prices = {}
    print(f"--- 正在抓取 {date_yyyymmdd} 全市場股價 ---")
    try:
        # 1. 上市 (MI_INDEX 支援歷史查詢)
        res = requests.get(f"https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&date={date_yyyymmdd}&type=ALL", timeout=15)
        data = res.json()
        if 'data9' in data: # 通常 data9 是收盤價表
            for row in data['data9']:
                prices[row[0].strip()] = float(row[8].replace(',', '')) if row[8].replace('.','',1).isdigit() else 0
        
        # 2. 上櫃
        res = requests.get(f"https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_quotes_result.php?l=zh-tw&d={date_yyyymmdd[:4]}/{date_yyyymmdd[4:6]}/{date_yyyymmdd[6:]}&o=json", timeout=15)
        for row in res.json().get('aaData', []):
            prices[row[0].strip()] = float(row[2].replace(',', '')) if row[2].replace('.','',1).isdigit() else 0
            
        print(f"✅ 股價抓取完成，共 {len(prices)} 筆標的。")
    except Exception as e:
        print(f"⚠️ 股價抓取警告 (可能該日休市): {e}")
    return prices

def fetch_unified(fund_code, m_date):
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}
    session.get("https://www.ezmoney.com.tw/ETF/Transaction/PCF", headers=headers)
    api_url = "https://www.ezmoney.com.tw/ETF/Transaction/GetPCF"
    payload = {"fundCode": fund_code, "date": m_date, "specificDate": True}
    res = session.post(api_url, json=payload, headers=headers)
    data = res.json()
    stocks = []
    for item in data.get('asset', []):
        if item.get('AssetCode') == 'ST':
            for d in item.get('Details', []):
                stocks.append({"id": d['DetailCode'].strip(), "name": d['DetailName'], "share": d['Share']})
    return stocks

def fetch_capital(fund_id, ad_date):
    url = "https://www.capitalfund.com.tw/CFWeb/api/etf/buyback"
    res = requests.post(url, json={"fundId": fund_id, "date": ad_date}, headers={"User-Agent": "Mozilla/5.0"})
    data = res.json()
    stocks = []
    for s in data.get('data', {}).get('stocks', []):
        stocks.append({"id": s['stocNo'].strip(), "name": s['stocName'], "share": s['share']})
    return stocks

if __name__ == "__main__":
    # 從環境變數讀取日期，預設為今天
    target_date = os.environ.get("TARGET_DATE", datetime.now().strftime("%Y-%m-%d"))
    ad_date, m_date, raw_date = get_dates(target_date)
    
    all_data = {"date": ad_date, "etfs": {}, "market_prices": {}}
    all_data["market_prices"] = get_tw_prices(raw_date)
    all_data["etfs"]["00981A"] = fetch_unified("49YTW", m_date)
    all_data["etfs"]["00982A"] = fetch_capital("399", ad_date)
    
    os.makedirs('data', exist_ok=True)
    file_path = f"data/{ad_date}.json"
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=4)
    print(f"🎉 日期 {ad_date} 數據已存檔")
