from langflow.custom import Component
from langflow.io import StrInput, SecretStrInput, Output
from langflow.field_typing import Tool
from langchain.tools import Tool as LangchainTool
import requests
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed


class NoticiasBVLToolComponent(Component):
    display_name = "Noticias BVL Tool"
    description = "Noticias del sector minero: Google News RSS + Alpha Vantage NEWS_SENTIMENT en paralelo."
    icon = "newspaper"
    name = "NoticiasBVLTool"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Alpha Vantage API Key",
            required=False,
        ),
    ]

    outputs = [
        Output(display_name="Tool", name="tool_output", method="build_tool"),
    ]

    def build_tool(self) -> Tool:
        api_key = self.api_key or os.environ.get("ALPHA_VANTAGE_KEY", "")

        def _fetch_news_ticker(ticker: str) -> list:
            for attempt in range(3):
                try:
                    url = (
                        "https://www.alphavantage.co/query"
                        "?function=NEWS_SENTIMENT&tickers=" + ticker + "&limit=15&apikey=" + api_key
                    )
                    r = requests.get(url, timeout=15)
                    r.raise_for_status()
                    data = r.json()
                    if data.get("Information") or data.get("Note"):
                        if attempt < 2:
                            time.sleep(15)
                            continue
                        return []
                    feed = data.get("feed", [])
                    relevant = []
                    for art in feed:
                        for ts_item in art.get("ticker_sentiment", []):
                            if ts_item.get("ticker") == ticker:
                                rel = float(ts_item.get("relevance_score", 0))
                                if rel >= 0.05:
                                    art2 = dict(art)
                                    art2["_rel"] = rel
                                    art2["_ts"] = float(ts_item.get("ticker_sentiment_score", 0))
                                    relevant.append(art2)
                                break
                    return relevant if relevant else feed
                except Exception:
                    if attempt < 2:
                        time.sleep(5)
            return []

        def _fetch_google_news_rss(query: str) -> list:
            """Titulares en espanol desde Google News RSS."""
            try:
                import feedparser
                encoded = requests.utils.quote(query)
                rss_url = (
                    "https://news.google.com/rss/search?q="
                    + encoded
                    + "&hl=es-419&gl=PE&ceid=PE:es-419"
                )
                feed = feedparser.parse(rss_url)
                articles = []
                for entry in (feed.entries or [])[:10]:
                    articles.append({
                        "title": entry.get("title", "Sin titulo"),
                        "link": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "summary": entry.get("summary", "")[:200],
                        "_source": "Google News",
                    })
                return articles
            except Exception:
                return []

        def buscar_noticias(input_text: str = "") -> str:
            text_lower = input_text.lower()
            if "scco" in text_lower or "southern" in text_lower or "copper" in text_lower or "cobre" in text_lower:
                primary, secondary = "SCCO", "BVN"
                rss_query = "Southern Copper Peru minera"
            elif "buenaventura" in text_lower or "bvn" in text_lower or "oro" in text_lower:
                primary, secondary = "BVN", "SCCO"
                rss_query = "Buenaventura minera Peru oro"
            else:
                primary, secondary = "BVN", "SCCO"
                rss_query = "mineras Peru BVL bolsa valores"

            av_articles = []
            rss_articles = []

            with ThreadPoolExecutor(max_workers=2) as executor:
                fut_av  = executor.submit(_fetch_news_ticker, primary)
                fut_rss = executor.submit(_fetch_google_news_rss, rss_query)
                for fut in as_completed([fut_av, fut_rss], timeout=30):
                    if fut is fut_av:
                        av_articles = fut.result() or []
                    else:
                        rss_articles = fut.result() or []

            if not av_articles:
                av_articles = _fetch_news_ticker(secondary)
                if av_articles:
                    primary = secondary

            NL = "\n"
            resultado = []

            if av_articles:
                alcistas = bajistas = neutros = 0
                lineas_av = []
                for i, art in enumerate(av_articles[:6], 1):
                    titulo = art.get("title", "Sin titulo")
                    fecha = art.get("time_published", "")[:8]
                    if len(fecha) == 8:
                        fecha = fecha[:4] + "-" + fecha[4:6] + "-" + fecha[6:8]
                    fuente = art.get("source", "Desconocida")
                    score = float(art.get("overall_sentiment_score", 0))
                    label = art.get("overall_sentiment_label", "Neutral")
                    ts_score = art.get("_ts", score)
                    resumen = art.get("summary", "")[:160]
                    if score > 0.15:
                        alcistas += 1
                    elif score < -0.15:
                        bajistas += 1
                    else:
                        neutros += 1
                    lineas_av.append(
                        "[" + str(i) + "] " + titulo + NL
                        + "    Fecha: " + fecha + " | Fuente: " + fuente + NL
                        + "    Sentimiento: " + label + " (" + ("+" if score >= 0 else "") + str(round(score, 3)) + ")"
                        + " | Score ticker: " + ("+" if ts_score >= 0 else "") + str(round(ts_score, 3)) + NL
                        + "    " + resumen
                    )
                total = alcistas + bajistas + neutros
                tendencia = "ALCISTA" if alcistas > bajistas else ("BAJISTA" if bajistas > alcistas else "NEUTRAL")
                resultado.append(
                    "=== NOTICIAS FINANCIERAS (Alpha Vantage) ===" + NL
                    + "TICKER: " + primary + " | " + str(total) + " noticias analizadas" + NL
                    + "Alcistas: " + str(alcistas) + " | Bajistas: " + str(bajistas) + " | Neutras: " + str(neutros) + NL
                    + "Tendencia dominante: " + tendencia + NL
                )
                resultado.append((NL + NL).join(lineas_av))

            if rss_articles:
                resultado.append(NL + "=== NOTICIAS EN ESPANOL (Google News) ===")
                for i, art in enumerate(rss_articles[:5], 1):
                    resultado.append(
                        "[" + str(i) + "] " + art.get("title", "Sin titulo") + NL
                        + "    Publicado: " + art.get("published", "?") + NL
                        + "    " + art.get("summary", "")[:160]
                    )

            if not resultado:
                return "No se encontraron noticias recientes. Usa score=0 y confianza=0."

            return NL.join(resultado)

        return LangchainTool(
            name="buscar_noticias_bvl",
            description=(
                "Busca noticias financieras y sentimiento del mercado para acciones mineras BVL. "
                "Combina Alpha Vantage NEWS_SENTIMENT (con scores de sentimiento) y Google News RSS (en espanol). "
                "Input: nombre de empresa o ticker (BVN, SCCO, Buenaventura, Southern Copper). "
                "SIEMPRE llama esta herramienta antes de dar tu analisis."
            ),
            func=buscar_noticias,
        )
