import yfinance as yf
import pandas as pd
import requests
import re

# 1. 你的 PushDeer PUSH_KEY
PUSH_KEY = "PDU41670T22D55V5R9teoDdNT1StkmMppq8351Evg"

# 2. 全量跨境 ETF / LOF 资产映射表
FUND_MAP = {
    # --- 美股宽基 & 科技系列 ---
    "159941": ["纳指ETF", "sz", "NQ=F"],
    "513100": ["纳指ETF", "sh", "NQ=F"],
    "159509": ["纳指科技ETF", "sz", "NQ=F"],
    "513300": ["纳斯达克ETF", "sh", "NQ=F"],
    "159632": ["纳斯达克ETF", "sz", "NQ=F"],
    "159659": ["纳斯达克100ETF", "sz", "NQ=F"],
    "513110": ["纳斯达克100ETF", "sh", "NQ=F"],
    "159513": ["纳指100指数ETF", "sz", "NQ=F"],
    "159501": ["纳斯达克指数ETF", "sz", "NQ=F"],
    "159660": ["纳指100ETF", "sz", "NQ=F"],
    "513390": ["纳指100ETF", "sh", "NQ=F"],
    "513870": ["纳指ETF富国", "sh", "NQ=F"],
    "159696": ["纳指ETF易方达", "sz", "NQ=F"],
    "161130": ["纳斯达克100LOF", "sz", "NQ=F"],
    "513500": ["标普500ETF", "sh", "ES=F"],
    "513650": ["标普500ETF基金", "sh", "ES=F"],
    "159655": ["标普ETF", "sz", "ES=F"],
    "159612": ["标普500ETF", "sz", "ES=F"],
    "161125": ["标普500LOF", "sz", "ES=F"],
    "513400": ["道琼斯ETF", "sh", "YM=F"],
    "513850": ["美国50ETF", "sh", "ES=F"],
    "159577": ["美国50ETF", "sz", "ES=F"],

    # --- 美股行业细分 (信息科技/生物/消费/油气) ---
    "161128": ["标普信息科技LOF", "sz", "XLK"],       
    "159502": ["标普生物科技ETF", "sz", "XBI"],       
    "161127": ["标普生物科技LOF", "sz", "XBI"],
    "513290": ["纳指生物科技ETF", "sh", "^IBB"],      
    "159529": ["标普消费ETF", "sz", "XLY"],           
    "162415": ["美国消费LOF", "sz", "XLY"],
    "513350": ["标普油气ETF", "sh", "XOP"],           
    "159518": ["标普油气ETF", "sz", "XOP"],
    "162411": ["华宝油气LOF", "sz", "XOP"],
    "162719": ["石油LOF", "sz", "XLE"],               
    "160416": ["石油基金LOF", "sz", "IXC"],           
    "163208": ["全球油气能源LOF", "sz", "XLE"],

    # --- 港股 & 中概互联网系列 ---
    "160644": ["港美互联网LOF", "sz", "KWEB"],        
    "513050": ["中概互联网ETF", "sh", "KWEB"],
    "159605": ["中概互联ETF", "sz", "KWEB"],
    "159607": ["中概互联网ETF", "sz", "KWEB"],
    "513220": ["中概互联ETF", "sh", "KWEB"],
    "164906": ["中概互联网LOF", "sz", "KWEB"],
    "159822": ["新经济ETF", "sz", "^HSI"],
    "160125": ["南方香港LOF", "sz", "^HSI"],
    "161726": ["恒生LOF", "sz", "^HSI"],
    "513360": ["教育ETF", "sh", "KWEB"],

    # --- 全球其他主要市场系列 (欧洲/亚太/新兴市场) ---
    "159561": ["德国ETF", "sz", "^GDAXI"],            
    "513030": ["德国ETF", "sh", "^GDAXI"],
    "513080": ["法国CAC40ETF", "sh", "^FCHI"],        
    "164824": ["印度基金LOF", "sz", "^BSESN"],         
    "513870": ["日经ETF/LOF", "sh", "NK=F"],          
    "520830": ["沙特ETF", "sh", "KSA"],               
    "159329": ["沙特ETF", "sz", "KSA"],
    "520870": ["巴西ETF", "sh", "EWZ"],               
    "159100": ["巴西ETF", "sz", "EWZ"],
    "513730": ["东南亚科技ETF", "sh", "ASEA"],        
    "159687": ["亚太精选ETF", "sz", "AAXJ"],          
    "520580": ["新兴亚洲ETF", "sh", "AAXJ"],
    "501312": ["海外科技LOF", "sz", "XLK"],
    "501225": ["全球芯片LOF", "sz", "SOXX"],          

    # --- 大宗商品、REITs、债券系列 ---
    "164701": ["黄金LOF", "sz", "GC=F"],              
    "161116": ["黄金主题LOF", "sz", "GC=F"],
    "160719": ["嘉实黄金LOF", "sz", "GC=F"],
    "501018": ["南方原油LOF", "sh", "CL=F"],           
    "160723": ["嘉实原油LOF", "sz", "CL=F"],
    "161129": ["原油LOF易方达", "sz", "CL=F"],
    "160216": ["国泰商品LOF", "sz", "DBC"],           
    "165513": ["中信保诚商品LOF", "sz", "DBC"],
    "161815": ["抗通胀LOF", "sz", "DBC"],
    "160140": ["美国REIT精选LOF", "sz", "IYR"],       
    "501300": ["美元债LOF", "sh", "AGG"]              
}

