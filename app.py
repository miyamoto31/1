import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

# Configuración
st.set_page_config(page_title="App Cripto | Brote", page_icon="📈", layout="centered")
st.title("📈 Asistente Financiero")

# Inputs globales en la parte superior
col_cap, col_mon = st.columns(2)
with col_cap:
    capital = st.number_input("Capital total disponible:", min_value=5.0, value=500.0, step=50.0)
with col_mon:
    moneda = st.selectbox("Moneda:", ["MXN", "USD"])

# --- FUNCIONES DE DATOS ---
def obtener_sentimiento():
    try:
        fng = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5).json()
        fng_val = int(fng["data"][0]["value"])
        fng_txt_en = fng["data"][0]["value_classification"]
    except:
        fng_val = 50; fng_txt_en = "Neutral"
    traductor = {"Extreme Fear": "Miedo Extremo", "Fear": "Miedo", "Neutral": "Neutral", "Greed": "Codicia", "Extreme Greed": "Codicia Extrema"}
    return fng_val, traductor.get(fng_txt_en, fng_txt_en)

@st.cache_data(ttl=600)
def obtener_noticias_y_hype():
    try:
        url = "https://min-api.cryptocompare.com/data/v2/news/?lang=ES"
        res = requests.get(url, timeout=5)
        noticias = []
        score = 0
        if res.status_code == 200:
            data = res.json()["Data"][:10]
            positivas = ["sube", "adopción", "alianza", "compra", "alcista", "aprobado", "crece", "optimismo", "máximo", "inversión"]
            negativas = ["cae", "hackeo", "demanda", "prohibición", "vende", "bajista", "multa", "miedo", "desplome", "sec", "fraude"]
            for n in data:
                titulo = n["title"].lower()
                cuerpo = n["body"].lower()
                noticias.append({"titulo": n["title"], "url": n["url"], "fuente": n["source_info"]["name"]})
                for p in positivas:
                    if p in titulo or p in cuerpo: score += 1
                for neg in negativas:
                    if neg in titulo or neg in cuerpo: score -= 1
        return noticias, score
    except:
        return [], 0

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
    raise ValueError("Error de conexión.")

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
    delta = df["precio"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    df["RSI"] = 100 - (100 / (1 + (gain / loss)))
    ema12 = df['precio'].ewm(span=12, adjust=False).mean()
    ema26 = df['precio'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df_sp = obtener_sp500()
    return df, fng_val, fng_txt, df_sp

# --- LÓGICA PRINCIPAL ---
try:
    df, fng_val, fng_txt, df_sp = cargar_datos_completos()
    noticias, hype_score = obtener_noticias_y_hype()
    
    precio_actual = df["precio"].iloc[-1]
    rsi = df["RSI"].iloc[-1]
    macd = df["MACD"].iloc[-1]
    signal = df["Signal_Line"].iloc[-1]
    resistencia = df["precio"].tail(30).max()
    
    advertencia_manipulacion = ""
    if hype_score <= -3:
        advertencia_manipulacion = "🛑 ALERTA: Pánico mediático. Protege tu capital."
    elif hype_score >= 3:
        advertencia_manipulacion = "🔥 ALERTA: Hype extremo. Riesgo de burbuja a corto plazo."
        
    if fng_val <= 30 and rsi < 40 and hype_score > -3:
        if macd > signal:
            estado_compra = "🔥 SEÑAL FUERTE: Momento óptimo confirmado."
            precio_compra = precio_actual
        else:
            estado_compra = "⚠️ ZONA DE OPORTUNIDAD: Esperando rebote."
            precio_compra = precio_actual * 0.96
    else:
        estado_compra = "❌ PACIENCIA: No es buen momento para comprar."
        precio_compra = df["SMA_20"].iloc[-1] * 0.95

    precio_venta = max(precio_compra * 1.15, resistencia)
    limite_nivel_1 = 500 if moneda == "MXN" else 25
    limite_nivel_2 = 2000 if moneda == "MXN" else 100

    # --- INTERFAZ SIMPLIFICADA EN 2 PESTAÑAS ---
    tab1, tab2 = st.tabs(["🎯 Qué Hacer (Operación)", "📊 Por Qué (Gráficos y Datos)"])

    with tab1:
        if advertencia_manipulacion:
            st.warning(advertencia_manipulacion)
            
        st.markdown(f"**Estado Actual:** {estado_compra}")
        
        # Bloque de Estrategia Dinámica
        if capital < limite_nivel_1:
            st.error(f"**Estrategia: Un Solo Disparo**")
            st.write("Monto limitado. Entra con el 100% solo cuando la señal sea FUERTE.")
            st.success(f"**🟢 Precio de Entrada:** `${precio_compra:,.2f} USD`")
            st.error(f"**🔴 Precio de Venta (Take Profit):** `${precio_venta:,.2f} USD`")
            
        elif capital < limite_nivel_2:
            fraccion = capital / 3
            st.warning(f"**Estrategia: Táctica de 3 Partes**")
            col1, col2 = st.columns(2)
            col1.success(f"**🟢 Compra 1 ({fraccion:,.0f} {moneda}):**\n`${precio_compra:,.2f} USD`")
            col2.info(f"**🔵 Compra 2 (Cobertura):**\n`${precio_compra * 0.95:,.2f} USD`")
            st.write(f"*💡 El 3er tercio ({fraccion:,.0f} {moneda}) envíalo a CETES como reserva de emergencia.*")
            
        else:
            st.success(f"**Estrategia: Largo Plazo (Policultivo)**")
            st.write(f"- **Seguridad (70%):** **{capital*0.7:,.2f} {moneda}** a Cetes o ETF S&P 500.")
            st.write(f"- **Riesgo (30%):** **{capital*0.3:,.2f} {moneda}** a Bitcoin en compras DCA automáticas.")

        # Respaldo (Oculto en un expander para ahorrar espacio)
        with st.expander("🛡️ Ver Plan de Respaldo (Riesgo Cero)"):
            rend_cetes = capital * 0.105
            st.info(f"Si dejas tus **{capital} {moneda}** en CETES, tendrías **{capital + rend_cetes:.2f} {moneda}** en 1 año sin riesgo.")

    with tab2:
        # Métricas rápidas arriba
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Miedo/Codicia", f"{fng_val}")
        col_m2.metric("Fuerza RSI", f"{rsi:.1f}")
        col_m3.metric("Hype", f"{hype_score} pts")
        
        st.markdown("### Acción del Precio")
        df_recent = df.tail(90)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_recent["fecha"], y=df_recent["precio"], name="Precio", line=dict(color="#f7931a")))
        fig.add_trace(go.Scatter(x=df_recent["fecha"], y=df_recent["SMA_20"], name="Tendencia", line=dict(color="#2962ff", dash="dot")))
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300)
        st.plotly_chart(fig, use_container_width=True)
        
        # Todo lo demás en expanders para no saturar
        with st.expander("📰 Ver Titulares y Noticias Recientes"):
            if noticias:
                for n in noticias:
                    st.markdown(f"- [{n['titulo']}]({n['url']})")
            else:
                st.write("Sin noticias relevantes hoy.")
                
        with st.expander("🧠 Ver Análisis Macro (5 Años)"):
            fig_macro = go.Figure()
            fig_macro.add_trace(go.Scatter(x=df["fecha"], y=df["precio"], name="Precio BTC", line=dict(color="#f7931a", width=1)))
            fig_macro.add_trace(go.Scatter(x=df["fecha"], y=df["SMA_200"], name="Promedio 200d", line=dict(color="#ff0000", width=2)))
            fig_macro.update_layout(margin=dict(l=0, r=0, t=10, b=0), template="plotly_dark", height=300)
            st.plotly_chart(fig_macro, use_container_width=True)
            
        with st.expander("🌎 Ver Mercado Tradicional (S&P 500)"):
            if not df_sp.empty:
                fig_sp = go.Figure()
                fig_sp.add_trace(go.Scatter(x=df_sp["fecha"], y=df_sp["precio"], name="S&P 500", line=dict(color="#00ff00")))
                fig_sp.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300)
                st.plotly_chart(fig_sp, use_container_width=True)

except Exception as e:
    st.error(f"Error cargando datos: {e}")
