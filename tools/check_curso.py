"""Comprueba el mapa del curso de GearStream (docs/curso/) y genera su diagrama.

    python -I tools/check_curso.py              # comprueba; sale con 1 si algo falla
    python -I tools/check_curso.py --escribir   # rehace docs/curso/mapa.md y después comprueba
    python -I tools/check_curso.py --prueba     # la prueba: el curso pasa y los errores sembrados se detectan

El curso se arma con dos archivos escritos a mano: conceptos.json (cada concepto con lo que necesita, las
palabras que lo nombran y las funciones del código que lo usan, más el inventario de esas funciones) e
indice.md (los capítulos en orden, con sus conceptos y sus preguntas). mapa.md sale de los dos.

Qué comprueba, y por qué:
  1. Orden. Cada concepto está una sola vez en el índice y después de todo lo que necesita (en un capítulo
     anterior, o más arriba en la lista del mismo capítulo): el curso se lee de corrido, sin saltos adelante.
  2. Glosario. Ningún término se usa en un capítulo anterior al del concepto que lo define: primero se ve la
     idea, después se le pone nombre. Se lee la prosa de cada capítulo (sin el código entre comillas
     invertidas ni las direcciones de los enlaces), sin distinguir mayúsculas ni tildes.
  3. Inventario. Cada función del inventario la usa algún concepto, cada función que nombra un concepto está
     en el inventario y, si el código está al lado (en este repo), la función está definida en su archivo.
De paso: los capítulos van numerados de corrido, los enlaces internos (#...) llevan a un título, cada
concepto que nombra el apéndice está en el capítulo que dice su fila, y mapa.md está al día.
Solo usa la biblioteca estándar.
"""
import argparse
import copy
import json
import re
import sys
import unicodedata
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CURSO = RAIZ / "docs" / "curso"

TITULO_CAP = re.compile(r"^## Capítulo (\d+) · (.+?)\s*$")
TITULO_APENDICE = re.compile(r"^## Apéndice\b")
LINEA_CONCEPTOS = re.compile(r"^\*\*Conceptos:\*\*(.*)$")
EN_CODIGO = re.compile(r"`([^`]*)`")
DESTINO = re.compile(r"\]\(([^)]*)\)")
TITULO = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
CAP_N = re.compile(r"\bcap\. (\d+)")


def emit(text):
    """print() que sobrevive a una consola cp1252 redirigida (los términos llevan θ, ω, →)."""
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "ascii"
        print(text.encode(enc, "replace").decode(enc), flush=True)


# ---------- leer ----------

def plano(texto):
    """Minúsculas y sin tildes (la ñ queda n): «Cuaternión» y «cuaternion» son el mismo término."""
    s = unicodedata.normalize("NFD", texto.lower())
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


def patron(termino):
    """El término como palabra entera; con * al final, como comienzo de palabra (integr* = integrar, integral…)."""
    t = plano(termino.strip())
    if t.endswith("*"):
        return re.compile(r"(?<!\w)" + re.escape(t[:-1]))
    return re.compile(r"(?<!\w)" + re.escape(t) + r"(?!\w)")


def prosa(linea):
    """Lo que se lee de una línea: sin el código entre comillas invertidas ni la dirección de los enlaces."""
    return DESTINO.sub("]", EN_CODIGO.sub(" ", linea))


def ancla(titulo):
    """El #ancla que GitHub le da a un título: minúsculas, sin puntuación, espacios a guiones."""
    return re.sub(r"[^\w\- ]", "", titulo.strip().lower()).replace(" ", "-")


def leer_indice(texto):
    """Los capítulos ({n, titulo, linea, conceptos, lineas}) y el apéndice. `lineas` son (número, texto) e
    incluyen el título; la línea **Conceptos:** no cuenta como prosa. Otra sección ## corta el capítulo."""
    caps, apendice, actual = [], None, None
    for i, linea in enumerate(texto.splitlines(), 1):
        m = TITULO_CAP.match(linea)
        if m:
            actual = {"n": int(m[1]), "titulo": m[2], "linea": i, "conceptos": [], "lineas": [(i, m[2])]}
            caps.append(actual)
            continue
        if TITULO_APENDICE.match(linea):
            actual = apendice = {"n": None, "titulo": linea[3:].strip(), "linea": i, "conceptos": [], "lineas": []}
            continue
        if linea.startswith("## "):
            actual = None
            continue
        if actual is None:
            continue
        m = LINEA_CONCEPTOS.match(linea)
        if m and actual is not apendice:
            actual["conceptos"] += EN_CODIGO.findall(m[1])
        else:
            actual["lineas"].append((i, linea))
    return caps, apendice


