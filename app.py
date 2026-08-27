import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go

st.set_page_config(page_title="BTC Signal App", page_icon="🪙", layout="centered")

st.title("🪙 Analizador de Compra/Venta Bitcoin")
st.caption("Optimizado para órdenes Spot en Binance")

with st.expander("⚙️ Configuración de Capital", expanded=True):
    capital = st.number_input("Monto a invertir:", min_value=5.0, value=95.0, step=5.0)
    moneda = st.selectbox("Moneda:", ["USD", "MXN"])

@st.cache_data(ttl=600)
def cargar_datos():
    fng = requests.get("https://api.alternative.me/fng/?limit=1").json()
    fng_val = int(fng["data"][0]["value"])
    fng_txt = fng["data"][0]["value_classification"]

    cg_url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=90&interval=daily"
    cg_data = requests.get(cg_url).json()
    fechas = [pd.to_datetime(p[0], unit='ms') for p in cg_data["prices"]]
    precios = [p[1] for p in cg_data["prices"]]
    
    df = pd.DataFrame({"fecha": fechas, "precio": precios})
    df["SMA_20"] = df["precio"].rolling(20).mean()
    df["SMA_50"] = df["precio"].rolling(50).mean()
    
    delta = df["precio"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    df["RSI"] = 100 - (100 / (1 + (gain / loss)))
    
    return df, fng_val, fng_txt

try:
    df, fng_val, fng_txt = cargar_datos()
    precio_actual = df["precio"].iloc[-1]
    rsi = df["RSI"].iloc[-1]
    sma_20 = df["SMA_20"].iloc[-1]
    resistencia = df["precio"].tail(30).max()
    
    col1, col2 = st.columns(2)
    col1.metric("Precio Actual", f"${precio_actual:,.2f} USD")
    col2.metric("Sentimiento", f"{fng_val}/100", fng_txt)
    
    compra_optima = min(precio_actual * 0.96, sma_20)
    if rsi < 35:
        compra_optima = precio_actual
        
    tp1 = max(compra_optima * 1.08, resistencia * 0.98)
    tp2 = compra_optima * 1.15
    stop_loss = compra_optima * 0.95
    
    btc_comprado = capital / compra_optima
    ganancia_tp1 = (btc_comprado * tp1) - capital
    ganancia_tp2 = (btc_comprado * tp2) - capital
    
    st.subheader("🎯 Niveles Sugeridos para Binance")
    st.success(f"**🟢 Entrada Óptima (Limit Buy):** `${compra_optima:,.2f} USD`\n\n*(Coloca una orden Limit Buy por ${capital:.2f} {moneda})*")
    st.info(f"**🔴 Venta 1 (Take Profit +8%):** `${tp1:,.2f} USD` | *Ganancia:* `+${ganancia_tp1:.2f} {moneda}`\n\n**🔴 Venta 2 (Take Profit +15%):** `${tp2:,.2f} USD` | *Ganancia:* `+${ganancia_tp2:.2f} {moneda}`")
    st.warning(f"**🛡️ Stop-Loss Sugerido (-5%):** `${stop_loss:,.2f} USD`")
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["fecha"], y=df["precio"], name="Precio BTC", line=dict(color="#f7931a")))
    fig.add_trace(go.Scatter(x=df["fecha"], y=df["SMA_20"], name="Media 20d", line=dict(color="#2962ff", dash="dash")))
    fig.update_layout(title="Historial 90 Días", xaxis_title="Fecha", yaxis_title="USD", margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Error al obtener datos: {e}")
