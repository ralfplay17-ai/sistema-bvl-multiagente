from langflow.custom import Component
from langflow.io import StrInput, SecretStrInput, Output
from langflow.field_typing import Tool
from langchain.tools import Tool as LangchainTool
import requests
import pandas as pd
import json
import os
from datetime import date, timedelta

TICKER_MAP = {
    "BVN": "BUENAVC1", "BUENAVC1": "BUENAVC1", "BUENAVI1": "BUENAVI1",
    "BUENAVENTURA": "BUENAVC1",
    "SCCO": "SCCO", "SOUTHERN": "SCCO", "SOUTHERNCOPPER": "SCCO",
    "SPCCPI1": "SPCCPI1", "SPCCPI2": "SPCCPI2",
    "CVERDEC1": "CVERDEC1", "CERROVERDE": "CVERDEC1", "CERRO VERDE": "CVERDEC1",
    "MINSURI1": "MINSURI1", "MINSUR": "MINSURI1",
    "VOLCABC1": "VOLCABC1", "VOLCAAC1": "VOLCAAC1", "VOLCAN": "VOLCABC1",
    "ATACOBC1": "ATACOBC1", "ATACOAC1": "ATACOAC1", "ATACOCHA": "ATACOBC1",
    "NEXAPEC1": "NEXAPEC1", "NEXAPEI1": "NEXAPEI1", "NEXA": "NEXAPEC1", "MILPO": "NEXAPEC1",
    "BROCALC1": "BROCALC1", "BROCALI1": "BROCALI1", "BROCAL": "BROCALC1",
    "MINCORC1": "MINCORC1", "MINCORI1": "MINCORI1", "CORONA": "MINCORC1",
    "SHPC1": "SHPC1", "SHOUGANG": "SHPC1",
    "PODERC1": "PODERC1", "PODEROSA": "PODERC1",
    "PERUBAI1": "PERUBAI1", "PERUBAR": "PERUBAI1",
    "LUISAI1": "LUISAI1", "LUISA": "LUISAI1", "SANTA LUISA": "LUISAI1",
    "MOROCOC1": "MOROCOC1", "MOROCOI1": "MOROCOI1", "MOROCOCHA": "MOROCOC1",
    "FOSPACC1": "FOSPACC1", "FOSPAC": "FOSPACC1",
    "ANDEXAC1": "ANDEXAC1", "ANDEXBC1": "ANDEXBC1",
    "CASTROC1": "CASTROC1", "CASTROI1": "CASTROI1", "CASTROVIRREYNA": "CASTROC1",
    "RIO": "RIO", "RIO2": "RIO",
    "PML": "PML", "PANORO": "PML",
    "PPX": "PPX",
    "REG": "REG", "REGULUS": "REG",
    "MIRL": "MIRL",
    "AGMR": "AGMR", "SILVER MOUNTAIN": "AGMR",
    "ECU": "ECU", "ELEMENT 29": "ECU",
    "CDPR": "CDPR", "CERRO DE PASCO": "CDPR",
}

# Mapa nemónico BVL → ticker internacional para Alpha Vantage
AV_TICKER_MAP = {
    "BUENAVC1": "BVN", "BUENAVI1": "BVN",
    "SCCO": "SCCO", "SPCCPI1": "SCCO", "SPCCPI2": "SCCO",
    "CVERDEC1": "CVERDEC1",
    "MINSURI1": "MINSURI1",
}

BVL_API_BASE = "https://dataondemand.bvl.com.pe/v1"
BVL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.bvl.com.pe/",
    "Origin": "https://www.bvl.com.pe",
}


def _f(v):
    try:
        return float(v) if v not in (None, "", "-", "0") else None
    except (ValueError, TypeError):
        return None


def _i(v):
    try:
        return int(float(v)) if v not in (None, "", "-") else None
    except (ValueError, TypeError):
        return None


