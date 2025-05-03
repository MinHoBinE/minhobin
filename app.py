from flask import Flask, request, render_template_string, jsonify
import pandas as pd
import traceback
import difflib
import requests
import base64
import os
import io
import time
from datetime import datetime
from MinhoReport import (
    parse_stock_input, get_latest_date, load_rs_from_markdown,
    load_stock_price_csv, mtt_checklist, format_mtt_report, get_first_float
)

app = Flask(__name__)

# GitHub API 설정
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
REPO_OWNER = 'MinHoBinE'
REPO_NAME = 'minhobin'
FILE_PATH = 'data/analysis_history.csv'

def save_to_github(query, stock_name, stock_code, result, error):
    if not GITHUB_TOKEN:
        print("GitHub 토큰이 설정되지 않았습니다.")
        return

    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }

    url = f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}'
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            content = base64.b64decode(response.json()['content']).decode('utf-8')
            df = pd.read_csv(io.StringIO(content))
            sha = response.json()['sha']
        else:
            df = pd.DataFrame(columns=['query', 'stock_name', 'stock_code', 'pass_count', 'error', 'created_at'])
            sha = None
    except Exception as e:
        print("기존 파일 로드 실패:", e)
        df = pd.DataFrame(columns=['query', 'stock_name', 'stock_code', 'pass_count', 'error', 'created_at'])
        sha = None

    pass_count = result.count('✅') if result else 0

    new_data = pd.DataFrame([{
        'query': query,
        'stock_name': stock_name or '',
        'stock_code': stock_code or '',
        'pass_count': pass_count,
        'error': error or '',
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }])

    df = pd.concat([df, new_data], ignore_index=True)
    csv_content = df.to_csv(index=False, encoding='utf-8-sig')

    data = {
        'message': f'Add analysis history: {query}',
        'content': base64.b64encode(csv_content.encode('utf-8-sig')).decode(),
        'branch': 'main'
    }
    if sha:
        data['sha'] = sha

    try:
        response = requests.put(url, headers=headers, json=data)
        print("GitHub에 저장 성공!" if response.ok else f"GitHub 저장 실패: {response.text}")
    except Exception as e:
        print("GitHub 저장 실패:", e)

STOCK_LIST_URL = 'https://raw.githubusercontent.com/dalinaum/rs/refs/heads/main/krx-list.csv'
stock_map = pd.read_csv(STOCK_LIST_URL, dtype={'Code': str})[['Code', 'Name']]
stock_names = stock_map['Name'].tolist()

