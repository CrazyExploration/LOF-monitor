import yfinance as yf
import pandas as pd
import requests
import re
import json
from io import StringIO
import os

# 1. 从环境变量读取 PushDeer PUSH_KEY
PUSH_KEY = os.getenv("PUSH_KEY")

def get_top_50_all_lof():
    """
    通过天天基金全量场内即时接口，动态获取今天全市场成交额最大的50只LOF/场内基金
    """
    print("🔄 正在动态获取全市场成交额 Top 50 的场内 LOF/活跃基金...")
    
    # 采用天天基金官方全量场内基金排行榜接口，数据极度稳定，标准JSON，且包含了完整的成交额数据
    url = "https://fundapi.eastmoney.com/fundmarkethand/common/GetFundMarketList?sType=全部场内基金&pageIndex=1&pageSize=200&sortColumn=VOLUME&sortOrder=desc&_v="
    headers = {
        "Referer": "https://fund.eastmoney.com/cnjy_list.html",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    top_funds = {}
    try:
        res = requests.get(url, headers=headers, timeout=8).json()
        raw_list = res.get("data", [])
        if not raw_list:
            print("⚠️ 接口返回的基金列表为空")
            return None
            
        all_data = []
        for item in raw_list:
            # 字段映射：JJDM(基金代码), JJJC(基金简称), CJJE(成交额)
            all_data.append({
                "code": item.get("JJDM"),
                "name": item.get("JJJC"),
                "amount": float(item.get("CJJE", 0)) if item.get("CJJE") else 0.0
            })
            
        df_all = pd.DataFrame(all_data)
        
        # 智能化过滤出属于 LOF 或高发套利品种（跨境、大宗等）的场内品种
        # 天天基金榜单包含普通LOF、跨境LOF和各类行业ETF
        keyword_filter = "LOF|纳指|纳斯达克|标普|油气|原油|黄金|石油|商品|德国|法国|日经|印|沙特|巴西|亚洲|港|恒生|互联网|中概|教育|海外|芯片|白酒|消费|医药|医疗|中药|新能源|有色|煤炭|资源|券商|红利"
        df_filtered = df_all[df_all['name'].str.contains(keyword_filter, na=False, regex=True)].copy()
        
        # 按照成交额全局倒序，切出前 50 只
        df_top50 = df_filtered.sort_values(by="amount", ascending=False).head(50)
        
        for _, row in df_top50.iterrows():
            code = str(row['code'])
            name = row['name']
            
            # 判断沪深前缀：沪市上市通常5开头或50开头，深市上市1开头或15开头
            prefix = "sh" if code.startswith(('5', '60', '50')) else "sz"
            
            # 智能化模糊匹配海外挂钩的标的期货代码
            ticker = "DOMESTIC" 
            if "纳指" in name or "纳斯达克" in name: ticker = "NQ=F"
            elif "标普500" in name or "美国50" in name: ticker = "ES=F"
            elif "道琼斯" in name: ticker = "YM=F"
            elif "油气" in name or "华宝油气" in name: ticker = "XOP"
            elif "石油" in name: ticker = "XLE"
            elif "原油" in name: ticker = "CL=F"
            elif "黄金" in name: ticker = "GC=F"
            elif "商品" in name or "抗通胀" in name: ticker = "DBC"
            elif "德国" in name: ticker = "^GDAXI"
            elif "法国" in name: ticker = "^FCHI"
            elif "印度" in name: ticker = "^BSESN"
            elif "日经" in name: ticker = "NK=F"
            elif "沙特" in name: ticker = "KSA"
            elif "巴西" in name: ticker = "EWZ"
            elif "互联网" in name or "中概" in name or "教育" in name: ticker = "KWEB"
            elif "恒生" in name or "新经济" in name or "香港" in name: ticker = "^HSI"
            elif "芯片" in name: ticker = "SOXX"
            elif "医药" in name or "生物" in name:
                if "海外" in name or "美国" in name or "创新药" in name and ("ETF" in name and prefix=="sz" and int(code)>159000): ticker = "XBI"
            elif "东南亚" in name: ticker = "ASEA"
            elif "亚太" in name: ticker = "AAXJ"
            
            # 天天基金接口返回的成交额单位本来就是“元”
            top_funds[code] = [name, prefix, ticker, row['amount']]
            
        print(f"✅ 成功动态筛选出全市场成交最活跃的 {len(top_funds)} 只 LOF/场内基金目标！")
        return top_funds
    except Exception as e:
        print(f"❌ 动态抓取全市场Top 50成交额失败: {e}")
        return None

def send_notification(msg):
    print(f"[开始发送 PushDeer 推送]...\n{msg}")
    url = "https://api2.pushdeer.com/message/push"
    payload = {
        "pushkey": PUSH_KEY,
        "text": "🚨 全市场 Top50 活跃 LOF 溢价雷达",
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
    dynamic_map = get_top_50_all_lof()
    if not dynamic_map:
        print("⚠️ 无法获取动态排行，程序终止。")
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
                    detail_limit = re.search(r'单日限额([^<、\s]+)', html_content)
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

    # 输出全市场大盘看板
    df = pd.DataFrame(results)
    df = df.sort_values(by="raw_premium", ascending=False) 
    
    print("🔥 ====== 全市场流动性最强 Top 50 LOF/场内基金套利监控大盘 ======")
    print(df[["代码", "名称", "现价", "估算IOPV", "实时溢价率", "今日成交额", "申购状态"]].to_string(index=False))
    print("====================================================================\n")

    # 5. 过滤出：【有套利价值 > 3%】且【没有暂停申购】的基金进行推送通知
    alert_funds = df[(df['raw_premium'] > 0.03) & (df['申购状态'] != "❌ 暂停申购")]
    if not alert_funds.empty:
        msg_markdown = "### 🚨 发现全市场高成交量LOF/ETF套利机会！\n"
        for _, row in alert_funds.iterrows():
            msg_markdown += f"- **{row['名称']} ({row['代码']})**\n"
            msg_markdown += f"  - 实时溢价率：`{row['实时溢价率']}` (成交额:{row['今日成交额']})\n"
            msg_markdown += f"  - 现价/估算IOPV：{row['现价']} / {row['估算IOPV']}\n"
            msg_markdown += f"  - 状态：{row['申购状态']}\n\n"
        
        send_notification(msg_markdown)

if __name__ == "__main__":
    get_all_iopv()