def _find_csv(name):
    extra = os.environ.get("BVL_DATA_DIR", "")
    candidates = [
        f"/app/data_bvl/data/{name}",
        os.path.join(extra, name) if extra else "",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


class DatosBVLToolComponent(Component):
    display_name = "Datos BVL Tool"
    description = "Indicadores tecnicos (RSI, MACD, SMA) para cualquier minera del sector BVL"
    icon = "database"
    name = "DatosBVLTool"

    inputs = [
        SecretStrInput(name="api_key", display_name="Alpha Vantage API Key", required=False),
        StrInput(name="default_tickers", display_name="Tickers por defecto", value="BVN,SCCO"),
    ]
    outputs = [Output(display_name="Tool", name="tool_output", method="build_tool")]

    def build_tool(self) -> Tool:
        api_key = self.api_key or os.environ.get("ALPHA_VANTAGE_KEY", "")

        def _detectar_nemonico(text):
            text_upper = text.upper().strip()
            for key in sorted(TICKER_MAP.keys(), key=len, reverse=True):
                if key in text_upper:
                    return TICKER_MAP[key]
            return "BUENAVC1"

        def calcular_rsi(precios, periodo=14):
            # Eliminar días sin negociación (precio 0 o NaN)
            precios = precios[precios > 0].dropna()
            if len(precios) < periodo + 2:
                return pd.Series([50.0] * len(precios), index=precios.index)
            delta = precios.diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            # Wilder smoothing (EMA alpha=1/periodo) — método estándar RSI
            avg_gain = gain.ewm(alpha=1.0 / periodo, min_periods=periodo, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1.0 / periodo, min_periods=periodo, adjust=False).mean()
            rs = avg_gain / avg_loss.replace(0, float("inf"))
            return (100 - (100 / (1 + rs))).clip(0, 100)

        def _cargar_precio_actual(nemonico):
            """Precio/variacion/volumen en tiempo real desde BVL API /issuers/{code}/value."""
            try:
                r_issuers = requests.get(
                    BVL_API_BASE + "/issuers",
                    headers=BVL_HEADERS,
                    timeout=15,
                )
                r_issuers.raise_for_status()
                company_code = None
                for issuer in r_issuers.json():
                    if issuer.get("tkrCode") == nemonico and issuer.get("active", True):
                        company_code = issuer.get("companyCode")
                        break
                if not company_code:
                    return None

                r_val = requests.get(
                    BVL_API_BASE + "/issuers/" + company_code + "/value",
                    headers=BVL_HEADERS,
                    timeout=15,
                )
                r_val.raise_for_status()

                for emisor in r_val.json():
                    for lv in emisor.get("listLastValue", []):
                        if lv.get("tkrCode") == nemonico:
                            return {
                                "precio": _f(lv.get("close") or lv.get("last")),
                                "variacion_pct": _f(lv.get("var")),
                                "volumen": _i(lv.get("quantityNegotiated")),
                                "monto": _f(lv.get("amount")),
                                "moneda": (lv.get("coin") or "S/.").strip(),
                            }
            except Exception:
                return None
            return None

        def _calcular_indicadores(close, nemonico, ticker_input, fuente, precio_rt=None):
            rsi = calcular_rsi(close)
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            signal = macd.ewm(span=9, adjust=False).mean()
            hist_v = macd - signal
            sma20 = close.rolling(window=20).mean()
            sma50 = close.rolling(window=50).mean() if len(close) >= 50 else None

            if precio_rt and precio_rt.get("precio"):
                precio_actual = precio_rt["precio"]
                variacion_pct = precio_rt.get("variacion_pct") or 0.0
                volumen = precio_rt.get("volumen")
                moneda = precio_rt.get("moneda", "S/.")
                fuente_precio = "BVL Tiempo Real"
            else:
                precio_actual = float(close.iloc[-1])
                precio_ant = float(close.iloc[-2]) if len(close) > 1 else precio_actual
                variacion_pct = (precio_actual - precio_ant) / precio_ant * 100 if precio_ant else 0
                volumen = None
                moneda = "S/."
                fuente_precio = fuente

            cambio_5d = None
            if len(close) >= 6:
                p5 = float(close.iloc[-6])
                if p5:
                    cambio_5d = round((precio_actual - p5) / p5 * 100, 2)

            rsi_v = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
            rsi_zona = "sobrecompra" if rsi_v >= 70 else ("sobreventa" if rsi_v <= 30 else "neutral")
            sma20_v = float(sma20.iloc[-1]) if not pd.isna(sma20.iloc[-1]) else None
            sma50_v = float(sma50.iloc[-1]) if sma50 is not None and not pd.isna(sma50.iloc[-1]) else None
            tendencia = ("alcista" if sma20_v and sma50_v and sma20_v > sma50_v else "bajista") if sma50_v else "indeterminada"
            macd_v = float(macd.iloc[-1]) if not pd.isna(macd.iloc[-1]) else 0.0
            signal_v = float(signal.iloc[-1]) if not pd.isna(signal.iloc[-1]) else 0.0
            hist_vv = float(hist_v.iloc[-1]) if not pd.isna(hist_v.iloc[-1]) else 0.0

            return {
                "ticker": ticker_input.upper(),
                "nemonico_bvl": nemonico,
                "precio_actual": round(precio_actual, 4),
                "variacion_pct": round(variacion_pct, 2),
                "volumen": volumen,
                "moneda": moneda,
                "cambio_5d_pct": cambio_5d,
                "RSI": round(rsi_v, 2),
                "RSI_zona": rsi_zona,
                "MACD": round(macd_v, 4),
                "MACD_signal": round(signal_v, 4),
                "MACD_hist": round(hist_vv, 4),
                "SMA20": round(sma20_v, 2) if sma20_v else None,
                "SMA50": round(sma50_v, 2) if sma50_v else None,
                "tendencia": tendencia,
                "fuente_indicadores": fuente,
                "fuente_precio": fuente_precio,
            }

        def _cargar_csv(nemonico):
            csv_path = _find_csv("bvl_historico.csv")
            if not csv_path:
                return None
            df = pd.read_csv(csv_path, encoding="utf-8-sig")
            df = df[df["nemonico"] == nemonico].copy()
            if df.empty:
                return None
            df["fecha"] = pd.to_datetime(df["fecha"])
            df["cierre"] = pd.to_numeric(df["cierre"], errors="coerce")
            df = df.sort_values("fecha").tail(60).dropna(subset=["cierre"]).reset_index(drop=True)
            if len(df) < 20:
                return None
            return pd.Series(df["cierre"].values, index=pd.to_datetime(df["fecha"].values))

        def _cargar_bvl_api(nemonico):
            try:
                fecha_fin = date.today()
                fecha_ini = fecha_fin - timedelta(days=120)
                r = requests.get(
                    BVL_API_BASE + "/stock-quote/share-value",
                    headers=BVL_HEADERS,
                    params={"name": nemonico, "startDate": fecha_ini.isoformat(), "endDate": fecha_fin.isoformat()},
                    timeout=15,
                )
                r.raise_for_status()
                data = r.json()
                values = data.get("values", [])
                if len(values) < 20:
                    return None
                serie = pd.Series(
                    [float(v[1]) for v in values],
                    index=pd.to_datetime([v[0] for v in values])
                ).sort_index()
                # Eliminar días sin negociación (precio 0 o NaN)
                serie = serie[serie > 0].dropna()
                if len(serie) < 20:
                    return None
                return serie
            except Exception:
                return None

        def _cargar_alpha_vantage(ticker_input, nemonico=""):
            if not api_key:
                return None
            # Preferir ticker internacional si el nemonico BVL no es reconocido en AV
            av_ticker = AV_TICKER_MAP.get(nemonico, ticker_input)
            try:
                r = requests.get(
                    "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY"
                    "&symbol=" + av_ticker + "&outputsize=compact&apikey=" + api_key,
                    timeout=20,
                )
                data = r.json()
                if "Time Series (Daily)" not in data:
                    return None
                ts = data["Time Series (Daily)"]
                df = pd.DataFrame.from_dict(ts, orient="index").astype(float)
                df.columns = ["Open", "High", "Low", "Close", "Volume"]
                df.index = pd.to_datetime(df.index)
                return df.sort_index().tail(60)["Close"]
            except Exception:
                return None

        def obtener_datos(input_text=""):
            nemonico = _detectar_nemonico(input_text)
            ticker_input = input_text.strip() or nemonico

            # Fuente 0: precio/variacion/volumen en tiempo real desde BVL API
            precio_rt = _cargar_precio_actual(nemonico)

            # Fuentes historicas para indicadores tecnicos (RSI/MACD/SMA)
            close = _cargar_csv(nemonico)
            if close is not None and len(close) >= 20:
                return json.dumps(_calcular_indicadores(close, nemonico, ticker_input, "BVL CSV", precio_rt), ensure_ascii=False)

            close = _cargar_bvl_api(nemonico)
            if close is not None and len(close) >= 20:
                return json.dumps(_calcular_indicadores(close, nemonico, ticker_input, "BVL API", precio_rt), ensure_ascii=False)

            close = _cargar_alpha_vantage(ticker_input, nemonico)
            if close is not None and len(close) >= 20:
                return json.dumps(_calcular_indicadores(close, nemonico, ticker_input, "Alpha Vantage", precio_rt), ensure_ascii=False)

            # Solo precio real-time sin historial suficiente para indicadores
            if precio_rt and precio_rt.get("precio"):
                return json.dumps({
                    "ticker": ticker_input.upper(),
                    "nemonico_bvl": nemonico,
                    "precio_actual": round(precio_rt["precio"], 4),
                    "variacion_pct": round(precio_rt.get("variacion_pct") or 0.0, 2),
                    "volumen": precio_rt.get("volumen"),
                    "moneda": precio_rt.get("moneda", "S/."),
                    "fuente_precio": "BVL Tiempo Real",
                    "nota": "Sin historial suficiente para RSI/MACD/SMA",
                }, ensure_ascii=False)

            return json.dumps({"error": "Sin datos para " + nemonico + ". Ticker no encontrado en BVL ni Alpha Vantage."})

        return LangchainTool(
            name="obtener_datos_bvl",
            description=(
                "Obtiene precio actual, cambio %, RSI, MACD, SMA20, SMA50 y tendencia "
                "para CUALQUIER accion minera de la BVL. Soporta todos los tickers: "
                "BVN/BUENAVC1, SCCO, CVERDEC1, MINSURI1, VOLCABC1, ATACOBC1, "
                "NEXAPEC1, BROCALC1, SHPC1, PODERC1, MOROCOC1, LUISAI1 y mas. "
                "Input: ticker o nombre de empresa. SIEMPRE llama antes de analizar."
            ),
            func=obtener_datos,
        )
