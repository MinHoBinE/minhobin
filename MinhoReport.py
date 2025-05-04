import pandas as pd
import requests
import re
from io import StringIO
from datetime import datetime, timedelta

def parse_stock_input(user_input, stock_map):
    # 종목코드가 입력됐을 때
    code_match = re.search(r"\b\d{6}\b", user_input)
    if code_match:
        code = code_match.group()
        row = stock_map[stock_map['Code'] == code]
        if not row.empty:
            name = row['Name'].values[0]
            return code, name
    # 종목명이 입력됐을 때 (이름 길이 긴 순서로 매칭)
    stock_map_sorted = stock_map.sort_values('Name', key=lambda x: x.str.len(), ascending=False)
    for name in stock_map_sorted['Name']:
        if name in user_input:
            code = stock_map[stock_map['Name'] == name]['Code'].values[0]
            return code, name
    return None, None

def get_latest_date(code, name):
    today = datetime.now()
    for i in range(30):
        check_date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
        rs_url = f'https://raw.githubusercontent.com/dalinaum/rs/main/docs/_posts/{check_date}-krx-rs.markdown'
        price_url = f'https://raw.githubusercontent.com/dalinaum/rs/main/DATA/{check_date}/{code}-{name}.csv'
        print(f"[{check_date}] RS 확인, 가격 확인")
        if requests.head(rs_url).status_code == 200 and requests.head(price_url).status_code == 200:
            return check_date
    raise Exception("최근 30일 내 둘 다 있는 날짜 없음")

def load_rs_from_markdown(date_str, code):
    url = f"https://raw.githubusercontent.com/dalinaum/rs/main/docs/_posts/{date_str}-krx-rs.markdown"
    resp = requests.get(url)
    if resp.status_code != 200:
        raise FileNotFoundError(f"RS 마크다운 파일 못 찾음: {url}")
    lines = resp.text.split('\n')
    start_idx = next(i for i, l in enumerate(lines) if l.strip().startswith('|') and '상대강도' in l)
    table = [l.strip() for l in lines[start_idx:] if l.strip().startswith('|')]
    header = [h.strip() for h in table[0].strip('|').split('|')]
    records = [row.strip('|').split('|') for row in table[2:] if row.strip()]
    df = pd.DataFrame([ [c.strip() for c in rec] for rec in records ], columns=header)
    df['Code'] = df[header[0]].str.extract(r"\[(\d{6})\]")[0].str.zfill(6)
    rs_col = next(c for c in df.columns if '상대강도' in c)
    df['RS'] = df[rs_col].str.extract(r'^(\d+)')[0].astype(float)
    return df[df['Code'] == str(code).zfill(6)]

def load_stock_price_csv(base_url, date, code, name):
    url = f"{base_url}/{date}/{code}-{name}.csv"
    resp = requests.get(url)
    if resp.status_code != 200:
        raise FileNotFoundError(f"가격 CSV 없음: {url}")
    return pd.read_csv(StringIO(resp.text))

def calc_ma(series, window):
    return series.rolling(window=window).mean()

def mtt_checklist(price_df, rs):
    price_df = price_df.copy()
    price_df['MA50']  = calc_ma(price_df['Close'], 50)
    price_df['MA150'] = calc_ma(price_df['Close'], 150)
    price_df['MA200'] = calc_ma(price_df['Close'], 200)
    latest = price_df.iloc[-1]
    prev200 = price_df.iloc[-21]['MA200'] if len(price_df) > 20 else latest['MA200']
    recent = price_df.tail(252)
    min52, max52 = recent['Close'].min(), recent['Close'].max()
    checks = [
        ("주가 > 150일선과 200일선", latest['Close'] > latest['MA150'] and latest['Close'] > latest['MA200']),
        ("150일선 > 200일선", latest['MA150'] > latest['MA200']),
        ("200일선 최근 1개월 상승", latest['MA200'] > prev200),
        ("50일선 > 150일선과 200일선", latest['MA50'] > latest['MA150'] and latest['MA50'] > latest['MA200']),
        ("주가 > 50일선", latest['Close'] > latest['MA50']),
        ("52주 저가 대비 +30% 이상", (latest['Close'] - min52) / min52 >= 0.3),
        ("52주 고가 대비 -25% 이내", (max52 - latest['Close']) / max52 <= 0.25),
        ("RS ≥ 70", rs >= 70),
    ]
    return checks, latest['Date']

def format_mtt_report(stock_name, 기준일, checklist, rs_value):
    # 참조일자 없이 기준일만 사용
    check, cross = "✅", "❌"
    lines = []
    passed = 0
    for i, (desc, ok) in enumerate(checklist, 1):
        emoji = check if ok else cross
        suffix = f" (현재 RS: {int(rs_value)})" if i == 8 else ''
        lines.append(f"{i}. {desc} {emoji}{suffix}\n")
        if ok: passed += 1
    summary = f"\n**▶ {'ALL PASS 💯 🎉' if passed == len(checklist) else f'{passed}/{len(checklist)} PASS'}**\n"
    date_line = f"\n⚠ {기준일} 데이터 기준\n"
    return f"**[MTT 체크리스트 - {stock_name} ({기준일})]**\n\n" + "\n".join(lines) + summary + date_line

def get_first_float(val):
    m = re.search(r"\d+(?:\.\d+)?", str(val))
    return float(m.group()) if m else float('nan')

if __name__ == "__main__":
    stock_list_url = 'https://raw.githubusercontent.com/dalinaum/rs/refs/heads/main/krx-list.csv'
    stock_map = pd.read_csv(stock_list_url, dtype={'Code':str})[['Code','Name']]

    inp = input("종목명 또는 코드 입력: ")
    code, name = parse_stock_input(inp, stock_map)
    if not code:
        print("종목명을 찾을 수 없습니다.")
        exit(1)
    try:
        latest_date = get_latest_date(code, name)
        rs_df = load_rs_from_markdown(latest_date, code)
        if rs_df.empty:
            print("RS 데이터 없음")
            exit(1)
        rs_val = get_first_float(rs_df.iloc[0]['RS'])
        price_df = load_stock_price_csv('https://raw.githubusercontent.com/dalinaum/rs/main/DATA', latest_date, code, name)
        checklist, 기준일 = mtt_checklist(price_df, rs_val)
        report = format_mtt_report(name, 기준일, checklist, rs_val)
        print(report)
    except Exception as e:
        print(f"실행 중 오류 발생: {e}")
