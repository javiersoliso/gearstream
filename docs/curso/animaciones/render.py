"""Renderiza las animaciones de un capítulo y deja los GIF (y los MP4 con sonido) en docs/curso/media/<capítulo>/.

    python docs/curso/animaciones/render.py                 # capítulo 11, todas las escenas
    python docs/curso/animaciones/render.py cap08           # capítulo 8
    python docs/curso/animaciones/render.py cap11 Enrollar  # una escena

Necesita manim (pip install manim), ffmpeg y LaTeX (MiKTeX o TeX Live) en el PATH; casi todos los capítulos, también node, y el 6 y el 12, scipy. Los videos intermedios quedan en
docs/curso/animaciones/media/, que no se sube.
"""
import os
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
MEDIA = os.path.join(AQUI, "media")
ESCENAS = {
    "cap00": ["Senal", "Unidades", "Muestreo", "MarcaDeTiempo", "InterpolacionLineal", "Cuantizar", "LecturasNuevas",
             "ResumirVentana", "Latencia", "AlinearRelojes", "AgruparMuestras"],
    "cap01": ["EjesDelReloj", "Acelerometro", "Giroscopio", "SensorDeGravedad", "Ruido", "TamanoTipico", "Varianza", "Sesgo",
             "Umbral", "AprenderSesgo"],
    "cap02": ["UnVector", "LargoDeUnVector", "VectorUnitario", "SenoYCoseno", "PorQueAtan2", "AngulosQueDanLaVuelta",
             "ProductoPunto", "PuntoEsCoseno", "ProductoCruz", "ReglaManoDerecha", "MarcoDeReferencia", "CoordenadasEnUnaBase",
             "CambioDeMarco", "SeisCaras"],
    "cap03": ["DerivarConNumeros", "SegundaDiferencia", "IntegrarConNumeros", "ComoSeEscriben", "ErrorAcumulado", "DosVecesIntegrar",
             "VelocidadCero", "Suavizar", "LaExponencial", "DerivarAmplificaRuido", "QuitarLoLento", "CurvaSuave", "UnaOnda",
             "IntegrarUnaOnda"],
    "cap04": ["QueMideElAcelerometro", "ArribaSinIntegrar", "SeisPosturas", "InclinacionConSigno",
             "AceleracionLineal", "BrazoColgando", "LoQueNoVe"],
    "cap05": ["RotarEnElPlano", "ProductoDeMatrices", "EjeYAngulo", "TodoGiroEsUnEje", "MatrizDeRotacion", "OrdenNoConmuta",
             "VelocidadAngular", "PuntoQueGira", "VistoDesdeElReloj", "AngulosDeEuler", "Singularidad", "Cuaternion",
             "IntegrarOrientacion"],
    "cap06": ["AntebrazoEsEjeX", "Roll", "Pitch", "Yaw", "BaseTorcida", "CasiVertical", "AtornillarNoMueveElCursor",
             "ManoEquivocada", "TresFlechas"],
    "cap07": ["ArcoDTheta", "RayoTangente", "DosAngulos", "Ganancia", "Recortar", "Subpixel", "ZonaMuerta",
             "CurvaDeAceleracion", "Filtro1Euro", "MapaLineal", "Potencias", "LeyDeFitts"],
    "cap08": ["DosTestigos", "Resorte", "Valle", "GravedadNoVeRumbo", "Triad", "MetodoDeProyeccion", "Mahony",
             "DerivaDelRumbo", "Recentrar"],
    "cap09": ["Esqueleto", "CinematicaDirecta", "Trayectorias", "Probabilidad", "LeyDeCosenos", "CinematicaInversa", "FabricarRuido",
             "SintetizarIMU", "PruebaConVerdad", "AceleracionDeUnPunto", "LimitesDelCuerpo", "Verosimilitud",
             "FiltroDeParticulas", "Remuestreo"],
    "cap10": ["DetectarUnPico", "DosUmbrales", "PeriodoRefractario", "UmbralQueSeAdapta", "DominanciaDeUnEje",
             "ClicDeTornillo", "ToqueEnLaEsfera", "ElEmpujon", "LaSacudida", "ClicPorPermanencia",
             "ScrollConElAntebrazo", "ElTempo", "AciertosYFalsasAlarmas", "MuestrasDeUnGolpe", "ElAUC"],
    "cap11": ["SumaDeSenos", "FlechaQueGira", "ElNumeroI", "Enrollar", "Fuga", "FrecuenciaDominante", "RespuestaH", "RetrasoPorCorrelacion", "Remanente",
             "Nyquist", "RitmoYArmonia", "Octavas"],
    "cap12": ["LetrasRedibujadas", "LoQueVeElReloj", "Rasgos", "Segmentar", "Estandarizar", "MinimosCuadrados", "LaSombraDeV",
             "RCuadrado", "Sobreajuste", "PruebaJusta", "Retardos", "RidgeCastigo", "ControlLambda",
             "PredecirVelocidad", "DescensoPorGradiente", "RedNeuronal", "MasDatos", "ParecidoDeForma", "CuantoCreo",
             "VecinosCercanos", "MatrizDeConfusion", "FDeAnova", "OtraPersona"],
}
CON_SONIDO = {"RitmoYArmonia", "Octavas"}
CALIDAD = ("-qm", "720p30")       # manim escribe en media/videos/<archivo>/720p30/


def gif(mp4, salida, ancho=560, fps=12):
    filtro = (f"fps={fps},scale={ancho}:-1:flags=lanczos,split[a][b];"
              "[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-filter_complex", filtro, "-loop", "0", salida], check=True)


def main():
    cap = sys.argv[1] if len(sys.argv) > 1 else "cap11"
    escenas = sys.argv[2:] or ESCENAS[cap]
    destino = os.path.join(AQUI, "..", "media", cap)
    os.makedirs(destino, exist_ok=True)
    for escena in escenas:
        print(f"== {escena}", flush=True)
        subprocess.run([sys.executable, "-m", "manim", CALIDAD[0], "--media_dir", MEDIA, "--disable_caching",
                        os.path.join(AQUI, f"{cap}.py"), escena], check=True)
        mp4 = os.path.join(MEDIA, "videos", cap, CALIDAD[1], f"{escena}.mp4")
        gif(mp4, os.path.join(destino, f"{escena}.gif"))
        if escena in CON_SONIDO:
            shutil.copyfile(mp4, os.path.join(destino, f"{escena}.mp4"))
        tam = os.path.getsize(os.path.join(destino, f"{escena}.gif")) / 1e6
        print(f"   {escena}.gif: {tam:.1f} MB", flush=True)


if __name__ == "__main__":
    main()
