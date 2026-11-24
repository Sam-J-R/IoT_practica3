#!/usr/bin/env python3
# Requiere la ASK CLI v2 (npm install -g ask-cli) y "ask configure" con su cuenta de desarrollador.
"""Prueba la skill completa en el simulador de Alexa (texto), con las frases de casos_alexa.json.

Dos modos:

  --ejecutar  Genera un archivo de repetición y corre `ask dialog --replay`, que envía
              cada frase al simulador de la etapa development y muestra la respuesta.
              Después compara cada respuesta con la esperada.
  --manual    No usa la CLI: escribe una tabla Markdown con las frases y las respuestas
              esperadas, para recorrerla a mano en Test -> Development y marcar el resultado.

Antes de --ejecutar:
  * Vincular un tendedero de PRUEBA: la corrida desvincula al usuario de la consola al final.
  * La skill debe estar en la etapa development con el modelo nuevo compilado.

Ejemplos:
  python tools/probar_alexa.py --manual --codigo 715204
  python tools/probar_alexa.py --ejecutar --skill-id amzn1.ask.skill.xxxx --codigo 715204

Si la salida de `ask dialog` cambia de formato y el script no reconoce las respuestas,
deja la salida completa en el informe para revisarla a mano.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CASOS = Path(__file__).with_name("casos_alexa.json")


def pasos(casos, codigo):
    """Lista ordenada de (id, nombre, frase, espera) para el simulador."""
    out = []
    for caso in casos:
        for frase, espera in caso.get("alexa", []):
            out.append((caso["id"], caso["nombre"], frase.replace("{codigo}", codigo), espera))
    return out


def archivo_replay(skill_id, lista):
    return {"skillId": skill_id, "locale": "es-MX", "type": "text",
            "userInput": [frase for _, _, frase, _ in lista] + [".quit"]}


def respuestas_de(salida):
    """Extrae las líneas 'Alexa > ...' de la salida de ask dialog (sin colores ANSI)."""
    limpia = re.sub(r"\x1b\[[0-9;]*m", "", salida)
    return [re.sub(r"<[^>]+>", "", m).strip() for m in re.findall(r"^\s*Alexa\s*>\s*(.*)$", limpia, re.M)]


def comparar(lista, respuestas):
    filas = []
    for i, (cid, nombre, frase, espera) in enumerate(lista):
        dicho = respuestas[i] if i < len(respuestas) else ""
        ok = bool(dicho) and bool(re.search(espera, dicho, re.I))
        filas.append((cid, frase, espera, "PASA" if ok else "FALLA", dicho or "(sin respuesta)"))
    return filas


def tabla(filas, con_resultado=True):
    cab = "| Caso | Frase | Respuesta esperada (contiene) |"
    sep = "| --- | --- | --- |"
    if con_resultado:
        cab, sep = cab + " Resultado | Respuesta de Alexa |", sep + " --- | --- |"
    out = [cab, sep]
    for f in filas:
        celdas = [f[0], f[1], f[2].replace("|", " o ")] + ([f[3], f[4].replace("|", "/")] if con_resultado else [])
        out.append("| " + " | ".join(celdas) + " |")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    modo = ap.add_mutually_exclusive_group(required=True)
    modo.add_argument("--ejecutar", action="store_true")
    modo.add_argument("--manual", action="store_true")
    ap.add_argument("--skill-id")
    ap.add_argument("--codigo", default="715204")
    ap.add_argument("--perfil", default="default", help="perfil de la ASK CLI")
    ap.add_argument("--casos", default=str(CASOS))
    ap.add_argument("--salida", default=str(RAIZ / "resultados_p4"))
    a = ap.parse_args(argv)

    lista = pasos(json.loads(Path(a.casos).read_text(encoding="utf-8"))["casos"], a.codigo)
    Path(a.salida).mkdir(parents=True, exist_ok=True)
    sello = f"{datetime.now():%Y%m%d-%H%M%S}"

    if a.manual:
        filas = [(c, f, e, "", "") for c, _, f, e in lista]
        ruta = Path(a.salida) / f"alexa-manual-{sello}.md"
        ruta.write_text("# Frases para el simulador de Alexa (Test -> Development)\n\n"
                        "Escribir cada frase en orden, en la misma sesión, y anotar el resultado.\n\n"
                        + tabla(filas) + "\n", encoding="utf-8")
        print(f"Lista para la prueba manual: {ruta}")
        return 0

    if not a.skill_id:
        sys.exit("--ejecutar necesita --skill-id")
    if not shutil.which("ask"):
        sys.exit("No se encontró la ASK CLI (comando 'ask'). Usen --manual o instalen ask-cli.")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(archivo_replay(a.skill_id, lista), f, ensure_ascii=False)
    r = subprocess.run(["ask", "dialog", "--replay", f.name, "--profile", a.perfil],
                       capture_output=True, text=True, encoding="utf-8", timeout=600)
    salida = r.stdout + r.stderr
    filas = comparar(lista, respuestas_de(salida))
    pasan = sum(f[3] == "PASA" for f in filas)
    texto = (f"# Simulador de Alexa — {datetime.now():%Y-%m-%d %H:%M}\n\n{pasan} de {len(filas)} pasos pasan.\n\n"
             + tabla(filas) + "\n\n## Salida de ask dialog\n\n```text\n" + salida + "\n```\n")
    ruta = Path(a.salida) / f"alexa-{sello}.md"
    ruta.write_text(texto, encoding="utf-8")
    for fila in filas:
        print(f"[{fila[3]}] {fila[0]} «{fila[1]}» -> {fila[4]}")
    print(f"\nInforme: {ruta}")
    return 0 if pasan == len(filas) else 1


if __name__ == "__main__":
    sys.exit(main())
