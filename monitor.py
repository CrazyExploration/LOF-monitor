import yfinance as yf
import pandas as pd
import requests
import re

def get_realtime_iopv():
    # 1. 获取美股期货和汇率的日内涨跌幅 (Yahoo Finance) - 这步你已经成功了
    tickers = yf.Tickers('NQ=F CNY=X')
    nq_change = tickers.tickers['NQ=F'].info.get('regularMarketChangePercent', 0) / 100
    cny_change = tickers.tickers['CNY=X'].info.get('regularMarketChangePercent', 0) / 100
    
    print(f"美股纳指期货今日变动: {nq_change:.2%}")
    print(f"美元/人民币汇率今日变动: {cny_change:.2%}")

    # 2. 【修复核心】改用新浪财经公开接口获取 A 股场内 LOF 实时价格（海外IP极度友好）
    fund_code = '161130'
    # 深圳基金前缀是 sz, 上海是 sh。纳指LOF 161130 是深交所上市
    sina_url = f"https://hq.sinajs.cn/list=sz{fund_code}"
    
    # 新浪接口需要加一个随便的 Referer 请求头防简单的拦截
    headers = {
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(sina_url, headers=headers, timeout=10)
        # 新浪返回的格式类似于: var hq_str_sz161130="纳指LOF,1.523,1.524,1.530,...";
        # 我们用正则表达式或者切片把价格拿出来
        text = response.text
        data_match = re.search(r'"([^"]*)"', text)
        if not data_match:
            print("未能解析到新浪行情数据")
            return
            
        data_list = data_match.group(1).split(',')
        if len(data_list) < 4:
            print("新浪返回数据格式不正确")
            return
            
        # data_list[3] 是当前最新价
        current_price = float(data_list[3])
        if current_price == 0:
            # 如果还没开盘或者停牌，取昨收盘价 data_list[2]
            current_price = float(data_list[2])
            
    except Exception as e:
        print(f"获取场内实时价格失败: {e}")
        return
        
    print(f"场内现价 (161130): {current_price}")

    # 3. 获取该基金 T-1 日的官方净值
    # 新浪接口的 data_list[1] 其实就是前一天的净值/昨收，但为了绝对精准，我们也可以用天天基金的轻量接口
    try:
        tt_url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
        tt_res = requests.get(tt_url, headers=headers, timeout=10)
        # 返回格式: jsonpgz({"fundcode":"161130","name":"...","dwjz":"1.4230","jzrq":"2026-05-26" ...});
        last_nav = float(re.search(r'"dwjz":"([^"]*)"', tt_res.text).group(1))
        nav_date = re.search(r'"jzrq":"([^"]*)"', tt_res.text).group(1)
        print(f"基金最新官方净值 ({nav_date}): {last_nav}")
    except Exception as e:
        print(f"获取官方净值失败，尝试使用新浪替代值")
        last_nav = float(data_list[1]) # 降级使用昨收

    # 4. 计算估算 IOPV 和 溢价率
    estimated_iopv = last_nav * (1 + nq_change) * (1 + cny_change)
    premium_rate = (current_price / estimated_iopv) - 1

    print(f"盘中估算IOPV: {estimated_iopv:.4f}")
    print(f"🔥 实时估算溢价率: {premium_rate:.2%}")
    
    # 5. 触发阈值通知
    if premium_rate > 0.05: 
        send_notification(f"纳指LOF溢价达 {premium_rate:.2%}，速去场外申购！")

def send_notification(msg):
    print(f"[发送通知]: {msg}")

if __name__ == "__main__":
    get_realtime_iopv()
