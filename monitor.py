import yfinance as yf
import pandas as pd
import requests
import re
import akshare as ak
import os

# 1. 从环境变量读取 PushDeer PUSH_KEY
PUSH_KEY = os.getenv("PUSH_KEY")

def get_top_50_dynamic_lof():
    """
    全盘海外化升级版：
    1. 强制将160644、501225等全网最易爆量高溢价的超级LOF全明星纳入。
    2. 动态扫描深市16号段 + 沪市501/502号段。
    3. 引入多重价格兜底，防止雅虎对个别A股代码断更导致的漏网。
    """
    print("🔄 正在构建全明星 + 沪深双市 LOF 号段的多维穿透扫描池...")
    
    # 🌟 【绝对不漏】全网高活跃、高溢价套利全明星特战队
    must_have_stars = [
        "160644.SZ", "501225.SS", "159509.SZ", "513100.SS", "513300.SS", 
        "513500.SS", "513400.SS", "513050.SS", "513030.SS", "513880.SS", 
        "520830.SS", "159329.SZ", "513730.SS", "164906.SZ", "162411.SZ",
        "162719.SZ", "160416.SZ", "501018.SS", "161129.SZ", "160216.SZ",
        "164824.SZ", "161725.SZ", "160632.SZ", "161726.SZ", "160125.SZ"
    ]
    
    # 📊 【动态捞鱼】生成深市核心 LOF 16号段 (160001 - 160160)
    sz_lof_pool = [f"16{str(i).zfill(4)}.SZ" for i in range(1, 160)]
    
    # 📊 【动态捞鱼】补全沪市核心 LOF 501/502 号段 (501000 - 501060, 501200 - 501230)
    sh_lof_pool = [f"501{str(i).zfill(3)}.SS" for i in range(0, 60)] + [f"501{str(i).zfill(3)}.SS" for i in range(200, 230)]
    
    # 合流去重，打造百级广度雷达网
    scan_pool = list(set(must_have_stars + sz_lof_pool + sh_lof_pool))
    print(f"📊 混合雷达网构建完成，当前正在高频透视全市场 {len(scan_pool)} 只场内核心品种...")

    try:
        # 批量抓取对象
        tickers_obj = yf.Tickers(' '.join(scan_pool))
        # 尝试下载今日K线快照
        history_df = yf.download(scan_pool, period="1d", group_by='ticker', progress=False)
    except Exception as e:
        print(f"❌ 雅虎财经号段批量下载失败: {e}")
        return None

    valid_funds = []
    for ticker_code in scan_pool:
        try:
            current_price = 0.0
            volume = 0.0
            
            # 轨道一：优先从历史快照中提取精准Close和Volume
            if ticker_code in history_df.columns.levels[0]:
                ticker_data = history_df[ticker_code]
                if not ticker_data.empty and pd.notna(ticker_data['Close'].iloc[-1]):
                    current_price = float(ticker_data['Close'].iloc[-1])
                    volume = float(ticker_data['Volume'].iloc[-1])
            
            # 轨道二（核心兜底）：如果快照不幸断更，直接穿透去拿它的 info 字典快照
            if current_price <= 0 or volume <= 0:
                try:
                    t_info = tickers_obj.tickers[ticker_code].info
                    current_price = float(t_info.get("regularMarketPrice", 0) or t_info.get("previousClose", 0))
                    volume = float(t_info.get("regularMarketVolume", 0) or t_info.get("volume", 0))
                except:
                    continue
            
            # 精准过滤脏数据
            if 0.1 < current_price < 200 and volume > 0:
                amount = current_price * volume # 内存动态计算成交额
                
                try:
                    fund_name = tickers_obj.tickers[ticker_code].info.get("shortName", "场内基金")
                except:
                    fund_name = "场内基金"
                    
                valid_funds.append({
                    "ticker": ticker_code,
                    "code": ticker_code.split('.')[0],
                    "name": fund_name,
                    "price": current_price,
                    "amount": amount
                })
        except:
            continue

    if not valid_funds:
        print("⚠️ 扫描池内所有品种今日成交量皆为0或雅虎接口完全未响应")
        return None

    # 完全根据成交额进行【动态倒序排列】
    df_all = pd.DataFrame(valid_funds)
    df_top50 = df_all.sort_values(by="amount", ascending=False).head(50)
    
    top_funds = {}
    for _, row in df_top50.iterrows():
        code = row['code']
        name = row['name']
        prefix = "sh" if row['ticker'].endswith("SS") else "sz"
        
        # 智能化、全方位的海外衍生标的锚定
        ticker = "DOMESTIC"
        if "纳指" in name or "NASDAQ" in name or code in ["513100", "159509", "513300", "161130"]: ticker = "NQ=F"
        elif "标普" in name or "S&P" in name or code in ["513500", "161125"]: ticker = "ES=F"
        elif "芯片" in name or "半导体" in name or code in ["501225"]: ticker = "SOXX"
        elif "华宝油气" in name or code == "162411": ticker = "XOP"
        elif "石油" in name or code in ["162719", "160416"]: ticker = "XLE"
        elif "原油" in name or code in ["501018", "161129"]: ticker = "CL=F"
        elif "黄金" in name or code == "164701": ticker = "GC=F"
        elif "印度" in name or code == "164824": ticker = "^BSESN"
        elif "日经" in name or code == "513880": ticker = "NK=F"
        elif "沙特" in name or code in ["520830", "159329"]: ticker = "KSA"
        elif "中概" in name or "互联网" in name or "香港" in name or code in ["160644", "513050", "164906", "161726", "160125"]: ticker = "KWEB"
        
        top_funds[code] = [name, prefix, ticker, row['price'], row['amount']]
        
    print(f"✅ 【双轨兜底】成功在内存中算出了今日流动性最强的 {len(top_funds)} 只场内基金！")
    return top_funds

