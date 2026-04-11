#!/usr/bin/env python3
from pathlib import Path
from math import ceil
import struct
import sys
import traceback
import time

from digi.xbee.devices import XBeeDevice, RemoteXBeeDevice
from digi.xbee.models.address import XBee64BitAddress
from digi.xbee.exception import XBeeException, TimeoutException


# =========================
# CONFIGURACIÓN
# =========================
SERIAL_PORT = "/dev/serial0"
BAUD_RATE = 115200

# Dirección 64-bit del receptor: SH + SL
DESTINATION_64 = "0013A200406EFB43"

# Timeout para operaciones síncronas de la librería.
SYNC_TIMEOUT_S = 5

# Cabecera de aplicación:
# [image_id:1][seq:2][total_chunks:2]
APP_HEADER_SIZE = 5

# Tamaño fijo del chunk de datos de la imagen.
# Esto evita depender de NP, que en tu módulo dio "Invalid command".
# Puedes probar luego 64, 72, 80 o 90 si todo funciona.
IMAGE_CHUNK_SIZE = 64

# Retries de aplicación.
APP_RETRIES = 2

# Archivo a enviar
IMAGE_PATH = "foto.jpg"
IMAGE_ID = 1


def safe_get_parameter(xbee: XBeeDevice, param: str):
    """
    Intenta leer un parámetro AT sin romper el programa.
    Devuelve bytes o None.
    """
    try:
        value = xbee.get_parameter(param)
        print(f"[AT] {param} = {value.hex().upper() if isinstance(value, (bytes, bytearray)) else value}")
        return value
    except Exception as e:
        print(f"[AT] No se pudo leer {param}: {e}")
        return None


def configure_xbee(xbee: XBeeDevice) -> None:
    """
    Configuración mínima en runtime.
    """
    xbee.set_sync_ops_timeout(SYNC_TIMEOUT_S)


def build_chunks(image_bytes: bytes, chunk_size: int, image_id: int):
    """
    Divide la imagen en fragmentos con una pequeña cabecera de aplicación.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size debe ser mayor que 0.")

    total_chunks = ceil(len(image_bytes) / chunk_size)

    for seq in range(total_chunks):
        start = seq * chunk_size
        end = min(start + chunk_size, len(image_bytes))
        chunk = image_bytes[start:end]

        header = struct.pack(">BHH", image_id & 0xFF, seq & 0xFFFF, total_chunks & 0xFFFF)
        yield seq, total_chunks, header + chunk


def send_image_unicast(
    xbee: XBeeDevice,
    remote: RemoteXBeeDevice,
    image_path: str,
    image_id: int
) -> bool:
    """
    Envía una imagen por unicast, fragmentada en chunks.
    """
    image_file = Path(image_path)
    if not image_file.is_file():
        raise FileNotFoundError(f"No existe el archivo: {image_path}")

    image_bytes = image_file.read_bytes()
    if not image_bytes:
        raise ValueError("La imagen está vacía.")

    payload_budget = IMAGE_CHUNK_SIZE
    if payload_budget <= 0:
        raise RuntimeError("El tamaño de chunk es inválido.")

    print(f"\n=== ENVÍO ===")
    print(f"Archivo: {image_file.resolve()}")
    print(f"Tamaño imagen: {len(image_bytes)} bytes")
    print(f"Chunk de datos: {payload_budget} bytes")
    print(f"Cabecera app: {APP_HEADER_SIZE} bytes")
    print(f"Total por paquete: {payload_budget + APP_HEADER_SIZE} bytes")

    chunks = list(build_chunks(image_bytes, payload_budget, image_id))
    print(f"Total chunks: {len(chunks)}\n")

    for seq, total_chunks, payload in chunks:
        sent = False

        for attempt in range(1, APP_RETRIES + 1):
            try:
                print(f"[TX] Chunk {seq + 1}/{total_chunks} | intento {attempt} | {len(payload)} bytes")
                xbee.send_data(remote, payload)
                time.sleep(0.02)
                sent = True
                break

            except TimeoutException as e:
                print(f"[TX] Timeout en chunk {seq + 1}/{total_chunks}, intento {attempt}: {e}")

            except XBeeException as e:
                print(f"[TX] Error XBee en chunk {seq + 1}/{total_chunks}, intento {attempt}: {e}")

            except Exception as e:
                print(f"[TX] Error inesperado en chunk {seq + 1}/{total_chunks}, intento {attempt}: {e}")
                traceback.print_exc()

        if not sent:
            print(f"[TX] Fallo definitivo enviando chunk {seq + 1}/{total_chunks}")
            return False

        if seq % 10 == 0 or seq == total_chunks - 1:
            print(f"[TX] Enviado chunk {seq + 1}/{total_chunks}")

    return True


def main():
    xbee = XBeeDevice(SERIAL_PORT, BAUD_RATE)

    try:
        print("=== ABRIENDO XBee ===")
        print(f"Puerto: {SERIAL_PORT}")
        print(f"Baud rate: {BAUD_RATE}")
        print(f"Destino 64-bit: {DESTINATION_64}")

        xbee.open()
        print("[OK] XBee abierto")

        configure_xbee(xbee)

        print("\n=== DIAGNÓSTICO AT ===")
        safe_get_parameter(xbee, "AP")
        safe_get_parameter(xbee, "BD")
        safe_get_parameter(xbee, "ID")
        safe_get_parameter(xbee, "CH")
        safe_get_parameter(xbee, "MY")
        safe_get_parameter(xbee, "SH")
        safe_get_parameter(xbee, "SL")
        safe_get_parameter(xbee, "VR")
        safe_get_parameter(xbee, "HV")

        remote = RemoteXBeeDevice(
            xbee,
            XBee64BitAddress.from_hex_string(DESTINATION_64)
        )

        print("\n=== INICIANDO ENVÍO ===")
        ok = send_image_unicast(xbee, remote, IMAGE_PATH, IMAGE_ID)

        print("\nTransmisión completada" if ok else "\nTransmisión fallida")
        return 0 if ok else 1

    except Exception as e:
        print(f"\nError: {e}")
        traceback.print_exc()
        return 1

    finally:
        try:
            if xbee.is_open():
                xbee.close()
                print("[OK] XBee cerrado")
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())