HTML = """
<!doctype html>
<html lang=\"ko\">
<head>
    <meta charset=\"utf-8\">
    <title>📈 Minervini Trend Template 분석기 📊</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, \"Helvetica Neue\", Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; }
        h1 { font-size: clamp(16px, 4.985vw, 33px); text-align: center; white-space: normal; }
        form { max-width: 600px; margin: 0 auto; text-align: center; }
        .input-group { display: flex; gap: 10px; margin-bottom: 20px; position: relative; justify-content: center; }
        input[type=\"text\"] { flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 16px; min-width: 0; }
        button { padding: 10px 20px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
        button:hover { background-color: #45a049; }
        .container { max-width: 600px; margin: 0 auto; text-align: center; }
        .stock-name-heading { font-size: 20px; margin: 10px 0; font-weight: bold; color: #333; }
        .mtt-result-box { font-size: 1.1em; border-radius: 12px; padding: 14px; margin-top: 20px; background: #f8f9fa; color: black; white-space: pre-wrap; text-align: left; }
        .naver-button { text-decoration: none; color: white; background: #4CAF50; padding: 10px 20px; border-radius: 6px; display: inline-block; font-size: 16px; margin-top: 16px; }
        .error { color: #ff4444; padding: 10px; border-radius: 4px; background-color: #ffebee; margin: 10px 0; }
        #suggestions { position: absolute; top: 100%; left: 0; right: 0; background: white; border: 1px solid #ddd; border-radius: 4px; max-height: 200px; overflow-y: auto; display: none; z-index: 1000; text-align: left; }
        .suggestion-item { padding: 8px 12px; cursor: pointer; text-align: left; }
        .suggestion-item:hover { background-color: #f0f0f0; }
    </style>
</head>
<body>
    <h1>📈 Minervini Trend Template 분석기 📊</h1>
    <form method=\"post\" id=\"search-form\">
        <div class=\"input-group\">
            <input type=\"text\" name=\"query\" id=\"stock-input\" placeholder=\"예: 삼성전자 또는 005930\" required autocomplete=\"off\">
            <button type=\"submit\" id=\"analyze-btn\">분석하기</button>
            <div id=\"suggestions\"></div>
        </div>
    </form>

    {% if result %}
        <div class=\"container\">
            {% if stock_name and stock_code %}<div class=\"stock-name-heading\">📌 {{ stock_name }} ({{ stock_code }})</div>{% endif %}
            {% if img_url %}
            <div><img src=\"{{ img_url }}\" alt=\"일봉 캔들 차트\" style=\"width: 100%; border: 1px solid #ccc; border-radius: 8px;\"></div>
            {% endif %}

            <div class=\"mtt-result-box\">{{ result }}</div>

            {% if stock_code %}
            <div><a class=\"naver-button\" href=\"https://finance.naver.com/item/main.naver?code={{ stock_code }}\" target=\"_blank\">🔗 네이버에서 자세히 보기</a></div>
            {% endif %}
        </div>
    {% elif error %}
        <div class=\"error\">❗ 오류 발생: {{ error }}</div>
    {% endif %}

    <script>
        const input = document.getElementById('stock-input');
        const suggestions = document.getElementById('suggestions');
        const form = document.getElementById('search-form');
        let timeoutId;
        let selectedIndex = -1;

        input.addEventListener('input', function(e) {
            clearTimeout(timeoutId);
            const query = e.target.value.trim();
            if (query.length < 2) {
                suggestions.style.display = 'none';
                return;
            }
            timeoutId = setTimeout(() => {
                fetch(`/suggest?q=${encodeURIComponent(query)}`)
                    .then(response => response.json())
                    .then(data => {
                        suggestions.innerHTML = '';
                        selectedIndex = -1;
                        if (data.length > 0) {
                            data.forEach((item, index) => {
                                const div = document.createElement('div');
                                div.className = 'suggestion-item';
                                div.textContent = item;
                                div.addEventListener('click', () => {
                                    input.value = item;
                                    suggestions.style.display = 'none';
                                    form.submit();
                                });
                                suggestions.appendChild(div);
                            });
                            suggestions.style.display = 'block';
                        } else {
                            suggestions.style.display = 'none';
                        }
                    });
            }, 300);
        });

        input.addEventListener('keydown', function(e) {
            const items = suggestions.querySelectorAll('.suggestion-item');
            if (e.key === 'ArrowDown') {
                selectedIndex = (selectedIndex + 1) % items.length;
            } else if (e.key === 'ArrowUp') {
                selectedIndex = (selectedIndex - 1 + items.length) % items.length;
            } else if (e.key === 'Enter') {
                if (selectedIndex >= 0 && items[selectedIndex]) {
                    e.preventDefault();
                    input.value = items[selectedIndex].textContent;
                    suggestions.style.display = 'none';
                    form.submit();
                }
            }
            items.forEach((item, index) => {
                item.style.backgroundColor = (index === selectedIndex) ? '#e0e0e0' : '';
            });
        });

        document.addEventListener('click', function(e) {
            if (!input.contains(e.target) && !suggestions.contains(e.target)) {
                suggestions.style.display = 'none';
            }
        });

        window.onload = () => {
            if (window.matchMedia('(hover: hover)').matches) {
                input.focus();
            }
        };
    </script>
</body>
</html>
"""

@app.route("/suggest")
def suggest():
    q = request.args.get("q", "").lower()  # 소문자로 변환
    lowered_names = {name.lower(): name for name in stock_names}  # 소문자 → 원본 매핑
    matches = difflib.get_close_matches(q, lowered_names.keys(), n=10, cutoff=0.3)
    original_matches = [lowered_names[m] for m in matches]
    return jsonify(original_matches)

@app.route("/", methods=["GET", "POST"])
def index():
    result = error = None
    stock_name = stock_code = img_url = None

    if request.method == "POST":
        q = request.form["query"]
        try:
            code, name = parse_stock_input(q, stock_map)
            if code is None:
                raise ValueError("종목을 찾을 수 없습니다. 정확히 입력하거나 자동완성에서 선택해 주세요.")

            latest_date = get_latest_date(code, name)
            rs_row = load_rs_from_markdown(latest_date, code)
            if rs_row.empty:
                raise ValueError("RS 데이터가 없습니다.")

            rs_val = get_first_float(rs_row.iloc[0]['RS'])
            price_df = load_stock_price_csv('https://raw.githubusercontent.com/dalinaum/rs/main/DATA', latest_date, code, name)
            checklist, 기준일 = mtt_checklist(price_df, rs_val)
            result = format_mtt_report(name, 기준일, checklist, rs_val)
            stock_name = name
            stock_code = code
            sidcode = int(time.time() * 1000)
            img_url = f"https://ssl.pstatic.net/imgfinance/chart/item/candle/day/{code}.png?sidcode={sidcode}"

        except Exception as e:
            error = str(e)
            print("분석 중 오류 발생:", e)
            print(traceback.format_exc())

        try:
            save_to_github(q, stock_name, stock_code, result, error)
        except Exception as e:
            print("GitHub 저장 중 오류 발생:", e)
            print(traceback.format_exc())

    return render_template_string(HTML, result=result, error=error, stock_code=stock_code, img_url=img_url, stock_name=stock_name)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
