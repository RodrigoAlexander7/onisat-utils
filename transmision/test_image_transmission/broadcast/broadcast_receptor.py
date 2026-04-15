#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from struct import Struct
from time import monotonic, sleep
from typing import Dict, Tuple

import serial


# =========================
# CONFIGURACIÓN (Windows)
# =========================
SERIAL_PORT = "COM3"                 # XBee receptor conectado al PC
BAUD_RATE = 9600                  # Debe coincidir con BD en XCTU
OUTPUT_DIR = Path(__file__).resolve().parent / "received_images"
READ_SIZE = 4096
STALE_TIMEOUT_S = 120
USE_RTSCTS = False            # En muchos adaptadores FTDI/XBee en Windows es más estable en False


# Protocolo de framing sobre serial transparente (AP=0):
# [MAGIC:4][image_id:1][seq:2][total_chunks:2][payload_len:2][payload:n]
MAGIC = b"XBIM"
HEADER = Struct(">4sBHHH")
HEADER_SIZE = HEADER.size


@dataclass
class ImageBuffer:
	image_id: int
	total_chunks: int
	first_seen: float = field(default_factory=monotonic)
	last_seen: float = field(default_factory=monotonic)
	chunks: Dict[int, bytes] = field(default_factory=dict)

	def add_chunk(self, seq: int, payload: bytes) -> None:
		self.chunks[seq] = payload
		self.last_seen = monotonic()

	def is_complete(self) -> bool:
		return len(self.chunks) == self.total_chunks

	def assemble(self) -> bytes:
		return b"".join(self.chunks[i] for i in range(self.total_chunks))


def cleanup_stale_buffers(buffers: Dict[Tuple[int, int], ImageBuffer]) -> None:
	now = monotonic()
	stale_keys = [
		key for key, buf in buffers.items()
		if now - buf.last_seen > STALE_TIMEOUT_S
	]
	for key in stale_keys:
		del buffers[key]
		print(f"[LIMPIEZA] Buffer incompleto eliminado: {key}")


def process_frame(
	image_id: int,
	seq: int,
	total_chunks: int,
	payload: bytes,
	buffers: Dict[Tuple[int, int], ImageBuffer],
) -> None:
	key = (image_id, total_chunks)
	buf = buffers.get(key)
	if buf is None:
		buf = ImageBuffer(image_id=image_id, total_chunks=total_chunks)
		buffers[key] = buf

	if seq in buf.chunks:
		print(f"[DUPLICADO] img={image_id} seq={seq + 1}/{total_chunks}")
		return

	buf.add_chunk(seq, payload)
	print(f"[RX] img={image_id} seq={seq + 1}/{total_chunks} bytes={len(payload)} recibidos={len(buf.chunks)}/{total_chunks}")

	if not buf.is_complete():
		return

	image_bytes = buf.assemble()
	timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
	out_path = OUTPUT_DIR / f"img_{image_id:03d}_{timestamp}.jpg"
	out_path.write_bytes(image_bytes)
	del buffers[key]

	print(f"[OK] Imagen reconstruida: {out_path} ({len(image_bytes)} bytes)")


def main() -> int:
	OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
	buffers: Dict[Tuple[int, int], ImageBuffer] = {}
	rx = bytearray()
	last_cleanup = monotonic()
	last_rx_log = monotonic()
	total_rx_bytes = 0

	print("=== RECEPTOR XBee S1 (AP=0) ===")
	print(f"Puerto: {SERIAL_PORT}")
	print(f"Baud: {BAUD_RATE}")
	print(f"Salida: {OUTPUT_DIR.resolve()}")
	print("Ctrl+C para salir")

	try:
		with serial.Serial(
			port=SERIAL_PORT,
			baudrate=BAUD_RATE,
			timeout=0.2,
			rtscts=USE_RTSCTS,
			dsrdtr=False,
			xonxoff=False,
		) as ser:
			ser.reset_input_buffer()
			print(f"RTS/CTS: {'ON' if USE_RTSCTS else 'OFF'}")

			while True:
				chunk = ser.read(READ_SIZE)
				if chunk:
					rx.extend(chunk)
					total_rx_bytes += len(chunk)
					now = monotonic()
					if now - last_rx_log >= 1.0:
						print(f"[RAW RX] bytes={len(chunk)} acumulado={total_rx_bytes} buffer={len(rx)}")
						last_rx_log = now

				while True:
					idx = rx.find(MAGIC)
					if idx < 0:
						if len(rx) > 3:
							del rx[:-3]
						break

					if idx > 0:
						del rx[:idx]

					if len(rx) < HEADER_SIZE:
						break

					magic, image_id, seq, total_chunks, payload_len = HEADER.unpack_from(rx)
					if magic != MAGIC:
						del rx[0]
						continue

					if total_chunks == 0 or seq >= total_chunks:
						del rx[0]
						continue

					if payload_len == 0 or payload_len > 4096:
						del rx[0]
						continue

					frame_size = HEADER_SIZE + payload_len
					if len(rx) < frame_size:
						break

					payload = bytes(rx[HEADER_SIZE:frame_size])
					del rx[:frame_size]

					process_frame(image_id, seq, total_chunks, payload, buffers)

				now = monotonic()
				if now - last_cleanup >= 5:
					cleanup_stale_buffers(buffers)
					last_cleanup = now
					if total_rx_bytes == 0:
						print("[RAW RX] Sin bytes entrantes desde XBee")

				sleep(0.002)

	except KeyboardInterrupt:
		print("\nSaliendo...")
		return 0

	except serial.SerialException as e:
		print(f"[ERROR SERIAL] {e}")
		return 1

	except Exception as e:
		print(f"[ERROR] {e}")
		return 1


if __name__ == "__main__":
	raise SystemExit(main())

