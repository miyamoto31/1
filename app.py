import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import tempfile
import os

st.set_page_config(page_title="Gestor Financiero | Brote", page_icon="🌱", layout="centered")
st.title("Gestor Financiero Integral Piloto")
st.caption("Presupuestos, Portafolios Diversificados y Análisis de Mercado")

# --- INTENTO DE IMPORTAR FPDF (Para el PDF) ---
try:
    from fpdf import FPDF
    pdf_disponible = True
except ImportError:
    pdf_disponible = False

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
        noticias, score = [], 0
        if res.status_code == 200:
            data = res.json()["Data"][:10]
            positivas = ["sube", "adopción", "alianza", "compra", "alcista", "aprobado", "crece", "optimismo"]
            negativas = ["cae", "hackeo", "demanda", "prohibición", "vende", "bajista", "miedo", "fraude"]
            for n in data:
                titulo, cuerpo = n["title"].lower(), n["body"].lower()
                noticias.append({"titulo": n["title"], "url": n["url"]})
                for p in positivas:
                    if p in titulo or p in cuerpo: score += 1
                for neg in negativas:
                    if neg in titulo or neg in cuerpo: score -= 1
        return noticias, score
    except: return [], 0

def obtener_precios_historicos():
    # PLAN A: Yahoo Finance (Súper estable, no bloquea fácil)
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD?range=5y&interval=1d"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if res.status_code == 200:
            data = res.json()
            fechas = [pd.to_datetime(ts, unit='s') for ts in data['chart']['result'][0]['timestamp']]
            closes = data['chart']['result'][0]['indicators']['quote'][0]['close']
            return pd.DataFrame({'fecha': fechas, 'precio': closes}).dropna()
    except: pass
    
    # PLAN B: CoinGecko
    try:
        url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=1825&interval=daily"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            return pd.DataFrame({"fecha": [pd.to_datetime(p[0], unit='ms') for p in data["prices"]], "precio": [p[1] for p in data["prices"]]}).dropna()
    except: pass
    
    return pd.DataFrame() # Si todo falla, devuelve vacío

@st.cache_data(ttl=1800)
def cargar_datos_completos():
    fng_val, fng_txt = obtener_sentimiento()
    df = obtener_precios_historicos()
    
    if not df.empty:
        df["SMA_20"] = df["precio"].rolling(20).mean()
        df["SMA_200"] = df["precio"].rolling(200).mean()
        delta = df["precio"].diff()
        df["RSI"] = 100 - (100 / (1 + (delta.clip(lower=0).rolling(14).mean() / -delta.clip(upper=0).rolling(14).mean())))
        ema12 = df['precio'].ewm(span=12, adjust=False).mean()
        ema26 = df['precio'].ewm(span=26, adjust=False).mean()
        df['MACD'] = ema12 - ema26
        df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
    return df, fng_val, fng_txt

def generar_pdf(ingreso, gastos, sobrante, p_seg, m_seg, p_mod, m_mod, p_cri, m_cri):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Encabezado
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="REPORTE DE PLANIFICACION FINANCIERA", ln=True, align='C')
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(200, 10, txt=f"Generado por Brote - Fecha: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align='C')
    pdf.cell(200, 10, txt="----------------------------------------------------------------", ln=True, align='C')
    
    # Presupuesto
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="1. FLUJO DE EFECTIVO OPERATIVO", ln=True)
    pdf.set_font("Arial", '', 12)
    pdf.cell(200, 10, txt=f"Ingresos Totales: ${ingreso:,.2f} MXN", ln=True)
    pdf.cell(200, 10, txt=f"Gastos Innegociables: ${gastos:,.2f} MXN", ln=True)
    pdf.cell(200, 10, txt=f"Capital Libre (Sobrante): ${sobrante:,.2f} MXN", ln=True)
    
    pdf.cell(200, 5, txt="", ln=True)
    
    # Portafolios
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="2. DISTRIBUCION DE PORTAFOLIOS", ln=True)
    pdf.set_font("Arial", '', 12)
    pdf.cell(200, 10, txt=f"- Fondo de Seguridad ({p_seg}%): ${m_seg:,.2f} MXN", ln=True)
    pdf.cell(200, 10, txt=f"- Riesgo Moderado/ETFs ({p_mod}%): ${m_mod:,.2f} MXN", ln=True)
    pdf.cell(200, 10, txt=f"- Alto Riesgo/Cripto ({p_cri}%): ${m_cri:,.2f} MXN", ln=True)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        return tmp.name

