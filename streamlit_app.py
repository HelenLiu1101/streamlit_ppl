import streamlit as st
import pandas as pd
import altair as alt 
import requests 
from datetime import datetime
from dateutil.relativedelta import relativedelta

st.set_page_config(
    page_title="Taiwan Migration Dashboard",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
)

"""
# :material/query_stats: Analyze migration trends by region in Taiwan 

Compare cities and counties at a glance
"""

""  # Add some space.

cols = st.columns([1, 3])
# Will declare right cell later to avoid showing it when no data.


def get_yyymm_list(months: int) -> list[str]:
    """產生往前推 N 個月的民國年月清單"""
    now = datetime.now()
    result = []
    for i in range(1, months + 1):
        dt = now - relativedelta(months=i)
        # 西元年轉民國年
        roc_year = dt.year - 1911
        yyymm = f"{roc_year}{dt.month:02d}"
        result.append(yyymm)
    return result  # 現在是11504 -> ["11503", "11502", "11501"]


###

COUNTIES = [
    "連江縣",
    "金門縣",
    "宜蘭縣",
    "新竹縣",
    "苗栗縣",
    "彰化縣",
    "南投縣",
    "雲林縣",
    "嘉義縣",
    "屏東縣",
    "臺東縣",
    "花蓮縣",   
    "澎湖縣",
    "基隆市",
    "新竹市",
    "嘉義市",
    "臺北市",
    "高雄市",
    "新北市",
    "臺中市",
    "臺南市",
    "桃園市"
]
DEFAULT_COUNTIES = ["臺北市", "新北市", "臺中市", "臺南市", "高雄市"]

def counties_to_str(counties):    
    return ",".join(counties)

if "tickers_input" not in st.session_state:
    st.session_state.tickers_input = st.query_params.get(
        "counties", counties_to_str(DEFAULT_COUNTIES)
    ).split(",")

# Callback to update query param when input changes
def update_query_param():
    if st.session_state.tickers_input:
        st.query_params["counties"] = counties_to_str(st.session_state.tickers_input)
    else:
        st.query_params.pop("counties", None)

top_left_cell = cols[0].container(
    border=True, height="stretch", vertical_alignment="top"
)

with top_left_cell:
    # Selectbox for counties
    tickers = st.multiselect(
        "County tickers",
        options=sorted(set(COUNTIES)),
        default=DEFAULT_COUNTIES,
        placeholder="Choose counties to compare. Example: 臺北市",
        accept_new_options=True,
    )

# Time horizon selector
horizon_map = {
    "3 Months": 3,
    "6 Months": 6,
    "9 Months": 9,
    "1 Year": 12
}

with top_left_cell:
    # Buttons for picking time horizon
    horizon = st.pills(
        "Time horizon",
        options=list(horizon_map.keys()),
        default="6 Months",
    )

# Update query param when text input changes
if tickers:
    st.query_params["counties"] = counties_to_str(tickers)
else:
    # Clear the param if input is empty
    st.query_params.pop("counties", None)

if not tickers:
    top_left_cell.info("Pick some counties to compare", icon=":material/info:")
    st.stop() 


### 

right_cell = cols[1].container(
    border=True, height="stretch", vertical_alignment="center"
)

@st.cache_data(show_spinner=True, ttl="30d") # cache_data = 快取資料，show_spinner = 顯示載入動畫，ttl = 資料有效期限
def fetch_data(yyymm: str) -> list:
    """抓單一月份所有頁，yyymm 為民國年月，例如 '11301'; 此api從'10701'開始有資料"""
    url = f"https://www.ris.gov.tw/rs-opendata/api/v1/datastore/ODRP011/{yyymm}"
    
    # 先抓第一頁，確認總頁數
    res = requests.get(url, params={"page": 1}, timeout=10)
    res.raise_for_status()
    first = res.json()
    
    total_pages = int(first["totalPage"])
    all_data = first["responseData"]  # 第一頁資料先存起來
    
    # 從第二頁開始抓
    for page in range(2, total_pages + 1):
        res = requests.get(url, params={"page": page}, timeout=10)
        res.raise_for_status()
        all_data.extend(res.json()["responseData"])  # 接在後面
    
    return all_data  # 回傳完整 list，可直接 pd.DataFrame(all_data)

# 參數 raw 預期傳入的是 list 型別; -> pd.DataFrame這個函式預期回傳 pd.DataFrame
def process_data(raw: list) -> pd.DataFrame:
    """將原始資料轉成適合分析的格式"""
    df = pd.DataFrame(raw) #把原始資料轉成df  
    df["city_code"] = df["district_code"].str[:5]  # 取前五碼，新增一欄
    df["city_name"] = df["site_id"].str[:3] # 取前三碼，新增一欄
    # 字串轉數字
    df["in_total_m"] = pd.to_numeric(df["in_total_m"], errors="coerce")
    df["in_total_f"] = pd.to_numeric(df["in_total_f"], errors="coerce")
    df["out_total_m"] = pd.to_numeric(df["out_total_m"], errors="coerce")
    df["out_total_f"] = pd.to_numeric(df["out_total_f"], errors="coerce")

    df["in_total"] = df["in_total_m"] + df["in_total_f"]
    df["out_total"] = df["out_total_m"] + df["out_total_f"]
    result = (
        df.groupby(["city_code", "city_name"])
        .agg(
            in_total_sum =("in_total", "sum"), 
            out_total_sum =("out_total", "sum")
            ) # agg = aggregate（聚合），對每個分組做計算
                # 語法是 新欄位名稱 = ("來源欄位", "計算方式")
        .reset_index()
    )
    return result

def load_data(months: int) -> pd.DataFrame:
    yyymm_list = get_yyymm_list(months) # 根據選的時間範圍，產生對應的 yyymm 清單
    
    all_dfs = []
    for yyymm in yyymm_list:
        raw = fetch_data(yyymm)       # list
        df = process_data(raw)        # df
        df["年月"] = yyymm           # 記錄月份
        all_dfs.append(df)
    return pd.concat(all_dfs, ignore_index=True)

try:
    data = load_data(horizon_map[horizon])  # 根據選的時間範圍，載入資料  
except Exception as e:
    st.warning(f"Error loading data: {e} \nTry again later.")
    st.stop()

# Plotting the data 
with right_cell:
    
    # melt 整理格式
    melted = data[["年月", "city_name", "in_total_sum"]].melt(
        id_vars=["年月", "city_name"],
        value_name="數量"
    )
    filtered = melted[melted["city_name"].isin(tickers)]

    st.altair_chart(
        alt.Chart(filtered)
        .mark_line()
        .encode(
            alt.X("年月:O"),           # O = Ordinal 類別，N = Nominal，Q = 數量
            alt.Y("數量:Q"),
            alt.Color("city_name:N"),
        )
        .properties(
            height=400,
            title="各縣市遷入人口趨勢"
        ),
        width = 'stretch'
    )

"""
## Raw data
"""

data

# data = fetch_data("11301")  # 抓取民國 113 年 1 月的資料
# df = process_data(data)  # 處理成分析用的格式 
# df["period"] = "11301"  # 加入 period 欄位，方便後續分析用 
