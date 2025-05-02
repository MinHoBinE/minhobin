from flask import Flask, request, render_template_string, jsonify
import pandas as pd
import traceback
import difflib
import requests
import base64
import os
from datetime import datetime
from MinhoReport import (
    parse_stock_input, get_latest_date, load_rs_from_markdown,
    load_stock_price_csv, mtt_checklist, format_mtt_report, get_first_float
)

app = Flask(__name__)

# GitHub API 설정
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')  # GitHub Personal Access Token
REPO_OWNER = 'MinHoBinE'  # GitHub 사용자명
REPO_NAME = 'minhobin'  # 저장소 이름
FILE_PATH = 'data/analysis_history.csv'  # 저장할 파일 경로

def save_to_github(query, stock_name, stock_code, result, error):
    if not GITHUB_TOKEN:
        print("GitHub 토큰이 설정되지 않았습니다.")
        return
    
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    # 기존 파일 내용 가져오기
    url = f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}'
    try:
        response = requests.get(url, headers=headers)
        print(f"GitHub API GET 응답: {response.status_code}")
        print(f"응답 내용: {response.text}")
        
        if response.status_code == 200:
            # 파일이 존재하면 기존 내용 가져오기
            content = base64.b64decode(response.json()['content']).decode('utf-8')
            df = pd.read_csv(pd.StringIO(content))
            sha = response.json()['sha']
        else:
            # 파일이 없으면 새로 생성
            df = pd.DataFrame(columns=['query', 'stock_name', 'stock_code', 'pass_count', 'error', 'created_at'])
            sha = None
    except Exception as e:
        print(f"기존 파일 로드 실패: {e}")
        print(f"오류 상세: {traceback.format_exc()}")
        df = pd.DataFrame(columns=['query', 'stock_name', 'stock_code', 'pass_count', 'error', 'created_at'])
        sha = None
    
    # 결과에서 패스한 항목 개수 추출
    pass_count = 0
    if result:
        pass_count = result.count('✅')
    
    # 새 데이터 추가
    new_data = pd.DataFrame([{
        'query': query,
        'stock_name': stock_name or '',
        'stock_code': stock_code or '',
        'pass_count': pass_count,
        'error': error or '',
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }])
    
    # 기존 데이터와 새 데이터 합치기
    df = pd.concat([df, new_data], ignore_index=True)
    
    # CSV로 변환
    csv_content = df.to_csv(index=False, encoding='utf-8-sig')
    
    # GitHub에 파일 업로드
    data = {
        'message': f'Add analysis history: {query}',
        'content': base64.b64encode(csv_content.encode('utf-8-sig')).decode(),
        'branch': 'main'
    }
    
    if sha:
        data['sha'] = sha
    
    try:
        response = requests.put(url, headers=headers, json=data)
        print(f"GitHub API PUT 응답: {response.status_code}")
        print(f"응답 내용: {response.text}")
        if response.status_code != 200 and response.status_code != 201:
            print(f"GitHub 저장 실패: {response.status_code}")
            print(f"응답 내용: {response.text}")
        else:
            print("GitHub에 저장 성공!")
    except Exception as e:
        print(f"GitHub 저장 실패: {e}")
        print(f"오류 상세: {traceback.format_exc()}")

def get_history():
    if not GITHUB_TOKEN:
        return []
    
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    url = f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}'
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # 파일 내용 디코딩
        content = base64.b64decode(response.json()['content']).decode('utf-8')
        df = pd.read_csv(pd.StringIO(content))
        
        # 최신순으로 정렬하고 최근 10개 반환
        df = df.sort_values('created_at', ascending=False)
        return df.head(10).values.tolist()
    except Exception as e:
        print(f"히스토리 로드 실패: {e}")
        return []

# 전역에서 한 번만 종목 리스트 로드
STOCK_LIST_URL = 'https://raw.githubusercontent.com/dalinaum/rs/refs/heads/main/krx-list.csv'
stock_map = pd.read_csv(STOCK_LIST_URL, dtype={'Code':str})[['Code','Name']]
stock_names = stock_map['Name'].tolist()

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
            position: relative;
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
        #suggestions {
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: white;
            border: 1px solid #ddd;
            border-radius: 4px;
            max-height: 200px;
            overflow-y: auto;
            display: none;
            z-index: 1000;
        }
        @media (prefers-color-scheme: dark) {
            #suggestions {
                background: #333;
                border-color: #444;
            }
        }
        .suggestion-item {
            padding: 8px 12px;
            cursor: pointer;
        }
        .suggestion-item:hover {
            background-color: #f0f0f0;
        }
        @media (prefers-color-scheme: dark) {
            .suggestion-item:hover {
                background-color: #444;
            }
        }
    </style>
</head>
<body>
    <h1>📈 Minervini Trend Template 자동 분석기 📊</h1>
    <p><strong>종목명(또는 6자리 코드)</strong>를 입력하면 최신 MTT 체크리스트 결과가 바로 출력됩니다.<br>예: 삼성전자, 005930</p>
    
    <form method="post">
        <div class="input-group">
            <input type="text" name="query" id="stock-input" placeholder="예: 삼성전자 또는 005930" required autocomplete="off">
            <button type="submit">분석하기</button>
            <div id="suggestions"></div>
        </div>
    </form>

    {% if result %}
        <div class="mtt-result-box">{{ result }}</div>
    {% elif error %}
        <div class="error">❗ 오류 발생: {{ error }}</div>
    {% endif %}

    <script>
        const input = document.getElementById('stock-input');
        const suggestions = document.getElementById('suggestions');
        let timeoutId;

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
                        if (data.length > 0) {
                            data.forEach(item => {
                                const div = document.createElement('div');
                                div.className = 'suggestion-item';
                                div.textContent = item;
                                div.addEventListener('click', () => {
                                    input.value = item;
                                    suggestions.style.display = 'none';
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

        document.addEventListener('click', function(e) {
            if (!input.contains(e.target) && !suggestions.contains(e.target)) {
                suggestions.style.display = 'none';
            }
        });
    </script>
</body>
</html>
"""

@app.route("/suggest")
def suggest():
    q = request.args.get("q", "")
    matches = difflib.get_close_matches(q, stock_names, n=10, cutoff=0.3)
    return jsonify(matches)

@app.route("/", methods=["GET", "POST"])
def index():
    result = error = None
    stock_name = stock_code = None
    
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
            price_df = load_stock_price_csv(
                'https://raw.githubusercontent.com/dalinaum/rs/main/DATA',
                latest_date, code, name
            )
            checklist, 기준일 = mtt_checklist(price_df, rs_val)
            result = format_mtt_report(name, 기준일, checklist, rs_val)
            stock_name = name
            stock_code = code

        except Exception as e:
            error = str(e)
            print(f"분석 중 오류 발생: {e}")
            print(f"오류 상세: {traceback.format_exc()}")
        
        # GitHub에 저장
        try:
            save_to_github(q, stock_name, stock_code, result, error)
        except Exception as e:
            print(f"히스토리 저장 중 오류 발생: {e}")
            print(f"오류 상세: {traceback.format_exc()}")
    
    return render_template_string(HTML, result=result, error=error)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
