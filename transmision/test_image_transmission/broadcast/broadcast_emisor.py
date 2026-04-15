#!/usr/bin/env python3
from __future__ import annotations

from math import ceil
from pathlib import Path
from struct import Struct
from time import sleep

import serial


# =========================
# CONFIGURACIÓN (Windows)
# =========================
SERIAL_PORT = "COM5"          # XBee emisor conectado al PC
BAUD_RATE = 9600            # Debe coincidir con BD en XCTU
IMAGE_PATH = Path(__file__).resolve().parent / "foto.jpg"
IMAGE_ID = 1                  # Cámbialo entre pruebas para no mezclar sesiones
CHUNK_SIZE = 64               # Carga útil por frame
INTER_FRAME_DELAY_S = 0.01    # Pequeña pausa para no saturar UART/RF
USE_RTSCTS = False            # En muchos adaptadores FTDI/XBee en Windows es más estable en False


# Protocolo de framing sobre serial transparente (AP=0):
# [MAGIC:4][image_id:1][seq:2][total_chunks:2][payload_len:2][payload:n]
MAGIC = b"XBIM"
HEADER = Struct(">4sBHHH")
HEADER_SIZE = HEADER.size


def build_frames(image_bytes: bytes, image_id: int, chunk_size: int):
	if chunk_size <= 0:
		raise ValueError("chunk_size debe ser mayor que 0")

	total_chunks = ceil(len(image_bytes) / chunk_size)
	if total_chunks == 0:
		raise ValueError("La imagen está vacía")

	for seq in range(total_chunks):
		start = seq * chunk_size
		end = min(start + chunk_size, len(image_bytes))
		payload = image_bytes[start:end]
		header = HEADER.pack(MAGIC, image_id & 0xFF, seq & 0xFFFF, total_chunks & 0xFFFF, len(payload) & 0xFFFF)
		yield seq, total_chunks, header + payload


def main() -> int:
	image_file = Path(IMAGE_PATH)
	if not image_file.is_file():
		print(f"[ERROR] No existe archivo: {image_file}")
		return 1

	image_bytes = image_file.read_bytes()
	if not image_bytes:
		print("[ERROR] La imagen está vacía")
		return 1

	total_chunks = ceil(len(image_bytes) / CHUNK_SIZE)

	print("=== EMISOR XBee S1 (AP=0) ===")
	print(f"Puerto: {SERIAL_PORT}")
	print(f"Baud: {BAUD_RATE}")
	print(f"Archivo: {image_file.resolve()}")
	print(f"Tamaño: {len(image_bytes)} bytes")
	print(f"Chunk: {CHUNK_SIZE} bytes")
	print(f"Total chunks: {total_chunks}")

	try:
		with serial.Serial(
			port=SERIAL_PORT,
			baudrate=BAUD_RATE,
			timeout=0.2,
			write_timeout=2,
			rtscts=USE_RTSCTS,
			dsrdtr=False,
			xonxoff=False,
		) as ser:
			ser.reset_input_buffer()
			ser.reset_output_buffer()
			print(f"RTS/CTS: {'ON' if USE_RTSCTS else 'OFF'}")

			total_written = 0
			for seq, total, frame in build_frames(image_bytes, IMAGE_ID, CHUNK_SIZE):
				written = ser.write(frame) or 0
				ser.flush()
				total_written += written

				if seq % 10 == 0 or seq == total - 1:
					print(f"[TX] {seq + 1}/{total} frame_bytes={len(frame)} written={written}")

				sleep(INTER_FRAME_DELAY_S)

			print(f"[TX] bytes_totales_escritos={total_written}")

		print("[OK] Envío finalizado (sin ACK, sin reintentos)")
		return 0

	except serial.SerialException as e:
		print(f"[ERROR SERIAL] {e}")
		return 1

	except Exception as e:
		print(f"[ERROR] {e}")
		return 1


if __name__ == "__main__":
	raise SystemExit(main())

