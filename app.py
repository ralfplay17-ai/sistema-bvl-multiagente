import os
import sys
import re
import json
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date, timedelta
import streamlit as st

# BVL historical data module (CSV local)
_BVL_DATA_DIR = os.path.join(os.path.dirname(__file__), "data_bvl")
if _BVL_DATA_DIR not in sys.path:
    sys.path.insert(0, _BVL_DATA_DIR)
try:
    from bvl_data import obtener_df_para_backtest, obtener_historico_para_grafico
    _BVL_DISPONIBLE = True
except Exception:
    _BVL_DISPONIBLE = False

st.set_page_config(
    page_title="Dashboard BVL — Análisis Minero",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────
LANGFLOW_BASE    = os.environ.get("LANGFLOW_BASE_URL", "http://localhost:7860")
LANGFLOW_API_KEY = os.environ.get("LANGFLOW_API_KEY", "")
LANGFLOW_USER    = os.environ.get("LANGFLOW_USER", "langflow")
LANGFLOW_PASS    = os.environ.get("LANGFLOW_PASS", "langflow")
AV_KEY           = os.environ.get("ALPHA_VANTAGE_KEY", "TPTUYCIWJ2JYRVWQ")

BVL_API_BASE = "https://dataondemand.bvl.com.pe/v1"
BVL_HEADERS  = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept":     "application/json, text/plain, */*",
    "Referer":    "https://www.bvl.com.pe/",
    "Origin":     "https://www.bvl.com.pe",
}

TICKERS_BVL = {
    "BVN — Buenaventura":          "BVN",
    "SCCO — Southern Copper":       "SCCO",
    "CVERDEC1 — Cerro Verde":       "CVERDEC1",
    "MINSURI1 — Minsur":            "MINSURI1",
    "VOLCABC1 — Volcan":            "VOLCABC1",
    "NEXAPEC1 — Nexa Resources":    "NEXAPEC1",
    "BROCALC1 — El Brocal":         "BROCALC1",
    "SHPC1 — Shougang Hierro":      "SHPC1",
    "PODERC1 — Poderosa":           "PODERC1",
    "MOROCOC1 — Morococha":         "MOROCOC1",
    "LUISAI1 — Santa Luisa":        "LUISAI1",
    "ATACOBC1 — Atacocha":          "ATACOBC1",
    "MINCORC1 — Cía Corona":        "MINCORC1",
    "PERUBAI1 — Perubar":           "PERUBAI1",
    "FOSPACC1 — Fosfatos Pacífico": "FOSPACC1",
    "CASTROC1 — Castrovirreyna":    "CASTROC1",
}

# ─────────────────────────────────────────────────────────────────────────────
# ESTILOS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.block-container { padding-top: 2.8rem; padding-bottom: 1rem; }

/* ── Tabs (Streamlit 1.35+) ───────────────────────────────────────── */
button[role="tab"] {
    color: #aaa !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    background: transparent !important;
    border: none !important;
    padding: 8px 18px !important;
}
button[role="tab"]:hover {
    color: #fff !important;
}
button[role="tab"][aria-selected="true"] {
    color: #fff !important;
}
button[role="tab"] p {
    color: inherit !important;
    font-size: 14px !important;
    font-weight: 600 !important;
}
div[role="tablist"] {
    border-bottom: 1px solid #2a2a2a;
    gap: 4px;
}

/* Tarjetas métricas */
.metric-card {
    background: #1e1e1e;
    border: 1px solid #333;
    border-radius: 12px;
    padding: 18px 20px;
    text-align: center;
}
.metric-card .label  { color: #888; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; }
.metric-card .value  { color: #fff; font-size: 32px; font-weight: 800; margin: 6px 0 4px; line-height: 1; }
.metric-card .sub    { color: #aaa; font-size: 13px; }

/* Señal principal */
.signal-banner {
    border-radius: 14px; padding: 28px 24px; text-align: center; margin-bottom: 4px;
}
.signal-banner.buy  { background: #0d2e1a; border: 2px solid #22c55e; }
.signal-banner.hold { background: #2c2200; border: 2px solid #eab308; }
.signal-banner.sell { background: #2e0d0d; border: 2px solid #ef4444; }
.signal-banner .sig-label { font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; margin-bottom: 6px; }
.signal-banner .sig-main  { font-size: 52px; font-weight: 900; line-height: 1; }
.signal-banner .sig-sub   { font-size: 16px; margin-top: 8px; opacity: .8; }
.signal-banner.buy  .sig-main  { color: #22c55e; }
.signal-banner.hold .sig-main  { color: #eab308; }
.signal-banner.sell .sig-main  { color: #ef4444; }

/* Tarjeta razones */
.reason-card {
    background: #1e1e1e; border: 1px solid #333; border-radius: 12px;
    padding: 20px 22px; color: #ddd; height: 100%;
}
.reason-card h4 { color: #fff; font-size: 15px; font-weight: 700; margin: 0 0 12px; }
.reason-card li { font-size: 14px; margin-bottom: 7px; line-height: 1.5; }

/* Agentes */
.agent-card {
    background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 10px;
    padding: 14px 16px; margin-bottom: 10px;
}
.agent-card .ag-name   { color: #bbb; font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.agent-card .ag-signal { font-size: 17px; font-weight: 800; }
.agent-card .ag-signal.buy  { color: #22c55e; }
.agent-card .ag-signal.hold { color: #eab308; }
.agent-card .ag-signal.sell { color: #ef4444; }
.agent-card .ag-conf   { color: #666; font-size: 12px; margin-top: 2px; }
.agent-card .ag-desc   { color: #999; font-size: 12px; margin-top: 7px; line-height: 1.5; border-top: 1px solid #2a2a2a; padding-top: 7px; }

/* Barra de progreso */
.prog-wrap { background: #2a2a2a; border-radius: 6px; height: 6px; overflow: hidden; margin-top: 6px; }
.prog-fill  { height: 6px; border-radius: 6px; }
.prog-fill.buy  { background: #22c55e; }
.prog-fill.hold { background: #eab308; }
.prog-fill.sell { background: #ef4444; }

/* Precio real-time sidebar */
.rt-price-box {
    background: #161616; border: 1px solid #2a2a2a; border-radius: 10px;
    padding: 12px 14px; margin-top: 8px;
}
.rt-price-box .rt-ticker { color: #888; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; }
.rt-price-box .rt-val    { color: #fff; font-size: 26px; font-weight: 800; line-height: 1; margin: 4px 0 2px; }
.rt-price-box .rt-change.up   { color: #22c55e; font-size: 14px; }
.rt-price-box .rt-change.down { color: #ef4444; font-size: 14px; }
.rt-price-box .rt-vol  { color: #666; font-size: 11px; margin-top: 4px; }

/* Tarjeta commodity */
.comm-card {
    background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 12px;
    padding: 18px 20px;
}
.comm-card .c-name  { color: #888; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .07em; }
.comm-card .c-price { color: #fff; font-size: 30px; font-weight: 800; margin: 6px 0 2px; }
.comm-card .c-label { color: #555; font-size: 11px; }
.comm-card .c-d-up  { color: #22c55e; font-size: 14px; font-weight: 700; }
.comm-card .c-d-dn  { color: #ef4444; font-size: 14px; font-weight: 700; }
.comm-card .c-d-eq  { color: #888;    font-size: 14px; font-weight: 700; }
.comm-card .c-src   { color: #444; font-size: 11px; margin-top: 6px; }

/* Noticias */
.news-card {
    background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 10px;
    padding: 14px 16px; margin-bottom: 10px;
}
.news-card .n-title  { color: #e8e8e8; font-size: 14px; font-weight: 600; margin-bottom: 5px; line-height: 1.4; }
.news-card .n-meta   { color: #555; font-size: 11px; margin-bottom: 7px; }
.news-card .n-desc   { color: #888; font-size: 12px; line-height: 1.5; }
.news-card .n-badge  { display: inline-block; padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: 700; margin-left: 6px; }
.n-badge.pos { background: #0d2e1a; color: #22c55e; }
.n-badge.neu { background: #1f1f00; color: #eab308; }
.n-badge.neg { background: #2e0d0d; color: #ef4444; }

/* Pesos PSO */
.peso-bar { background:#1a1a1a; border: 1px solid #2a2a2a; border-radius: 10px; padding: 14px 16px; margin-bottom: 8px; }
.peso-bar .p-name { color: #999; font-size: 13px; }
.peso-bar .p-pct  { color: #fff; font-size: 22px; font-weight: 800; float: right; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIONES LANGFLOW
# ─────────────────────────────────────────────────────────────────────────────
_lf_token:   str | None = None
_lf_flow_id: str | None = None


def _lf_get_token() -> str:
    """Obtiene token de LangFlow. Prueba auto_login primero, luego credenciales."""
    global _lf_token
    if _lf_token:
        return _lf_token

    # auto_login (requiere LANGFLOW_SKIP_AUTH_AUTO_LOGIN=true en el servidor)
    try:
        r = requests.get(f"{LANGFLOW_BASE}/api/v1/auto_login", timeout=10)
        if r.ok:
            tok = r.json().get("access_token")
            if tok:
                _lf_token = tok
                return tok
    except Exception:
        pass

    # Fallback: login con credenciales
    for user, pwd in [
        (LANGFLOW_USER, LANGFLOW_PASS),
        ("admin", "admin1234"),
        ("langflow", "langflow"),
    ]:
        try:
            r = requests.post(
                f"{LANGFLOW_BASE}/api/v1/login",
                data={"username": user, "password": pwd},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )
            if r.ok:
                tok = r.json().get("access_token")
                if tok:
                    _lf_token = tok
                    return tok
        except Exception:
            pass

    raise RuntimeError("No se pudo autenticar con LangFlow")


def _lf_auth_headers() -> dict:
    return {"Content-Type": "application/json", "Authorization": f"Bearer {_lf_get_token()}"}


def _lf_get_flow_id() -> str:
    global _lf_flow_id
    if _lf_flow_id:
        return _lf_flow_id
    r = requests.get(f"{LANGFLOW_BASE}/api/v1/flows/", headers=_lf_auth_headers(), timeout=10)
    r.raise_for_status()
    flows = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    for f in flows:
        name = f.get("name", "").lower()
        if "sistema" in name or "bvl" in name or "minera" in name:
            _lf_flow_id = f["id"]
            return _lf_flow_id
    if flows:
        _lf_flow_id = flows[0]["id"]
        return _lf_flow_id
    raise RuntimeError("No se encontró ningún flow en LangFlow")


def _extraer_json(texto: str):
    texto = texto.strip()
    try:
        d = json.loads(texto)
        if isinstance(d, dict):
            return d
    except Exception:
        pass
    match = re.search(r"\{.*\}", texto, re.DOTALL)
    if match:
        try:
            d = json.loads(match.group())
            if isinstance(d, dict):
                return d
        except Exception:
            pass
    return None


def _extraer_json_de_response(response_json):
    textos = []
    def recorrer(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("text", "content", "message") and isinstance(v, str):
                    textos.append(v)
                recorrer(v)
        elif isinstance(obj, list):
            for item in obj:
                recorrer(item)
    recorrer(response_json)
    for texto in textos:
        data = _extraer_json(texto)
        if data:
            return data
    raise ValueError("No se encontró JSON en la respuesta de LangFlow.")


def ejecutar_langflow(ticker: str) -> dict:
    global _lf_token, _lf_flow_id
    payload = {"output_type": "chat", "input_type": "chat", "input_value": f"Analiza {ticker}"}

    def _run():
        flow_id = _lf_get_flow_id()
        return requests.post(
            f"{LANGFLOW_BASE}/api/v1/run/{flow_id}",
            json=payload, headers=_lf_auth_headers(), timeout=240,
        )

    resp = _run()
    if resp.status_code in (401, 403):
        _lf_token = None   # forzar re-autenticación
        _lf_flow_id = None
        resp = _run()
    resp.raise_for_status()
    return _extraer_json_de_response(resp.json())


# ─────────────────────────────────────────────────────────────────────────────
# DATOS EN TIEMPO REAL — BVL (precio, variación, volumen)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def _fetch_bvl_precio_rt(nemonico: str) -> dict | None:
    try:
        r = requests.get(BVL_API_BASE + "/issuers", headers=BVL_HEADERS, timeout=10)
        r.raise_for_status()
        company_code = None
        for issuer in r.json():
            if issuer.get("tkrCode") == nemonico and issuer.get("active", True):
                company_code = issuer.get("companyCode")
                break
        if not company_code:
            return None
        r2 = requests.get(BVL_API_BASE + "/issuers/" + company_code + "/value", headers=BVL_HEADERS, timeout=10)
        r2.raise_for_status()
        def _f(v):
            try: return float(v) if v not in (None, "", "-", "0") else None
            except: return None
        def _i(v):
            try: return int(float(v)) if v not in (None, "", "-") else None
            except: return None
        for emisor in r2.json():
            for lv in emisor.get("listLastValue", []):
                if lv.get("tkrCode") == nemonico:
                    return {
                        "precio":       _f(lv.get("close") or lv.get("last")),
                        "variacion_pct": _f(lv.get("var")),
                        "volumen":      _i(lv.get("quantityNegotiated")),
                        "moneda":       (lv.get("coin") or "S/.").strip(),
                        "nombre":       lv.get("companyName", nemonico),
                    }
    except Exception:
        return None
    return None


# ─────────────────────────────────────────────────────────────────────────────
# COMMODITIES — yfinance (fallback: Twelve Data / Alpha Vantage)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def _fetch_commodities() -> dict:
    result = {}
    metals = [
        ("Oro",   "GC=F", "XAU/USD", "oz"),
        ("Plata", "SI=F", "XAG/USD", "oz"),
        ("Cobre", "HG=F", "HG=F",    "lb"),
    ]
    for nombre, symbol, label, unit in metals:
        try:
            import yfinance as yf
            hist = yf.Ticker(symbol).history(period="15d")
            if hist.empty or len(hist) < 2:
                result[nombre] = {"error": "Sin datos"}
                continue
            closes = hist["Close"].dropna()
            ph = float(closes.iloc[-1])
            pa = float(closes.iloc[-2])
            p5 = float(closes.iloc[-5]) if len(closes) >= 5 else float(closes.iloc[0])
            result[nombre] = {
                "label":     label,
                "unit":      unit,
                "precio":    ph,
                "cambio_dia": (ph - pa) / pa * 100,
                "tend_5d":   (ph - p5) / p5 * 100,
                "closes":    [round(c, 2) for c in closes.tolist()],
                "dates":     [d.strftime("%d/%m") for d in closes.index],
                "fuente":    "yfinance",
            }
        except Exception as e:
            result[nombre] = {"error": str(e)}
    return result


# ─────────────────────────────────────────────────────────────────────────────
# NOTICIAS — Alpha Vantage + Google News RSS
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def _fetch_noticias(ticker: str) -> dict:
    out = {"av": [], "rss": [], "ticker": ticker}

    # Alpha Vantage
    if AV_KEY:
        try:
            url = (f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT"
                   f"&tickers={ticker}&limit=15&apikey={AV_KEY}")
            resp = requests.get(url, timeout=15).json()
            if not resp.get("Information") and not resp.get("Note"):
                for art in resp.get("feed", []):
                    for ts in art.get("ticker_sentiment", []):
                        if ts.get("ticker") == ticker and float(ts.get("relevance_score", 0)) >= 0.05:
                            fd = art.get("time_published", "")[:8]
                            if len(fd) == 8:
                                fd = f"{fd[:4]}-{fd[4:6]}-{fd[6:8]}"
                            out["av"].append({
                                "titulo":  art.get("title", ""),
                                "fecha":   fd,
                                "fuente":  art.get("source", ""),
                                "score":   float(art.get("overall_sentiment_score", 0)),
                                "label":   art.get("overall_sentiment_label", "Neutral"),
                                "resumen": art.get("summary", "")[:220],
                                "url":     art.get("url", ""),
                            })
                            break
        except Exception:
            pass

    # Google News RSS
    try:
        import feedparser
        q = requests.utils.quote(f"{ticker} Peru minera bolsa Lima")
        feed = feedparser.parse(
            f"https://news.google.com/rss/search?q={q}&hl=es-419&gl=PE&ceid=PE:es-419"
        )
        for entry in (feed.entries or [])[:8]:
            resumen = re.sub(r"<[^>]+>", "", entry.get("summary", ""))[:220]
            out["rss"].append({
                "titulo":    entry.get("title", ""),
                "publicado": entry.get("published", ""),
                "link":      entry.get("link", ""),
                "resumen":   resumen,
            })
    except Exception:
        pass

    return out


# ─────────────────────────────────────────────────────────────────────────────
# DATOS HISTÓRICOS + INDICADORES
# ─────────────────────────────────────────────────────────────────────────────
def _wilder_rsi(close: pd.Series, periodo: int = 14) -> pd.Series:
    """RSI con suavizado Wilder (EMA alpha=1/periodo). Filtra días sin negociación."""
    p = close[close > 0].dropna()
    if len(p) < periodo + 2:
        return pd.Series([float("nan")] * len(close), index=close.index)
    delta    = p.diff()
    avg_gain = delta.clip(lower=0).ewm(alpha=1.0 / periodo, min_periods=periodo, adjust=False).mean()
    avg_loss = (-delta.clip(upper=0)).ewm(alpha=1.0 / periodo, min_periods=periodo, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, float("inf"))
    return (100 - (100 / (1 + rs))).clip(0, 100).reindex(close.index)


def _calcular_indicadores(close: pd.Series) -> list[dict]:
    # Filtrar días sin negociación (precio 0 o repetido)
    close = close[close > 0].dropna()

    rsi    = _wilder_rsi(close)
    ema12  = close.ewm(span=12, adjust=False).mean()
    ema26  = close.ewm(span=26, adjust=False).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    sma20  = close.rolling(20).mean()
    sma50  = close.rolling(50).mean() if len(close) >= 50 else None

    rows = []
    for dt, precio in close.items():
        def _v(s, _dt=dt):
            if s is None or _dt not in s.index:
                return None
            v = s.loc[_dt]
            return None if pd.isna(v) else float(v)
        rows.append({
            "fecha":  dt.strftime("%Y-%m-%d"),
            "close":  float(precio),
            "rsi":    _v(rsi),
            "macd":   _v(macd),
            "signal": _v(signal),
            "sma20":  _v(sma20),
            "sma50":  _v(sma50),
        })
    return rows


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_historico(ticker: str) -> list[dict] | None:
    if _BVL_DISPONIBLE:
        try:
            h = obtener_historico_para_grafico(ticker, dias=60)
            if h and len(h) >= 20:
                return h
        except Exception:
            pass
    # Fallback: BVL API directa
    try:
        fecha_fin = date.today()
        fecha_ini = fecha_fin - timedelta(days=120)
        r = requests.get(
            BVL_API_BASE + "/stock-quote/share-value",
            headers=BVL_HEADERS,
            params={"name": ticker, "startDate": fecha_ini.isoformat(), "endDate": fecha_fin.isoformat()},
            timeout=15,
        )
        r.raise_for_status()
        values = r.json().get("values", [])
        if len(values) >= 20:
            s = pd.Series(
                [float(v[1]) for v in values],
                index=pd.to_datetime([v[0] for v in values]),
            ).sort_index()
            s = s[s > 0].dropna()
            if len(s) >= 15:
                return _calcular_indicadores(s)
    except Exception:
        pass
    # Fallback: Alpha Vantage
    if AV_KEY:
        try:
            r = requests.get(
                f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY"
                f"&symbol={ticker}&outputsize=compact&apikey={AV_KEY}",
                timeout=20,
            )
            ts = r.json().get("Time Series (Daily)", {})
            if ts:
                df = pd.DataFrame.from_dict(ts, orient="index").astype(float)
                df.columns = ["Open", "High", "Low", "Close", "Volume"]
                df.index = pd.to_datetime(df.index)
                df = df.sort_index().tail(60)
                return _calcular_indicadores(df["Close"])
        except Exception:
            pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# GRÁFICOS
# ─────────────────────────────────────────────────────────────────────────────
def _grafico_tecnico(historico: list[dict], ticker: str) -> go.Figure:
    df = pd.DataFrame(historico)
    df["fecha"] = pd.to_datetime(df["fecha"])

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.55, 0.22, 0.23],
        subplot_titles=[f"{ticker} — Precio y Medias Móviles", "RSI (14)", "MACD"],
    )

    # Precio
    fig.add_trace(go.Scatter(x=df["fecha"], y=df["close"], name="Precio",
                             line=dict(color="#60a5fa", width=2.5)), row=1, col=1)
    if "sma20" in df:
        fig.add_trace(go.Scatter(x=df["fecha"], y=df["sma20"], name="SMA 20",
                                 line=dict(color="#fbbf24", width=1.5, dash="dot")), row=1, col=1)
    if "sma50" in df:
        fig.add_trace(go.Scatter(x=df["fecha"], y=df["sma50"], name="SMA 50",
                                 line=dict(color="#f87171", width=1.5, dash="dot")), row=1, col=1)

    # RSI
    if "rsi" in df:
        fig.add_trace(go.Scatter(x=df["fecha"], y=df["rsi"], name="RSI",
                                 line=dict(color="#34d399", width=2)), row=2, col=1)
        fig.add_hline(y=70, line=dict(color="#ef4444", width=1, dash="dash"), row=2, col=1)
        fig.add_hline(y=30, line=dict(color="#22c55e", width=1, dash="dash"), row=2, col=1)
        fig.add_hrect(y0=70, y1=100, fillcolor="#ef4444", opacity=0.06, line_width=0, row=2, col=1)
        fig.add_hrect(y0=0,  y1=30,  fillcolor="#22c55e", opacity=0.06, line_width=0, row=2, col=1)

    # MACD
    if "macd" in df and "signal" in df:
        df["hist"] = df["macd"] - df["signal"]
        colors = ["#22c55e" if v >= 0 else "#ef4444" for v in df["hist"].fillna(0)]
        fig.add_trace(go.Bar(x=df["fecha"], y=df["hist"], name="Histograma",
                             marker_color=colors, opacity=0.6), row=3, col=1)
        fig.add_trace(go.Scatter(x=df["fecha"], y=df["macd"], name="MACD",
                                 line=dict(color="#60a5fa", width=2)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df["fecha"], y=df["signal"], name="Señal",
                                 line=dict(color="#fbbf24", width=2)), row=3, col=1)

    fig.update_layout(
        height=680, hovermode="x unified",
        plot_bgcolor="#111", paper_bgcolor="#111",
        font=dict(color="#ccc", size=12),
        legend=dict(orientation="h", y=1.02, bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=8, r=8, t=42, b=8),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#222", zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#222", zeroline=False)
    return fig


def _grafico_sparkline(closes: list, dates: list, color: str = "#60a5fa") -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=closes,
        line=dict(color=color, width=1.5),
        fill="tozeroy", fillcolor=color.replace(")", ", 0.10)").replace("rgb", "rgba"),
        mode="lines",
    ))
    fig.update_layout(
        height=70, margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False, xaxis=dict(visible=False), yaxis=dict(visible=False),
    )
    return fig


def _grafico_backtest(bt: dict) -> go.Figure:
    df_pso = pd.DataFrame(bt["estrategia_pso"]["historial_capital"])
    df_bh  = pd.DataFrame(bt["buy_hold"]["historial_capital"])
    df_pso["fecha"] = pd.to_datetime(df_pso["fecha"])
    df_bh["fecha"]  = pd.to_datetime(df_bh["fecha"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_pso["fecha"], y=df_pso["capital"],
                             name="Estrategia PSO", line=dict(color="#60a5fa", width=3)))
    fig.add_trace(go.Scatter(x=df_bh["fecha"],  y=df_bh["capital"],
                             name="Buy & Hold",  line=dict(color="#fbbf24", width=3)))
    fig.update_layout(
        height=440, title="Evolución del Capital: PSO vs Buy & Hold",
        plot_bgcolor="#111", paper_bgcolor="#111",
        font=dict(color="#ccc"), hovermode="x unified",
        legend=dict(orientation="h", y=1.06, bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=8, r=8, t=44, b=8),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#222")
    fig.update_yaxes(showgrid=True, gridcolor="#222", tickprefix="$")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# BACKTESTING
# ─────────────────────────────────────────────────────────────────────────────
def _ejecutar_backtest(ticker: str, dias: int) -> dict:
    try:
        df, error = None, None
        if _BVL_DISPONIBLE:
            df = obtener_df_para_backtest(ticker, dias)
        if df is None or len(df) < 20:
            # Fallback Alpha Vantage
            url = (f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY"
                   f"&symbol={ticker}&outputsize=full&apikey={AV_KEY}")
            resp = requests.get(url, timeout=25).json()
            if "Time Series (Daily)" not in resp:
                return {"error": resp.get("Note") or resp.get("Information") or "Sin datos históricos"}
            ts = resp["Time Series (Daily)"]
            df = pd.DataFrame.from_dict(ts, orient="index").astype(float)
            df.columns = ["Open", "High", "Low", "Close", "Volume"]
            df.index = pd.to_datetime(df.index)
            df = df.sort_index().tail(dias)

        if len(df) < 20:
            return {"error": "Datos insuficientes para backtesting"}

        df["RSI"]      = _wilder_rsi(df["Close"])
        ema12          = df["Close"].ewm(span=12, adjust=False).mean()
        ema26          = df["Close"].ewm(span=26, adjust=False).mean()
        df["MACD"]     = ema12 - ema26
        df["Signal"]   = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_H"]   = df["MACD"] - df["Signal"]
        df["SMA20"]    = df["Close"].rolling(20).mean()
        df["SMA50"]    = df["Close"].rolling(50).mean()

        def _senal(row):
            if pd.isna(row["RSI"]) or pd.isna(row["SMA20"]) or pd.isna(row["SMA50"]):
                return "MANTENER"
            alc = baj = 0
            if row["RSI"] < 30: alc += 1
            elif row["RSI"] > 70: baj += 1
            if row["MACD_H"] > 0: alc += 1
            elif row["MACD_H"] < 0: baj += 1
            if row["SMA20"] > row["SMA50"]: alc += 1
            elif row["SMA20"] < row["SMA50"]: baj += 1
            return "COMPRAR" if alc > baj else ("VENDER" if baj > alc else "MANTENER")

        df["Senal"] = df.apply(_senal, axis=1)

        capital = 10_000.0
        posicion = 0.0
        ops: list[dict] = []
        hist: list[dict] = []

        for i, (fecha, row) in enumerate(df.iterrows()):
            precio = row["Close"]
            if row["Senal"] == "COMPRAR" and posicion == 0:
                posicion = capital / precio
                capital = 0.0
                ops.append({"fecha": fecha.strftime("%Y-%m-%d"), "tipo": "COMPRA", "precio": float(precio)})
            elif row["Senal"] == "VENDER" and posicion > 0:
                capital = posicion * precio
                ops.append({"fecha": fecha.strftime("%Y-%m-%d"), "tipo": "VENTA",
                             "precio": float(precio), "ganancia": float(capital - 10_000)})
                posicion = 0.0
            hist.append({"fecha": fecha.strftime("%Y-%m-%d"),
                         "capital": float(posicion * precio if posicion > 0 else capital)})

        if posicion > 0:
            capital = posicion * float(df["Close"].iloc[-1])

        caps = [h["capital"] for h in hist]
        ret_pso = (caps[-1] - 10_000) / 10_000 * 100
        rets_d  = pd.Series(caps).pct_change().dropna()
        sharpe  = float((rets_d.mean() / rets_d.std()) * (252 ** 0.5)) if rets_d.std() != 0 else 0.0
        cummax  = pd.Series(caps).cummax()
        mdd     = float(((pd.Series(caps) - cummax) / cummax).min() * 100)
        cerradas = [o for o in ops if "ganancia" in o]
        win_rate = len([o for o in cerradas if o["ganancia"] > 0]) / len(cerradas) * 100 if cerradas else 0.0

        pi = float(df["Close"].iloc[0])
        pf = float(df["Close"].iloc[-1])
        ret_bh = (pf - pi) / pi * 100
        hist_bh = [{"fecha": df.index[i].strftime("%Y-%m-%d"),
                    "capital": float(10_000 * df["Close"].iloc[i] / pi)}
                   for i in range(len(df))]

        return {
            "ticker": ticker,
            "periodo": {"inicio": df.index[0].strftime("%Y-%m-%d"), "fin": df.index[-1].strftime("%Y-%m-%d"), "dias": len(df)},
            "estrategia_pso": {
                "capital_final": caps[-1], "retorno_total": ret_pso,
                "sharpe_ratio": sharpe, "max_drawdown": mdd,
                "win_rate": win_rate, "num_operaciones": len(cerradas),
                "historial_capital": hist,
            },
            "buy_hold": {"capital_final": 10_000 * (1 + ret_bh / 100), "retorno_total": ret_bh, "historial_capital": hist_bh},
            "comparacion": {"diferencia": ret_pso - ret_bh, "ganador": "PSO" if caps[-1] > 10_000 * (1 + ret_bh / 100) else "Buy & Hold"},
            "operaciones": ops,
        }
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS UI
# ─────────────────────────────────────────────────────────────────────────────
def _signal_css(senal: str) -> str:
    s = str(senal).upper()
    return "buy" if s == "COMPRAR" else ("sell" if s == "VENDER" else "hold")


def _pct(v) -> int:
    try: return int(round(float(v) * 100))
    except: return 0


def _delta_color(v) -> str:
    try: return "c-d-up" if float(v) >= 0 else "c-d-dn"
    except: return "c-d-eq"


def _fmt_precio(v, moneda="S/.") -> str:
    if v is None: return "—"
    return f"{moneda} {v:,.4f}" if float(v) < 10 else f"{moneda} {v:,.2f}"


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## Dashboard BVL")
    st.markdown("Análisis multiagente del sector minero peruano")
    st.divider()

    ticker_label = st.selectbox(
        "Empresa / Ticker",
        list(TICKERS_BVL.keys()),
        index=0,
    )
    ticker = TICKERS_BVL[ticker_label]

    # Precio en tiempo real
    with st.spinner(""):
        rt = _fetch_bvl_precio_rt(ticker)

    if rt and rt.get("precio"):
        var = rt.get("variacion_pct", 0) or 0
        var_cls = "up" if var >= 0 else "down"
        var_str = f"{'▲' if var >= 0 else '▼'} {var:+.2f}%"
        vol_str = f"Vol: {rt['volumen']:,}" if rt.get("volumen") else ""
        moneda  = rt.get("moneda", "S/.")
        precio_fmt = _fmt_precio(rt["precio"], moneda)
        st.markdown(f"""
        <div class="rt-price-box">
            <div class="rt-ticker">{ticker} · Tiempo Real</div>
            <div class="rt-val">{precio_fmt}</div>
            <div class="rt-change {var_cls}">{var_str}</div>
            <div class="rt-vol">{vol_str}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.caption(f"Precio no disponible para {ticker}")

    st.divider()
    if st.button("Ejecutar análisis completo", type="primary", use_container_width=True):
        with st.spinner("Cargando histórico..."):
            _fetch_historico.clear()
            hist_pre = _fetch_historico(ticker)
        with st.spinner("Ejecutando agentes IA en LangFlow..."):
            try:
                result = ejecutar_langflow(ticker)
                st.session_state["data"]   = result
                st.session_state["ticker"] = ticker
                st.success("Análisis completado")
            except Exception as e:
                st.error("Error ejecutando LangFlow")
                st.exception(e)

    st.caption(f"Agentes: Técnico · Commodities · Sentimiento · Riesgo · PSO")


# ─────────────────────────────────────────────────────────────────────────────
# TABS PRINCIPALES
# ─────────────────────────────────────────────────────────────────────────────
tab_analisis, tab_comm, tab_noticias, tab_bt = st.tabs([
    "📊 Análisis",
    "🥇 Commodities",
    "📰 Noticias",
    "📈 Backtesting",
])


# ═══════════════════════════════════════════════════════
# TAB 1 — ANÁLISIS
# ═══════════════════════════════════════════════════════
with tab_analisis:
    data = st.session_state.get("data")
    ticker_data = st.session_state.get("ticker", ticker)

    if not data:
        st.markdown("### Bienvenido al Dashboard BVL")
        c1, c2, c3 = st.columns(3)
        c1.info("**1. Selecciona** una empresa en el panel izquierdo")
        c2.info("**2. Presiona** 'Ejecutar análisis completo'")
        c3.info("**3. Los agentes IA** analizarán precio, commodities, noticias y riesgo")
        st.markdown("---")
        st.markdown("**Empresas disponibles:** " + ", ".join(TICKERS_BVL.values()))
    else:
        senal_final    = data.get("senal_final", "MANTENER")
        score_final    = float(data.get("score_final", 0))
        confianza_final = float(data.get("confianza_final", 0))
        pesos          = data.get("pesos_utilizados", {})
        detalle        = data.get("detalle_agentes", {})
        senales_ag     = data.get("senales_agentes", {})
        confianzas_ag  = data.get("confianzas_agentes", {})
        factores       = data.get("factores_clave", [])
        limitaciones   = data.get("limitaciones", [])
        nivel_conf     = data.get("dashboard", {}).get("nivel_confianza", "—")

        # ── Fila 1: Signal + métricas ─────────────────────────────────────────
        col_sig, col_mets = st.columns([1, 2])

        with col_sig:
            sc = _signal_css(senal_final)
            rt_actual = _fetch_bvl_precio_rt(ticker_data)
            precio_str = ""
            if rt_actual and rt_actual.get("precio"):
                var = rt_actual.get("variacion_pct", 0) or 0
                precio_str = f"{_fmt_precio(rt_actual['precio'], rt_actual.get('moneda','S/.'))}  {'▲' if var >= 0 else '▼'} {var:+.2f}%"
            st.markdown(f"""
            <div class="signal-banner {sc}">
                <div class="sig-label">Señal consolidada · {ticker_data}</div>
                <div class="sig-main">{senal_final}</div>
                <div class="sig-sub">Score PSO: {score_final:.4f} · Confianza: {_pct(confianza_final)}% ({nivel_conf})</div>
                {'<div class="sig-sub" style="margin-top:6px;font-size:14px;">'+precio_str+'</div>' if precio_str else ''}
            </div>
            """, unsafe_allow_html=True)

        with col_mets:
            ag_names = {"tecnico": "Técnico", "commodities": "Commodities", "sentimiento": "Sentimiento", "riesgo": "Riesgo"}
            for key, name in ag_names.items():
                senal  = senales_ag.get(key, "MANTENER")
                conf   = _pct(confianzas_ag.get(key, 0))
                sc_ag  = _signal_css(senal)
                resumen = detalle.get(key, {}).get("resumen", "")
                resumen_html = (f'<div class="ag-desc">{resumen[:160]}</div>' if resumen else "")
                st.markdown(f"""
                <div class="agent-card">
                    <div class="ag-name">{name}</div>
                    <div class="ag-signal {sc_ag}">{senal}</div>
                    <div class="ag-conf">Confianza: {conf}%</div>
                    <div class="prog-wrap"><div class="prog-fill {sc_ag}" style="width:{max(conf,2)}%;"></div></div>
                    {resumen_html}
                </div>
                """, unsafe_allow_html=True)

        # ── Fila 2: Gráfico técnico ────────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### Análisis Técnico Visual")

        with st.spinner("Cargando datos históricos..."):
            historico = _fetch_historico(ticker_data)

        if historico and len(historico) >= 10:
            df_h = pd.DataFrame(historico)
            # Detectar iliquidez: si >70% de los precios son iguales, el gráfico no aporta
            if df_h["close"].nunique() <= max(3, len(df_h) * 0.3):
                st.warning(
                    f"⚠️ **{ticker_data} es un activo de muy baja liquidez** — "
                    "los precios históricos no varían significativamente. "
                    "Los indicadores técnicos (RSI, MACD, SMA) no son fiables para este ticker."
                )
            st.plotly_chart(_grafico_tecnico(historico, ticker_data), use_container_width=True)
        else:
            st.warning("Sin datos históricos suficientes para graficar.")

        # ── Fila 3: Factores + Pesos PSO ─────────────────────────────────────
        st.markdown("---")
        col_fact, col_pesos = st.columns([3, 2])

        with col_fact:
            st.markdown("#### Por qué esta señal")
            if factores:
                items_html = "".join(f"<li>{f}</li>" for f in factores)
                st.markdown(f'<div class="reason-card"><ul style="padding-left:18px;margin:0">{items_html}</ul></div>',
                            unsafe_allow_html=True)
            else:
                st.info("Sin factores clave disponibles.")

        with col_pesos:
            st.markdown("#### Pesos PSO")
            peso_labels = {"tecnico": "Técnico", "commodities": "Commodities",
                           "sentimiento": "Sentimiento", "riesgo": "Riesgo"}
            for key, name in peso_labels.items():
                val = _pct(pesos.get(key, 0))
                st.markdown(f"""
                <div class="peso-bar">
                    <span class="p-name">{name}</span>
                    <span class="p-pct">{val}%</span>
                    <div style="clear:both"></div>
                    <div class="prog-wrap" style="margin-top:8px;">
                        <div class="prog-fill buy" style="width:{max(val,2)}%;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # ── Fila 4: Limitaciones ─────────────────────────────────────────────
        if limitaciones:
            st.markdown("---")
            with st.expander("Limitaciones del análisis"):
                for lim in limitaciones:
                    st.warning(lim)

        with st.expander("Ver JSON completo del análisis"):
            st.json(data)


# ═══════════════════════════════════════════════════════
# TAB 2 — COMMODITIES
# ═══════════════════════════════════════════════════════
with tab_comm:
    st.markdown("#### Precios en Tiempo Real — Metales Industriales")
    st.caption("Fuente primaria: yfinance (mercado global) · Actualización cada 5 min")

    with st.spinner("Obteniendo precios de commodities..."):
        comm = _fetch_commodities()

    if "error" in comm:
        st.error(f"Error al obtener datos de commodities: {comm['error']}")
        st.info("Verifica que `yfinance` esté instalado en el contenedor.")
    else:
        c1, c2, c3 = st.columns(3)
        metal_cols  = [c1, c2, c3]
        metal_names = ["Oro", "Plata", "Cobre"]
        metal_colors = ["#fbbf24", "#94a3b8", "#f97316"]
        metal_rel   = {
            "Oro":   "Relevante para **BVN** (Buenaventura), **PODERC1** (Poderosa)",
            "Plata": "Relevante para **MINSURI1** (Minsur), **VOLCABC1** (Volcan), **BROCALC1** (El Brocal)",
            "Cobre": "Relevante para **SCCO** (Southern Copper), **CVERDEC1** (Cerro Verde), **NEXAPEC1** (Nexa)",
        }

        for col, nombre, color in zip(metal_cols, metal_names, metal_colors):
            with col:
                d = comm.get(nombre, {})
                if "error" in d:
                    st.error(f"{nombre}: {d['error']}")
                    continue

                precio = d["precio"]
                cam    = d["cambio_dia"]
                tend   = d["tend_5d"]
                unit   = d["unit"]
                label  = d["label"]
                src    = d.get("fuente", "?")

                cam_cls  = "c-d-up" if cam  >= 0 else "c-d-dn"
                tend_cls = "c-d-up" if tend >= 0 else "c-d-dn"
                cam_sym  = "▲" if cam  >= 0 else "▼"
                ten_sym  = "▲" if tend >= 0 else "▼"

                st.markdown(f"""
                <div class="comm-card">
                    <div class="c-name">{nombre}</div>
                    <div class="c-price">${precio:,.2f}</div>
                    <div class="c-label">USD/{unit} · {label}</div>
                    <div style="margin-top:8px;">
                        <span class="{cam_cls}">{cam_sym} {cam:+.2f}% hoy</span>
                        &nbsp;&nbsp;
                        <span class="{tend_cls}" style="font-size:12px;">{ten_sym} {tend:+.2f}% (5d)</span>
                    </div>
                    <div class="c-src">Fuente: {src}</div>
                </div>
                """, unsafe_allow_html=True)

                if d.get("closes") and len(d["closes"]) >= 4:
                    st.plotly_chart(
                        _grafico_sparkline(d["closes"], d["dates"], color),
                        use_container_width=True,
                    )

                st.caption(metal_rel[nombre])

        st.markdown("---")
        st.markdown("#### Relevancia por empresa BVL")
        rel_data = {
            "Empresa":   ["BVN (Buenaventura)", "SCCO (Southern Copper)", "CVERDEC1 (Cerro Verde)",
                          "MINSURI1 (Minsur)", "VOLCABC1 (Volcan)", "BROCALC1 (El Brocal)", "NEXAPEC1 (Nexa)"],
            "Commodity principal": ["Oro", "Cobre", "Cobre", "Estaño/Plata", "Zinc/Plata", "Polimetálico", "Zinc/Plata"],
            "Correlación esperada": ["Alta con Oro", "Alta con Cobre", "Alta con Cobre",
                                     "Media con Plata", "Media con Plata", "Media mixta", "Media con Zinc"],
        }
        st.dataframe(pd.DataFrame(rel_data), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════
# TAB 3 — NOTICIAS
# ═══════════════════════════════════════════════════════
with tab_noticias:
    st.markdown(f"#### Noticias para **{ticker}**")
    st.caption("Alpha Vantage NEWS_SENTIMENT (con scores) + Google News RSS (español)")

    with st.spinner("Buscando noticias..."):
        noticias = _fetch_noticias(ticker)

    av_arts  = noticias.get("av", [])
    rss_arts = noticias.get("rss", [])

    # ── Sentimiento resumido ──────────────────────────────────────────────────
    if av_arts:
        alc = len([a for a in av_arts if a["score"] > 0.15])
        baj = len([a for a in av_arts if a["score"] < -0.15])
        neu = len(av_arts) - alc - baj
        total = len(av_arts)
        tend_color = "#22c55e" if alc > baj else ("#ef4444" if baj > alc else "#eab308")
        tend_label = "ALCISTA" if alc > baj else ("BAJISTA" if baj > alc else "NEUTRAL")

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Noticias analizadas", total)
        s2.metric("Alcistas", alc, delta=None)
        s3.metric("Bajistas", baj, delta=None)
        s4.metric("Tendencia", tend_label)

        st.markdown("---")

    # ── Columnas: AV | RSS ────────────────────────────────────────────────────
    col_av, col_rss = st.columns(2)

    with col_av:
        st.markdown("##### Alpha Vantage — Análisis financiero")
        if not av_arts:
            st.info("Sin noticias de Alpha Vantage para este ticker. "
                    "Puede ser por límite de consultas (25/día en plan gratuito).")
        for art in av_arts[:8]:
            score = art["score"]
            badge_cls = "pos" if score > 0.15 else ("neg" if score < -0.15 else "neu")
            score_str = f"{score:+.3f}"
            url_html  = f'<a href="{art["url"]}" target="_blank" style="color:#60a5fa;font-size:11px;">Ver artículo ↗</a>' if art.get("url") else ""
            st.markdown(f"""
            <div class="news-card">
                <div class="n-title">
                    {art['titulo']}
                    <span class="n-badge {badge_cls}">{art['label']} {score_str}</span>
                </div>
                <div class="n-meta">{art['fecha']} · {art['fuente']}</div>
                <div class="n-desc">{art['resumen']}</div>
                <div style="margin-top:6px;">{url_html}</div>
            </div>
            """, unsafe_allow_html=True)

    with col_rss:
        st.markdown("##### Google News — Noticias en español")
        if not rss_arts:
            st.info("Sin resultados en Google News RSS. "
                    "Verifica que `feedparser` esté instalado en el contenedor.")
        for art in rss_arts[:8]:
            url_html = (f'<a href="{art["link"]}" target="_blank" style="color:#60a5fa;font-size:11px;">Leer noticia ↗</a>'
                        if art.get("link") else "")
            st.markdown(f"""
            <div class="news-card">
                <div class="n-title">{art['titulo']}</div>
                <div class="n-meta">{art['publicado']}</div>
                <div class="n-desc">{art['resumen']}</div>
                <div style="margin-top:6px;">{url_html}</div>
            </div>
            """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════
# TAB 4 — BACKTESTING
# ═══════════════════════════════════════════════════════
with tab_bt:
    st.markdown("#### Backtesting — Validación Histórica de Estrategia")

    bc1, bc2, bc3 = st.columns([1, 1, 2])
    with bc1:
        periodo = st.selectbox("Período", ["3 meses (90 días)", "6 meses (180 días)", "1 año (365 días)"], key="bt_periodo")
    with bc2:
        st.markdown("<br>", unsafe_allow_html=True)
        run_bt = st.button("Ejecutar Backtest", type="primary", key="btn_bt")
    with bc3:
        st.caption("Compara la estrategia PSO (basada en RSI + MACD + SMA) contra Buy & Hold simple.")

    dias_map = {"3 meses (90 días)": 90, "6 meses (180 días)": 180, "1 año (365 días)": 365}
    dias = dias_map[periodo]

    if run_bt:
        with st.spinner(f"Ejecutando backtest de {dias} días para {ticker}..."):
            resultado = _ejecutar_backtest(ticker, dias)
        st.session_state["bt_data"]   = resultado
        st.session_state["bt_ticker"] = ticker

    bt = st.session_state.get("bt_data")
    if not bt:
        st.info("Selecciona un período y presiona 'Ejecutar Backtest'.")
    elif "error" in bt:
        st.error(f"Error: {bt['error']}")
    else:
        pso  = bt["estrategia_pso"]
        bh   = bt["buy_hold"]
        comp = bt["comparacion"]

        st.markdown(f"**{bt['ticker']}** · {bt['periodo']['inicio']} → {bt['periodo']['fin']} ({bt['periodo']['dias']} días)")
        st.markdown("---")

        # Métricas comparativas
        m1, m2, m3 = st.columns(3)
        ret_color_pso = "#22c55e" if pso["retorno_total"] >= 0 else "#ef4444"
        ret_color_bh  = "#22c55e" if bh["retorno_total"]  >= 0 else "#ef4444"
        ganador_color = "#22c55e" if comp["ganador"] == "PSO" else "#fbbf24"

        m1.markdown(f"""<div class="metric-card">
            <div class="label">Estrategia PSO</div>
            <div class="value" style="color:{ret_color_pso};">{pso['retorno_total']:.2f}%</div>
            <div class="sub">Capital final: ${pso['capital_final']:,.0f}</div>
        </div>""", unsafe_allow_html=True)

        m2.markdown(f"""<div class="metric-card">
            <div class="label">Buy & Hold</div>
            <div class="value" style="color:{ret_color_bh};">{bh['retorno_total']:.2f}%</div>
            <div class="sub">Capital final: ${bh['capital_final']:,.0f}</div>
        </div>""", unsafe_allow_html=True)

        m3.markdown(f"""<div class="metric-card">
            <div class="label">Ganador</div>
            <div class="value" style="color:{ganador_color};">{comp['ganador']}</div>
            <div class="sub">Diferencia: {comp['diferencia']:+.2f}%</div>
        </div>""", unsafe_allow_html=True)

        st.write("")
        st.plotly_chart(_grafico_backtest(bt), use_container_width=True)

        st.markdown("---")
        st.markdown("#### Métricas de Riesgo")
        r1, r2, r3, r4 = st.columns(4)
        r1.markdown(f"""<div class="metric-card">
            <div class="label">Sharpe Ratio</div>
            <div class="value">{pso['sharpe_ratio']:.2f}</div>
            <div class="sub">Anualizado</div>
        </div>""", unsafe_allow_html=True)
        r2.markdown(f"""<div class="metric-card">
            <div class="label">Max Drawdown</div>
            <div class="value" style="color:#ef4444;">{pso['max_drawdown']:.2f}%</div>
            <div class="sub">Pérdida máxima</div>
        </div>""", unsafe_allow_html=True)
        r3.markdown(f"""<div class="metric-card">
            <div class="label">Win Rate</div>
            <div class="value">{pso['win_rate']:.1f}%</div>
            <div class="sub">Operaciones ganadoras</div>
        </div>""", unsafe_allow_html=True)
        r4.markdown(f"""<div class="metric-card">
            <div class="label">Operaciones</div>
            <div class="value">{pso['num_operaciones']}</div>
            <div class="sub">Cerradas en el período</div>
        </div>""", unsafe_allow_html=True)

        if bt["operaciones"]:
            st.markdown("---")
            with st.expander("Historial de operaciones"):
                df_ops = pd.DataFrame(bt["operaciones"])
                st.dataframe(df_ops, use_container_width=True, hide_index=True)
