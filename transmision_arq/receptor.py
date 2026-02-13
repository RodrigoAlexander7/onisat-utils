import serial
import numpy as np
from PIL import Image
import os
import time

# --- CONFIGURACIÓN ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'imgs/received')
PORT = '/dev/ttyUSB0'            # Ajusta según tu sistema (COMx en Windows)
BAUD = 9600                      
WIDTH = 256                      # Debe coincidir con el transmisor
HEIGHT = 155                      # Debe coincidir con el transmisor
EXPECTED_BYTES = WIDTH * HEIGHT  # 5000 bytes

# --- FUNCIONES ---
def rgb332_to_rgb(byte_val):
    """Convierte RGB332 (8 bits) a RGB (24 bits)."""
    r = ((byte_val >> 5) & 0x07) << 5
    g = ((byte_val >> 2) & 0x07) << 5
    b = (byte_val & 0x03) << 6
    return r, g, b

def recibir_imagen():
    """Recibe imagen por puerto serial."""
    print(f'Conectando a {PORT} @ {BAUD} bps...')
    print(f'Esperando {EXPECTED_BYTES} bytes ({WIDTH}x{HEIGHT})...')
    print('ESPERANDO... (ahora ejecuta raw.py en la Raspberry)\n')
    
    data = []
    
    with serial.Serial(PORT, BAUD, timeout=2) as ser:
        ser.reset_input_buffer()
        inicio = time.time()
        ultimo_byte = time.time()
        
        while len(data) < EXPECTED_BYTES:
            if ser.in_waiting > 0:
                chunk = ser.read(min(ser.in_waiting, EXPECTED_BYTES - len(data)))
                data.extend(chunk)
                ultimo_byte = time.time()
                print(f'\rRecibidos: {len(data)}/{EXPECTED_BYTES} bytes ({len(data)*100//EXPECTED_BYTES}%)', end='', flush=True)
            
            # Timeout: 60s esperando primer byte, 10s entre bytes
            tiempo_sin_datos = time.time() - ultimo_byte
            if len(data) == 0 and tiempo_sin_datos > 60:
                print('\n\n✗ Timeout: No se recibieron datos en 60s')
                print('  Verifica:')
                print('  - XBee conectado en ambos lados')
                print('  - Puerto correcto (/dev/ttyUSB0)')
                print('  - Ejecutaste raw.py en la Raspberry DESPUÉS de este script')
                return None
            elif len(data) > 0 and tiempo_sin_datos > 10:
                print(f'\n\n✗ Timeout: Transmisión interrumpida')
                print(f'  Recibidos solo {len(data)}/{EXPECTED_BYTES} bytes')
                return None
            
            time.sleep(0.01)
        
        print(f'\n✓ Completado en {time.time()-inicio:.1f}s\n')
    
    return data

def reconstruir_imagen(data):
    """Reconstruye imagen RGB desde datos RGB332."""
    img = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    
    for i, byte in enumerate(data):
        fila = i // WIDTH
        col = i % WIDTH
        img[fila, col] = rgb332_to_rgb(byte)
    
    return Image.fromarray(img)

def guardar_imagen(imagen):
    """Guarda la imagen recibida."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    nombre = f'received_{int(time.time())}.png'
    ruta = os.path.join(OUTPUT_DIR, nombre)
    imagen.save(ruta)
    return ruta

# --- MAIN ---
def main():
    print("=" * 50)
    print("  RECEPTOR XBEE - IMÁGENES ESTEREOSCÓPICAS")
    print("=" * 50)
    print(f"  Puerto: {PORT}")
    print(f"  Baudios: {BAUD}")
    print(f"  Dimensiones: {WIDTH}x{HEIGHT} px")
    print(f"  Bytes esperados: {EXPECTED_BYTES}")
    print(f"  Tiempo estimado: ~{EXPECTED_BYTES//960}s (@9600bps)")
    print("=" * 50)
    print()
    print("INSTRUCCIONES:")
    print("  1. Este script DEBE ejecutarse PRIMERO")
    print("  2. Luego ejecuta 'python raw.py' en la Raspberry")
    print("=" * 50)
    print()
    
    try:
        # Recibir datos
        data = recibir_imagen()
        if not data:
            print('Error: No se recibieron datos')
            return
        
        # Reconstruir imagen
        print('Reconstruyendo imagen...')
        imagen = reconstruir_imagen(data)
        
        # Guardar
        ruta = guardar_imagen(imagen)
        print(f'✓ Imagen guardada: {ruta}')
        
    except KeyboardInterrupt:
        print('\n\nCancelado por el usuario')
    except Exception as e:
        print(f'\n✗ Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