# --- INTERFAZ ---
tab_presupuesto, tab_cripto, tab_datos = st.tabs(["Tu Presupuesto", "Operación Cripto", "Gráficos"])

with tab_presupuesto:
    if not pdf_disponible:
        st.warning("⚠️ **Aviso técnico:** Para activar el botón de PDF, agrega la palabra `fpdf` a tu archivo `requirements.txt` en GitHub.")

    st.markdown("### 1. Tu Flujo de Efectivo Mensual")
    ingreso = st.number_input("Ingresos Totales (Salario, proyectos, etc):", min_value=0.0, value=5000.0, step=500.0)
    
    st.write("**Gastos Innegociables (Base Operativa):**")
    col1, col2 = st.columns(2)
    with col1:
        gasto_transporte = st.number_input("Transporte / Universidad", value=600.0, step=50.0)
        gasto_mascotas = st.number_input("Mascotas (Perros, Conejo, Agustín)", value=400.0, step=50.0)
    with col2:
        gasto_comida = st.number_input("Alimentación / Despensa", value=1500.0, step=100.0)
        gasto_otros = st.number_input("Salidas y Gustos", value=500.0, step=50.0)
        
    gastos_totales = gasto_transporte + gasto_mascotas + gasto_comida + gasto_otros
    sobrante = ingreso - gastos_totales
    
    st.markdown("---")
    if sobrante > 0:
        st.success(f"**Capital Libre para Invertir:** `${sobrante:,.2f} MXN`")
        
        st.markdown("### 2. Distribución de Portafolios (Ingresos Pasivos)")
        st.write("Ajusta los porcentajes según tu estrategia mensual. El sistema usa la regla 50/30/20 por defecto:")
        
        c_pct1, c_pct2, c_pct3 = st.columns(3)
        with c_pct1:
            pct_seguridad = st.number_input("% Sin Riesgo", min_value=0, max_value=100, value=50, step=5)
        with c_pct2:
            pct_moderado = st.number_input("% Riesgo Moderado", min_value=0, max_value=100, value=30, step=5)
        with c_pct3:
            pct_cripto = st.number_input("% Alto Riesgo", min_value=0, max_value=100, value=20, step=5)
            
        suma_pct = pct_seguridad + pct_moderado + pct_cripto
        
        if suma_pct != 100:
            st.warning(f"⚠️ Tus porcentajes suman **{suma_pct}%**. Por favor, ajústalos para que el total sea exactamente 100%.")
            
        fondo_seguridad = sobrante * (pct_seguridad / 100)
        etf_crecimiento = sobrante * (pct_moderado / 100)
        riesgo_cripto = sobrante * (pct_cripto / 100)
        
        # --- BOTON DE PDF ---
        if pdf_disponible and suma_pct == 100:
            ruta_pdf = generar_pdf(ingreso, gastos_totales, sobrante, pct_seguridad, fondo_seguridad, pct_moderado, etf_crecimiento, pct_cripto, riesgo_cripto)
            with open(ruta_pdf, "rb") as f:
                st.download_button(
                    label="Descargar Reporte PDF del Mes",
                    data=f,
                    file_name=f"Reporte_Financiero_{datetime.now().strftime('%Y-%m')}.pdf",
                    mime="application/pdf"
                )
            os.remove(ruta_pdf)
        
        with st.expander(f" Sin Riesgo ({pct_seguridad}%) -> Destina ${fondo_seguridad:,.2f} MXN", expanded=True):
            st.markdown("- **Cajitas Nu (SOFIPO):** Alto rendimiento pasivo, liquidez inmediata (24/7). Ideal para fondo de emergencias.")
            st.markdown("- **Mercado Pago / GBM:** Fondo líquido, excelente para dinero de uso rápido.")
            st.markdown("- **Cetesdirecto (BONDDIA):** La opción más segura del país (Respaldada por Hacienda).")

        with st.expander(f" Riesgo Moderado ({pct_moderado}%) -> Destina ${etf_crecimiento:,.2f} MXN", expanded=True):
            st.markdown("- **FIBRAs (Ej. Fibra Monterrey / Fibra Uno):** Fideicomisos inmobiliarios.")
            st.markdown("- **ETFs de Dividendos:** Participaciones en empresas seguras.")

        with st.expander(f" Alto Riesgo ({pct_cripto}%) -> Destina ${riesgo_cripto:,.2f} MXN", expanded=True):
            st.markdown("- **Staking de Dólares Digitales (USDT) en Binance.**")
            st.markdown("- **Trading Estratégico (BTC):** Compras guiadas por MACD y Hype.")
    else:
        st.error(f"**Déficit Operativo:** Te faltan `${abs(sobrante):,.2f}` para cubrir tus gastos este mes.")
        riesgo_cripto = 0

