import pandas as pd
import requests
import re
from io import StringIO
from datetime import datetime, timedelta

def parse_stock_input(user_input, stock_map):
    # 종목코드가 입력됐을 때
    code_match = re.search(r'\b\d{6}\b', user_input)
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
        rs_url    = f'https://raw.githubusercontent.com/dalinaum/rs/main/docs/_posts/{check_date}-krx-rs.markdown'
        price_url = f'https://raw.githubusercontent.com/dalinaum/rs/main/DATA/{check_date}/{code}-{name}.csv'
        rs_status    = requests.head(rs_url).status_code
        price_status = requests.head(price_url).status_code
        print(f"[{check_date}] RS:{rs_status}, PRICE:{price_status}")
        if rs_status == 200 and price_status == 200:
            return check_date
    raise Exception("최근 30일 내 둘 다 있는 날짜 없음")

def load_rs_from_markdown(date_str, code):
    url = f"https://raw.githubusercontent.com/dalinaum/rs/main/docs/_posts/{date_str}-krx-rs.markdown"
    resp = requests.get(url)
    if resp.status_code != 200:
        raise FileNotFoundError(f"RS 표를 못 찾음: {url}")
    lines = resp.text.split('\n')
    # 테이블 시작점 찾기 (컬럼에 '상대강도' 포함 줄)
    start_idx = [i for i, l in enumerate(lines) if l.strip().startswith('|') and '상대강도' in l][0]
    table_lines = []
    for l in lines[start_idx:]:
        if l.strip().startswith('|'):
            table_lines.append(l.strip())
        else:
            break
    header = [h.strip() for h in table_lines[0].strip('|').split('|')]
    rows = [r.strip('|') for r in table_lines[2:]]  # [1]=구분선
    records = [[c.strip() for c in row.split('|')] for row in rows if row.strip()]
    df = pd.DataFrame(records, columns=header)

    # 종목코드 추출
    df['Code'] = df[header[0]].str.extract(r'\[(\d{6})\]')[0].str.zfill(6)
    # RS 값 추출
    rs_col = [col for col in df.columns if '상대강도' in col][0]
    df['RS'] = df[rs_col].str.extract(r'^(\d+)')[0].astype(float)
    df = df.dropna(subset=['Code'])

    return df[df['Code'] == str(code).zfill(6)]

def load_stock_price_csv(base_url, date, code, name):
    url = f"{base_url}/{date}/{code}-{name}.csv"
    resp = requests.get(url)
    if resp.status_code != 200:
        raise FileNotFoundError(f"{url} 파일이 없음")
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
    recent_252 = price_df.tail(252)
    min_52w = float(recent_252['Close'].min())
    max_52w = float(recent_252['Close'].max())

    checks = [
        ("주가 > 150일선과 200일선", latest['Close'] > latest['MA150'] and latest['Close'] > latest['MA200']),
        ("150일 이동평균선 > 200일 이동평균선", latest['MA150'] > latest['MA200']),
        ("200일 이동평균선이 1개월 이상 상승추세", latest['MA200'] > prev200),
        ("50일 이동평균선 > 150/200일선", latest['MA50'] > latest['MA150'] and latest['MA50'] > latest['MA200']),
        ("주가 > 50일 이동평균선", latest['Close'] > latest['MA50']),
        ("주가가 52주(1년) 최저가 대비 30% 이상", (latest['Close'] - min_52w) / min_52w >= 0.3 if min_52w > 0 else False),
        ("주가가 52주(1년) 최고가 대비 25% 이내", (max_52w - latest['Close']) / max_52w <= 0.25 if max_52w > 0 else False),
        ("상대강도(RS) 지수가 70 이상", rs >= 70),
    ]
    return checks, latest['Date']

def format_mtt_report(stock_name, 기준일, checklist, rs_value):
    checkmark = "✅"
    cross     = "❌"
    pass_count = 0
    lines = []

    for i, (desc, passed) in enumerate(checklist, 1):
        emoji = checkmark if passed else cross
        extra = f" (현재 RS: {int(rs_value)})" if i == 8 else ""
        lines.append(f"{i}. {desc} {emoji}{extra}")
        if passed:
            pass_count += 1

    all_pass = (pass_count == len(checklist))
    summary  = f"\n▶ {'ALL PASS 💯 🎉' if all_pass else f'{pass_count}/{len(checklist)} PASS'}"
    date_line = f"\n⚠ {기준일} 데이터 기준"

    return (
        f"[MTT 체크리스트 - {stock_name} ({기준일})]\n"
        + "\n".join(lines)
        + summary
        + date_line
    )

def get_first_float(val):
    m = re.search(r'\d+(\.\d+)?', str(val))
    return float(m.group()) if m else float('nan')

if __name__ == "__main__":
    stock_list_url = 'https://raw.githubusercontent.com/dalinaum/rs/refs/heads/main/krx-list.csv'
    stock_list_df  = pd.read_csv(stock_list_url, dtype={'Code':str})[['Code','Name']]

    user_input = input("종목명 또는 코드 입력: ")
    code, name = parse_stock_input(user_input, stock_list_df)
    if code is None:
        print("입력에서 종목명을 찾지 못했습니다.")
        exit(1)

    try:
        latest_date = get_latest_date(code, name)
        rs_row     = load_rs_from_markdown(latest_date, code)
        if rs_row.empty:
            print("RS 데이터에서 해당 종목 없음")
            exit(1)
        rs_value = get_first_float(rs_row.iloc[0]['RS'])

        price_df = load_stock_price_csv(
            'https://raw.githubusercontent.com/dalinaum/rs/main/DATA',
             latest_date, code, name
        )
        checklist, 기준일 = mtt_checklist(price_df, rs_value)

        # 참조일자 없이 기준일만 사용
        report = format_mtt_report(name, 기준일, checklist, rs_value)
        print(report)

    except Exception as e:
        print(f"실행 중 오류 발생: {e}")
