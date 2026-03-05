import streamlit as st
import pandas as pd
from geopy.distance import geodesic

# --- 页面配置 ---
st.set_page_config(page_title="法国中学智能选择系统", layout="wide")

def init_style():
    st.markdown("""
        <style>
        .main { background-color: #f5f7f9; }
        .stMetric { background-color: #ffffff; padding: 10px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        </style>
        """, unsafe_allow_html=True)

init_style()

# --- 数据加载逻辑 ---
@st.cache_data
def load_data(file_path):
    # 根据后缀名自动读取
    if file_path.endswith('.xlsx'):
        df = pd.read_excel(file_path)
    else:
        df = pd.read_csv(file_path)
    
    # 清洗数据：确保 IPS 是数字，经纬度无缺失
    df['IPS'] = pd.to_numeric(df['IPS'], errors='coerce').fillna(0)
    df = df.dropna(subset=['Latitude WGS84', 'Longitude WGS84'])
    
    # 填充语言列的空值，方便后续搜索
    df['Langues'] = df['Langues'].fillna('Non spécifié')
    return df

# --- 侧边栏控制面板 ---
st.sidebar.header("📍 1. 您的位置 (Home)")
home_lat = st.sidebar.number_input("纬度 (Latitude)", value=48.8566, format="%.6f")
home_lon = st.sidebar.number_input("经度 (Longitude)", value=2.3522, format="%.6f")
home_coords = (home_lat, home_lon)

search_radius = st.sidebar.slider("搜索半径 (km)", 1, 100, 10)

st.sidebar.markdown("---")
st.sidebar.header("🎯 2. 筛选条件")

# 尝试加载数据
try:
    # 默认读取名为 data.xlsx 或 data.csv 的文件
    df_raw = load_data("data.xlsx") 
except:
    try:
        df_raw = load_data("data.csv")
    except:
        st.error("❌ 未找到数据文件！请确保目录下有 'data.xlsx' 或 'data.csv'")
        st.stop()

# 筛选：公私立 (Secteur de)
all_secteurs = df_raw['Secteur de'].unique().tolist()
selected_secteur = st.sidebar.multiselect("学校性质 (Secteur)", all_secteurs, default=all_secteurs)

# 筛选：IPS 评分范围
min_ips = int(df_raw['IPS'].min())
max_ips = int(df_raw['IPS'].max())
selected_ips = st.sidebar.slider("IPS 评分范围", min_ips, max_ips, (min_ips, max_ips))

# 筛选：LV1/LV2 语言搜索
st.sidebar.subheader("🗣 语言偏好 (LV1/LV2)")
search_lang = st.sidebar.text_input("输入语种关键词 (如: Anglais, Allemand, Chinois)", "").strip()

# --- 核心计算与过滤 ---
def calculate_km(row):
    return geodesic(home_coords, (row['Latitude WGS84'], row['Longitude WGS84'])).km

# 执行计算
df_raw['Distance_KM'] = df_raw.apply(calculate_km, axis=1)

# 应用过滤逻辑
mask = (
    (df_raw['Distance_KM'] <= search_radius) &
    (df_raw['Secteur de'].isin(selected_secteur)) &
    (df_raw['IPS'] >= selected_ips[0]) &
    (df_raw['IPS'] <= selected_ips[1])
)

# 语言模糊匹配逻辑
if search_lang:
    mask = mask & df_raw['Langues'].str.contains(search_lang, case=False, na=False)

filtered_df = df_raw[mask].sort_values("Distance_KM")

# --- 主界面展示 ---
st.title("🏫 中学选择系统测试版")

# 顶部指标卡
m1, m2, m3 = st.columns(3)
m1.metric("符合条件学校数量", len(filtered_df))
m2.metric("搜索半径", f"{search_radius} km")
if not filtered_df.empty:
    m3.metric("最近学校距离", f"{filtered_df['Distance_KM'].min():.2f} km")

st.markdown("---")

col_left, col_right = st.columns([3, 2])

with col_left:
    st.subheader("📋 学校清单")
    # 定义要展示的列（匹配您的图片列名）
    display_cols = [
        'Libellé', 'Commune', 'Secteur de', 'IPS', 
        'Distance_KM', 'Langues', 'Adresse'
    ]
    # 格式化距离显示
    st.dataframe(
        filtered_df[display_cols].style.format({"Distance_KM": "{:.2f} km", "IPS": "{:.1f}"}),
        use_container_width=True,
        height=500
    )

with col_right:
    st.subheader("🗺️ 地理分布")
    # Streamlit 地图需要 'lat' 和 'lon' 命名的列
    map_df = filtered_df.rename(columns={'Latitude WGS84': 'lat', 'Longitude WGS84': 'lon'})
    if not map_df.empty:
        st.map(map_df[['lat', 'lon']])
    else:
        st.info("当前范围内无数据，请调整侧边栏参数。")

# 底部下载功能
if not filtered_df.empty:
    csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 下载当前筛选结果 (CSV)",
        data=csv,
        file_name="selected_schools.csv",
        mime="text/csv",
    )
