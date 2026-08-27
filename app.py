import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Configuración de la página
st.set_page_config(page_title="App Cripto | Brote", page_icon="📈", layout="centered")

st.title("📈 Asistente Cripto")
st.markdown("### Analizador Avanzado de Bitcoin")

tab1, tab2, tab3 = st.tabs(["💰 Órdenes y Fechas", "📊 Gráfico", "🧠 Análisis de 5 Años"])

with tab1:
    st.info("Ajusta tu inversión para calcular tus ganancias exactas.")
    col_cap, col_mon = st.columns(2)
    with col_cap:
        capital = st.number_input("Monto a invertir:", min_value=5.0, value=95.0, step=5.0)
    with col_mon:
        moneda = st.selectbox("Moneda:", ["USD", "MXN"])

@st.cache_data(ttl=3600)
def cargar_datos_5_anos():
    fng = requests.get("https://api.alternative.me/fng/?limit=1").json()
    fng_val = int(fng["data"][0]["value"])
    fng_txt_en = fng["data"][0]["value_classification"]
    
    traductor = {
        "Extreme Fear": "Miedo Extremo", "Fear": "Miedo", 
        "Neutral": "Neutral", 
        "Greed": "Codicia", "Extreme Greed": "Codicia Extrema"
    }
    fng_txt = traductor.get(fng_txt_en, fng_txt_en)
    
    cg_url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=1825&interval=daily"
    cg_res = requests.get(cg_url)
    
    # NUEVA VALIDACIÓN: Si la API nos bloquea temporalmente (Código 429)
    if cg_res.status_code == 429:
        raise ValueError("Límite de consultas alcanzado. CoinGecko nos puso en pausa. Espera 3 minutos y recarga la página.")
        
    cg_data = cg_res.json()
    
    # NUEVA VALIDACIÓN: Si la API no devuelve los precios por otro error
    if "prices" not in cg_data:
        raise ValueError("La API de CoinGecko no devolvió los precios en este momento. Intenta más tarde.")
    
    fechas = [pd.to_datetime(p[0], unit='ms') for p in cg_data["prices"]]
    precios = [p[1] for p in cg_data["prices"]]
    
    df = pd.DataFrame({"fecha": fechas, "precio": precios})
    df["SMA_20"] = df["precio"].rolling(20).mean()
    df["SMA_50"] = df["precio"].rolling(50).mean()
    df["SMA_200"] = df["precio"].rolling(200).mean()
    
    delta = df["precio"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    df["RSI"] = 100 - (100 / (1 + (gain / loss)))
    
    return df, fng_val, fng_txt

try:
    df, fng_val, fng_txt = cargar_datos_5_anos()
    precio_actual = df["precio"].iloc[-1]
    rsi = df["RSI"].iloc[-1]
    sma_20 = df["SMA_20"].iloc[-1]
    sma_50 = df["SMA_50"].iloc[-1]
    sma_200 = df["SMA_200"].iloc[-1]
    resistencia = df["precio"].tail(60).max()
    soporte = df["precio"].tail(60).min()
    
    if rsi < 35 or precio_actual <= soporte:
        estado_compra = "Excelente oportunidad (Activo en sobreventa o zona de soporte)"
        momento_optimo_compra = precio_actual
    else:
        estado_compra = "Esperar retroceso estratégico"
        momento_optimo_compra = min(precio_actual * 0.95, sma_20)
        
    momento_optimo_venta = max(momento_optimo_compra * 1.10, resistencia)
    stop_loss = momento_optimo_compra * 0.93

    btc_comprado = capital / momento_optimo_compra
    ganancia = (btc_comprado * momento_optimo_venta) - capital

    # --- PREDICCIÓN DE FECHAS (MODELO CÍCLICO Y TENDENCIAL) ---
    fecha_actual = datetime.now()
    
    # Proyección a corto plazo (velocidad del precio hacia el soporte)
    tendencia_diaria = (precio_actual - df["precio"].iloc[-14]) / 14
    if tendencia_diaria < 0 and precio_actual > momento_optimo_compra:
        dias_para_compra = int(abs((precio_actual - momento_optimo_compra) / tendencia_diaria))
        fecha_estimada_compra = fecha_actual + timedelta(days=dias_para_compra)
        str_fecha_compra = fecha_estimada_compra.strftime('%d de %B, %Y')
    else:
        str_fecha_compra = "El mercado está listo ahora o en tendencia alcista (esperar consolidación)."
    
    # Proyección Macro (Ciclo de Halving: Abr 2024 -> Abr 2028)
    str_fecha_venta_macro = "Finales de 2028 / Inicios de 2029 (12-18 meses post-halving de 2028)"
    str_fecha_compra_macro = "Finales de 2026 / 2027 (Zona histórica de acumulación profunda)"

    with tab1:
        st.markdown("### 🟢 Momento Óptimo de Compra (Precio)")
        st.success(f"**Precio Sugerido:** `${momento_optimo_compra:,.2f} USD`\n\n*Por qué:* {estado_compra}")
        
        st.markdown("### 🔴 Momento Óptimo de Venta (Precio)")
        st.error(f"**Precio Sugerido:** `${momento_optimo_venta:,.2f} USD`\n\n*Ganancia estimada:* `+${ganancia:,.2f} {moneda}`")
        
        st.markdown("### 🔮 Predicción de Fechas Estimadas")
        st.info(f"**Corto plazo - Próxima oportunidad de compra:**\n{str_fecha_compra}")
        st.warning(f"**Largo plazo - Ventana ideal para acumular (Compra Macro):**\n{str_fecha_compra_macro}\n\n**Largo plazo - Ventana ideal para vender todo (Pico Macro):**\n{str_fecha_venta_macro}")
        
        st.markdown("### 🛡️ Nivel de Riesgo (Stop-Loss)")
        st.error(f"**Salida de emergencia:** `${stop_loss:,.2f} USD`")

    with tab2:
        st.markdown("### Situación Actual (Últimos 6 Meses)")
        col_s1, col_s2 = st.columns(2)
        col_s1.metric("Sentimiento", f"{fng_val}/100", fng_txt)
        col_s2.metric("RSI (Fuerza)", f"{rsi:.1f}", "Sobrecomprado" if rsi > 70 else "Sobrevendido" if rsi < 30 else "Neutral")
        
        df_recent = df.tail(180) 
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_recent["fecha"], y=df_recent["precio"], name="Precio BTC", line=dict(color="#f7931a", width=2)))
        fig.add_trace(go.Scatter(x=df_recent["fecha"], y=df_recent["SMA_20"], name="Tendencia (20d)", line=dict(color="#2962ff", dash="dot")))
        fig.update_layout(xaxis_title="Fecha", yaxis_title="Precio (USD)", margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.markdown("### Comportamiento a 5 Años")
        st.write("Análisis de patrones utilizando la media móvil de 200 días. Identifica ciclos históricos de acumulación y euforia.")
        
        fig_macro = go.Figure()
        fig_macro.add_trace(go.Scatter(x=df["fecha"], y=df["precio"], name="Precio BTC", line=dict(color="#f7931a", width=1)))
        fig_macro.add_trace(go.Scatter(x=df["fecha"], y=df["SMA_200"], name="Promedio 200d", line=dict(color="#ff0000", width=2)))
        fig_macro.update_layout(xaxis_title="Año", yaxis_title="Precio (USD)", margin=dict(l=0, r=0, t=30, b=0), template="plotly_dark", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_macro, use_container_width=True)
        
        if precio_actual > sma_200:
            st.success("📈 **Patrón Macro:** El mercado a largo plazo está en fase ALCISTA (el precio superó su promedio de 5 años).")
        else:
            st.error("📉 **Patrón Macro:** El mercado a largo plazo está en fase BAJISTA (oportunidad histórica de acumulación barata).")

except Exception as e:
    st.error(f"Ocurrió un error al cargar los datos del mercado: {e}")
