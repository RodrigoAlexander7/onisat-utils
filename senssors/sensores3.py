#!/usr/bin/env python3
import time
import math
from smbus2 import SMBus

# =========================
# I2C CONFIG
# =========================
I2C_BUS = 1
bus = SMBus(I2C_BUS)

# =========================
# DIRECCIONES
# =========================
ADDR_MS5611 = 0x77
ADDR_MMC5603 = 0x30
ADDR_BME280 = 0x76

# =========================
# IMPORT LIBS
# =========================
import board
import busio
import adafruit_mmc56x3
import adafruit_bme280.basic as adafruit_bme280

i2c = busio.I2C(board.SCL, board.SDA)

# =========================
# INIT SENSORES
# =========================
mag = adafruit_mmc56x3.MMC5603(i2c)
bme = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=ADDR_BME280)

bme.sea_level_pressure = 850  # Ajustado para Arequipa


# =========================
# MS5611 (TU ESTILO)
# =========================
CMD_RESET = 0x1E
CMD_CONV_D1 = 0x48
CMD_CONV_D2 = 0x58
CMD_ADC = 0x00

def reset_ms5611():
    bus.write_byte(ADDR_MS5611, CMD_RESET)
    time.sleep(0.01)

def read_adc(cmd):
    bus.write_byte(ADDR_MS5611, cmd)
    time.sleep(0.01)
    data = bus.read_i2c_block_data(ADDR_MS5611, CMD_ADC, 3)
    return data[0] << 16 | data[1] << 8 | data[2]

reset_ms5611()



# =========================
# LOOP PRINCIPAL
# =========================
while True:

    # -------- MMC5603 --------
    mx, my, mz = mag.magnetic

    heading = math.atan2(my, mx) * (180 / math.pi)
    if heading < 0:
        heading += 360

    # -------- BME280 --------
    temp = bme.temperature
    pres = bme.pressure
    hum  = bme.humidity
    alt  = bme.altitude

    # -------- MS5611 --------
    d1 = read_adc(CMD_CONV_D1)
    d2 = read_adc(CMD_CONV_D2)

    # (simplificado, luego puedes meter compensación completa)
    pres_ms = d1 / 100.0

    # =========================
    # PRINT
    # =========================
    print("========== DATOS ==========")

    print(f"Mag [uT] -> X:{mx:.2f} Y:{my:.2f} Z:{mz:.2f}")
    print(f"Heading: {heading:.2f}°")

    print(f"BME280 -> T:{temp:.2f}C  P:{pres:.2f}hPa  H:{hum:.2f}%  Alt:{alt:.2f}m")

    print(f"MS5611 -> Pres RAW:{pres_ms:.2f}")

    print("===========================\n")

    time.sleep(1)