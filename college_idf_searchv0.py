import streamlit as st
import pandas as pd
from geopy.distance import geodesic

# --- 1. 页面配置 ---
st.set_page_config(page_title="法国中学智能选择系统", layout="wide")

# --- 2. 核心数据加载函数 ---
@st.cache_data
def load_data(target_file):
    try:
        # 1. 读取 Excel，强制不限制列数
        df = pd.read_excel(target_file, engine='openpyxl')
        
        # 2. 深度清洗列名：去除空格、换行符、统一单引号格式
        df.columns = [
            str(c).strip().replace('\n', '').replace("’", "'") 
            for c in df.columns
        ]
        
        # 调试辅助：在页面上列出所有读到的列，看看 IPS 和 Position 在不在
        # st.write("✅ 成功读取到的所有列名：", df.columns.tolist())

        # 3. 智能定位关键列（模糊匹配）
        def find_col(keywords):
            for col in df.columns:
                if any(k in col for k in keywords):
                    return col
            return None

        # 自动寻找对应的列名
        pos_col = find_col(['Position', 'Coordinate'])
        ips_col = find_col(['IPS'])
        secteur_col = find_col(['Secteur'])
        lang_col = find_col(['Langues', 'Language'])

        # 4. 处理坐标 (Position)
        if pos_col:
            # 兼容处理：有些 Position 可能是 "(48.8, 2.3)" 这种带括号的
            clean_pos = df[pos_col].astype(str).str.replace('(', '').str.replace(')', '')
            coords = clean_pos.str.split(',', expand=True)
            df['lat'] = pd.to_numeric(coords[0], errors='coerce')
            df['lon'] = pd.to_numeric(coords[1], errors='coerce')
        else:
            st.error(f"❌ 找不到坐标列，请检查是否有 'Position' 列。当前列：{df.columns.tolist()}")
            return None

        # 5. 处理 IPS
        if ips_col:
            df['IPS_val'] = pd.to_numeric(df[ips_col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        else:
            df['IPS_val'] = 0

        # 6. 保存识别出的列名供后续使用
        df['_matched_secteur'] = secteur_col
        df['_matched_lang'] = lang_col

        # 清理无效坐标行
        df = df.dropna(subset=['lat', 'lon'])
        return df
    except Exception as e:
        st.error(f"❌ 读取失败: {e}")
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





