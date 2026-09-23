"""
Pruebas del rules-service (:8002) — catálogo de reglas del DOC-05.

Verifica, en proceso y sin modificar el catálogo:
1. El health check responde y reporta la conexión a PostgreSQL.
2. El listado devuelve reglas con los campos del esquema ReglaResponse.
3. Las reglas pertenecen a las familias oficiales RIE, RCV, RSC y RDS.
4. El filtro por familia solo devuelve reglas de esa familia.
5. La consulta por un identificador inexistente responde 404.
6. Una regla con datos inválidos se rechaza con 422 sin llegar a la BD.

Uso:  python tests/test_rules_service.py   (requiere PostgreSQL con el seed del DOC-05)
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "rules-service")))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402

client = TestClient(app)
FAMILIAS = {"RIE", "RCV", "RSC", "RDS"}
CAMPOS = {"id", "codigo_regla", "nombre_regla", "familia_regla", "descripcion", "severidad", "accion", "activo"}

_resultados: list[bool] = []


def verificar(condicion: bool, titulo: str, detalle: str = "") -> None:
    _resultados.append(bool(condicion))
    print(f"  {'[ OK ]' if condicion else '[FALLA]'} {titulo}" + (f"  -> {detalle}" if detalle else ""))


def main() -> int:
    print("=== PRUEBAS DEL RULES-SERVICE (:8002) ===\n")

    salud = client.get("/api/v1/health")
    verificar(salud.status_code == 200, "Health check responde 200")
    verificar(salud.json().get("conexion_bd") is True, "Conexión a PostgreSQL activa")

    respuesta = client.get("/api/v1/reglas")
    reglas = respuesta.json() if respuesta.status_code == 200 else []
    verificar(respuesta.status_code == 200 and len(reglas) > 0, "El catálogo lista reglas", f"{len(reglas)} reglas")
    verificar(all(CAMPOS <= set(r) for r in reglas), "Cada regla trae los campos del esquema")
    verificar(
        all(r["familia_regla"] in FAMILIAS for r in reglas),
        "Todas las reglas pertenecen a una familia oficial",
        ", ".join(sorted({r["familia_regla"] for r in reglas})),
    )

    rie = client.get("/api/v1/reglas", params={"familia_regla": "RIE"})
    verificar(
        rie.status_code == 200 and all(r["familia_regla"] == "RIE" for r in rie.json()),
        "El filtro por familia devuelve solo esa familia",
        f"{len(rie.json())} reglas RIE",
    )

    inexistente = client.get("/api/v1/reglas/00000000-0000-0000-0000-000000000000")
    verificar(inexistente.status_code == 404, "Un id inexistente responde 404", f"HTTP {inexistente.status_code}")

    invalida = client.post("/api/v1/reglas", json={"codigo_regla": "X", "nombre_regla": "ab"})
    verificar(invalida.status_code == 422, "Una regla inválida se rechaza con 422", f"HTTP {invalida.status_code}")

    aprobadas = sum(_resultados)
    print(f"\nResultado: {aprobadas}/{len(_resultados)} verificaciones aprobadas")
    return 0 if aprobadas == len(_resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
