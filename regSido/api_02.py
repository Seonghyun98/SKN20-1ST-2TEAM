import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os
import plotly.express as px

# 환경 변수 로드
load_dotenv()

engine = create_engine(
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:3306/{os.getenv('DB_NAME')}?charset=utf8mb4"
)

st.set_page_config(page_title="차량 등록 통계 조회", layout="wide")

# CSS
st.markdown("""
<style>
/* 사이드바 폭 고정 */
section[data-testid="stSidebar"] {
    width: 200px !important;
    min-width: 200px !important;
    max-width: 200px !important;
    overflow-x: hidden !important;
    position: relative;
}

/* 내부 컨테이너 폭 맞춤 */
section[data-testid="stSidebar"] > div {
    width: 200px !important;
}

/* 사이드바 내부 모든 요소 마우스 오버 커서 제거 */
section[data-testid="stSidebar"] * {
    cursor: default !important;
}

/* 드롭다운 라벨 및 옵션 좌우 중앙 정렬 */
div[data-testid="stSidebar"] label,
div[data-baseweb="select"] > div > div {
    text-align: center !important;
    justify-content: center !important;
}

/* 특정 요소 크기 확대 */
.st-emotion-cache-1aplgmp {
    min-width: 2.5rem !important;
    min-height: 2.5rem !important;
}
.st-emotion-cache-pd6qx2 {
    width: 2.5rem !important;
    height: 2.5rem !important;
}

/* 메인 블록 상/하 패딩 조정 */
#root > div:nth-child(1) > div.withScreencast > div > div > div > section >
div.stMainBlockContainer.block-container.st-emotion-cache-zy6yx3.e4man114 {
    padding-top: 1.5rem !important;
    padding-bottom: 40px !important;
}

/* 탭 내 스크롤 제거 */
section[data-testid="stTabbedContent"] {
    overflow: visible !important;
}

/* 접기/펼치기 버튼 완전히 삭제 */
.stExpanderToggleIcon,
.st-emotion-cache-1ghvj0e,
.st-emotion-cache-f1u957 {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)

# 제목
st.title("🚗 차량 등록 통계 조회 대시보드")

# 데이터 로드
@st.cache_data(ttl=600)
def load_data():
    query = """
        SELECT * FROM CAR_REGIST_SIDO
        ORDER BY car_type ASC, usage_type ASC
    """
    df = pd.read_sql(query, engine)
    df["year"] = df["reg_date"].str[:4]
    df["month"] = df["reg_date"].str[4:6]
    return df

df = load_data()

# 사이드바 필터
st.sidebar.header("🔍 조회 조건 설정")
years = sorted(df["year"].unique())
selected_year = st.sidebar.selectbox("연도", years)

months = sorted(df[df["year"] == selected_year]["month"].unique())
selected_month = st.sidebar.selectbox("월", months)

sido_list = sorted(df["sido"].unique())
selected_sido = st.sidebar.selectbox("시도", sido_list)

filtered_sigungu = sorted(df[df["sido"] == selected_sido]["sigungu"].unique())
selected_sigungu = st.sidebar.selectbox("시군구", filtered_sigungu)

# 데이터 필터링
filtered_df = df[
    (df["year"] == selected_year) &
    (df["month"] == selected_month) &
    (df["sido"] == selected_sido) &
    (df["sigungu"] == selected_sigungu)
]

if filtered_df.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
else:
    # 세션에 현재 탭 상태 저장
    if "active_tab" not in st.session_state:
        st.session_state.active_tab = "차량 종류별 바 차트"

    tabs = ["차량 종류별 바 차트", "차량 용도별 원형 차트", "차량 유형×용도 원형 차트", "데이터 테이블"]
    tab_objects = st.tabs(tabs)

    for i, tab in enumerate(tab_objects):
        with tab:
            st.session_state.active_tab = tabs[i]

            if tabs[i] == "차량 종류별 바 차트":
                st.subheader("📈 차량 종류(car_type)별 등록대수")
                chart_df = filtered_df.groupby("car_type")["count"].sum().reset_index()
                st.bar_chart(chart_df.set_index("car_type"), height=300, width=None)

            elif tabs[i] == "차량 용도별 원형 차트":
                st.subheader("🧩 차량 용도(usage_type)별 비율")
                pie_df = filtered_df.groupby("usage_type")["count"].sum().reset_index()
                fig = px.pie(
                    pie_df,
                    names='usage_type',
                    values='count',
                    hole=0.45,
                    color='usage_type',
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig.update_traces(
                    hoverinfo='label+percent+value',
                    textinfo='label+percent',
                    textfont_size=14,
                    marker=dict(line=dict(color='#000000', width=2))
                )
                fig.update_layout(
                    margin=dict(l=10, r=10, t=40, b=10),
                    height=320,
                    showlegend=True,
                    legend_title_text='용도'
                )
                st.plotly_chart(fig, use_container_width=True)

            elif tabs[i] == "차량 유형×용도 원형 차트":
                st.subheader("🔍 차량 유형(car_type) × 용도(usage_type) 조합별 비율")
                combo_df = filtered_df.groupby(['car_type', 'usage_type'])['count'].sum().reset_index()
                combo_df['label'] = combo_df['car_type'] + ' / ' + combo_df['usage_type']
                col1, col2 = st.columns([2, 1])

                with col1:
                    fig2 = px.pie(
                        combo_df,
                        names='label',
                        values='count',
                        hole=0.5,
                        color='label',
                        color_discrete_sequence=px.colors.qualitative.Set3
                    )
                    fig2.update_traces(
                        hoverinfo='label+percent+value',
                        textinfo='label+percent',
                        textfont_size=12,
                        marker=dict(line=dict(color='#222222', width=1))
                    )
                    fig2.update_layout(
                        margin=dict(l=10, r=10, t=40, b=10),
                        height=400,
                        showlegend=False
                    )
                    st.plotly_chart(fig2, use_container_width=True)

                with col2:
                    total_count = combo_df['count'].sum()
                    combo_df['ratio'] = combo_df['count'] / total_count * 100
                    st.dataframe(combo_df.style.format({
                        'count': '{:,}',
                        'ratio': '{:.2f}%'
                    }), height=400, use_container_width=True)

            elif tabs[i] == "데이터 테이블":
                st.subheader("🗂 필터링된 차량 등록 데이터")
                st.dataframe(filtered_df, height=400, use_container_width=True)