def definida(nombre, fuente, python):
    """¿El archivo define `nombre`? def/class en Python; function, class, const/let/var o un método en JS."""
    n = re.escape(nombre)
    if python:
        return re.search(rf"^\s*(?:async\s+)?(?:def|class)\s+{n}\b", fuente, re.M) is not None
    return re.search(rf"\bfunction\s+{n}\b|\bclass\s+{n}\b|\b(?:const|let|var)\s+{n}\s*=|"
                     rf"^\s*(?:async\s+|static\s+|get\s+)*{n}\s*\([^)]*\)\s*\{{", fuente, re.M) is not None


# ---------- comprobar ----------

def revisar(datos, indice, mapa=None, raiz=RAIZ):
    """(errores, notas): errores vacío = el curso pasa. `mapa` es el texto de mapa.md (None: no se compara)."""
    errores, notas = [], []
    conceptos = datos.get("conceptos", [])
    por_id = {}
    for c in conceptos:
        if c["id"] in por_id:
            errores.append(f"conceptos.json: el id «{c['id']}» está dos veces")
        por_id[c["id"]] = c
    caps, apendice = leer_indice(indice)
    for k, cap in enumerate(caps):
        if cap["n"] != k:
            errores.append(f"indice.md:{cap['linea']}: el capítulo {cap['n']} debería ser el {k}")

    # 1. orden
    pos = {}
    for cap in caps:
        for k, cid in enumerate(cap["conceptos"]):
            if cid not in por_id:
                errores.append(f"indice.md:{cap['linea']}: «{cid}» no está en conceptos.json")
            elif cid in pos:
                errores.append(f"indice.md:{cap['linea']}: «{cid}» ya está en el capítulo {pos[cid][0]}")
            else:
                pos[cid] = (cap["n"], k)
    for c in conceptos:
        cid = c["id"]
        if cid not in pos:
            errores.append(f"«{cid}» no está en ningún capítulo del índice")
            continue
        for p in c.get("prerrequisitos", []):
            if p not in por_id:
                errores.append(f"«{cid}» necesita «{p}», que no está en conceptos.json")
            elif p in pos and pos[p] >= pos[cid]:
                donde = "más abajo en el mismo capítulo" if pos[p][0] == pos[cid][0] else f"en el cap. {pos[p][0]}"
                errores.append(f"«{cid}» (cap. {pos[cid][0]}) necesita «{p}», que llega después: {donde}")

    # 2. glosario
    duenos = {}
    for c in conceptos:
        for t in c.get("terminos", []):
            clave = plano(t)
            if clave in duenos and duenos[clave] != c["id"]:
                errores.append(f"glosario: «{t}» es de «{duenos[clave]}» y de «{c['id']}»")
            duenos[clave] = c["id"]
    terminos = [(t, patron(t), c["id"], pos[c["id"]][0]) for c in conceptos if c["id"] in pos
                for t in c.get("terminos", [])]
    for cap in caps:
        tarde = [x for x in terminos if x[3] > cap["n"]]
        vistos = set()
        for i, linea in cap["lineas"]:
            texto = plano(prosa(linea))
            for t, rx, cid, n in tarde:
                if rx.search(texto):
                    vistos.add(t)
                    errores.append(f"indice.md:{i}: el cap. {cap['n']} dice «{t}», que se define en el cap. {n} («{cid}»)")
        junto = plano(" ".join(prosa(linea) for _, linea in cap["lineas"]))   # términos partidos en dos líneas
        for t, rx, cid, n in tarde:
            if t not in vistos and rx.search(junto):
                errores.append(f"indice.md:{cap['linea']}: el cap. {cap['n']} dice «{t}» (partido en dos líneas), "
                               f"que se define en el cap. {n} («{cid}»)")

    # 3. inventario
    inventario = {}
    for f in datos.get("inventario", []):
        if f["id"] in inventario:
            errores.append(f"inventario: {f['id']} está dos veces")
        inventario[f["id"]] = f
    usadas = set()
    for c in conceptos:
        for fid in c.get("codigo", []):
            if fid not in inventario:
                errores.append(f"«{c['id']}» nombra {fid}, que no está en el inventario")
            usadas.add(fid)
    fuentes, sin_fuente = {}, 0
    for fid in inventario:
        if fid not in usadas:
            errores.append(f"inventario: ningún concepto cubre {fid}")
        archivo, _, nombre = fid.rpartition(":")
        ruta = raiz / archivo
        if not archivo or not ruta.is_file():
            sin_fuente += 1
            continue
        if archivo not in fuentes:
            fuentes[archivo] = ruta.read_text(encoding="utf-8", errors="replace")
        for parte in nombre.split("."):
            if not definida(parte, fuentes[archivo], archivo.endswith(".py")):
                errores.append(f"inventario: {archivo} no define «{parte}» ({fid})")
    if sin_fuente:
        notas.append(f"{sin_fuente} funciones del inventario no se buscaron: su archivo no está en {raiz}")

    # de paso: enlaces internos, apéndice, mapa
    anclas = {ancla(m[2]) for linea in indice.splitlines() if (m := TITULO.match(linea))}
    for i, linea in enumerate(indice.splitlines(), 1):
        for destino in DESTINO.findall(linea):
            if destino.startswith("#") and destino[1:] not in anclas:
                errores.append(f"indice.md:{i}: el enlace {destino} no lleva a ningún título")
    if apendice:
        for i, linea in apendice["lineas"]:
            nums = {int(n) for n in CAP_N.findall(linea)}
            for cid in EN_CODIGO.findall(linea):
                if cid in pos and pos[cid][0] not in nums:
                    errores.append(f"indice.md:{i}: el apéndice manda «{cid}» al cap. "
                                   f"{', '.join(map(str, sorted(nums))) or '?'}, pero está en el cap. {pos[cid][0]}")
    if mapa is not None and not errores and mapa != generar_mapa(datos, indice):
        errores.append("mapa.md no está al día: corre  python -I tools/check_curso.py --escribir")
    return errores, notas