with tab_cripto:
    df, fng_val, fng_txt = cargar_datos_completos()
    noticias, hype_score = obtener_noticias_y_hype()
    
    if not df.empty:
        precio_actual = df["precio"].iloc[-1]
        rsi = df["RSI"].iloc[-1]
        macd = df["MACD"].iloc[-1]
        signal = df["Signal_Line"].iloc[-1]
        
        advertencia_manipulacion = ""
        if hype_score <= -3: advertencia_manipulacion = "🛑 ALERTA FUD: Pánico mediático detectado."
        elif hype_score >= 3: advertencia_manipulacion = "🔥 ALERTA HYPE: Euforia extrema."
            
        if fng_val <= 30 and rsi < 40 and hype_score > -3 and macd > signal:
            estado_compra = "🔥 SEÑAL FUERTE: Momento óptimo confirmado por MACD."
            precio_compra = precio_actual
        else:
            estado_compra = "❌ PACIENCIA TÁCTICA: El mercado no ofrece ventajas hoy."
            precio_compra = df["SMA_20"].iloc[-1] * 0.95
            
        precio_venta = max(precio_compra * 1.15, df["precio"].tail(30).max())

        if advertencia_manipulacion: st.warning(advertencia_manipulacion)
        st.markdown(f"### Análisis de Mercado: {estado_compra}")
        
        if riesgo_cripto < 100:
            st.error("Tu presupuesto cripto sobrante es menor al mínimo operativo de Binance (~$100 MXN). Enfócate en tu Liquidez Nu/Mercado Pago este mes.")
        else:
            st.write(f"Con tu asignación (**${riesgo_cripto:,.2f}**), esta es tu estrategia:")
            c1, c2 = st.columns(2)
            c1.success(f"**🟢 Entrada Sugerida:**\n`${precio_compra:,.2f} USD`")
            c2.error(f"**🔴 Salida (Take Profit):**\n`${precio_venta:,.2f} USD`")
    else:
        st.error("No se pudieron cargar los precios de la red en este momento. Intenta de nuevo en un par de minutos.")

with tab_datos:
    if not df.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Miedo/Codicia", f"{fng_val}")
        c2.metric("RSI", f"{rsi:.1f}")
        c3.metric("Hype Score", f"{hype_score} pts")
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.tail(90)["fecha"], y=df.tail(90)["precio"], name="Precio", line=dict(color="#f7931a")))
        fig.add_trace(go.Scatter(x=df.tail(90)["fecha"], y=df.tail(90)["SMA_20"], name="SMA 20", line=dict(color="#2962ff", dash="dot")))
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Los gráficos están temporalmente en pausa porque la conexión al servidor de precios fue rechazada.")
