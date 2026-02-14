import sys
import serial
import numpy as np
from PIL import Image, ImageFile
import os
import time

# Permitir cargar imágenes truncadas
ImageFile.LOAD_TRUNCATED_IMAGES = True

# --- CONFIGURACIÓN ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_FILE = os.path.join(SCRIPT_DIR, '../imgs/img1b.jpg')  # imagen side-by-side
OUTPUT_DIR = os.path.join(SCRIPT_DIR, '../imgs/estereoscopic')
PORT = '/dev/ttyS0'            # puerto serie del XBee
BAUD = 9600                      # velocidad en baudios
WIDTH = 256                      # ancho deseado del anaglifo (px)
HEIGHT = 155                     # alto deseado del anaglifo (px)
GENERATE_HEADER = False          # true para crear archivo .h con bytes
HEADER_NAME = 'imagen_rgb332.h'

# --- FUNCIONES ---
def rgb_to_rgb332(r, g, b):
    """Convierte un color de 24 bits (8-8-8) a 8 bits (RRRGGGBB)."""
    r3 = (r >> 5) & 0x07
    g3 = (g >> 5) & 0x07
    b2 = (b >> 6) & 0x03
    return (r3 << 5) | (g3 << 2) | b2

def create_anaglyph(left_img, right_img):
    """Crea imagen anaglifo rojo-azul desde dos imágenes (optimizado con numpy)."""
    left_arr = np.array(left_img, dtype=np.uint8)
    right_arr = np.array(right_img, dtype=np.uint8)

    # Anaglifo: R del lado izquierdo, G y B del lado derecho
    anaglyph = np.zeros_like(left_arr)
    anaglyph[:, :, 0] = left_arr[:, :, 0]   # Canal rojo de la izquierda
    anaglyph[:, :, 1] = right_arr[:, :, 1]  # Canal verde de la derecha
    anaglyph[:, :, 2] = right_arr[:, :, 2]  # Canal azul de la derecha

    return Image.fromarray(anaglyph)

def process_image(filename, width, height):
    """Procesa imagen side-by-side, crea anaglifo 3D y convierte a RGB332."""
    # Cargar imagen side-by-side
    img = Image.open(filename).convert('RGB')
    img_width, img_height = img.size

    # Dividir en mitades (left y right)
    half_width = img_width // 2
    left_img = img.crop((0, 0, half_width, img_height))
    right_img = img.crop((half_width, 0, img_width, img_height))

    # Redimensionar antes de crear anaglifo (más eficiente)
    left_img = left_img.resize((width, height), Image.LANCZOS)
    right_img = right_img.resize((width, height), Image.LANCZOS)

    # Crear anaglifo rojo-azul
    t_start = time.time()
    anaglyph_img = create_anaglyph(left_img, right_img)
    t_generation = time.time() - t_start

    # Convertir a RGB332 usando numpy (optimizado)
    t_start = time.time()
    pixels = np.array(anaglyph_img, dtype=np.uint8)
    r = (pixels[:, :, 0] >> 5) & 0x07
    g = (pixels[:, :, 1] >> 5) & 0x07
    b = (pixels[:, :, 2] >> 6) & 0x03
    data = ((r << 5) | (g << 2) | b).flatten().tolist()
    t_compression = time.time() - t_start

    return data, anaglyph_img, t_generation, t_compression

def generate_header_bytes(data, width, height, header_name):
    """Genera un archivo .h con arreglo C tipo PROGMEM."""
    lines = []
    lines.append(f'static const unsigned char image_8bit_RRRGGGBB[{len(data)}] PROGMEM = {{')
    for i, val in enumerate(data):
        if i % width == 0:
            lines.append('\n    ')
        lines[-1] += f'{val:3d}, '
    lines.append('\n};\n')
    with open(header_name, 'w') as f:
        f.write('\n'.join(lines))
    return header_name

def send_via_serial(port, baud, data):
    """Envía los bytes de la imagen comprimida por puerto serial."""
    print(f'Conectando a {port} a {baud} baudios...')
    t_start = time.time()
    with serial.Serial(port, baud, timeout=2) as ser:
        total = len(data)
        for i, b in enumerate(data):
            ser.write(bytes([b]))
            if (i + 1) % 1000 == 0 or i + 1 == total:
                print(f'Enviados {i+1}/{total} bytes')
    t_transmission = time.time() - t_start
    print('Transmisión completa.')
    return t_transmission

# --- MAIN ---
def main():
    # Crear directorio de salida si no existe
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    try:
        data, anaglyph_img, t_gen, t_comp = process_image(IMAGE_FILE, WIDTH, HEIGHT)
        print(f"Anaglifo 3D creado desde '{IMAGE_FILE}' -> {WIDTH}x{HEIGHT}, {len(data)} bytes totales")
        print(f"Generación anaglifo: {t_gen*1000:.2f} ms")
        print(f"Compresión RGB332: {t_comp*1000:.2f} ms")

        # Guardar imagen estereoscópica
        output_path = os.path.join(OUTPUT_DIR, 'anaglifo_3d.png')
        anaglyph_img.save(output_path)
        print(f"Imagen guardada en: {output_path}")
    except Exception as e:
        print('Error procesando imagen:', e)
        sys.exit(1)

    if GENERATE_HEADER:
        try:
            out = generate_header_bytes(data, WIDTH, HEIGHT, HEADER_NAME)
            print(f'Header C generado: {out}')
        except Exception as e:
            print('Error generando header:', e)

    try:
        t_trans = send_via_serial(PORT, BAUD, data)
        print(f" Transmisión: {t_trans:.2f} s ({len(data)/t_trans:.0f} bytes/s)")
        print(f"\n-------------------------")
        print(f"\nRESUMEN DE TIEMPOS:")
        print(f"  Generación: {t_gen*1000:.2f} ms")
        print(f"  Compresión: {t_comp*1000:.2f} ms")
        print(f"  Transmisión: {t_trans:.2f} s")
        print(f"  TOTAL: {(t_gen + t_comp + t_trans):.2f} s")
    except Exception as e:
        print('Error enviando por serial:', e)
        sys.exit(1)

if __name__ == '__main__':
    main()