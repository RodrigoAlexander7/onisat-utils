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
IMAGE_FILE = os.path.join(SCRIPT_DIR, '../../imgs/img1b.jpg')  # imagen side-by-side
OUTPUT_DIR = os.path.join(SCRIPT_DIR, './imgs/estereoscopic_generated')
PORT = '/dev/ttyUSB0'
BAUD = 9600
WIDTH = 256
HEIGHT = 155
GENERATE_HEADER = False
HEADER_NAME = 'imagen_rgb332.h'

METHOD = "RAW (RGB332)"

# --- FUNCIONES ---
def create_anaglyph(left_img, right_img):
    """Crea imagen anaglifo rojo-azul desde dos imágenes."""
    left_arr = np.array(left_img, dtype=np.uint8)
    right_arr = np.array(right_img, dtype=np.uint8)

    anaglyph = np.zeros_like(left_arr)
    anaglyph[:, :, 0] = left_arr[:, :, 0]
    anaglyph[:, :, 1] = right_arr[:, :, 1]
    anaglyph[:, :, 2] = right_arr[:, :, 2]

    return Image.fromarray(anaglyph)

def process_image(filename, width, height):
    """Procesa imagen side-by-side, crea anaglifo 3D y convierte a RGB332."""
    t_start = time.time()

    img = Image.open(filename).convert('RGB')
    img_width, img_height = img.size

    half_width = img_width // 2
    left_img = img.crop((0, 0, half_width, img_height))
    right_img = img.crop((half_width, 0, img_width, img_height))

    left_img = left_img.resize((width, height), Image.Resampling.BILINEAR)
    right_img = right_img.resize((width, height), Image.Resampling.BILINEAR)

    anaglyph_img = create_anaglyph(left_img, right_img)
    t_generation = time.time() - t_start

    # Convertir a RGB332
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
    t_start = time.time()
    with serial.Serial(port, baud, timeout=2) as ser:
        total = len(data)
        for i, b in enumerate(data):
            ser.write(bytes([b]))
            if (i + 1) % 5000 == 0 or i + 1 == total:
                print(f"  TX: {i+1}/{total} bytes ({(i+1)*100//total}%)")
    t_transmission = time.time() - t_start
    return t_transmission

# --- MAIN ---
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"={'='*50}")
    print(f"  CANSAT TX - {METHOD}")
    print(f"={'='*50}")
    print(f"  Puerto:     {PORT} @ {BAUD} bps")
    print(f"  Resolución: {WIDTH}x{HEIGHT}")
    print(f"  Compresión: RGB332 (8 bpp)")
    print(f"={'='*50}\n")

    # 1. Procesar imagen
    try:
        data, anaglyph_img, t_gen, t_comp = process_image(IMAGE_FILE, WIDTH, HEIGHT)

        nombre = f'anaglyph_{int(time.time())}.png'
        output_path = os.path.join(OUTPUT_DIR, nombre)
        anaglyph_img.save(output_path)

        print(f"[1/3] Imagen procesada")
        print(f"  Anaglifo:    {t_gen*1000:.1f} ms")
        print(f"  Compresión:  {t_comp*1000:.1f} ms")
        print(f"  Tamaño TX:   {len(data):,} bytes")
        print(f"  Guardado:    {output_path}\n")
    except Exception as e:
        print(f"[ERROR] Procesando imagen: {e}")
        sys.exit(1)

    # 2. Header C (opcional)
    if GENERATE_HEADER:
        try:
            out = generate_header_bytes(data, WIDTH, HEIGHT, HEADER_NAME)
            print(f"[OPT] Header C generado: {out}\n")
        except Exception as e:
            print(f"[ERROR] Generando header: {e}")

    # 3. Transmitir
    try:
        print(f"[2/3] Transmitiendo {len(data):,} bytes...")
        t_trans = send_via_serial(PORT, BAUD, data)
        throughput = len(data) / t_trans
        print(f"\n[3/3] Transmisión completa\n")
    except Exception as e:
        print(f"[ERROR] Transmisión: {e}")
        sys.exit(1)

    # Resumen
    t_total = t_gen + t_comp + t_trans
    print(f"={'='*50}")
    print(f"  RESUMEN - {METHOD}")
    print(f"={'='*50}")
    print(f"  Anaglifo:      {t_gen*1000:.1f} ms")
    print(f"  Compresión:    {t_comp*1000:.1f} ms")
    print(f"  Transmisión:   {t_trans:.2f} s")
    print(f"  ------------------------------------")
    print(f"  TOTAL:         {t_total:.2f} s")
    print(f"  Throughput:    {throughput:.0f} bytes/s ({throughput*8/1000:.1f} kbps)")
    print(f"  Tamaño TX:     {len(data):,} bytes")
    print(f"  Calidad:       256 colores (8 bpp)")
    print(f"={'='*50}")

if __name__ == '__main__':
    main()