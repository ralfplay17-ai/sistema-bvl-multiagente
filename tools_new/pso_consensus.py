import numpy as np
import pyswarms as ps
import json
import re

from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message


class PSOConsensusComponent(Component):
    display_name = "PSO Consensus Engine"
    description = "Optimiza pesos de agentes usando PySwarms GlobalBestPSO (50 partículas, 100 iter.)"
    icon = "cpu"
    name = "PSOConsensusComponent"

    inputs = [
        MessageTextInput(name="agente_tecnico", display_name="Señal Agente Técnico"),
        MessageTextInput(name="agente_commodities", display_name="Señal Agente Commodities"),
        MessageTextInput(name="agente_sentimiento", display_name="Señal Agente Sentimiento"),
        MessageTextInput(name="agente_riesgo", display_name="Señal Agente Riesgo"),
    ]

    outputs = [
        Output(display_name="PSO Result", name="message_output", method="run_pso")
    ]

    def normalizar_texto(self, entrada) -> str:
        """
        Convierte cualquier entrada de Langflow a texto.
        Puede recibir string, Message, dict u otros objetos.
        """
        if entrada is None:
            return ""

        if isinstance(entrada, dict):
            return json.dumps(entrada, ensure_ascii=False)

        if hasattr(entrada, "text"):
            return str(entrada.text)

        if hasattr(entrada, "content"):
            return str(entrada.content)

        if hasattr(entrada, "data"):
            try:
                return json.dumps(entrada.data, ensure_ascii=False)
            except Exception:
                return str(entrada.data)

        return str(entrada)

    def extraer_json(self, entrada) -> dict:
        """
        Extrae JSON desde la salida de un agente.
        Acepta JSON puro, bloques ```json ... ``` o texto que contenga un JSON.
        """
        texto = self.normalizar_texto(entrada).strip()

        if not texto:
            return {}

        # Intento 1: parsear directamente como JSON
        try:
            return json.loads(texto)
        except Exception:
            pass

        # Intento 2: extraer bloque ```json ... ``` que genera a veces el LLM
        match_md = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", texto, re.DOTALL)
        if match_md:
            try:
                return json.loads(match_md.group(1))
            except Exception:
                pass

        # Intento 3: extraer el bloque JSON mas largo entre { ... }
        # Busca desde el primer { hasta el ultimo } para capturar JSON completo
        start = texto.find("{")
        end = texto.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(texto[start:end + 1])
            except Exception:
                pass

        # Intento 4: buscar cualquier objeto JSON con regex
        match = re.search(r"\{.*\}", texto, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass

        return {}

    def senal_a_valor(self, senal: str) -> float:
        """
        Convierte COMPRAR / MANTENER / VENDER a valor numérico.
        """
        senal = str(senal).upper().strip()

        if senal == "COMPRAR":
            return 1.0
        elif senal == "VENDER":
            return -1.0
        elif senal == "MANTENER":
            return 0.0

        return 0.0

    def procesar_agente(self, entrada, nombre_agente: str) -> dict:
        """
        Procesa la salida de cada agente.
        Prioriza score si existe.
        Si no hay score, usa senal/señal.
        """
        data = self.extraer_json(entrada)
        texto = self.normalizar_texto(entrada)

        agente = data.get("agente", nombre_agente)
        ticker = data.get("ticker", "")

        # Acepta "senal" sin tilde y "señal" con tilde
        senal = data.get("senal", data.get("señal", "MANTENER"))

        # Prioridad 1: usar score si existe
        try:
            score = float(data.get("score"))
        except Exception:
            score = self.senal_a_valor(senal)

        # Limitar score a rango [-1, 1]
        score = max(-1.0, min(1.0, score))

        # Confianza
        try:
            confianza = float(data.get("confianza", 0.5))
        except Exception:
            confianza = 0.5

        # Si confianza viene como porcentaje, convertir a 0-1
        if confianza > 1:
            confianza = confianza / 100.0

        confianza = max(0.0, min(1.0, confianza))

        datos_usados = data.get("datos_usados", "")
        justificacion = data.get("justificacion", data.get("razon", ""))

        # Fallback si el JSON no pudo leerse
        if not data:
            texto_upper = texto.upper()

            # Contar ocurrencias para decidir senal dominante
            n_comprar = texto_upper.count("COMPRAR")
            n_vender  = texto_upper.count("VENDER")
            n_mantener = texto_upper.count("MANTENER")

            if n_comprar > n_vender and n_comprar > n_mantener:
                senal = "COMPRAR"
                score = 0.5
                confianza = 0.35
            elif n_vender > n_comprar and n_vender > n_mantener:
                senal = "VENDER"
                score = -0.5
                confianza = 0.35
            else:
                senal = "MANTENER"
                score = 0.0
                confianza = 0.3

            datos_usados = "No se pudo extraer JSON estructurado. Lectura de respaldo desde texto."
            justificacion = "Señal extraída por conteo de palabras clave en respuesta del agente."

        return {
            "agente": agente,
            "ticker": ticker,
            "senal": senal,
            "score": score,
            "confianza": confianza,
            "datos_usados": datos_usados,
            "justificacion": justificacion,
        }

    def run_pso(self) -> Message:
        agentes = [
            self.procesar_agente(self.agente_tecnico, "tecnico"),
            self.procesar_agente(self.agente_commodities, "commodities"),
            self.procesar_agente(self.agente_sentimiento, "sentimiento"),
            self.procesar_agente(self.agente_riesgo, "riesgo"),
        ]

        scores = np.array([agente["score"] for agente in agentes], dtype=float)
        confianzas = np.array([agente["confianza"] for agente in agentes], dtype=float)

        # Evitar que todas las confianzas sean cero
        if confianzas.sum() == 0:
            confianzas = np.array([0.25, 0.25, 0.25, 0.25], dtype=float)
        else:
            confianzas = confianzas / confianzas.sum()

        def objective_function(particles):
            costs = []

            for particle in particles:
                pesos = np.abs(particle)

                if pesos.sum() == 0:
                    pesos = np.array([0.25, 0.25, 0.25, 0.25])
                else:
                    pesos = pesos / pesos.sum()

                score_pso = np.dot(pesos, scores)

                # Penaliza que los pesos se alejen mucho de las confianzas
                confianza_penalty = np.sum((pesos - confianzas) ** 2)

                # Favorece distribución no extremadamente concentrada
                entropia = -np.sum(pesos * np.log(pesos + 1e-10))
                desbalance_penalty = -entropia

                # Penaliza decisiones extremas cuando hay señales enfrentadas
                senales_activas = np.abs(scores) > 0.1
                if senales_activas.sum() > 1:
                    hay_positivas = (scores[senales_activas] > 0).sum() > 0
                    hay_negativas = (scores[senales_activas] < 0).sum() > 0

                    if hay_positivas and hay_negativas and abs(score_pso) > 0.7:
                        coherencia_penalty = abs(score_pso) * 2
                    else:
                        coherencia_penalty = 0
                else:
                    coherencia_penalty = 0

                cost = (
                    confianza_penalty * 0.4 +
                    desbalance_penalty * 0.3 +
                    coherencia_penalty * 0.3
                )

                costs.append(cost)

            return np.array(costs)

        options = {
            "c1": 0.5,
            "c2": 0.3,
            "w": 0.9,
        }

        bounds = (
            np.zeros(4),
            np.ones(4),
        )

        optimizer = ps.single.GlobalBestPSO(
            n_particles=50,
            dimensions=4,
            options=options,
            bounds=bounds,
        )

        cost, best_pos = optimizer.optimize(
            objective_function,
            iters=100,
            verbose=False,
        )

        pesos_optimos = np.abs(best_pos)

        if pesos_optimos.sum() == 0:
            pesos_optimos = np.array([0.25, 0.25, 0.25, 0.25])
        else:
            pesos_optimos = pesos_optimos / pesos_optimos.sum()

        score_final = float(np.dot(pesos_optimos, scores))

        if score_final >= 0.25:
            decision = "COMPRAR"
        elif score_final <= -0.25:
            decision = "VENDER"
        else:
            decision = "MANTENER"

        # Confianza final ponderada por los pesos óptimos
        confianza_final = float(np.dot(pesos_optimos, np.array([a["confianza"] for a in agentes])))
        confianza_final = max(0.0, min(1.0, confianza_final))

        tickers = [a["ticker"] for a in agentes if a["ticker"]]
        ticker_final = tickers[0] if tickers else "DESCONOCIDO"

        resultado = {
            "motor": "PSO Consensus Engine",
            "algoritmo": "PySwarms GlobalBestPSO",
            "configuracion": {
                "particulas": 50,
                "iteraciones": 100,
                "dimensiones": 4,
            },
            "ticker": ticker_final,
            "senal_final": decision,
            "score_final": round(score_final, 4),
            "confianza_final": round(confianza_final, 4),
            "pesos_optimos": {
                "tecnico": round(float(pesos_optimos[0]), 4),
                "commodities": round(float(pesos_optimos[1]), 4),
                "sentimiento": round(float(pesos_optimos[2]), 4),
                "riesgo": round(float(pesos_optimos[3]), 4),
            },
            "agentes": {
                "tecnico": agentes[0],
                "commodities": agentes[1],
                "sentimiento": agentes[2],
                "riesgo": agentes[3],
            },
            "costo_optimizacion": round(float(cost), 6),
        }

        return Message(text=json.dumps(resultado, ensure_ascii=False, indent=2))