import streamlit as st
import pandas as pd
from geopy.distance import geodesic

# --- 页面配置 ---
st.set_page_config(page_title="法国中学智能选择系统", layout="wide")

# --- 数据加载逻辑 ---
@st.cache_data
def load_data(file_path):
    try:
        # 读取指定的 Excel 文件
        df = pd.read_excel("fr-en-college-idf-language.xlsx")
        
        # 1. 转换 IPS 为数字，处理可能的非法字符（如逗号）
        if 'IPS' in df.columns:
            df['IPS'] = pd.to_numeric(df['IPS'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        
        # 2. 清理经纬度缺失值
        df = df.dropna(subset=['Latitude WGS84', 'Longitude WGS84'])
        
        # 3. 填充语言列空值
        if 'Langues' in df.columns:
            df['Langues'] = df['Langues'].fillna('Non spécifié')
            
        return df
    except Exception as e:
        st.error(f"加载文件失败: {e}")
        return None

# --- 侧边栏：用户输入 ---
st.sidebar.header("📍 1. 您的位置 (Home)")
# 设定默认坐标（以巴黎为例）
home_lat = st.sidebar.number_input("纬度 (Latitude)", value=48.8566, format="%.6f")
home_lon = st.sidebar.number_input("经度 (Longitude)", value=2.3522, format="%.6f")

# 明确闭合元组括号，防止 SyntaxError
home_coords = (home_lat, home_lon)

search_radius = st.sidebar.slider("搜索半径 (km)", 1, 50, 10)

st.sidebar.markdown("---")
st.sidebar.header("🎯 2. 筛选条件")

# 加载你的数据文件
data_file = "fr-en-college-idf-language.xlsx"
df_raw = load_data(data_file)

if df_raw is not None:
    # 筛选：公私立 (Secteur de)
    all_secteurs = df_raw['Secteur de'].unique().tolist()
    selected_secteur = st.sidebar.multiselect("学校性质 (Secteur)", all_secteurs, default=all_secteurs)

    # 筛选：IPS 评分范围
    min_ips = int(df_raw['IPS'].min())
    max_ips = int(df_raw['IPS'].max())
    selected_ips = st.sidebar.slider("IPS 评分范围", min_ips, max_ips, (min_ips, max_ips))

    # 筛选：LV1/LV2 语言搜索
    search_lang = st.sidebar.text_input("搜索语种 (如: Anglais, Allemand, Chinois)", "").strip()

    # --- 核心计算 ---
    def calculate_km(row):
        # 使用 geopy 计算高精度距离
        return geodesic(home_coords, (row['Latitude WGS84'], row['Longitude WGS84'])).km

    df_raw['Distance_KM'] = df_raw.apply(calculate_km, axis=1)

    # --- 过滤逻辑 ---
    mask = (
        (df_raw['Distance_KM'] <= search_radius) &
        (df_raw['Secteur de'].isin(selected_secteur)) &
        (df_raw['IPS'] >= selected_ips[0]) &
        (df_raw['IPS'] <= selected_ips[1])
    )

    # 如果输入了语言，进行模糊匹配
    if search_lang:
        mask = mask & df_raw['Langues'].str.contains(search_lang, case=False, na=False)

    filtered_df = df_raw[mask].sort_values("Distance_KM")

    # --- 主界面展示 ---
    st.title("🏫 法国中学选择系统")
    
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("匹配学校", len(filtered_df))
    col_m2.metric("最大半径", f"{search_radius} km")
    if not filtered_df.empty:
        col_m3.metric("最近距离", f"{filtered_df['Distance_KM'].min():.2f} km")

    st.markdown("---")

    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("📋 筛选清单")
        display_cols = ['Libellé', 'Commune', 'Secteur de', 'IPS', 'Distance_KM', 'Langues', 'Adresse']
        st.dataframe(
            filtered_df[display_cols].style.format({"Distance_KM": "{:.2f} km"}),
            use_container_width=True,
            height=600
        )

    with col_right:
        st.subheader("🗺️ 地图分布")
        # 转换列名以适配 st.map
        map_df = filtered_df.rename(columns={'Latitude WGS84': 'lat', 'Longitude WGS84': 'lon'})
        if not map_df.empty:
            st.map(map_df[['lat', 'lon']])
        else:
            st.info("当前筛选条件下无数据。")

    # 下载按钮
    if not filtered_df.empty:
        csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下载结果", csv, "results.csv", "text/csv")
else:
    st.warning(f"请确保文件 '{data_file}' 位于程序相同目录下。")


