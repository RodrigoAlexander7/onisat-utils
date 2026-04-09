import serial
import numpy as np
from PIL import Image
import os
import time

# --- CONFIGURACIÓN ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'imgs/received')
PORT = '/dev/ttyUSB0'
BAUD = 9600
WIDTH = 256
HEIGHT = 155
EXPECTED_BYTES = WIDTH * HEIGHT

METHOD = "RAW (RGB332)"

# --- FUNCIONES ---
def rgb332_to_rgb(byte_val):
    """Convierte RGB332 (8 bits) a RGB (24 bits)."""
    r = ((byte_val >> 5) & 0x07) << 5
    g = ((byte_val >> 2) & 0x07) << 5
    b = (byte_val & 0x03) << 6
    return r, g, b

def recibir_imagen():
    """Recibe imagen por puerto serial."""
    data = []

    with serial.Serial(PORT, BAUD, timeout=2) as ser:
        ser.reset_input_buffer()
        inicio = time.time()
        ultimo_byte = time.time()

        print(f"  Esperando datos...\n")

        while len(data) < EXPECTED_BYTES:
            if ser.in_waiting > 0:
                chunk = ser.read(min(ser.in_waiting, EXPECTED_BYTES - len(data)))
                data.extend(chunk)
                ultimo_byte = time.time()

                received = len(data)
                if received % 5000 == 0 or received == EXPECTED_BYTES:
                    print(f"  RX: {received}/{EXPECTED_BYTES} bytes ({received*100//EXPECTED_BYTES}%)")

            # Timeouts
            tiempo_sin_datos = time.time() - ultimo_byte
            if len(data) == 0 and tiempo_sin_datos > 60:
                print(f"  [TIMEOUT] Sin datos en 60s")
                return None, None
            elif len(data) > 0 and tiempo_sin_datos > 10:
                print(f"  [TIMEOUT] Transmisión interrumpida: {len(data)}/{EXPECTED_BYTES} bytes")
                return None, None

            time.sleep(0.01)

        t_rx = time.time() - inicio
        print(f"\n  Recepción completa en {t_rx:.1f}s")

    return data, t_rx

def reconstruir_imagen(data):
    """Reconstruye imagen RGB desde datos RGB332."""
    t_start = time.time()

    img = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    for i, byte in enumerate(data):
        fila = i // WIDTH
        col = i % WIDTH
        img[fila, col] = rgb332_to_rgb(byte)

    t_rebuild = time.time() - t_start
    return Image.fromarray(img), t_rebuild

def guardar_imagen(imagen):
    """Guarda la imagen recibida."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    nombre = f'received_{int(time.time())}.png'
    ruta = os.path.join(OUTPUT_DIR, nombre)
    imagen.save(ruta)
    return ruta

# --- MAIN ---
def main():
    print(f"={'='*50}")
    print(f"  CANSAT RX - {METHOD}")
    print(f"={'='*50}")
    print(f"  Puerto:     {PORT} @ {BAUD} bps")
    print(f"  Resolución: {WIDTH}x{HEIGHT}")
    print(f"  Esperando:  {EXPECTED_BYTES:,} bytes")
    print(f"={'='*50}")
    print()
    print(f"  1. Ejecutar ESTE script PRIMERO")
    print(f"  2. Luego ejecutar raw.py en la Raspberry")
    print(f"={'='*50}\n")

    try:
        # 1. Recibir datos
        print(f"[1/3] Recibiendo...")
        result = recibir_imagen()

        if result[0] is None:
            print(f"[ERROR] No se recibieron datos")
            return 1

        data, t_rx = result

        # 2. Reconstruir imagen
        print(f"\n[2/3] Reconstruyendo imagen...")
        imagen, t_rebuild = reconstruir_imagen(data)
        print(f"  Reconstrucción: {t_rebuild*1000:.1f} ms")

        # 3. Guardar
        ruta = guardar_imagen(imagen)
        print(f"\n[3/3] Imagen guardada: {ruta}")

        # Resumen
        throughput = len(data) / t_rx if t_rx > 0 else 0

        print(f"\n={'='*50}")
        print(f"  RESUMEN - {METHOD}")
        print(f"={'='*50}")
        print(f"  Recepción:     {t_rx:.2f} s")
        print(f"  Reconstrucción:{t_rebuild*1000:.1f} ms")
        print(f"  ------------------------------------")
        print(f"  Throughput:    {throughput:.0f} bytes/s ({throughput*8/1000:.1f} kbps)")
        print(f"  Bytes:         {len(data):,} recibidos")
        print(f"  Calidad:       256 colores (8 bpp)")
        print(f"={'='*50}")

    except KeyboardInterrupt:
        print('\n\nCancelado por el usuario')
    except Exception as e:
        print(f'[ERROR] {e}')
        return 1

    return 0

if __name__ == '__main__':
    exit(main())
