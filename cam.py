import subprocess
import time
import os
import threading

# Configuración de dispositivos (Asegúrate de que estos sean los correctos)
dispositivo = "/dev/video4"


def config_camera(dispositivo):
    """Configura la cámara para evitar barrido por movimiento"""
    try:
        # 1. Forzar exposición manual
        subprocess.run(
            ["v4l2-ctl", "-d", dispositivo, "-c", "auto_exposure=1"], check=True
        )
        # 2. Ajustar exposición (ajusta este valor según la luz de tu ambiente)
        # Un valor menor = menos borroso, pero más oscuro.
        subprocess.run(
            ["v4l2-ctl", "-d", dispositivo, "-c", "exposure_time_absolute=300"],
            check=True,
        )
        print(f"{dispositivo} configurado con obturacion manual.")
    except Exception as e:
        print(f"No se pudo configurar {dispositivo}: {e}")


def capturar_individual(dispositivo, nombre_archivo):
    """Función para ser ejecutada en un hilo independiente"""
    try:
        comando = [
            "fswebcam",
            "-d",
            dispositivo,
            "-r",
            "2560x720",
            "--skip",
            "20",
            "--no-banner",
            nombre_archivo,
        ]
        subprocess.run(
            comando,
            check=True,  # , stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return True
    except Exception as e:
        print(f"Error en {dispositivo}: {e}")
        return False


def tomar_par_estereo(indice):
    timestamp = time.strftime("%H%M%S")
    ruta_L = f"fotos_prueba/L_{indice}_{timestamp}.jpg"

    # Creamos dos hilos para disparar las cámaras al "mismo" tiempo
    hilo_L = threading.Thread(target=capturar_individual, args=(dispositivo, ruta_L))

    hilo_L.start()

    # Esperamos a que ambos terminen
    hilo_L.join()

    print(f"✅ Par {indice} capturado (L y R).")


# --- Lógica Principal ---
if not os.path.exists("fotos_prueba"):
    os.makedirs("fotos_prueba")

config_camera(dispositivo)

TOTAL_FOTOS = 3
INTERVALO = 3

for i in range(1, TOTAL_FOTOS + 1):
    tomar_par_estereo(i)
    if i < TOTAL_FOTOS:
        print(f"Esperando {INTERVALO} segundos...")
        time.sleep(INTERVALO)