# ---------- generar mapa.md ----------

def celda(texto):
    """Texto seguro dentro de una tabla de Markdown."""
    return texto.replace("|", "\\|").replace("*", "\\*")


def etiqueta(texto):
    """Texto seguro dentro de un nodo de Mermaid."""
    return texto.replace('"', "'")


def generar_mapa(datos, indice):
    """mapa.md: los capítulos, un diagrama por capítulo, el mapa entero, el inventario y el glosario."""
    conceptos = {c["id"]: c for c in datos["conceptos"]}
    caps, _ = leer_indice(indice)
    cap_de = {cid: cap["n"] for cap in caps for cid in cap["conceptos"] if cid in conceptos}
    titulo = {cap["n"]: cap["titulo"] for cap in caps}
    pre = {cid: [p for p in conceptos[cid].get("prerrequisitos", []) if p in cap_de] for cid in cap_de}
    memo = {}

    def ancestros(cid):
        if cid not in memo:
            memo[cid] = set()
            for p in pre[cid]:
                memo[cid] |= {p} | ancestros(p)
        return memo[cid]

    # solo las flechas directas: si A lleva a B y B a C, la de A a C sobra
    directas = {cid: [p for p in pre[cid] if not any(p in ancestros(q) for q in pre[cid] if q != p)] for cid in cap_de}
    nodo = lambda cid: "k_" + cid
    flechas_cap = {(cap_de[p], cap_de[cid]) for cid in cap_de for p in directas[cid] if cap_de[p] != cap_de[cid]}
    llega = {n: {a for a, b in flechas_cap if b == n} for n in titulo}
    memo_cap = {}

    def antes_cap(n):
        if n not in memo_cap:
            memo_cap[n] = set()
            for a in llega[n]:
                memo_cap[n] |= {a} | antes_cap(a)
        return memo_cap[n]

    flechas_cap = sorted((a, b) for a, b in flechas_cap if not any(a in antes_cap(x) for x in llega[b] if x != a))
    archivos = sorted({f["id"].rpartition(":")[0] for f in datos["inventario"]})
    corto = lambda fid: fid.rpartition("/")[2]
    usan = {}
    for cid in cap_de:
        for fid in conceptos[cid].get("codigo", []):
            usan.setdefault(fid, []).append(cid)
    n_terminos = sum(len(conceptos[cid].get("terminos", [])) for cid in cap_de)

    out = ["# Mapa de prerrequisitos", "",
           "> Generado por `python -I tools/check_curso.py --escribir` a partir de [conceptos.json](conceptos.json) "
           "y del orden de [indice.md](indice.md). No lo edites a mano: cambia esos dos y vuelve a generarlo.", "",
           f"{len(cap_de)} conceptos en {len(caps)} capítulos · {len(datos['inventario'])} funciones de "
           f"{len(archivos)} archivos · {n_terminos} términos en el glosario.", "",
           "En `conceptos.json` cada concepto dice qué necesita. En los diagramas la flecha va al revés, en el "
           "sentido en que se aprende: de lo que necesitas a lo que te deja entender. Para que se lean, solo "
           "están las flechas directas (si A lleva a B y B lleva a C, la de A a C no se dibuja). Los recuadros "
           "punteados son conceptos de capítulos anteriores.", "",
           "## Los capítulos", "", "```mermaid", "flowchart TD"]
    out += [f'  c{n}["{n} · {etiqueta(titulo[n])}"]' for n in sorted(titulo)]
    out += [f"  c{a} --> c{b}" for a, b in flechas_cap]
    out += ["```", "", "## Capítulo por capítulo", ""]
    for cap in caps:
        ids = [cid for cid in cap["conceptos"] if cid in conceptos]
        de_fuera = sorted({p for cid in ids for p in directas[cid] if cap_de[p] != cap["n"]},
                          key=lambda p: (cap_de[p], list(cap_de).index(p)))
        out += [f"### {cap['n']} · {cap['titulo']}", "", "```mermaid", "flowchart TD",
                "  classDef fuera stroke-dasharray: 4 3"]
        out += [f'  {nodo(p)}["{etiqueta(conceptos[p]["nombre"])} · cap. {cap_de[p]}"]:::fuera' for p in de_fuera]
        out += [f'  {nodo(cid)}["{etiqueta(conceptos[cid]["nombre"])}"]' for cid in ids]
        out += [f"  {nodo(p)} --> {nodo(cid)}" for cid in ids for p in directas[cid]]
        out += ["```", "", "| Concepto | Qué es | Necesita | En el código |", "|---|---|---|---|"]
        for cid in ids:
            c = conceptos[cid]
            necesita = ", ".join(f"`{p}`" for p in c.get("prerrequisitos", [])) or "—"
            codigo = ", ".join(f"`{corto(f)}`" for f in c.get("codigo", [])) or "—"
            out.append(f"| **{celda(c['nombre'])}** `{cid}` | {celda(c['definicion'])} | {necesita} | {codigo} |")
        out.append("")
    out += ["## El mapa entero", "", "<details><summary>Los conceptos de todos los capítulos en un solo diagrama "
            "(es grande)</summary>", "", "```mermaid", "flowchart TD"]
    for cap in caps:
        out.append(f'  subgraph c{cap["n"]} ["{cap["n"]} · {etiqueta(cap["titulo"])}"]')
        out += [f'    {nodo(cid)}["{etiqueta(conceptos[cid]["nombre"])}"]' for cid in cap["conceptos"] if cid in conceptos]
        out.append("  end")
    out += [f"  {nodo(p)} --> {nodo(cid)}" for cid in cap_de for p in directas[cid]]
    out += ["```", "", "</details>", "", "## Inventario: qué conceptos usa cada función", "",
            "Cada función del repo que hace matemática y los conceptos que la explican (con su capítulo).", ""]
    for archivo in archivos:
        out += [f"### `{archivo}`", "", "| Función | Qué hace | Conceptos |", "|---|---|---|"]
        for f in datos["inventario"]:
            if f["id"].rpartition(":")[0] != archivo:
                continue
            cs = sorted(usan.get(f["id"], []), key=lambda cid: (cap_de[cid], list(cap_de).index(cid)))
            lista = ", ".join(f"{celda(conceptos[cid]['nombre'])} ({cap_de[cid]})" for cid in cs) or "—"
            out.append(f"| `{f['id'].rpartition(':')[2]}` | {celda(f['que_hace'])} | {lista} |")
        out.append("")
    out += ["## Glosario", "", "El capítulo es donde se define el término: antes de él, el índice no lo usa.", "",
            "| Término | Concepto | Cap. |", "|---|---|---|"]
    for cid in cap_de:
        for t in conceptos[cid].get("terminos", []):
            out.append(f"| {celda(t)} | {celda(conceptos[cid]['nombre'])} | {cap_de[cid]} |")
    return "\n".join(out) + "\n"


