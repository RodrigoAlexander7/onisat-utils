#!/usr/bin/env python3
"""
CanSat TX - Transmisión de imágenes JPEG progresivo
"""

import sys
import numpy as np
from PIL import Image, ImageFile
from io import BytesIO
import serial
import struct
import time
import os

# Permitir cargar imágenes truncadas
ImageFile.LOAD_TRUNCATED_IMAGES = True

# ============================================
# CONFIGURACIÓN
# ============================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_FILE = os.path.join(SCRIPT_DIR, '../../imgs/img1b.jpg')  # imagen side-by-side
OUTPUT_DIR = os.path.join(SCRIPT_DIR, './imgs/estereoscopic_generated')
PORT = '/dev/ttyUSB0'
BAUD = 9600

# Resolución y calidad
WIDTH = 256
HEIGHT = 155
JPEG_QUALITY = 50

# Protocolo
CHUNK_SIZE = 100
HEADER_SIZE = 5                 # ImgID(1B) + SeqNum(2B) + TotalChunks(2B)
PAYLOAD_SIZE = CHUNK_SIZE - HEADER_SIZE

METHOD = "JPEG PROGRESIVO"

# ============================================
# FUNCIONES
# ============================================

def create_anaglyph(left_img, right_img):
    """Crea imagen anaglifo rojo-azul desde dos imágenes."""
    left_arr = np.array(left_img, dtype=np.uint8)
    right_arr = np.array(right_img, dtype=np.uint8)

    anaglyph = np.zeros_like(left_arr)
    anaglyph[:, :, 0] = left_arr[:, :, 0]
    anaglyph[:, :, 1] = right_arr[:, :, 1]
    anaglyph[:, :, 2] = right_arr[:, :, 2]

    return Image.fromarray(anaglyph)

def load_and_process_image(filename, width, height, quality):
    """Carga imagen side-by-side, crea anaglifo 3D y comprime a JPEG progresivo."""
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

    # Guardar anaglifo PNG
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    nombre = f'anaglyph_{int(time.time())}.png'
    output_path = os.path.join(OUTPUT_DIR, nombre)
    anaglyph_img.save(output_path)

    # Comprimir a JPEG progresivo
    t_start = time.time()
    buffer = BytesIO()
    anaglyph_img.save(
        buffer,
        format='JPEG',
        quality=quality,
        progressive=True,
        optimize=True
    )
    jpeg_bytes = buffer.getvalue()
    t_encode = time.time() - t_start

    return jpeg_bytes, output_path, t_generation, t_encode

def fragment_image(jpeg_data, img_id=0):
    """Fragmenta JPEG en chunks con header de control."""
    t_start = time.time()

    total_bytes = len(jpeg_data)
    total_chunks = (total_bytes + PAYLOAD_SIZE - 1) // PAYLOAD_SIZE

    chunks = []
    for seq in range(total_chunks):
        start = seq * PAYLOAD_SIZE
        end = min(start + PAYLOAD_SIZE, total_bytes)
        payload = jpeg_data[start:end]

        if len(payload) < PAYLOAD_SIZE:
            payload += b'\x00' * (PAYLOAD_SIZE - len(payload))

        header = struct.pack('BHH', img_id, seq, total_chunks)
        chunks.append(header + payload)

    t_fragment = time.time() - t_start
    return chunks, t_fragment

def send_chunks(port, baud, chunks):
    """Envía chunks por XBee."""
    t_start = time.time()
    total_chunks = len(chunks)

    with serial.Serial(port, baud, timeout=0.1) as ser:
        for i, chunk in enumerate(chunks):
            ser.write(chunk)
            time.sleep(0.002)

            if (i + 1) % 50 == 0 or (i + 1) == total_chunks:
                print(f"  TX: {i+1}/{total_chunks} chunks ({(i+1)*100//total_chunks}%)")

    t_tx = time.time() - t_start
    return t_tx

# ============================================
# MAIN
# ============================================

def main():
    print(f"={'='*50}")
    print(f"  CANSAT TX - {METHOD}")
    print(f"={'='*50}")
    print(f"  Puerto:     {PORT} @ {BAUD} bps")
    print(f"  Resolución: {WIDTH}x{HEIGHT}")
    print(f"  Compresión: JPEG Q{JPEG_QUALITY} progresivo")
    print(f"  Chunk:      {CHUNK_SIZE} bytes ({PAYLOAD_SIZE} payload + {HEADER_SIZE} header)")
    print(f"={'='*50}\n")

    try:
        # 1. Procesar imagen
        jpeg_data, output_path, t_gen, t_enc = load_and_process_image(
            IMAGE_FILE, WIDTH, HEIGHT, JPEG_QUALITY
        )

        print(f"[1/3] Imagen procesada")
        print(f"  Anaglifo:    {t_gen*1000:.1f} ms")
        print(f"  Encoding:    {t_enc*1000:.1f} ms")
        print(f"  Tamaño TX:   {len(jpeg_data):,} bytes")
        print(f"  Guardado:    {output_path}\n")

        # 2. Fragmentar
        chunks, t_frag = fragment_image(jpeg_data, img_id=0)
        print(f"[2/3] Fragmentado: {len(chunks)} chunks en {t_frag*1000:.1f} ms\n")

        # 3. Transmitir
        print(f"[3/3] Transmitiendo {len(chunks)} chunks...")
        t_trans = send_chunks(PORT, BAUD, chunks)
        total_tx_bytes = len(chunks) * CHUNK_SIZE
        throughput = total_tx_bytes / t_trans
        print()

    except FileNotFoundError:
        print(f"[ERROR] Imagen no encontrada: {IMAGE_FILE}")
        return 1
    except Exception as e:
        print(f"[ERROR] {e}")
        return 1

    # Resumen
    t_total = t_gen + t_enc + t_frag + t_trans
    print(f"={'='*50}")
    print(f"  RESUMEN - {METHOD}")
    print(f"={'='*50}")
    print(f"  Anaglifo:      {t_gen*1000:.1f} ms")
    print(f"  Encoding:      {t_enc*1000:.1f} ms")
    print(f"  Fragmentación: {t_frag*1000:.1f} ms")
    print(f"  Transmisión:   {t_trans:.2f} s")
    print(f"  ------------------------------------")
    print(f"  TOTAL:         {t_total:.2f} s")
    print(f"  Throughput:    {throughput:.0f} bytes/s ({throughput*8/1000:.1f} kbps)")
    print(f"  Tamaño TX:     {len(jpeg_data):,} bytes (payload útil)")
    print(f"  Overhead TX:   {total_tx_bytes:,} bytes (con headers)")
    print(f"  Chunks:        {len(chunks)}")
    print(f"  Calidad:       JPEG Q{JPEG_QUALITY} (16M colores)")
    print(f"={'='*50}")

    return 0

if __name__ == '__main__':
    exit(main())