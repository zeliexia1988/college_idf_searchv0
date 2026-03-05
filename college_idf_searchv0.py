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
home_coords = (home_lat