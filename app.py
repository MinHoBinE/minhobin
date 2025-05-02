from flask import Flask, request, render_template_string
import pandas as pd
import traceback

from MinhoReport import (
    parse_stock_input,
    get_latest_date,
    load_rs_from_markdown,
    get_first_float,
    load_stock_price_csv,
    mtt_checklist,
    format_mtt_report
)

app = Flask(__name__)

HTML = """
<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><title>Minho 분석기</title></head>
<body>
  <h1>Minho 분석기</h1>
  <form method="post">
    <label>종목명 또는 코드: <input type="text" name="query" required></label>
    <button type="submit">분석 실행</button>
  </form>
  {% if result %}
    <pre style="background:#f0f0f0; padding:1em;">{{ result }}</pre>
  {% elif error %}
    <p style="color:red;">오류 발생: {{ error }}</p>
  {% endif %}
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    result = error = None
    if request.method == "POST":
        q = request.form["query"]
        try:
            # 종목 리스트 로드
            stock_list_url = 'https://raw.githubusercontent.com/dalinaum/rs/refs/heads/main/krx-list.csv'
            stock_map = pd.read_csv(stock_list_url, dtype={'Code':str})[['Code','Name']]

            code, name = parse_stock_input(q, stock_map)
            if code is None:
                raise ValueError("입력에서 종목을 찾을 수 없습니다.")

            latest_date = get_latest_date(code, name)
            rs_row = load_rs_from_markdown(latest_date, code)
            rs_val = get_first_float(rs_row.iloc[0]['RS'])
            price_df = load_stock_price_csv('https://raw.githubusercontent.com/dalinaum/rs/main/DATA', latest_date, code, name)
            checklist, 기준일 = mtt_checklist(price_df, rs_val)
            result = format_mtt_report(name, 기준일, checklist, rs_val, latest_date)

        except Exception as e:
            error = traceback.format_exc().splitlines()[-1]

    return render_template_string(HTML, result=result, error=error)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
