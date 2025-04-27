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
        rs_url = f'https://raw.githubusercontent.com/dalinaum/rs/main/docs/_posts/{check_date}-krx-rs.markdown'
        price_url = f'https://raw.githubusercontent.com/dalinaum/rs/main/DATA/{check_date}/{code}-{name}.csv'
        rs_file = f"{check_date}-krx-rs.markdown"
        price_file = f"{check_date}/{code}-{name}.csv"
        print(f"[{rs_file}] 대조중, [{price_file}] 대조중")
        rs_status = requests.head(rs_url).status_code
        price_status = requests.head(price_url).status_code
        print(f"[{check_date}] RS:{rs_status}, PRICE:{price_status}")
        if rs_status == 200 and price_status == 200:
            print(f"==> 반환 날짜: {check_date}")
            return check_date
    raise Exception("최근 30일 내 둘 다 있는 날짜 없음")

def load_rs_from_markdown(date_str, code):
    url = f"https://raw.githubusercontent.com/dalinaum/rs/main/docs/_posts/{date_str}-krx-rs.markdown"
    print(f"[RS 마크다운 파일 로드] {url}")
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
    print(f"\n[디버그] RS 마크다운 컬럼명 목록: {df.columns.tolist()}")

    # 종목코드 추출
    def get_code(x):
        m = re.search(r'\[(\d{6})\]', x)
        return m.group(1) if m else None

    df['Code'] = df[header[0]].apply(get_code)
    df['Code'] = df['Code'].astype(str).str.strip().str.zfill(6)
    code = str(code).strip().zfill(6)

    # RS 값 추출 (한글 '상대강도' 컬럼)
    rs_col = [col for col in df.columns if '상대강도' in col][0]

    def extract_rs_value(x):
        # 숫자(정수, 소수 가능)로 시작하는 부분만 추출
        m = re.match(r'^\d+', str(x).strip())
        return float(m.group()) if m else float('nan')

    df['RS'] = df[rs_col].apply(extract_rs_value)
    df = df.dropna(subset=['Code'])  # 코드 없는 행 제거

    # 종목 찾기 (정확히 코드 일치)
    rs_row = df[df['Code'] == code]
    return rs_row

def load_stock_price_csv(base_url, date, code, name):
    url = f"{base_url}/{date}/{code}-{name}.csv"
    print(f"[가격 데이터 CSV 로드] {url}")
    resp = requests.get(url)
    if resp.status_code != 200:
        raise FileNotFoundError(f"{url} 파일이 없음")
    df = pd.read_csv(StringIO(resp.text))
    return df

def calc_ma(series, window):
    return series.rolling(window=window).mean()

def mtt_checklist(price_df, rs):
    price_df = price_df.copy()
    price_df['MA50'] = calc_ma(price_df['Close'], 50)
    price_df['MA150'] = calc_ma(price_df['Close'], 150)
    price_df['MA200'] = calc_ma(price_df['Close'], 200)

    latest = price_df.iloc[-1]
    close = float(latest['Close'])
    ma50 = float(latest['MA50'])
    ma150 = float(latest['MA150'])
    ma200 = float(latest['MA200'])

    prev50 = float(price_df.iloc[-2]['MA50']) if len(price_df) > 1 else ma50
    prev200 = float(price_df.iloc[-21]['MA200']) if len(price_df) > 20 else ma200

    # 52주(252거래일) 고가/저가 계산
    recent_252 = price_df.tail(252)
    min_52w = float(recent_252['Close'].min())
    max_52w = float(recent_252['Close'].max())

    # 조건 (한글 설명)
    checks = [
        ("주가 > 150일선과 200일선", close > ma150 and close > ma200),
        ("150일 이동평균선 > 200일 이동평균선", ma150 > ma200),
        ("200일 이동평균선이 1개월 이상 상승추세", ma200 > prev200),
        ("50일 이동평균선 > 150일선과 200일선", ma50 > ma150 and ma50 > ma200),
        ("주가 > 50일 이동평균선", close > ma50),
        ("주가가 52주(1년) 최저가 대비 30% 이상", (close - min_52w) / min_52w >= 0.3 if min_52w > 0 else False),
        ("주가가 52주(1년) 최고가 대비 25% 이내", (max_52w - close) / max_52w <= 0.25 if max_52w > 0 else False),
        ("상대강도(RS) 지수가 70 이상", rs >= 70),
    ]
    return checks, latest['Date']

def format_mtt_report(stock_name, 기준일, checklist, rs_value, 참조일자):
    checkmark = "✅"
    cross = "❌"
    pass_count = 0
    lines = []

    for i, (desc, passed) in enumerate(checklist, 1):
        # 8번 항목이면 RS 수치 추가 표기
        if i == 8:
            emoji = checkmark if passed else cross
            lines.append(f"{i}. {desc} {emoji} (현재 RS: {int(rs_value)})")
        else:
            emoji = checkmark if passed else cross
            lines.append(f"{i}. {desc} {emoji}")
        if passed:
            pass_count += 1

    all_pass = pass_count == len(checklist)
    summary = f"\n▶ {'ALL PASS 🎉' if all_pass else f'{pass_count}/{len(checklist)} PASS'}"
    date_line = f"\n⚠ {참조일자} 데이터 기준"
    return f"[MTT 체크리스트 - {stock_name} ({기준일})]\n" + "\n".join(lines) + summary + date_line

def get_first_float(val):
    """앞에 나오는 숫자만 추출해서 float으로 변환."""
    m = re.search(r'\d+(\.\d+)?', str(val))
    return float(m.group()) if m else float('nan')

if __name__ == "__main__":
    stock_list_url = 'https://raw.githubusercontent.com/dalinaum/rs/refs/heads/main/krx-list.csv'
    stock_list_df = pd.read_csv(stock_list_url, dtype={'Code':str})
    stock_list_df = stock_list_df[['Code', 'Name']]

    user_input = input("종목명 또는 코드 입력: ")
    code, name = parse_stock_input(user_input, stock_list_df)
    if code is None:
        print("입력에서 종목명을 찾지 못했습니다.")
        exit(1)
    try:
        latest_date = get_latest_date(code, name)
        rs_row = load_rs_from_markdown(latest_date, code)
        if rs_row.empty:
            print("RS 데이터에서 해당 종목 없음")
            exit(1)
        rs_value_raw = rs_row.iloc[0]['RS']
        rs_value = get_first_float(rs_value_raw)
        price_df = load_stock_price_csv('https://raw.githubusercontent.com/dalinaum/rs/main/DATA', latest_date, code, name)
        checklist, 기준일 = mtt_checklist(price_df, rs_value)
        report = format_mtt_report(name, 기준일, checklist, rs_value, latest_date)
        print(report)
    except Exception as e:
        print(f"실행 중 오류 발생: {e}")
