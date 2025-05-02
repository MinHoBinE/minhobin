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
        status_rs = requests.head(rs_url).status_code
        status_price = requests.head(price_url).status_code
        print(f"[{check_date}] RS:{status_rs}, PRICE:{status_price}")
        if status_rs == 200 and status_price == 200:
            return check_date
    raise Exception("최근 30일 내에 RS와 가격 데이터가 모두 있는 날짜가 없습니다.")


def load_rs_from_markdown(date_str, code):
    url = f"https://raw.githubusercontent.com/dalinaum/rs/main/docs/_posts/{date_str}-krx-rs.markdown"
    resp = requests.get(url)
    if resp.status_code != 200:
        raise FileNotFoundError(f"RS 마크다운을 찾을 수 없습니다: {url}")
    lines = resp.text.split('\n')
    start = next(i for i, l in enumerate(lines) if l.startswith('|') and '상대강도' in l)
    table = [l for l in lines[start:] if l.startswith('|')]
    header = [h.strip() for h in table[0].strip('|').split('|')]
    rows = [r.strip('|') for r in table[2:]]
    data = [row.split('|') for row in rows if row]
    df = pd.DataFrame(data, columns=header)
    df['Code'] = df[header[0]].str.extract(r"\[(\d{6})\]")[0]
    rs_col = next(c for c in df.columns if '상대강도' in c)
    df['RS'] = df[rs_col].str.extract(r'^(\d+)')[0].astype(float)
    return df[df['Code'] == code]


def load_stock_price_csv(base_url, date, code, name):
    url = f"{base_url}/{date}/{code}-{name}.csv"
    resp = requests.get(url)
    if resp.status_code != 200:
        raise FileNotFoundError(f"가격 CSV를 찾을 수 없습니다: {url}")
    return pd.read_csv(StringIO(resp.text))


def calc_ma(series, window):
    return series.rolling(window=window).mean()


def mtt_checklist(price_df, rs):
    price_df['MA50'] = calc_ma(price_df['Close'], 50)
    price_df['MA150'] = calc_ma(price_df['Close'], 150)
    price_df['MA200'] = calc_ma(price_df['Close'], 200)
    latest = price_df.iloc[-1]
    recent = price_df.tail(252)
    return [
        ("주가 > 150/200일선", latest['Close'] > latest['MA150'] and latest['Close'] > latest['MA200']),
        ("150일선 > 200일선", latest['MA150'] > latest['MA200']),
        ("200일선 1개월 상승", latest['MA200'] > price_df.iloc[-21]['MA200']),
        ("50일선 > 150/200일선", latest['MA50'] > latest['MA150'] and latest['MA50'] > latest['MA200']),
        ("주가 > 50일선", latest['Close'] > latest['MA50']),
        ("52주 저가 대비 +30%", (latest['Close'] - recent['Close'].min()) / recent['Close'].min() >= 0.3),
        ("52주 고가 대비 -25% 이내", (recent['Close'].max() - latest['Close']) / recent['Close'].max() <= 0.25),
        ("상대강도 RS ≥ 70", rs >= 70),
    ]


def format_mtt_report(stock_name, date_str, checklist, rs_value):
    symbols = ['✅' if ok else '❌' for _, ok in checklist]
    lines = []
    for i, ((desc, ok), sym) in enumerate(zip(checklist, symbols), 1):
        extra = f" (현재 RS: {int(rs_value)})" if i == 8 else ''
        lines.append(f"{i}. {desc} {sym}{extra}")
    passed = sum(ok for _, ok in checklist)
    summary = f"▶ {'ALL PASS 💯 🎉' if passed == len(checklist) else f'{passed}/{len(checklist)} PASS'}"
    return (
        f"[MTT 체크리스트 - {stock_name} ({date_str})]\n"
        + "\n".join(lines)
        + f"\n{summary}\n"
        + f"⚠ {date_str} 데이터 기준"
    )


def get_first_float(val):
    m = re.search(r"\d+(?:\.\d+)?", str(val))
    return float(m.group()) if m else float('nan')


if __name__ == '__main__':
    stock_list_url = 'https://raw.githubusercontent.com/dalinaum/rs/main/krx-list.csv'
    stock_map = pd.read_csv(stock_list_url, dtype={'Code': str})[['Code', 'Name']]

    inp = input("종목명 또는 코드 입력: ")
    code, name = parse_stock_input(inp, stock_map)
    if not code:
        print("종목을 찾을 수 없습니다.")
        exit(1)
    try:
        date_str = get_latest_date(code, name)
        rs_df = load_rs_from_markdown(date_str, code)
        if rs_df.empty:
            print("RS 데이터 없음")
            exit(1)
        rs_val = get_first_float(rs_df.iloc[0]['RS'])
        price_df = load_stock_price_csv('https://raw.githubusercontent.com/dalinaum/rs/main/DATA', date_str, code, name)
        checklist = mtt_checklist(price_df, rs_val)
        report = format_mtt_report(name, date_str, checklist, rs_val)
        print(report)
    except Exception as e:
        print(f"오류 발생: {e}")
