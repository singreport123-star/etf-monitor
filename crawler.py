import requests
import json
from datetime import datetime

def get_minguo_date():
    today = datetime.now()
    # 計算民國年 (2026 -> 115)
    year = today.year - 1911
    return f"{year}/{today.strftime('%m/%d')}"

def probe():
    print("--- [雲端連線診斷 V4：Session 模擬與日期校正] ---")
    
    # 建立一個會話 (Session)，它會自動幫我們存取 Cookie
    session = requests.Session()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest", # 關鍵：假裝是前端網頁發出的 Ajax 請求
        "Content-Type": "application/json;charset=UTF-8",
    }

    # 1. 第一步：先訪問首頁獲取 Session/Cookie
    print("[1/3] 正在訪問首頁建立 Session...")
    home_url = "https://www.ezmoney.com.tw/ETF/Transaction/PCF"
    session.get(home_url, headers=headers, timeout=10)

    # 2. 第二步：發送 API 請求
    print(f"[2/3] 正在請求 00981A 資料 (日期: {get_minguo_date()})...")
    api_url = "https://www.ezmoney.com.tw/ETF/Transaction/GetPCF"
    payload = {
        "fundCode": "49YTW", # 00981A 的真實代碼
        "date": get_minguo_date(), 
        "specificDate": False
    }
    
    try:
        res = session.post(api_url, json=payload, headers=headers, timeout=15)
        print(f"狀態碼: {res.status_code}")
        
        # 再次嘗試解析
        if "<!DOCTYPE" in res.text:
            print("❌ 失敗：伺服器依然踢回了 HTML 網頁。")
            print(res.text[:100]) # 印出開頭確認
        else:
            data = res.json()
            stocks = []
            # 遍歷尋找股票資產
            for asset_item in data.get('asset', []):
                if asset_item.get('AssetCode') == 'ST':
                    stocks = asset_item.get('Details', [])
                    break
            print(f"✅ 00981A 成功穿透！抓取到 {len(stocks)} 檔成分股。")
            
    except Exception as e:
        print(f"❌ 請求出錯: {e}")

    # 3. 00982A 群益 (維持原狀，確保整體不掛掉)
    print("\n[3/3] 00982A 之前已成功，目前跳過細節...")

if __name__ == "__main__":
    probe()
