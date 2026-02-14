#!/usr/bin/env python3
"""
CanSat RX - Receptor de imágenes JPEG progresivo
Recibe chunks con header [ImgID(1B) | SeqNum(2B) | TotalChunks(2B)]
"""

import struct
import serial
import time
import os

# --- CONFIGURACIÓN ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'imgs/received')
PORT = '/dev/ttyUSB0'
BAUD = 9600

# Protocolo (debe coincidir con el transmisor)
CHUNK_SIZE = 100
HEADER_SIZE = 5                 # ImgID(1B) + SeqNum(2B) + TotalChunks(2B)
PAYLOAD_SIZE = CHUNK_SIZE - HEADER_SIZE

METHOD = "JPEG PROGRESIVO"

# --- FUNCIONES ---
def recibir_chunks():
    """Recibe chunks JPEG por puerto serial y los reensambla."""
    total_chunks = None
    chunks_received = {}
    img_id = None

    with serial.Serial(PORT, BAUD, timeout=2) as ser:
        # Limpiar buffer agresivamente
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(0.5)  # Dar tiempo al hardware
        ser.reset_input_buffer()  # Limpiar de nuevo
        
        inicio = time.time()
        ultimo_dato = time.time()

        print(f"  Esperando datos...\n")

        buffer = bytearray()
        chunks_totalmente_invalidos = 0

        while True:
            # Leer datos disponibles
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                buffer.extend(data)
                ultimo_dato = time.time()
            
            # Procesar chunks completos del buffer
            while len(buffer) >= CHUNK_SIZE:
                raw = bytes(buffer[:CHUNK_SIZE])
                buffer = buffer[CHUNK_SIZE:]
                
                # Verificar que recibimos exactamente el tamaño esperado
                if len(raw) != CHUNK_SIZE:
                    print(f"  [WARNING] Chunk incompleto: {len(raw)}/{CHUNK_SIZE} bytes")
                    continue

                # Parsear header con formato explícito (sin padding)
                try:
                    h_img_id, h_seq, h_total = struct.unpack('<BHH', raw[:HEADER_SIZE])
                    payload = raw[HEADER_SIZE:]
                    
                    # Debug del primer chunk
                    if total_chunks is None:
                        print(f"  [DEBUG] Chunk recibido:")
                        print(f"    Header bytes: {raw[:HEADER_SIZE].hex()}")
                        print(f"    img_id={h_img_id}, seq={h_seq}, total={h_total}")
                    
                except struct.error as e:
                    print(f"  [ERROR] Error parsing header: {e}")
                    print(f"  Raw bytes received: {len(raw)}, expected: {CHUNK_SIZE}")
                    continue

                # Primer chunk: inicializar y validar
                if total_chunks is None:
                    # Validar que el chunk sea válido (seq=0, total>0)
                    if h_total == 0 or h_seq != 0:
                        chunks_totalmente_invalidos += 1
                        if chunks_totalmente_invalidos > 10:
                            print(f"  [ERROR] Demasiados chunks inválidos. Abortando.")
                            return None, None, None
                        print(f"  [WARNING] Chunk inválido ignorado (seq debe ser 0, total>0)")
                        continue
                    
                    total_chunks = h_total
                    img_id = h_img_id
                    print(f"  Imagen #{img_id}: {total_chunks} chunks esperados")
                    chunks_totalmente_invalidos = 0  # Reset contador
                
                # Validar que el chunk pertenece a la misma imagen
                if h_img_id != img_id:
                    print(f"  [WARNING] img_id incorrecto: esperado {img_id}, recibido {h_img_id}. Ignorando.")
                    continue
                
                # Validar secuencia
                if h_seq >= total_chunks:
                    print(f"  [WARNING] seq fuera de rango: {h_seq} >= {total_chunks}. Ignorando.")
                    continue

                # Guardar chunk (sin duplicados)
                if h_seq not in chunks_received:
                    chunks_received[h_seq] = payload

                ultimo_dato = time.time()
                received = len(chunks_received)

                if received % 25 == 0 or received == total_chunks:
                    print(f"  RX: {received}/{total_chunks} chunks ({received*100//total_chunks}%)")

                # Completo
                if received >= total_chunks:
                    t_rx = time.time() - inicio
                    print(f"\n  Recepción completa en {t_rx:.1f}s")
                    return chunks_received, total_chunks, t_rx

            # Timeouts
            tiempo_sin_datos = time.time() - ultimo_dato
            if total_chunks is None and tiempo_sin_datos > 60:
                print(f"  [TIMEOUT] Sin datos en 60s")
                return None, None, None
            elif total_chunks is not None and tiempo_sin_datos > 15:
                received = len(chunks_received)
                print(f"\n  [TIMEOUT] Transmisión interrumpida: {received}/{total_chunks} chunks")
                return chunks_received, total_chunks, time.time() - inicio

            time.sleep(0.01)

