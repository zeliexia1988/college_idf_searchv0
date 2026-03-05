import streamlit as st
import pandas as pd
from geopy.distance import geodesic

# --- 1. 页面配置 ---
st.set_page_config(page_title="法国中学智能选择系统", layout="wide")

# --- 2. 核心数据加载函数 ---
@st.cache_data
def load_data(target_file):
    try:
        # 显式读取指定的文件名
        df = pd.read_excel(target_file, engine='openpyxl')
        
        # 清洗列名：去除看不见的空格或换行符
        df.columns = [str(c).strip() for c in df.columns]
        
        # IPS 数据处理：将法国格式的逗号转为点号并转为数字
        if 'IPS' in df.columns:
            df['IPS'] = pd.to_numeric(df['IPS'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        
        # 必须包含的经纬度列名检查
        req_cols = ['Latitude WGS84', 'Longitude WGS84']
        for col in req_cols:
            if col not in df.columns:
                st.error(f"❌ 错误：Excel 中找不到列名 '{col}'。目前有的列名是：{df.columns.tolist()}")
                return None
        
        # 删除经纬度为空的行
        df = df.dropna(subset=req_cols)
        
        # 填充语言列空值
        if 'Langues' in df.columns:
            df['Langues'] = df['Langues'].fillna('Non spécifié')
            
        return df
    except Exception as e:
        st.error(f"❌ 无法读取文件 '{target_file}': {e}")
        return None

# --- 3. 设置文件名 (确保这里完全匹配) ---
FILE_NAME = "fr-en-college-idf-language.xlsx"

# --- 4. 侧边栏交互 ---
st.sidebar.header("📍 1. 您的位置 (Home)")
home_lat = st.sidebar.number_input("您的纬度 (Latitude)", value=48.8566, format="%.6f")
home_lon = st.sidebar.number_input("您的经度 (Longitude)", value=2.3522, format="%.6f")
home_coords = (home_lat, home_lon)

search_radius = st.sidebar.slider("搜索半径 (km)", 1, 100, 10)

st.sidebar.markdown("---")
st.sidebar.header("🎯 2. 筛选条件")

# 执行加载
df_raw = load_data(FILE_NAME)

if df_raw is not None:
    # 公私立筛选
    if 'Secteur de' in df_raw.columns:
        all_secteurs = df_raw['Secteur de'].unique().tolist()
        selected_secteur = st.sidebar.multiselect("学校性质 (Secteur)", all_secteurs, default=all_secteurs)
    else:
        selected_secteur = []

    # IPS 筛选
    min_ips = int(df_raw['IPS'].min())
    max_ips = int(df_raw['IPS'].max())
    selected_ips = st.sidebar.slider("IPS 评分范围", min_ips, max_ips, (min_ips, max_ips))

    # 语言搜索
    search_lang = st.sidebar.text_input("🗣 搜索语种 (如: Anglais, Allemand, Chinois)", "").strip()

    # --- 5. 距离计算 ---
    def get_distance(row):
        return geodesic(home_coords, (row['Latitude WGS84'], row['Longitude WGS84'])).km

    df_raw['Distance_KM'] = df_raw.apply(get_distance, axis=1)

    # --- 6. 过滤逻辑 ---
    mask = (
        (df_raw['Distance_KM'] <= search_radius) &
        (df_raw['IPS'] >= selected_ips[0]) &
        (df_raw['IPS'] <= selected_ips[1])
    )
    
    if selected_secteur:
        mask = mask & df_raw['Secteur de'].isin(selected_secteur)

    if search_lang:
        mask = mask & df_raw['Langues'].str.contains(search_lang, case=False, na=False)

    filtered_df = df_raw[mask].sort_values("Distance_KM")

    # --- 7. UI 展示 ---
    st.title("🏫 法国中学智能选择系统")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("匹配学校", len(filtered_df))
    m2.metric("搜索半径", f"{search_radius} km")
    if not filtered_df.empty:
        m3.metric("最近距离", f"{filtered_df['Distance_KM'].min():.2f} km")

    st.markdown("---")
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("📋 筛选清单")
        display_cols = ['Libellé', 'Commune', 'Secteur de', 'IPS', 'Distance_KM', 'Langues']
        # 确保只显示存在的列
        actual_cols = [c for c in display_cols if c in filtered_df.columns]
        st.dataframe(
            filtered_df[actual_cols].style.format({"Distance_KM": "{:.2f} km"}),
            use_container_width=True, height=550
        )

    with col_right:
        st.subheader("🗺️ 地理分布")
        map_df = filtered_df.rename(columns={'Latitude WGS84': 'lat', 'Longitude WGS84': 'lon'})
        if not map_df.empty:
            st.map(map_df[['lat', 'lon']])
        else:
            st.info("无结果，请调整筛选条件。")

    # 下载
    if not filtered_df.empty:
        csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下载结果 (CSV)", csv, "search_results.csv", "text/csv")
else:
    st.error(f"⚠️ 在根目录下未找到文件: {FILE_NAME}")




