from langflow.custom import Component
from langflow.io import Output
from langflow.field_typing import Tool
from langchain.tools import Tool as LangchainTool
import requests
import json
from datetime import datetime, timedelta


class DatosBCRPToolComponent(Component):
    display_name = "Datos BCRP Tool"
    description = "Indicadores macroeconómicos del BCRP: tipo de cambio y contexto monetario."
    icon = "landmark"
    name = "DatosBCRPTool"

    inputs = []
    outputs = [Output(display_name="Tool", name="tool_output", method="build_tool")]

    def build_tool(self) -> Tool:

        BVL_HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.bvl.com.pe/",
            "Origin": "https://www.bvl.com.pe",
        }

        def _bvl_tipo_cambio():
            """Tipo de cambio desde la API BVL — accesible globalmente."""
            r = requests.get(
                "https://dataondemand.bvl.com.pe/v1/exchange-rate",
                headers=BVL_HEADERS,
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            tc = float(data.get("exchangeRate", 0))
            fecha = data.get("date", "")
            return tc, fecha

        def _bcrp_fetch(codigo, fecha_inicio, fecha_fin):
            """Llama a la API BCRP — puede estar bloqueada desde IPs fuera de Perú."""
            url = (
                "https://estadisticas.bcrp.gob.pe/estadisticas/series/api/"
                + codigo + "/json/" + fecha_inicio + "/" + fecha_fin
            )
            try:
                r = requests.get(url, timeout=10)
                if b"Acceso denegado" in r.content or b"No autorizado" in r.content:
                    return None
                try:
                    data = json.loads(r.content.decode("utf-8-sig"))
                except Exception:
                    data = r.json()
                periodos = data.get("periods", [])
                return periodos if periodos else None
            except Exception:
                return None

        def _valores_numericos(periodos):
            vals = []
            for p in periodos:
                try:
                    v = float(p["values"][0])
                    vals.append((p["name"], v))
                except Exception:
                    continue
            return vals

        def obtener_datos_bcrp(input_text: str = "") -> str:
            fecha_fin    = datetime.now().strftime("%Y-%m-%d")
            fecha_inicio = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            hoy = datetime.now().strftime("%d/%m/%Y")

            resultado = ["=== INDICADORES MACRO PERU (" + hoy + ") ==="]

            # ── Tipo de Cambio — BVL API (fuente primaria, siempre accesible) ──
            tc_bvl = None
            try:
                tc_bvl, fecha_tc = _bvl_tipo_cambio()
                resultado.append(
                    "\nTipo de cambio USD/PEN (BVL):"
                    "\n  Valor: " + f"{tc_bvl:.4f}" + " S/ por USD (" + fecha_tc + ")"
                )
            except Exception as e:
                resultado.append("\nTipo de cambio BVL: no disponible (" + str(e) + ")")

            # ── Tipo de Cambio — BCRP (compra/venta + volatilidad 30d) ───────
            tc_series = {
                "PD04640PD": "TC compra (S/ por USD)",
                "PD04638PD": "TC venta  (S/ por USD)",
            }
            tc_compra = None
            tc_venta  = None
            bcrp_ok   = False

            for codigo, descripcion in tc_series.items():
                periodos = _bcrp_fetch(codigo, fecha_inicio, fecha_fin)
                if not periodos:
                    continue
                vals = _valores_numericos(periodos)
                if not vals:
                    continue
                bcrp_ok = True
                ultimo   = vals[-1][1]
                anterior = vals[-2][1] if len(vals) > 1 else ultimo
                cambio_pct = (ultimo - anterior) / anterior * 100 if anterior else 0

                if len(vals) > 1:
                    promedio    = sum(v for _, v in vals) / len(vals)
                    volatilidad = (sum((v - promedio) ** 2 for _, v in vals) / len(vals)) ** 0.5
                    nivel_vol   = "bajo" if volatilidad < 0.005 else ("moderado" if volatilidad < 0.02 else "alto")
                else:
                    volatilidad, nivel_vol = 0, "bajo"

                if "compra" in descripcion.lower():
                    tc_compra = ultimo
                else:
                    tc_venta = ultimo

                resultado.append(
                    "\n" + descripcion + ":"
                    "\n  Valor actual: " + f"{ultimo:.4f}"
                    + "\n  Cambio: " + f"{cambio_pct:+.4f}%"
                    + "\n  Volatilidad 30d: " + f"{volatilidad:.4f}" + " -> riesgo " + nivel_vol
                )

            if not bcrp_ok and tc_bvl:
                resultado.append(
                    "\nNota: API BCRP no accesible desde esta red (requiere IP peruana)."
                    "\n  Usando tipo de cambio BVL: " + f"{tc_bvl:.4f}" + " S/ por USD."
                )

            if tc_compra and tc_venta:
                spread = abs(tc_venta - tc_compra)
                resultado.append("\nSpread compra/venta: " + f"{spread:.4f}" + " S/ (liquidez del mercado FX)")

            # ── Tasa Interbancaria — BCRP ──────────────────────────────────
            periodos_tasa = _bcrp_fetch("PD04722PD", fecha_inicio, fecha_fin)
            if periodos_tasa:
                vals_tasa = _valores_numericos(periodos_tasa)
                if vals_tasa:
                    tasa_actual = vals_tasa[-1][1]
                    resultado.append(
                        "\nTasa interbancaria MN (BCRP):"
                        "\n  Valor actual: " + f"{tasa_actual:.4f}%"
                    )
                else:
                    resultado.append("\nTasa interbancaria: sin datos numéricos en BCRP")
            else:
                resultado.append(
                    "\nTasa interbancaria MN:"
                    "\n  API BCRP no accesible desde esta red."
                    "\n  Referencia: BCRP inició ciclo de reducción desde set-2023."
                    "\n  Tasa de referencia vigente: 4.75% - 5.25% (rango 2024-2025)."
                    "\n  Política monetaria: expansiva-moderada para estimular crecimiento."
                )

            # ── Contexto Macro ─────────────────────────────────────────────
            resultado.append(
                "\n=== CONTEXTO MACRO PERU ==="
                "\n- Economía abierta, dolarizada (~70% créditos corporativos en USD)"
                "\n- Minería: ~60% exportaciones totales (oro, cobre, zinc, plomo, plata)"
                "\n- Riesgo político: moderado (presupuesto 2025-2026 en marcha)"
                "\n- Sol: estable con sesgo depreciatario ante fortaleza global del USD"
                "\n- Impacto en mineras: ingresos en USD, costos parciales en soles"
                "\n  -> depreciación del sol mejora márgenes en soles"
            )

            return "\n".join(resultado)

        return LangchainTool(
            name="obtener_datos_bcrp",
            description=(
                "Obtiene indicadores macroeconómicos del BCRP y contexto macro peruano: "
                "tipo de cambio USD/PEN (compra, venta, spread), volatilidad 30d, "
                "tasa interbancaria y análisis de impacto en el sector minero. "
                "Sin parámetros: devuelve todos los indicadores disponibles."
            ),
            func=obtener_datos_bcrp,
        )
