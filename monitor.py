import yfinance as yf
import pandas as pd
import requests
import re
import json
from io import StringIO
import os

# 1. 从环境变量读取 PushDeer PUSH_KEY
PUSH_KEY = os.getenv("PUSH_KEY")

def get_top_50_dynamic_lof():
    """
    通过雪球网大盘接口，每天彻底动态获取全市场成交额最大的50只场内基金/LOF
    """
    print("🔄 正在通过雪球网底层动态获取今日全市场成交额 Top 50 的场内基金...")
    
    # 模拟浏览器访问，先获取雪球初始Cookie（这是绕过海外IP反爬的核心战术）
    session = requests.Session()
    base_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        session.get("https://xueqiu.com", headers=base_headers, timeout=5)
    except Exception as e:
        print(f"⚠️ 初始化雪球Session失败: {e}，尝试直接请求...")

    # 雪球全量场内基金动态接口：_size=100(取前100只)，order_by=amount(按成交额排序)
    url = "https://stock.xueqiu.com/v5/stock/screener/quote/list.json?page=1&size=100&order=desc&order_by=amount&market=CN&type=sh_sz_fund"
    
    top_funds = {}
    try:
        res = session.get(url, headers=base_headers, timeout=8).json()
        raw_list = res.get("data", {}).get("list", [])
        if not raw_list:
            print("⚠️ 雪球接口返回的数据列表为空")
            return None
            
        all_data = []
        for item in raw_list:
            # symbol 格式如 SH513100 或 SZ161130
            symbol = item.get("symbol", "")
            name = item.get("name", "")
            amount = item.get("amount", 0) # 当日实时成交额
            
            if not symbol or not name:
                continue
                
            prefix = symbol[:2].lower()   # sh 或 sz
            code = symbol[2:]             # 6位数字代码
            
            # 完全动态过滤：锁定LOF基金(16开头)以及名字里带有高频套利字眼的品种
            if code.startswith("16") or any(k in name for k in ["LOF", "纳指", "标普", "油气", "原油", "黄金", "境外", "海外", "互联网", "中概"]):
                all_data.append({
                    "code": code,
                    "name": name,
                    "prefix": prefix,
                    "amount": float(amount)
                })
        
        df_all = pd.DataFrame(all_data)
        if df_all.empty:
            print("⚠️ 未能筛选出符合LOF/跨境特征的动态品种")
            return None
            
        # 按照成交额精准切出前 50 只
        df_top50 = df_all.sort_values(by="amount", ascending=False).head(50)
        
        for _, row in df_top50.iterrows():
            code = row['code']
            name = row['name']
            prefix = row['prefix']
            
            # 动态模糊分配海外期货联动标的
            ticker = "DOMESTIC" 
            if "纳指" in name or "纳斯达克" in name: ticker = "NQ=F"
            elif "标普500" in name or "美国50" in name: ticker = "ES=F"
            elif "道琼斯" in name: ticker = "YM=F"
            elif "油气" in name: ticker = "XOP"
            elif "石油" in name: ticker = "XLE"
            elif "原油" in name: ticker = "CL=F"
            elif "黄金" in name: ticker = "GC=F"
            elif "德国" in name: ticker = "^GDAXI"
            elif "印度" in name: ticker = "^BSESN"
            elif "日经" in name: ticker = "NK=F"
            elif "沙特" in name: ticker = "KSA"
            elif "互联网" in name or "中概" in name: ticker = "KWEB"
            elif "恒生" in name or "香港" in name: ticker = "^HSI"
            
            top_funds[code] = [name, prefix, ticker, row['amount']]
            
        print(f"✅ 【完全动态】成功从雪球大盘筛选出今日成交最火爆的 {len(top_funds)} 只场内基金！")
        return top_funds
    except Exception as e:
        print(f"❌ 动态抓取雪球大盘数据失败: {e}")
        return None

