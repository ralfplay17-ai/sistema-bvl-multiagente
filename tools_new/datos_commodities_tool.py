from langflow.custom import Component
from langflow.io import SecretStrInput, Output
from langflow.field_typing import Tool
from langchain.tools import Tool as LangchainTool
import requests
import os


class DatosCommoditiesToolComponentV2(Component):
    display_name = "Datos Commodities Tool"
    description = "Precios, variacion diaria y tendencia 5d de oro, plata y cobre."
    icon = "trending-up"
    name = "DatosCommoditiesTool"

    inputs = [
        SecretStrInput(name="api_key", display_name="Twelve Data API Key", required=False),
        SecretStrInput(name="av_key",  display_name="Alpha Vantage API Key", value="TPTUYCIWJ2JYRVWQ"),
    ]
    outputs = [Output(display_name="Tool", name="tool_output", method="build_tool")]

    def build_tool(self) -> Tool:
        td_key = self.api_key or os.environ.get("TWELVE_DATA_KEY", "e81a8f3d635e4f8aac10cd2230d43e0c")
        av_key = self.av_key or os.environ.get("ALPHA_VANTAGE_KEY", "TPTUYCIWJ2JYRVWQ")

        def _formato_metal(nombre, simbolo, precio_hoy, precio_ayer, precio_5d, unidad="oz"):
            if None in (precio_hoy, precio_ayer):
                return "\n" + nombre + ": Sin datos suficientes"
            cambio_dia = (precio_hoy - precio_ayer) / precio_ayer * 100
            tend_5d = ((precio_hoy - precio_5d) / precio_5d * 100) if precio_5d else cambio_dia
            dir_dia = "sube" if cambio_dia > 0 else ("baja" if cambio_dia < 0 else "estable")
            dir_5d  = "positiva" if tend_5d > 0 else ("negativa" if tend_5d < 0 else "plana")
            return (
                "\n" + nombre + " (" + simbolo + "): $" + f"{precio_hoy:.2f}" + " USD/" + unidad
                + "\n  Cambio diario: " + f"{cambio_dia:+.2f}%" + " (" + dir_dia + ")"
                + "\n  Tendencia 5d:  " + f"{tend_5d:+.2f}%" + " (" + dir_5d + ")"
            )

        def _yfinance_metal(symbol):
            """Obtiene precio actual y serie reciente usando yfinance (sin API key)."""
            try:
                import yfinance as yf
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="10d")
                if hist.empty or len(hist) < 2:
                    return None
                closes = hist["Close"].dropna()
                if len(closes) < 2:
                    return None
                return {
                    "precio_hoy": float(closes.iloc[-1]),
                    "precio_ayer": float(closes.iloc[-2]),
                    "precio_5d": float(closes.iloc[-5]) if len(closes) >= 5 else float(closes.iloc[0]),
                }
            except Exception:
                return None

        def _twelve_data_metal(symbol, outputsize=6):
            """Fallback Twelve Data para oro y plata."""
            try:
                r = requests.get(
                    "https://api.twelvedata.com/time_series"
                    "?symbol=" + symbol + "&interval=1day&outputsize=" + str(outputsize) + "&apikey=" + td_key,
                    timeout=10,
                )
                values = r.json().get("values", [])
                if len(values) < 2:
                    return None
                return {
                    "precio_hoy": float(values[0]["close"]),
                    "precio_ayer": float(values[1]["close"]),
                    "precio_5d": float(values[min(4, len(values) - 1)]["close"]),
                }
            except Exception:
                return None

        def _alpha_vantage_cobre():
            """Fallback cobre mensual desde Alpha Vantage."""
            try:
                r = requests.get(
                    "https://www.alphavantage.co/query?function=COPPER&interval=monthly&apikey=" + av_key,
                    timeout=10,
                )
                d = r.json()
                if d.get("Information") or d.get("Note"):
                    return None, "Rate limit Alpha Vantage"
                data_pts = d.get("data", [])
                if len(data_pts) < 2:
                    return None, "Sin datos"
                precio_ton = float(data_pts[0]["value"])
                precio_ant = float(data_pts[1]["value"])
                precio_3m  = float(data_pts[2]["value"]) if len(data_pts) >= 3 else precio_ant
                return {
                    "precio_hoy": precio_ton / 2204.62,
                    "precio_ayer": precio_ant / 2204.62,
                    "precio_5d": precio_3m / 2204.62,
                    "fecha": data_pts[0]["date"],
                    "precio_ton": precio_ton,
                }, None
            except Exception as e:
                return None, str(e)

        def obtener_datos_commodities(input_text: str = "") -> str:
            resultado = ["=== PRECIOS COMMODITIES ==="]

            # ORO (GC=F): yfinance -> Twelve Data
            try:
                d = _yfinance_metal("GC=F")
                if d:
                    linea = _formato_metal("Oro", "XAU/USD", d["precio_hoy"], d["precio_ayer"], d["precio_5d"])
                    resultado.append(linea + " [yfinance]")
                else:
                    d = _twelve_data_metal("XAU/USD")
                    if d:
                        linea = _formato_metal("Oro", "XAU/USD", d["precio_hoy"], d["precio_ayer"], d["precio_5d"])
                        resultado.append(linea + " [Twelve Data]")
                    else:
                        resultado.append("\nOro: Sin datos disponibles")
            except Exception as e:
                resultado.append("\nOro: Error - " + str(e))

            # PLATA (SI=F): yfinance -> Twelve Data
            try:
                d = _yfinance_metal("SI=F")
                if d:
                    linea = _formato_metal("Plata", "XAG/USD", d["precio_hoy"], d["precio_ayer"], d["precio_5d"])
                    resultado.append(linea + " [yfinance]")
                else:
                    d = _twelve_data_metal("XAG/USD")
                    if d:
                        linea = _formato_metal("Plata", "XAG/USD", d["precio_hoy"], d["precio_ayer"], d["precio_5d"])
                        resultado.append(linea + " [Twelve Data]")
                    else:
                        resultado.append("\nPlata: Sin datos disponibles")
            except Exception as e:
                resultado.append("\nPlata: Error - " + str(e))

            # COBRE (HG=F): yfinance -> Alpha Vantage
            try:
                d = _yfinance_metal("HG=F")
                if d:
                    # HG=F cotiza en USD/lb directamente
                    linea = _formato_metal("Cobre", "HG=F", d["precio_hoy"], d["precio_ayer"], d["precio_5d"], unidad="lb")
                    resultado.append(linea + " [yfinance]")
                else:
                    d_av, err = _alpha_vantage_cobre()
                    if d_av:
                        linea = _formato_metal("Cobre", "LME", d_av["precio_hoy"], d_av["precio_ayer"], d_av["precio_5d"], unidad="lb")
                        resultado.append(linea + " [Alpha Vantage - " + d_av.get("fecha", "") + "]")
                    else:
                        resultado.append("\nCobre: " + (err or "Sin datos"))
            except Exception as e:
                resultado.append("\nCobre: Error - " + str(e))

            resultado.append(
                "\n\nContexto BVL:"
                "\n- BVN (Buenaventura): commodity principal = Oro"
                "\n- SCCO (Southern Copper): commodity principal = Cobre"
                "\n- Mineras polimetalicas (Minsur, Volcan, El Brocal): Plata y Zinc tambien relevantes"
            )
            return "\n".join(resultado)

        return LangchainTool(
            name="obtener_datos_commodities",
            description=(
                "Obtiene precio actual, variacion diaria y tendencia de commodities: "
                "Oro (XAU/USD via GC=F), Plata (XAG/USD via SI=F) y Cobre (HG=F). "
                "Relevante para BVN (oro), SCCO (cobre) y mineras polimetalicas (plata). "
                "Input: cualquier texto."
            ),
            func=obtener_datos_commodities,
        )
