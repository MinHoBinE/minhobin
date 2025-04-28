import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from MinhoReport import (
    parse_stock_input, get_latest_date, load_rs_from_markdown,
    load_stock_price_csv, mtt_checklist, format_mtt_report, get_first_float
)

STOCK_LIST_URL = 'https://raw.githubusercontent.com/dalinaum/rs/refs/heads/main/krx-list.csv'
stock_list = pd.read_csv(STOCK_LIST_URL, dtype={'Code':str})[['Code','Name']]

def suggest_stocks(user_input, stock_map, n=5):
    user_input = user_input.strip()
    if not user_input:
        return []
    matches = stock_map[
        stock_map['Name'].str.contains(user_input, case=False, na=False) |
        stock_map['Code'].str.contains(user_input)
    ]
    return matches[['Name','Code']].head(n).values.tolist()

st.title("📈 Minervini Trend Template 자동 분석기 📊")
st.markdown("**종목명(또는 6자리 코드)**를 입력하면 최신 MTT 체크리스트 결과와 TradingView 차트가 바로 출력됩니다.<br>예: 삼성전자, 005930", unsafe_allow_html=True)

# 다크/라이트 모드 스타일
st.markdown(
    """
    <style>
    .mtt-result-box {
      font-size: 1.1em;
      border-radius: 12px;
      padding: 14px;
      margin-top: 10px;
      background: #f8f9fa;
      color: black;
    }
    @media (prefers-color-scheme: dark) {
      .mtt-result-box {
        background: #222831 !important;
        color: #f1f1f1 !important;
      }
    }
    </style>
    """,
    unsafe_allow_html=True
)

user_input = st.text_input("종목명 또는 6자리 종목코드 입력", value="", placeholder="예: 삼성전자 또는 005930")
run_btn = st.button("분석하기")

def main(user_input):
    if not user_input:
        st.info("분석할 종목명을 입력해 주세요.")
        return
    try:
        code, name = parse_stock_input(user_input, stock_list)
        if code is None:
            suggestions = suggest_stocks(user_input, stock_list, n=5)
            if suggestions:
                st.error(f"종목 '{user_input}'을(를) 찾을 수 없습니다.")
                st.markdown("아래와 비슷한 종목이 있습니다. 복사해서 입력해 보세요:")
                for n, c in suggestions:
                    st.markdown(f"- **{n}** (`{c}`)")
            else:
                st.error(f"종목 '{user_input}'을(를) 찾을 수 없습니다. 예: 삼성전자, 005930")
            return
        latest = get_latest_date(code, name)
        rs_row = load_rs_from_markdown(latest, code)
        if rs_row.empty:
            st.warning("❗ RS 데이터가 없습니다.")
            return
        rs_raw = rs_row.iloc[0]['RS']
        rs_value = get_first_float(rs_raw)
        price_df = load_stock_price_csv(
            'https://raw.githubusercontent.com/dalinaum/rs/main/DATA',
            latest, code, name
        )
        checklist, base_date = mtt_checklist(price_df, rs_value)
        
        # 🔥 TradingView 차트 붙이기
        tradingview_code = f"KRX:{code}"
        widget_html = f"""
        <div class="tradingview-widget-container">
          <div id="tradingview_{code}" style="height:360px"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
          <script type="text/javascript">
            new TradingView.widget({{
              "width": "100%",
              "height": 360,
              "symbol": "{tradingview_code}",
              "interval": "D",
              "timezone": "Asia/Seoul",
              "theme": "light",
              "style": "1",
              "locale": "ko",
              "toolbar_bg": "#f1f3f6",
              "withdateranges": true,
              "hide_side_toolbar": false,
              "allow_symbol_change": true,
              "save_image": false,
              "container_id": "tradingview_{code}"
            }});
          </script>
        </div>
        """
        st.markdown("### 📊 TradingView 실시간 차트")
        components.html(widget_html, height=380, scrolling=False)
        
        # 분석 결과 출력
        report = format_mtt_report(name, base_date, checklist, rs_value, latest)
        st.markdown(
            f"<div class='mtt-result-box'>{report.replace(chr(10), '<br>')}</div>",
            unsafe_allow_html=True
        )
    except Exception as e:
        st.error(f"❗ 오류 발생: {e}")

if run_btn or (user_input and st.session_state.get("input_submitted")):
    main(user_input)
elif user_input:
    st.session_state["input_submitted"] = True
    main(user_input)
