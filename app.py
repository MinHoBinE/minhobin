from flask import Flask, request, render_template_string
import pandas as pd
import traceback
from MinhoReport import (
    parse_stock_input, get_latest_date, load_rs_from_markdown,
    load_stock_price_csv, mtt_checklist, format_mtt_report, get_first_float
)

app = Flask(__name__)

HTML = """
<!doctype html>
<html lang="ko">
<head>
    <meta charset="utf-8">
    <title>📈 Minervini Trend Template 자동 분석기 📊</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
        }
        h1 {
            text-align: center;
            margin-bottom: 30px;
        }
        .input-group {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        input[type="text"] {
            flex: 1;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 16px;
        }
        button {
            padding: 10px 20px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
        }
        button:hover {
            background-color: #45a049;
        }
        .mtt-result-box {
            font-size: 1.1em;
            border-radius: 12px;
            padding: 14px;
            margin-top: 10px;
            background: #f8f9fa;
            color: black;
            white-space: pre-wrap;
        }
        @media (prefers-color-scheme: dark) {
            body {
                background-color: #1a1a1a;
                color: #f1f1f1;
            }
            .mtt-result-box {
                background: #222831 !important;
                color: #f1f1f1 !important;
            }
            input[type="text"] {
                background-color: #333;
                color: #fff;
                border-color: #444;
            }
        }
        .error {
            color: #ff4444;
            padding: 10px;
            border-radius: 4px;
            background-color: #ffebee;
            margin: 10px 0;
        }
        .info {
            color: #0d47a1;
            padding: 10px;
            border-radius: 4px;
            background-color: #e3f2fd;
            margin: 10px 0;
        }
        .warning {
            color: #f57c00;
            padding: 10px;
            border-radius: 4px;
            background-color: #fff3e0;
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <h1>📈 Minervini Trend Template 자동 분석기 📊</h1>
    <p><strong>종목명(또는 6자리 코드)</strong>를 입력하면 최신 MTT 체크리스트 결과가 바로 출력됩니다.<br>예: 삼성전자, 005930</p>
    
    <form method="post">
        <div class="input-group">
            <input type="text" name="query" placeholder="예: 삼성전자 또는 005930" required>
            <button type="submit">분석하기</button>
        </div>
    </form>

    {% if result %}
        <div class="mtt-result-box">{{ result }}</div>
    {% elif error %}
        <div class="error">❗ 오류 발생: {{ error }}</div>
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
                raise ValueError("종목을 찾을 수 없습니다. 예: 삼성전자, 005930")

            latest_date = get_latest_date(code, name)
            rs_row = load_rs_from_markdown(latest_date, code)
            if rs_row.empty:
                raise ValueError("RS 데이터가 없습니다.")
            
            rs_val = get_first_float(rs_row.iloc[0]['RS'])
            price_df = load_stock_price_csv('https://raw.githubusercontent.com/dalinaum/rs/main/DATA', latest_date, code, name)
            checklist, 기준일 = mtt_checklist(price_df, rs_val)
            result = format_mtt_report(name, 기준일, checklist, rs_val)

        except Exception as e:
            error = str(e)

    return render_template_string(HTML, result=result, error=error)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
