import serial
import time

PUERTO = "/dev/ttyUSB0"   # cambia si es necesario
BAUDIOS = 9600

ser = serial.Serial(
    port=PUERTO,
    baudrate=BAUDIOS,
    timeout=1
)

print("Enviando datos...")

valor = 0

while True:
    ser.write(bytes([valor]))  # enviar 1 byte
    print("Enviado:", valor)

    valor = (valor + 1) % 256
    time.sleep(0.1)
