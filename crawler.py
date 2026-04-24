import requests
import json

def probe():
    print("--- [雲端連線診斷 V3：解析 00981A 報錯內容] ---")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": "https://www.ezmoney.com.tw",
    }

    # 1. 診斷 00981A (統一)
    url_981 = "https://www.ezmoney.com.tw/ETF/Transaction/GetPCF"
    headers_981 = headers.copy()
    headers_981["Referer"] = "https://www.ezmoney.com.tw/ETF/Transaction/PCF"
    
    # 修改 Payload：date 不使用 None，改用空字串
    payload_981 = {"fundCode": "49YTW", "date": "", "specificDate": False}
    
    try:
        res = requests.post(url_981, json=payload_981, headers=headers_981, timeout=15)
        print(f"00981A 狀態碼: {res.status_code}")
        
        # 如果 JSON 解析失敗，列印前 200 個字元查看原文
        try:
            data = res.json()
            # 嘗試讀取 Details (00981A 的結構中 Details 在 asset 的特定 index)
            # 我們改用更安全的搜索方式
            stocks = []
            for asset_item in data.get('asset', []):
                if asset_item.get('AssetCode') == 'ST':
                    stocks = asset_item.get('Details', [])
                    break
            print(f"✅ 00981A 成功抓取到 {len(stocks)} 檔成分股。")
        except:
            print("❌ 00981A JSON 解析失敗，伺服器回傳的前 200 字內容如下：")
            print(res.text[:200])
            
    except Exception as e:
        print(f"❌ 00981A 請求異常: {e}")

    # 2. 00982A 已確認成功，維持原狀以供對照
    print("\n[00982A 群益已知成功，略過詳細日誌]")

if __name__ == "__main__":
    probe()
