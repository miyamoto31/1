import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

# Configuración
st.set_page_config(page_title="App Cripto | Brote", page_icon="📈", layout="centered")
st.title("📈 Asistente Financiero")
st.markdown("### Analizador Cripto + Tradicional")

tab1, tab2, tab3, tab4 = st.tabs(["🎯 Estrategia Spot", "📊 Gráficos Avanzados", "🧠 Macro 5 Años", "🏦 Tradicional"])

with tab1:
    col_cap, col_mon = st.columns(2)
    with col_cap:
        capital = st.number_input("Monto total disponible:", min_value=5.0, value=100.0, step=5.0)
    with col_mon:
        moneda = st.selectbox("Moneda:", ["MXN", "USD"])

def obtener_sentimiento():
    try:
        fng = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5).json()
        fng_val = int(fng["data"][0]["value"])
        fng_txt_en = fng["data"][0]["value_classification"]
    except:
        fng_val = 50; fng_txt_en = "Neutral"
    traductor = {"Extreme Fear": "Miedo Extremo", "Fear": "Miedo", "Neutral": "Neutral", "Greed": "Codicia", "Extreme Greed": "Codicia Extrema"}
    return fng_val, traductor.get(fng_txt_en, fng_txt_en)

def obtener_precios_historicos():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD?range=5y&interval=1d"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if res.status_code == 200:
            data = res.json()
            fechas = [pd.to_datetime(ts, unit='s') for ts in data['chart']['result'][0]['timestamp']]
            closes = data['chart']['result'][0]['indicators']['quote'][0]['close']
            return pd.DataFrame({'fecha': fechas, 'precio': closes}).dropna()
    except: pass
    try:
        url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=1825&interval=daily"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            return pd.DataFrame({"fecha": [pd.to_datetime(p[0], unit='ms') for p in data["prices"]], "precio": [p[1] for p in data["prices"]]}).dropna()
    except: pass
    raise ValueError("Error de conexión con servidores financieros.")

def obtener_sp500():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/^GSPC?range=1y&interval=1d"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if res.status_code == 200:
            data = res.json()
            fechas = [pd.to_datetime(ts, unit='s') for ts in data['chart']['result'][0]['timestamp']]
            closes = data['chart']['result'][0]['indicators']['quote'][0]['close']
            return pd.DataFrame({'fecha': fechas, 'precio': closes}).dropna()
    except:
        return pd.DataFrame()

@st.cache_data(ttl=1800)
def cargar_datos_completos():
    fng_val, fng_txt = obtener_sentimiento()
    df = obtener_precios_historicos()
    
    df["SMA_20"] = df["precio"].rolling(20).mean()
    df["SMA_200"] = df["precio"].rolling(200).mean()
    
    # RSI
    delta = df["precio"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    df["RSI"] = 100 - (100 / (1 + (gain / loss)))
    
    # MACD (Avanzado)
    ema12 = df['precio'].ewm(span=12, adjust=False).mean()
    ema26 = df['precio'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    df_sp = obtener_sp500()
    return df, fng_val, fng_txt, df_sp

try:
    df, fng_val, fng_txt, df_sp = cargar_datos_completos()
    precio_actual = df["precio"].iloc[-1]
    rsi = df["RSI"].iloc[-1]
    macd = df["MACD"].iloc[-1]
    signal = df["Signal_Line"].iloc[-1]
    resistencia = df["precio"].tail(30).max()
    
    # Estrategia de un solo disparo (Tirador)
    estado_compra = ""
    if fng_val <= 25 and rsi < 35:
        if macd > signal:
            estado_compra = "🔥 SEÑAL FUERTE: Miedo extremo + RSI bajo + MACD cruzando al alza. COMPRAR AHORA."
            precio_compra = precio_actual
        else:
            estado_compra = "⚠️ Zona de oportunidad, pero el precio sigue cayendo (MACD negativo). Espera a que se detenga la sangría."
            precio_compra = precio_actual * 0.96
    else:
        estado_compra = "❌ No entres. El mercado no está en pánico extremo. Guarda tu único disparo."
        precio_compra = df["SMA_20"].iloc[-1] * 0.95

    precio_venta = max(precio_compra * 1.15, resistencia) # Objetivo 15%

    with tab1:
        st.markdown("### 🎯 Estrategia de 'Un Solo Disparo'")
        st.write("Con un capital ajustado al mínimo de Binance, dependes de entradas de altísima precisión.")
        
        if "❌" in estado_compra or "⚠️" in estado_compra:
            st.warning(f"**Análisis:** {estado_compra}")
            st.info(f"**Precio Objetivo para colocar orden:** `${precio_compra:,.2f} USD`")
        else:
            st.success(f"**Análisis:** {estado_compra}")
            st.success(f"**Entrada Óptima:** `${precio_compra:,.2f} USD`")

        st.markdown("---")
        st.markdown("### 💰 Salida Segura (Take Profit)")
        st.write("Vende el 100% de tu posición en este nivel para asegurar ganancia:")
        ganancia = (capital / precio_compra * precio_venta) - capital
        st.success(f"**Precio de Venta:** `${precio_venta:,.2f} USD` (+15% aprox)\n\n**Ganancia neta:** `+${ganancia:.2f} {moneda}`")

    with tab2:
        st.markdown("### 📊 Gráfico Avanzado (Precio + MACD)")
        df_recent = df.tail(120)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_recent["fecha"], y=df_recent["precio"], name="Precio", line=dict(color="#f7931a")))
        fig.update_layout(title="Acción del Precio", margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)
        
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=df_recent["fecha"], y=df_recent["MACD"], name="MACD", line=dict(color="blue")))
        fig2.add_trace(go.Scatter(x=df_recent["fecha"], y=df_recent["Signal_Line"], name="Señal", line=dict(color="orange")))
        fig2.update_layout(title="Indicador MACD (Momentum)", margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        st.markdown("### Comportamiento a 5 Años")
        fig_macro = go.Figure()
        fig_macro.add_trace(go.Scatter(x=df["fecha"], y=df["precio"], name="Precio BTC", line=dict(color="#f7931a", width=1)))
        fig_macro.add_trace(go.Scatter(x=df["fecha"], y=df["SMA_200"], name="Promedio 200d", line=dict(color="#ff0000", width=2)))
        fig_macro.update_layout(margin=dict(l=0, r=0, t=30, b=0), template="plotly_dark")
        st.plotly_chart(fig_macro, use_container_width=True)

    with tab4:
        st.markdown("### 🏦 El Plan de Respaldo (Riesgo Cero)")
        st.write("Si el mercado cripto está inestable, aquí es donde descansa tu capital.")
        
        # Simulación Cetes (10.5% anual)
        rend_cetes = capital * 0.105
        st.info(f"**🇲🇽 CETES Directo (Renta Fija):**\nSi dejas tus {capital} {moneda} un año a la tasa actual (~10.5%), tendrías asegurados **{capital + rend_cetes:.2f} {moneda}** sin ningún riesgo de pérdida.")
        
        if not df_sp.empty:
            st.markdown("---")
            st.markdown("### 🌎 S&P 500 (ETF de las 500 empresas más grandes)")
            st.write("Rendimiento del mercado tradicional en el último año:")
            fig_sp = go.Figure()
            fig_sp.add_trace(go.Scatter(x=df_sp["fecha"], y=df_sp["precio"], name="S&P 500", line=dict(color="#00ff00")))
            fig_sp.update_layout(margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig_sp, use_container_width=True)

except Exception as e:
    st.error(f"Error: {e}")