def reconstruir_jpeg(chunks_received, total_chunks):
    """Reensambla los chunks en datos JPEG."""
    t_start = time.time()

    jpeg_data = bytearray()
    perdidos = []

    for seq in range(total_chunks):
        if seq in chunks_received:
            jpeg_data.extend(chunks_received[seq])
        else:
            perdidos.append(seq)
            # Rellenar con ceros (la imagen tendrá artefactos pero no crashea)
            jpeg_data.extend(b'\x00' * PAYLOAD_SIZE)

    # Eliminar padding del último chunk (buscar fin de JPEG: FFD9)
    # JPEG siempre termina con 0xFFD9
    end_marker = jpeg_data.rfind(b'\xff\xd9')
    if end_marker != -1:
        jpeg_data = jpeg_data[:end_marker + 2]

    t_rebuild = time.time() - t_start
    return bytes(jpeg_data), perdidos, t_rebuild

def guardar_imagen(jpeg_data):
    """Guarda los datos JPEG como archivo."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    nombre = f'received_{int(time.time())}.jpg'
    ruta = os.path.join(OUTPUT_DIR, nombre)
    with open(ruta, 'wb') as f:
        f.write(jpeg_data)
    return ruta

# --- MAIN ---
def main():
    print(f"={'='*50}")
    print(f"  CANSAT RX - {METHOD}")
    print(f"={'='*50}")
    print(f"  Puerto:     {PORT} @ {BAUD} bps")
    print(f"  Chunk:      {CHUNK_SIZE} bytes ({PAYLOAD_SIZE} payload + {HEADER_SIZE} header)")
    print(f"={'='*50}")
    print()
    print(f"  1. Ejecutar ESTE script PRIMERO")
    print(f"  2. Luego ejecutar progresive.py en la Raspberry")
    print(f"={'='*50}\n")

    try:
        # 1. Recibir chunks
        print(f"[1/3] Recibiendo...")
        chunks_received, total_chunks, t_rx = recibir_chunks()

        if chunks_received is None:
            print(f"[ERROR] No se recibieron datos")
            return 1

        received = len(chunks_received)

        # 2. Reconstruir JPEG
        print(f"\n[2/3] Reconstruyendo imagen...")
        jpeg_data, perdidos, t_rebuild = reconstruir_jpeg(chunks_received, total_chunks)

        if perdidos:
            print(f"  Chunks perdidos: {len(perdidos)}/{total_chunks} ({len(perdidos)*100//total_chunks}%)")
        else:
            print(f"  Sin pérdidas")

        # 3. Guardar
        ruta = guardar_imagen(jpeg_data)
        print(f"\n[3/3] Imagen guardada: {ruta}")

        # Resumen
        total_rx_bytes = received * CHUNK_SIZE
        throughput = total_rx_bytes / t_rx if t_rx > 0 else 0

        print(f"\n={'='*50}")
        print(f"  RESUMEN - {METHOD}")
        print(f"={'='*50}")
        print(f"  Recepción:     {t_rx:.2f} s")
        print(f"  Reconstrucción:{t_rebuild*1000:.1f} ms")
        print(f"  ------------------------------------")
        print(f"  Throughput:    {throughput:.0f} bytes/s ({throughput*8/1000:.1f} kbps)")
        print(f"  Chunks:        {received}/{total_chunks} recibidos")
        print(f"  Perdidos:      {len(perdidos)}")
        print(f"  Tamaño JPEG:   {len(jpeg_data):,} bytes")
        print(f"={'='*50}")

    except KeyboardInterrupt:
        print('\n\nCancelado por el usuario')
    except Exception as e:
        print(f'[ERROR] {e}')
        return 1

    return 0

if __name__ == '__main__':
    exit(main())