def send_notification(msg):
    print(f"[开始发送 PushDeer 推送]...\n{msg}")
    url = "https://api2.pushdeer.com/message/push"
    payload = {
        "pushkey": PUSH_KEY,
        "text": "🚨 终极穿透型全明星动态 LOF 溢价雷达",
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
    dynamic_map = get_top_50_dynamic_lof()
    if not dynamic_map:
        print("⚠️ 无法动态计算排行榜，程序终止。")
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
        fund_name, prefix, ticker_code, current_price, amount = info
        
        # 动态去天天基金抓取官方准确中文名称（单代码高频接口，通常不封IP）
        try:
            tt_url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
            tt_res = requests.get(tt_url, headers=headers_pc, timeout=3)
            real_name_match = re.search(r'"name":"([^"]*)"', tt_res.text)
            if real_name_match:
                fund_name = real_name_match.group(1)
        except:
            pass

        # 双轨制计算实时 IOPV
        estimated_iopv = 0.0
        if ticker_code == "DOMESTIC":
            try:
                tt_url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
                tt_res = requests.get(tt_url, headers=headers_pc, timeout=3)
                gsz_match = re.search(r'"gsz":"([^"]*)"', tt_res.text)
                if gsz_match:
                    estimated_iopv = float(gsz_match.group(1))
                else:
                    estimated_iopv = float(re.search(r'"dwjz":"([^"]*)"', tt_res.text).group(1))
            except:
                estimated_iopv = current_price
        else:
            last_nav = current_price
            try:
                tt_url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
                tt_res = requests.get(tt_url, headers=headers_pc, timeout=3)
                last_nav = float(re.search(r'"dwjz":"([^"]*)"', tt_res.text).group(1))
            except:
                pass
            
            asset_change = market_changes.get(ticker_code, 0)
            if ticker_code in ["^HSI", "KWEB", "KSA", "EWZ", "ASEA", "AAXJ", "XLK", "XBI", "XOP", "XLE", "IXC", "SOXX", "IYR", "AGG", "DBC"]:
                estimated_iopv = last_nav * (1 + asset_change) 
            else:
                estimated_iopv = last_nav * (1 + asset_change) * (1 + cny_change)

        # 计算真实实时溢价率
        premium_rate = (current_price / estimated_iopv) - 1 if estimated_iopv > 0 else 0.0

        # 精准解析申购状态
        status_str = "✅ 自由申购"
        try:
            pc_url = f"https://fund.eastmoney.com/{fund_code}.html"
            html_content = requests.get(pc_url, headers=headers_pc, timeout=3).content.decode('utf-8')
            if "暂停申购" in html_content:
                status_str = "❌ 暂停申购"
            else:
                limit_info = re.search(r'限制大额申购.*?(\d+元|\d+万)', html_content)
                if limit_info:
                    status_str = f"⚠️ 限购 {limit_info.group(1)}"
        except:
            status_str = "✅ 自由申购(估)"

        results.append({
            "代码": fund_code,
            "名称": fund_name,
            "现价": round(current_price, 4),
            "估算IOPV": round(estimated_iopv, 4),
            "实时溢价率": f"{premium_rate:.2%}",
            "今日成交额": f"{amount/10000:.1f}万",
            "申购状态": status_str,
            "raw_premium": premium_rate
        })

    df = pd.DataFrame(results)
    df = df.sort_values(by="raw_premium", ascending=False) 
    
    print("🔥 ====== yfinance全明星+双市号段广度动态监控大盘 ======")
    print(df[["代码", "名称", "现价", "估算IOPV", "实时溢价率", "今日成交额", "申购状态"]].to_string(index=False))
    print("====================================================================\n")

    alert_funds = df[(df['raw_premium'] > 0.03) & (df['申购状态'] != "❌ 暂停申购")]
    if not alert_funds.empty:
        msg_markdown = "### 🚨 发现明星高成交量动态LOF套利机会！\n"
        for _, row in alert_funds.iterrows():
            msg_markdown += f"- **{row['名称']} ({row['代码']})**\n"
            msg_markdown += f"  - 实时溢价率：`{row['实时溢价率']}` (最新成交额:{row['今日成交额']})\n"
            msg_markdown += f"  - 现价/估算IOPV：{row['现价']} / {row['估算IOPV']}\n"
            msg_markdown += f"  - 状态：{row['申购状态']}\n\n"
        
        send_notification(msg_markdown)

if __name__ == "__main__":
    get_all_iopv()
