#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from math import ceil
from pathlib import Path
from struct import Struct
from threading import Event, Lock
from time import monotonic, sleep
from typing import Dict, Tuple

from digi.xbee.devices import XBeeDevice
from digi.xbee.exception import XBeeException


SERIAL_PORT = "/dev/ttyUSB0"   # puerto USB del Arduino
BAUD_RATE = 115200             # debe coincidir con Serial.begin() del sketch
OUTPUT_DIR = Path("received_images")
STALE_BUFFER_TIMEOUT_S = 300

APP_HEADER = Struct(">BHH")    # [image_id:1][seq:2][total_chunks:2]
APP_HEADER_SIZE = APP_HEADER.size

stop_event = Event()
buffers_lock = Lock()
buffers: Dict[Tuple[str, int, int], "ImageBuffer"] = {}


@dataclass
class ImageBuffer:
    sender: str
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


def safe_sender_name(sender: str) -> str:
    return sender.replace(":", "").replace(" ", "").replace("/", "_")


def cleanup_stale_buffers() -> None:
    while not stop_event.is_set():
        sleep(10)
        now = monotonic()
        with buffers_lock:
            stale_keys = [
                key for key, buf in buffers.items()
                if now - buf.last_seen > STALE_BUFFER_TIMEOUT_S
            ]
            for key in stale_keys:
                del buffers[key]
                print(f"[LIMPIEZA] Buffer incompleto eliminado: {key}")


def on_data_received(xbee_message) -> None:
    try:
        data = bytes(xbee_message.data)
        sender = str(xbee_message.remote_device.get_64bit_addr())
        is_broadcast = bool(getattr(xbee_message, "is_broadcast", False))

        if len(data) < APP_HEADER_SIZE:
            print(f"[DESCARTADO] Paquete muy corto de {sender} ({len(data)} bytes)")
            return

        image_id, seq, total_chunks = APP_HEADER.unpack_from(data)
        payload = data[APP_HEADER_SIZE:]

        if total_chunks == 0 or seq >= total_chunks:
            print(f"[DESCARTADO] Encabezado inválido de {sender}")
            return

        key = (sender, image_id, total_chunks)

        with buffers_lock:
            buf = buffers.get(key)
            if buf is None:
                buf = ImageBuffer(sender=sender, image_id=image_id, total_chunks=total_chunks)
                buffers[key] = buf

            if seq in buf.chunks:
                print(f"[DUPLICADO] sender={sender} img={image_id} seq={seq + 1}/{total_chunks}")
                return

            buf.add_chunk(seq, payload)
            received_now = len(buf.chunks)

            print(
                f"[RX] sender={sender} "
                f"{'broadcast' if is_broadcast else 'unicast'} "
                f"img={image_id} seq={seq + 1}/{total_chunks} "
                f"bytes={len(payload)} recibidos={received_now}/{total_chunks}"
            )

            if not buf.is_complete():
                return

            image_bytes = buf.assemble()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"img_{image_id:03d}_{safe_sender_name(sender)}_{timestamp}.jpg"
            out_path = OUTPUT_DIR / filename
            out_path.write_bytes(image_bytes)
            del buffers[key]

        print(f"[OK] Imagen reconstruida: {out_path} ({len(image_bytes)} bytes)")

    except Exception as e:
        print(f"[ERROR CALLBACK] {e}")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    xbee = XBeeDevice(SERIAL_PORT, BAUD_RATE)

    try:
        xbee.open()
        xbee.add_data_received_callback(on_data_received)

        print("Receptor listo. Esperando fragmentos...")
        print("Ctrl+C para salir.")

        cleaner = __import__("threading").Thread(target=cleanup_stale_buffers, daemon=True)
        cleaner.start()

        while not stop_event.is_set():
            sleep(1)

        return 0

    except KeyboardInterrupt:
        print("\nSaliendo...")
        return 0

    except XBeeException as e:
        print(f"Error XBee: {e}")
        return 1

    except Exception as e:
        print(f"Error general: {e}")
        return 1

    finally:
        stop_event.set()
        try:
            if xbee.is_open():
                xbee.del_data_received_callback(on_data_received)
                xbee.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())