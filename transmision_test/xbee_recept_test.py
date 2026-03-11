import serial
import time

# --- CONFIGURACIÓN ---
PUERTO = "/dev/ttyUSB0"  # Asegúrate de que sea el correcto (puede ser COMx en Windows)
BAUDIOS = 9600         # ¡Debe coincidir con la config en XCTU!

def iniciar_escucha():
    try:
        # Configuración con timeout para evitar que el programa se congele
        xbee = serial.Serial(
            port=PUERTO,
            baudrate=BAUDIOS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=1
        )
        
        # Limpiamos basura que haya quedado en el puerto al conectar
        xbee.reset_input_buffer()
        xbee.reset_output_buffer()

        print(f"--- MONITOREO XBEE ACTIVADO ---")
        print(f"Puerto: {PUERTO} | Baudios: {BAUDIOS}")
        print("Presiona Ctrl+C para detener\n")

        while True:
            if xbee.in_waiting > 0:
                # Leemos los bytes disponibles
                datos_raw = xbee.read(xbee.in_waiting)
                
                # Convertimos a lista de enteros
                lista_numeros = list(datos_raw)
                
                # Convertimos a Hexadecimal para ver si son nulos reales (00) 
                # o caracteres de control
                hex_format = ' '.join([f'{b:02x}' for b in datos_raw])
                print(f"CANTIDAD: {len(lista_numeros)} bytes")
                print(f"DECIMAL : {lista_numeros}")

            # Pequeña pausa para no saturar el CPU
            time.sleep(0.01)

    except serial.SerialException as e:
        print(f"\n[ERROR DE PUERTO]: {e}")
        print("Verifica que el XBee esté conectado y que el nombre del puerto sea correcto.")
    except KeyboardInterrupt:
        print("\nDeteniendo escucha...")
    finally:
        if 'xbee' in locals() and xbee.is_open:
            xbee.close()
            print("Puerto cerrado correctamente.")

if __name__ == "__main__":
    iniciar_escucha()