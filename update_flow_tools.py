"""
Inyecta el codigo actualizado de los 3 tools en sistema_bvl.json.
Ejecutar: python update_flow_tools.py
"""
import json
import sys
from pathlib import Path

BASE = Path(__file__).parent
FLOW_FILE = BASE / "sistema_bvl.json"
TOOLS_DIR = BASE / "tools_new"

TOOL_FILE_MAP = {
    "DatosBVLTool":        TOOLS_DIR / "datos_bvl_tool.py",
    "DatosCommoditiesTool": TOOLS_DIR / "datos_commodities_tool.py",
    "NoticiasBVLTool":     TOOLS_DIR / "noticias_bvl_tool.py",
    "DatosBCRPTool":       TOOLS_DIR / "datos_bcrp_tool.py",
}

print("Cargando sistema_bvl.json ...")
with open(FLOW_FILE, encoding="utf-8") as f:
    flow = json.load(f)

nodes = flow.get("data", {}).get("nodes", [])
updated = {}

for node in nodes:
    node_type = node.get("data", {}).get("type", "")
    if node_type in TOOL_FILE_MAP:
        tool_file = TOOL_FILE_MAP[node_type]
        new_code = tool_file.read_text(encoding="utf-8")
        tmpl = node["data"]["node"]["template"]
        old_len = len(tmpl.get("code", {}).get("value", ""))
        tmpl.setdefault("code", {})["value"] = new_code
        updated[node_type] = (old_len, len(new_code))
        print(f"  {node_type}: {old_len} -> {len(new_code)} chars")

if not updated:
    print("ERROR: No se encontraron nodos para actualizar. Verifica el flow.")
    sys.exit(1)

missing = set(TOOL_FILE_MAP) - set(updated)
if missing:
    print(f"AVISO: No se encontraron nodos para: {missing}")

backup = FLOW_FILE.with_suffix(".json.bak")
import shutil
shutil.copy2(FLOW_FILE, backup)
print(f"Backup guardado en {backup.name}")

with open(FLOW_FILE, "w", encoding="utf-8") as f:
    json.dump(flow, f, ensure_ascii=False, separators=(",", ":"))

size_kb = FLOW_FILE.stat().st_size / 1024
print(f"\nsistema_bvl.json actualizado ({size_kb:.0f} KB)")
print(f"Tools actualizados: {list(updated.keys())}")
print("\nListo. Ejecuta 'docker compose up --build -d' para aplicar.")