def send_notification(msg):
    print(f"[开始发送 PushDeer 推送]...\n{msg}")
    url = "https://api2.pushdeer.com/message/push"
    payload = {
        "pushkey": PUSH_KEY,
        "text": "🚨 每日全动态 Top50 LOF 溢价雷达",
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
    # 每天完全动态获取名单
    dynamic_map = get_top_50_dynamic_lof()
    if not dynamic_map:
        print("⚠️ 动态排行获取彻底失败，程序终止。")
        return

    print("====== 开始获取海外市场实时动态 ======")
    global_tickers = list(set([info[2] for info in dynamic_map.values() if info[2] != "DOMESTIC"]))
    global_tickers.append("CNY=X") 
    
    market_changes = {}
    if len(global_tickers) > 1:
        try:
            tickers_data = yf.Tickers(' '.join(global_tickers))
            for ticker in global_tickers:
                change = tickers_data.tickers[ticker].info.get('regularMarketChangePercent', 0) / 100
                market_changes[ticker] = change
                print(f"海外资产 {ticker} 今日日内变动: {change:.2%}")
        except Exception as e:
            print(f"获取海外市场数据失败: {e}")
    
    if "CNY=X" not in market_changes:
        market_changes["CNY=X"] = 0.0
    cny_change = market_changes.get("CNY=X", 0)
    print("======================================\n")

    headers_pc = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    results = []

    for fund_code, info in dynamic_map.items():
        fund_name, prefix, ticker_code, amount = info
        
        # A. 获取 A 股场内现价 (新浪基础价格接口，通常不封IP)
        sina_url = f"https://hq.sinajs.cn/list={prefix}{fund_code}"
        try:
            res = requests.get(sina_url, headers={"Referer": "https://finance.sina.com.cn"}, timeout=5)
            data_match = re.search(r'"([^"]*)"', res.text)
            if not data_match: continue
            data_list = data_match.group(1).split(',')
            current_price = float(data_list[3]) if float(data_list[3]) > 0 else float(data_list[2])
        except:
            continue

        # B. 双轨制计算实时 IOPV
        estimated_iopv = 0.0
        if ticker_code == "DOMESTIC":
            try:
                tt_url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
                tt_res = requests.get(tt_url, headers=headers_pc, timeout=4)
                gsz_match = re.search(r'"gsz":"([^"]*)"', tt_res.text)
                if gsz_match:
                    estimated_iopv = float(gsz_match.group(1))
                else:
                    estimated_iopv = float(re.search(r'"dwjz":"([^"]*)"', tt_res.text).group(1))
            except:
                estimated_iopv = float(data_list[1]) if float(data_list[1]) > 0 else current_price
        else:
            last_nav = float(data_list[1])
            try:
                tt_url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
                tt_res = requests.get(tt_url, headers=headers_pc, timeout=4)
                last_nav = float(re.search(r'"dwjz":"([^"]*)"', tt_res.text).group(1))
            except:
                pass
            
            asset_change = market_changes.get(ticker_code, 0)
            if ticker_code in ["^HSI", "KWEB", "KSA", "EWZ", "ASEA", "AAXJ", "XLK", "XBI", "XOP", "XLE", "IXC", "SOXX", "IYR", "AGG", "DBC"]:
                estimated_iopv = last_nav * (1 + asset_change) 
            else:
                estimated_iopv = last_nav * (1 + asset_change) * (1 + cny_change)

        # C. 计算实时溢价率
        if estimated_iopv > 0:
            premium_rate = (current_price / estimated_iopv) - 1
        else:
            premium_rate = 0.0

        # D. 精准解析申购状态
        status_str = "✅ 自由申购"
        try:
            pc_url = f"https://fund.eastmoney.com/{fund_code}.html"
            html_content = requests.get(pc_url, headers=headers_pc, timeout=4).content.decode('utf-8')
            if "暂停申购" in html_content:
                status_str = "❌ 暂停申购"
            else:
                limit_info = re.search(r'限制大额申购.*?(\d+元|\d+万)', html_content)
                if limit_info:
                    status_str = f"⚠️ 限购 {limit_info.group(1)}"
                elif "限购" in html_content:
                    detail_limit = re.search(r'单日限额([^< canvas\s]+)', html_content)
                    if detail_limit: status_str = f"⚠️ 限购 {detail_limit.group(1)}"
        except:
            status_str = "✅ 自由申购(估)"

        results.append({
            "代码": fund_code,
            "名称": fund_name,
            "现价": current_price,
            "估算IOPV": round(estimated_iopv, 4),
            "实时溢价率": f"{premium_rate:.2%}",
            "今日成交额": f"{amount/10000:.1f}万",
            "申购状态": status_str,
            "raw_premium": premium_rate
        })

    df = pd.DataFrame(results).sort_values(by="raw_premium", ascending=False) 
    
    print("🔥 ====== 全市场动态Top 50 LOF/场内基金套利监控大盘 ======")
    print(df[["代码", "名称", "现价", "估算IOPV", "实时溢价率", "今日成交额", "申购状态"]].to_string(index=False))
    print("====================================================================\n")

    alert_funds = df[(df['raw_premium'] > 0.03) & (df['申购状态'] != "❌ 暂停申购")]
    if not alert_funds.empty:
        msg_markdown = "### 🚨 发现全动态高成交量LOF/ETF套利机会！\n"
        for _, row in alert_funds.iterrows():
            msg_markdown += f"- **{row['名称']} ({row['代码']})**\n"
            msg_markdown += f"  - 实时溢价率：`{row['实时溢价率']}` (成交额:{row['今日成交额']})\n"
            msg_markdown += f"  - 现价/估算IOPV：{row['现价']} / {row['估算IOPV']}\n"
            msg_markdown += f"  - 状态：{row['申购状态']}\n\n"
        
        send_notification(msg_markdown)

if __name__ == "__main__":
    get_all_iopv()
