import akshare as ak
import yfinance as yf
import pandas as pd

def get_realtime_iopv():
    # 1. 获取美股期货和汇率的日内涨跌幅 (Yahoo Finance)
    # NQ=F 是纳斯达克期货，CNY=X 是美元/人民币汇率
    tickers = yf.Tickers('NQ=F CNY=X')
    
    nq_change = tickers.tickers['NQ=F'].info.get('regularMarketChangePercent', 0) / 100
    cny_change = tickers.tickers['CNY=X'].info.get('regularMarketChangePercent', 0) / 100
    
    print(f"美股纳指期货今日变动: {nq_change:.2%}")
    print(f"美元/人民币汇率今日变动: {cny_change:.2%}")

    # 2. 获取 A 股场内 LOF 实时价格 (东方财富接口)
    lof_df = ak.fund_lof_spot_em()
    # 筛选出 纳指LOF (161130)
    target_lof = lof_df[lof_df['基金代码'] == '161130']
    if target_lof.empty:
        print("未找到该基金场内数据")
        return
        
    current_price = float(target_lof.iloc[0]['最新价'])
    
    # 3. 获取该基金 T-1 日的官方净值
    # 注意：为了严谨，实际生产中建议用 ak.fund_open_fund_info_em 获取最新一条历史净值
    fund_info = ak.fund_open_fund_info_em(fund="161130", indicator="单位净值走势")
    last_nav = float(fund_info.iloc[-1]['单位净值']) 
    nav_date = fund_info.iloc[-1]['净值日期']
    print(f"基金最新官方净值 ({nav_date}): {last_nav}")

    # 4. 计算估算 IOPV 和 溢价率
    # 估算 IOPV = 昨末净值 * (1 + 期货涨幅) * (1 + 汇率涨幅)
    estimated_iopv = last_nav * (1 + nq_change) * (1 + cny_change)
    premium_rate = (current_price / estimated_iopv) - 1

    print(f"场内现价: {current_price}")
    print(f"盘中估算IOPV: {estimated_iopv:.4f}")
    print(f"🔥 实时估算溢价率: {premium_rate:.2%}")
    
    # 5. 触发阈值通知 (伪代码：你可以对接钉钉/企业微信 Webhook)
    if premium_rate > 0.05: # 溢价大于 5%
        send_notification(f"纳指LOF溢价达 {premium_rate:.2%}，速去场外申购！")

def send_notification(msg):
    print(f"[发送通知]: {msg}")
    # 这里可以用 requests.post(webhook_url, json=...) 转发到你的手机

if __name__ == "__main__":
    get_realtime_iopv()
