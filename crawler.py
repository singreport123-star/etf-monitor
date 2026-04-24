import requests
import json

def probe():
    print("--- [雲端連線診斷 V2：模擬瀏覽器] ---")
    
    # 共同的人類標頭設定
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
    }

    # 1. 診斷 00981A (統一) - 加入來源網址模擬
    url_981 = "https://www.ezmoney.com.tw/ETF/Transaction/GetPCF"
    headers_981 = headers.copy()
    headers_981["Referer"] = "https://www.ezmoney.com.tw/ETF/Transaction/PCF"
    
    payload_981 = {"fundCode": "49YTW", "date": None, "specificDate": False}
    
    try:
        res = requests.post(url_981, json=payload_981, headers=headers_981, timeout=15)
        print(f"00981A 回傳狀態碼: {res.status_code}")
        data = res.json()
        stocks = data.get('asset', [])[1].get('Details', [])
        print(f"✅ 00981A 連線成功，抓取到 {len(stocks)} 檔成分股。")
    except Exception as e:
        print(f"❌ 00981A 失敗原因: {e}")

    # 2. 診斷 00982A (群益) - 加入來源網址模擬
    url_982 = "https://www.capitalfund.com.tw/CFWeb/api/etf/buyback"
    headers_982 = headers.copy()
    headers_982["Referer"] = "https://www.capitalfund.com.tw/etf/transaction/buyback"
    
    payload_982 = {"fundId": "399", "date": None}
    
    try:
        res = requests.post(url_982, json=payload_982, headers=headers_982, timeout=15)
        print(f"00982A 回傳狀態碼: {res.status_code}")
        data = res.json()
        stocks = data.get('data', {}).get('stocks', [])
        print(f"✅ 00982A 連線成功，抓取到 {len(stocks)} 檔成分股。")
    except Exception as e:
        print(f"❌ 00982A 失敗原因: {e}")

if __name__ == "__main__":
    probe()
