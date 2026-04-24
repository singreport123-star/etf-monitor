import requests
import json

def probe():
    print("--- [雲端診斷開始] ---")
    
    # 1. 診斷 00981A (統一)
    url_981 = "https://www.ezmoney.com.tw/ETF/Transaction/GetPCF"
    payload_981 = {"fundCode": "49YTW", "date": None, "specificDate": False}
    try:
        res = requests.post(url_981, json=payload_981, timeout=15)
        data = res.json()
        # 根據證據鏈路徑提取
        stocks = data.get('asset', [])[1].get('Details', []) # 索引 1 通常是股票 ST
        print(f"✅ 00981A 連線成功，抓取到 {len(stocks)} 檔成分股。")
    except Exception as e:
        print(f"❌ 00981A 連線失敗: {e}")

    # 2. 診斷 00982A (群益)
    url_982 = "https://www.capitalfund.com.tw/CFWeb/api/etf/buyback"
    payload_982 = {"fundId": "399", "date": None}
    try:
        res = requests.post(url_982, json=payload_982, timeout=15)
        data = res.json()
        stocks = data.get('data', {}).get('stocks', [])
        print(f"✅ 00982A 連線成功，抓取到 {len(stocks)} 檔成分股。")
    except Exception as e:
        print(f"❌ 00982A 連線失敗: {e}")

if __name__ == "__main__":
    probe()