# ---------- la prueba ----------

def cargar():
    datos = json.loads((CURSO / "conceptos.json").read_text(encoding="utf-8"))
    indice = (CURSO / "indice.md").read_text(encoding="utf-8")
    ruta = CURSO / "mapa.md"
    return datos, indice, ruta.read_text(encoding="utf-8") if ruta.exists() else ""


class Prueba(unittest.TestCase):
    """El curso real pasa, y cada tipo de error sembrado a propósito se detecta."""

    @classmethod
    def setUpClass(cls):
        cls.datos, cls.indice, cls.mapa = cargar()

    def errores(self, datos=None, indice=None, mapa=None):
        return revisar(datos or self.datos, indice or self.indice, mapa)[0]

    def concepto(self, datos, cid):
        return next(c for c in datos["conceptos"] if c["id"] == cid)

    def test_el_curso_pasa(self):
        self.assertEqual(self.errores(mapa=self.mapa), [])

    def test_prerrequisito_que_llega_despues(self):
        d = copy.deepcopy(self.datos)
        self.concepto(d, "senal")["prerrequisitos"].append("cuaternion")
        self.assertTrue(any("«senal»" in e and "«cuaternion»" in e for e in self.errores(d)))

    def test_concepto_fuera_del_indice(self):
        indice = self.indice.replace("`nyquist`", "", 1)
        self.assertTrue(any("«nyquist» no está en ningún capítulo" in e for e in self.errores(indice=indice)))

    def test_termino_antes_de_tiempo(self):
        titulo = next(l for l in self.indice.splitlines() if l.startswith("## Capítulo 0 · "))
        indice = self.indice.replace(titulo, titulo + "\n\nGuardamos el giro en un Cuaternión.", 1)
        self.assertTrue(any("«cuaternión»" in e and "cap. 0" in e for e in self.errores(indice=indice)))

    def test_termino_partido_en_dos_lineas(self):
        titulo = next(l for l in self.indice.splitlines() if l.startswith("## Capítulo 1 · "))
        indice = self.indice.replace(titulo, titulo + "\n\nSin zona\nmuerta.", 1)
        self.assertTrue(any("«zona muerta» (partido" in e for e in self.errores(indice=indice)))

    def test_el_codigo_no_cuenta_como_prosa(self):
        titulo = next(l for l in self.indice.splitlines() if l.startswith("## Capítulo 0 · "))
        indice = self.indice.replace(titulo, titulo + "\n\nVer `cuaternión` en [la fuente](../cuaterniones.md).", 1)
        self.assertEqual(self.errores(indice=indice), [])

    def test_funcion_sin_concepto(self):
        d = copy.deepcopy(self.datos)
        d["inventario"].append({"id": "server/web/wrist.js:loadHand", "que_hace": "lee la mano guardada"})
        self.assertTrue(any("ningún concepto cubre server/web/wrist.js:loadHand" in e for e in self.errores(d)))

    def test_funcion_que_no_existe(self):
        d = copy.deepcopy(self.datos)
        d["inventario"].append({"id": "server/web/wrist.js:noExiste", "que_hace": "nada"})
        self.concepto(d, "roll")["codigo"].append("server/web/wrist.js:noExiste")
        self.assertTrue(any("no define «noExiste»" in e for e in self.errores(d)))

    def test_enlace_roto(self):
        indice = self.indice + "\n[otro lado](#no-existe)\n"
        self.assertTrue(any("#no-existe" in e for e in self.errores(indice=indice)))

    def test_apendice_al_capitulo_equivocado(self):
        indice = self.indice + "\n| 99 | prueba | cap. 0 · `cuaternion` |\n"
        self.assertTrue(any("«cuaternion»" in e and "apéndice" in e for e in self.errores(indice=indice)))

    def test_mapa_viejo(self):
        self.assertTrue(any("mapa.md no está al día" in e for e in self.errores(mapa=self.mapa + "\nviejo\n")))


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description="Comprueba el mapa del curso (docs/curso/) y genera mapa.md.")
    ap.add_argument("--escribir", action="store_true", help="rehace docs/curso/mapa.md antes de comprobar")
    ap.add_argument("--prueba", action="store_true", help="corre la prueba del comprobador")
    args = ap.parse_args()
    if args.prueba:
        r = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Prueba))
        sys.exit(0 if r.wasSuccessful() else 1)
    datos, indice, mapa = cargar()
    if args.escribir:
        mapa = generar_mapa(datos, indice)
        (CURSO / "mapa.md").write_text(mapa, encoding="utf-8", newline="\n")
        emit("escrito docs/curso/mapa.md")
    errores, notas = revisar(datos, indice, mapa)
    for n in notas:
        emit(f"nota: {n}")
    if errores:
        for e in errores:
            emit(f"MAL  {e}")
        emit(f"\n{len(errores)} problemas")
        sys.exit(1)
    caps, _ = leer_indice(indice)
    emit(f"bien: {len(datos['conceptos'])} conceptos en {len(caps)} capítulos, en orden; glosario sin términos "
         f"adelantados; {len(datos['inventario'])} funciones, todas cubiertas{'' if notas else ' y encontradas'}; "
         f"mapa.md al día")


if __name__ == "__main__":
    main()
