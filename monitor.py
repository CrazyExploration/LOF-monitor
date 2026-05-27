import yfinance as yf
import pandas as pd
import requests
import re

# 1. 定义你要监控的海外 LOF 资产清单（覆盖集思录核心品种）
# 格式: A股代码: [中文简称, 新浪接口前缀, 对应的海外参考期货/指数]
FUND_MAP = {
    # --- 美股系列 ---
    "161130": ["纳指LOF", "sz", "NQ=F"],
    "512100": ["纳斯达克LOF", "sh", "NQ=F"],
    "161125": ["标普500LOF", "sz", "ES=F"],
    "164701": ["黄金LOF", "sz", "GC=F"],       # 纽约黄金期货
    "162411": ["华宝油气LOF", "sz", "CL=F"],     # WTI原油期货
    
    # --- 港股/中概系列 (A股盘中恒指期货在交易) ---
    "164906": ["中国互联LOF", "sz", "HSI=F"],    # 恒生指数期货修正
    "501005": ["中概互联网LOF", "sh", "HSI=F"],
    "161726": ["恒生LOF", "sz", "HSI=F"],
    
    # --- 其他海外系列 ---
    "164824": ["印度基金LOF", "sz", "^BSESN"],    # 印度SENSEX指数
    "513030": ["德国DAXLOF", "sh", "^GDAXI"],     # 德国DAX指数
    "513880": ["日经ETF/LOF", "sh", "NK=F"]      # 日经225期货
}

def get_all_iopv():
    print("====== 开始获取海外市场实时动态 ======")
    # 统一提取所有需要用到的海外期货和指数代码
    global_tickers = list(set([info[2] for info in FUND_MAP.values()]))
    # 加上美元兑人民币汇率
    global_tickers.append("CNY=X")
    
    try:
        tickers_data = yf.Tickers(' '.join(global_tickers))
        # 构建一个涨跌幅字典
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

    # 2. 循环计算每一个 LOF 的实时溢价
    for fund_code, info in FUND_MAP.items():
        fund_name, prefix, ticker_code = info
        
        # 获取 A 股场内现价
        sina_url = f"https://hq.sinajs.cn/list={prefix}{fund_code}"
        try:
            res = requests.get(sina_url, headers=headers, timeout=5)
            data_match = re.search(r'"([^"]*)"', res.text)
            if not data_match: continue
            data_list = data_match.group(1).split(',')
            current_price = float(data_list[3]) if float(data_list[3]) > 0 else float(data_list[2])
        except:
            continue

        # 获取 T-1 日官方净值
        try:
            tt_url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
            tt_res = requests.get(tt_url, headers=headers, timeout=5)
            last_nav = float(re.search(r'"dwjz":"([^"]*)"', tt_res.text).group(1))
        except:
            last_nav = float(data_list[1]) # 天天基金不通时降级使用昨收

        # 3. 计算实时 IOPV
        # 实时估算IOPV = 昨末净值 * (1 + 对应标的期货涨幅) * (1 + 汇率涨幅)
        asset_change = market_changes.get(ticker_code, 0)
        
        # 特殊处理：如果是港股中概，汇率对冲逻辑不同，简化处理
        if ticker_code == "HSI=F":
            estimated_iopv = last_nav * (1 + asset_change) # 港币挂钩美元，日内波动主要看恒指
        else:
            estimated_iopv = last_nav * (1 + asset_change) * (1 + cny_change)
            
        premium_rate = (current_price / estimated_iopv) - 1

        results.append({
            "代码": fund_code,
            "名称": fund_name,
            "现价": current_price,
            "估算IOPV": round(estimated_iopv, 4),
            "实时溢价率": f"{premium_rate:.2%}",
            "raw_premium": premium_rate
        })

    # 4. 输出大盘看板
    df = pd.DataFrame(results)
    df = df.sort_values(by="raw_premium", ascending=False) # 按溢价率从高到低排序
    
    print("🔥 ====== 全网海外 LOF 溢价率实时监控看板 ======")
    print(df[["代码", "名称", "现价", "估算IOPV", "实时溢价率"]].to_string(index=False))
    print("================================================\n")

    # 5. 筛选高溢价进行通知（比如溢价率 > 3% 触发通知）
    alert_funds = df[df['raw_premium'] > 0.03]
    if not alert_funds.empty:
        msg_list = [f"{row['名称']}({row['代码']}): 溢价率 {row['实时溢价率']}" for _, row in alert_funds.iterrows()]
        send_notification("发现高溢价LOF！\n" + "\n".join(msg_list))

def send_notification(msg):
    print(f"[微信/钉钉推送]:\n{msg}")
    # TODO: 绑定你的推送 Token，例如使用 Server酱 或企业微信 Webhook

if __name__ == "__main__":
    get_all_iopv()
