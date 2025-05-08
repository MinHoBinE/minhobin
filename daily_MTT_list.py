import requests
import re
from datetime import datetime, timedelta
import os

# === 설정 ===
OUTPUT_PATH = "static/mtt-latest.html"
BASE_URL = "https://raw.githubusercontent.com/dalinaum/rs/main/docs/_posts"

# === 날짜 기준 가장 가까운 거래일 찾기 ===
def get_latest_trading_date(before_date=None):
    if before_date is None:
        before_date = datetime.today()
    for i in range(1, 15):  # 최대 2주 전까지 탐색
        candidate = before_date - timedelta(days=i)
        date_str = candidate.strftime("%Y-%m-%d")
        url = f"{BASE_URL}/{date_str}-krx-trend-template.markdown"
        if requests.head(url).status_code == 200:
            return date_str
    raise Exception("이전 거래일 마크다운을 찾을 수 없습니다.")

# === 마크다운에서 종목코드, 이름, RS 추출 ===
def load_mtt_data(date_str):
    url = f"{BASE_URL}/{date_str}-krx-trend-template.markdown"
    head_check = requests.head(url)
    if head_check.status_code != 200:
        raise FileNotFoundError(f"{date_str} 마크다운 없음: {url}")
    response = requests.get(url)
    response.raise_for_status()
    markdown = response.text
    pattern = r'\[(\d{6})\]\(https://finance\.daum\.net/quotes/A\d{6}\)\|([^\|]+)\|[^\|]+\|(\d{2})\|'
    return re.findall(pattern, markdown)

# === 종목별 HTML 블록 생성 ===
def make_html_block(code, name, rs, is_new=False):
    new_tag = "<span class='new'>✨ 신규 진입</span>" if is_new else ""
    return f'''
<div class="stock-block">
  <div class="stock-title">
    <div class="left">
      📌 {name} ({code}) <span class="rs">RS: {rs}</span>
    </div>
    {new_tag}
  </div>
  <a href="https://finance.naver.com/item/main.nhn?code={code}" target="_blank">
    <img src="https://ssl.pstatic.net/imgfinance/chart/item/candle/day/{code}.png">
  </a>
</div>'''

# === 메인 실행 ===
def main():
    today = datetime.today()
    today_str = today.strftime("%Y-%m-%d")

    # 1. today 기준 데이터 찾기
    try:
        today_matches = load_mtt_data(today_str)
    except FileNotFoundError:
        print(f"❗ 오늘({today_str}) 마크다운 없음 → 가장 최근 거래일로 대체")
        today_str = get_latest_trading_date(today)
        today_matches = load_mtt_data(today_str)

    # 2. 비교 대상 전일자 찾기 (today_str보다 더 전)
    yesterday_str = get_latest_trading_date(datetime.strptime(today_str, "%Y-%m-%d"))
    yesterday_matches = load_mtt_data(yesterday_str)

    # 3. 비교 및 정렬
    yesterday_codes = {code for code, _, _ in yesterday_matches}
    today_dict = {code: (code, name, int(rs)) for code, name, rs in today_matches}

    new_entries = [v for code, v in today_dict.items() if code not in yesterday_codes]
    existing_entries = [v for code, v in today_dict.items() if code in yesterday_codes]

    new_sorted = sorted(new_entries, key=lambda x: -x[2])
    existing_sorted = sorted(existing_entries, key=lambda x: -x[2])
    final_sorted = new_sorted + existing_sorted

    # 4. HTML 생성
    html_blocks = [
        make_html_block(code, name, rs, is_new=(code not in yesterday_codes))
        for code, name, rs in final_sorted
    ]
    html_body = "\n".join(html_blocks)

    html_final = f"""<!DOCTYPE html>
<html lang=\"ko\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
  <title>MTT ALL PASS 종목 차트</title>
  <style>
    body {{
      width: 100%;
      max-width: 600px;
      margin: 0 auto;
      padding: 20px;
      box-sizing: border-box;
      font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, \"Helvetica Neue\", Arial, sans-serif;
      line-height: 1.6;
    }}
    h2 {{
      font-size: clamp(15px, 4.9vw, 30px);
      text-align: center;
      white-space: nowrap;
    }}
    .stock-block {{
      margin-bottom: 90px;
    }}
    .stock-title {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 18px;
      font-weight: bold;
      margin-bottom: 8px;
      white-space: nowrap;
      gap: 12px;
    }}
    .stock-title .left {{
      display: flex;
      gap: 8px;
      align-items: center;
    }}
    .stock-title .new {{
      color: red;
      white-space: nowrap;
      margin-left: auto;
    }}
    img {{
      width: 100%;
      max-width: 600px;
      height: auto;
      border: 1px solid #ccc;
      border-radius: 4px;
    }}
    .home-button {{
      margin-top: 40px;
      text-align: center;
    }}
    .home-button a {{
      background-color: #4CAF50;
      color: white;
      padding: 10px 20px;
      border-radius: 8px;
      text-decoration: none;
      font-weight: bold;
      display: inline-block;
      box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
    }}
  </style>
</head>
<body>
  <h2>📈 {today_str} MTT ALL PASS 리스트 💯</h2>
  <p>차트 클릭시 해당 종목의 네이버 증권 페이지로 이동합니다.<br>
  <span style=\"color: crimson;\">※ 차트 및 데이터에 수정주가 반영이 되지 않은 경우가 있으니 꼭 확인하세요!</span></p>

  {html_body}
  <div class=\"home-button\">
    <a href=\"https://minhobin.fly.dev/\">🏠 홈으로 돌아가기</a>
  </div>
</body>
</html>"""

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_final)

    print(f"✅ mtt-latest.html 생성 완료 ({today_str})")

# 실행
if __name__ == "__main__":
    main()