def send_notification(msg):
    """
    负责把报警信息打通到你的 PushDeer
    """
    print(f"[开始发送 PushDeer 推送]...\n{msg}")
    url = "https://api2.pushdeer.com/message/push"
    payload = {
        "pushkey": PUSH_KEY,
        "text": "🚨 LOF套利雷达发现黄金机会！",
        "desp": msg,
        "type": "markdown"
    }
    try:
        res = requests.post(url, data=payload, timeout=10).json()
        if res.get("content", {}).get("result") == "ok":
            print("🚀 PushDeer 推送成功！")
        else:
            print(f"❌ PushDeer 返回错误: {res}")
    except Exception as e:
        print(f"❌ 推送失败，网络异常: {e}")

def get_all_iopv():
    print("====== 开始获取海外市场实时动态 ======")
    global_tickers = list(set([info[2] for info in FUND_MAP.values()]))
    global_tickers.append("CNY=X") 
    
    try:
        tickers_data = yf.Tickers(' '.join(global_tickers))
        market_changes = {}
        for ticker in global_tickers:
            change = tickers_data.tickers[ticker].info.get('regularMarketChangePercent', 0) / 100
            market_changes[ticker] = change
            print(f"海外资产 {ticker} 今日日内变动: {change:.2%}")
    except Exception as e:
        print(f"获取海外市场数据失败: {e}，将使用0误差替代")
        market_changes = {ticker: 0.0 for ticker in global_tickers}

    cny_change = market_changes.get("CNY=X", 0)
    print("======================================\n")

    headers = {
        "Referer": "https://fund.eastmoney.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    results = []

    for fund_code, info in FUND_MAP.items():
        fund_name, prefix, ticker_code = info
        
        # A. 获取 A 股场内现价 (新浪接口)
        sina_url = f"https://hq.sinajs.cn/list={prefix}{fund_code}"
        try:
            res = requests.get(sina_url, headers={"Referer": "https://finance.sina.com.cn"}, timeout=5)
            data_match = re.search(r'"([^"]*)"', res.text)
            if not data_match: continue
            data_list = data_match.group(1).split(',')
            current_price = float(data_list[3]) if float(data_list[3]) > 0 else float(data_list[2])
        except:
            continue

        # B. 获取 T-1 日官方净值
        last_nav = float(data_list[1]) 
        try:
            tt_url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
            tt_res = requests.get(tt_url, headers=headers, timeout=5)
            last_nav = float(re.search(r'"dwjz":"([^"]*)"', tt_res.text).group(1))
        except:
            pass

        # C. 解析天天基金网页版公开接口获取申购状态与限额
        status_str = "✅ 自由申购"
        try:
            web_info_url = f"https://fundpage.1234567.com.cn/FundHQInfo/StaticFundHQInfo.ashx?FCODE={fund_code}"
            web_res = requests.get(web_info_url, headers=headers, timeout=5).text
            
            if "暂停申购" in web_res or '"IsPurchase":false' in web_res.replace(" ", ""):
                status_str = "❌ 暂停申购"
            else:
                limit_match = re.search(r'限制大额申购.*?(\d+元|\d+万)', web_res)
                if not limit_match:
                    limit_match = re.search(r'"PurLmtAmt"\s*:\s*"([^"]+)"', web_res)
                
                if limit_match:
                    limit_val = limit_match.group(1)
                    if limit_val and limit_val != "0" and limit_val != "无限制":
                        status_str = f"⚠️ 限购 {limit_val}"
        except:
            status_str = "⚠️ 解析失败"

        # D. 计算实时 IOPV
        asset_change = market_changes.get(ticker_code, 0)
        
        if ticker_code in ["^HSI", "KWEB", "KSA", "EWZ", "ASEA", "AAXJ", "XLK", "XBI", "XOP", "XLE", "IXC", "SOXX", "IYR", "AGG", "DBC"]:
            estimated_iopv = last_nav * (1 + asset_change) 
        else:
            estimated_iopv = last_nav * (1 + asset_change) * (1 + cny_change)
            
        premium_rate = (current_price / estimated_iopv) - 1

        results.append({
            "代码": fund_code,
            "名称": fund_name,
            "现价": current_price,
            "估算IOPV": round(estimated_iopv, 4),
            "实时溢价率": f"{premium_rate:.2%}",
            "申购状态": status_str,
            "raw_premium": premium_rate
        })

    # 4. 输出大盘看板
    df = pd.DataFrame(results)
    df = df.sort_values(by="raw_premium", ascending=False) 
    
    print("🔥 ====== 全网海外 LOF/ETF 溢价率 + 申购状态监控看板 ======")
    pd.set_option('display.max_rows', None) 
    print(df[["代码", "名称", "现价", "估算IOPV", "实时溢价率", "申购状态"]].to_string(index=False))
    print("========================================================\n")

    # 5. 过滤出：【有套利价值 > 3%】且【没有暂停申购】的基金进行通知
    alert_funds = df[(df['raw_premium'] > 0.03) & (df['申购状态'] != "❌ 暂停申购")]
    if not alert_funds.empty:
        msg_markdown = "### 🚨 发现可套利高溢价LOF/ETF！\n"
        for _, row in alert_funds.iterrows():
            msg_markdown += f"- **{row['名称']} ({row['代码']})**\n"
            msg_markdown += f"  - 实时溢价率：`{row['实时溢价率']}`\n"
            msg_markdown += f"  - 现价/估算IOPV：{row['现价']} / {row['估算IOPV']}\n"
            msg_markdown += f"  - 状态：{row['申购状态']}\n\n"
        
        send_notification(msg_markdown)

if __name__ == "__main__":
    get_all_iopv()
