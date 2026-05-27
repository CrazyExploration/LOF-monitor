import yfinance as yf
import pandas as pd
import requests
import re
import json

# 1. 定义你要监控的海外 LOF 资产清单
# 格式: A股代码: [中文简称, 新浪接口前缀, 对应的海外参考期货/指数]
FUND_MAP = {
    # --- 美股系列 ---
    "161130": ["纳指LOF", "sz", "NQ=F"],
    "512100": ["纳斯达克LOF", "sh", "NQ=F"],
    "161125": ["标普500LOF", "sz", "ES=F"],
    "164701": ["黄金LOF", "sz", "GC=F"],       
    "162411": ["华宝油气LOF", "sz", "CL=F"],     
    
    # --- 港股/中概系列 (修复 HSI=F 报错，改用 ^HSI) ---
    "164906": ["中国互联LOF", "sz", "^HSI"],    
    "501005": ["中概互联网LOF", "sh", "^HSI"],
    "161726": ["恒生LOF", "sz", "^HSI"],
    
    # --- 其他海外系列 ---
    "164824": ["印度基金LOF", "sz", "^BSESN"],    
    "513030": ["德国DAXLOF", "sh", "^GDAXI"],     
    "513880": ["日经ETF/LOF", "sh", "NK=F"]      
}

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
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    results = []

    for fund_code, info in FUND_MAP.items():
        fund_name, prefix, ticker_code = info
        
        # A. 获取 A 股场内现价 (新浪接口)
        sina_url = f"https://hq.sinajs.cn/list={prefix}{fund_code}"
        try:
            res = requests.get(sina_url, headers=headers, timeout=5)
            data_match = re.search(r'"([^"]*)"', res.text)
            if not data_match: continue
            data_list = data_match.group(1).split(',')
            current_price = float(data_list[3]) if float(data_list[3]) > 0 else float(data_list[2])
        except:
            continue

        # B. 获取 T-1 日官方净值 及 【新增】场外申购限额状态 (天天基金接口)
        status_str = "未知"
        last_nav = float(data_list[1]) # 默认降级使用新浪昨收
        try:
            tt_url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
            tt_res = requests.get(tt_url, headers=headers, timeout=5)
            
            # 提取昨末净值
            last_nav = float(re.search(r'"dwjz":"([^"]*)"', tt_res.text).group(1))
            
            # 【核心逻辑】通过天天基金另一个网页接口获取申购状态（该接口海外IP通常可用）
            detail_url = f"https://fundmobapi.eastmoney.com/FundMApi/FundBaseTypeInformation.ashx?FCODE={fund_code}&deviceid=Wap&version=6.5.5"
            detail_res = requests.get(detail_url, timeout=5).json()
            
            if detail_res and "Datas" in detail_res:
                # 状态：如“开放申购”、“暂停申购”、“限制大额申购”
                sg_status = detail_res["Datas"].get("GZSHSTATUE", "") 
                # 限额限额额度：如果有限额，通常会写在备注里，或者直接显示额度
                desc = detail_res["Datas"].get("BTOTLMT", "无限制")
                
                if "暂停" in sg_status:
                    status_str = "❌ 暂停申购"
                elif "限制大额" in sg_status or (desc and desc != "无限制" and float(desc) > 0):
                    status_str = f"⚠️ 限购 {desc}元"
                else:
                    status_str = "✅ 自由申购"
        except Exception as e:
            status_str = "⚠️ 接口获取失败"

        # C. 计算实时 IOPV
        asset_change = market_changes.get(ticker_code, 0)
        if ticker_code == "^HSI":
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
    
    print("🔥 ====== 全网海外 LOF 溢价率 + 申购状态监控看板 ======")
    print(df[["代码", "名称", "现价", "估算IOPV", "实时溢价率", "申购状态"]].to_string(index=False))
    print("========================================================\n")

    # 5. 过滤出：【有套利价值】且【没有暂停申购】的基金进行通知
    # 溢价大于 3% 且 状态不是暂停申购
    alert_funds = df[(df['raw_premium'] > 0.03) & (df['申购状态'] != "❌ 暂停申购")]
    if not alert_funds.empty:
        msg_list = [f"{row['名称']}({row['代码']}): 溢价 {row['实时溢价率']} ({row['申购状态']})" for _, row in alert_funds.iterrows()]
        send_notification("发现可套利高溢价LOF！\n" + "\n".join(msg_list))

def send_notification(msg):
    print(f"[发送通知]:\n{msg}")

if __name__ == "__main__":
    get_all_iopv()
