#!/bin/bash

# 1. Arrancar LangFlow en background
langflow run --host 0.0.0.0 --port 7860 &
LANGFLOW_PID=$!

# 2. Esperar a que LangFlow esté listo (health check)
echo "[start] Esperando LangFlow..."
for i in $(seq 1 90); do
    if curl -s http://localhost:7860/health | grep -q "ok\|healthy\|status"; then
        echo "[start] LangFlow listo en ${i}s"
        break
    fi
    sleep 2
done

# 3. Esperar un poco más para que la API de flows esté disponible
sleep 10

# 4. Inyectar DeepSeek key (errores aquí no deben matar el contenedor)
python3 - <<'PYEOF'
import requests, os, time, sys

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
BASE = "http://localhost:7860"

if not DEEPSEEK_KEY:
    print("[start] DEEPSEEK_API_KEY no configurada, saltando inyeccion")
    sys.exit(0)

# Obtener token — probar auto_login primero (LANGFLOW_AUTO_LOGIN=true)
# luego login con credenciales configuradas
token = None

# Intento 1: auto_login endpoint
for attempt in range(3):
    try:
        r = requests.get(f"{BASE}/api/v1/auto_login", timeout=10)
        if r.ok:
            token = r.json().get("access_token")
            if token:
                print("[start] Auth via auto_login OK")
                break
    except Exception:
        pass
    time.sleep(2)

# Intento 2: login con credenciales del env
if not token:
    for user, pwd in [
        (os.environ.get("LANGFLOW_SUPERUSER", "langflow"), os.environ.get("LANGFLOW_SUPERUSER_PASSWORD", "langflow")),
        ("admin", "admin1234"),
        ("langflow", "langflow"),
    ]:
        try:
            r = requests.post(
                f"{BASE}/api/v1/login",
                data={"username": user, "password": pwd},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )
            if r.ok:
                token = r.json().get("access_token")
                if token:
                    print(f"[start] Auth via login ({user}) OK")
                    break
        except Exception:
            pass

if not token:
    print("[start] No se pudo autenticar, saltando inyeccion")
    sys.exit(0)

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Obtener lista de flows
flows_r = None
for attempt in range(5):
    try:
        r = requests.get(f"{BASE}/api/v1/flows/", headers=headers, timeout=10)
        if r.ok:
            flows_r = r
            break
        print(f"[start] GET /flows intento {attempt+1}: {r.status_code}")
    except Exception as e:
        print(f"[start] GET /flows intento {attempt+1}: {e}")
    time.sleep(3)

if not flows_r:
    print("[start] No se pudo obtener flows, saltando inyeccion")
    sys.exit(0)

data = flows_r.json()
flow_list = data if isinstance(data, list) else data.get("items", data.get("flows", []))
print(f"[start] {len(flow_list)} flows encontrados")

# Importar sistema_bvl.json si el flow no existe en la base de datos
import json as _json

FLOW_FILE = "/app/sistema_bvl.json"
flow_names = [f.get("name", "").lower() for f in flow_list]
bvl_exists = any("sistema" in n or "bvl" in n for n in flow_names)

if not bvl_exists and os.path.exists(FLOW_FILE):
    print("[start] Flow 'sistema_bvl' no encontrado, importando desde sistema_bvl.json...")
    try:
        with open(FLOW_FILE, encoding="utf-8") as fp:
            flow_json = _json.load(fp)
        r_import = requests.post(
            f"{BASE}/api/v1/flows/",
            json=flow_json,
            headers=headers,
            timeout=30,
        )
        if r_import.ok:
            imported = r_import.json()
            print(f"[start] Flow importado: '{imported.get('name')}' (id={imported.get('id')})")
            flow_list.append(imported)
        else:
            print(f"[start] Error importando flow: {r_import.status_code} {r_import.text[:200]}")
    except Exception as e:
        print(f"[start] Excepcion al importar flow: {e}")
elif bvl_exists:
    print("[start] Flow 'sistema_bvl' ya existe en la base de datos, saltando importacion.")
else:
    print(f"[start] {FLOW_FILE} no encontrado en el contenedor.")

# Inyectar DeepSeek key en cada flow
updated_total = 0
for flow_meta in flow_list:
    flow_id = flow_meta.get("id")
    if not flow_id:
        continue
    try:
        r2 = requests.get(f"{BASE}/api/v1/flows/{flow_id}", headers=headers, timeout=10)
        if not r2.ok:
            continue
        flow = r2.json()
        flow_data = flow.get("data") or {}
        if not flow_data:
            continue

        updated = 0
        for n in flow_data.get("nodes", []):
            if n.get("data", {}).get("type") == "DeepSeekModelComponent":
                tmpl = n["data"]["node"]["template"]
                if "api_key" in tmpl:
                    tmpl["api_key"]["value"] = DEEPSEEK_KEY
                    updated += 1

        if updated > 0:
            r3 = requests.put(
                f"{BASE}/api/v1/flows/{flow_id}",
                json={"name": flow.get("name", ""), "description": flow.get("description", ""), "data": flow_data},
                headers=headers,
                timeout=30,
            )
            print(f"[start] '{flow.get('name')}': {updated} nodos actualizados (status {r3.status_code})")
            updated_total += updated
    except Exception as e:
        print(f"[start] Error en flow {flow_id}: {e}")

print(f"[start] Inyeccion completada. Total nodos actualizados: {updated_total}")
PYEOF

# 5. Mantener el contenedor vivo con LangFlow en primer plano
wait $LANGFLOW_PID
