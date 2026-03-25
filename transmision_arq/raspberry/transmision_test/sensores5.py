#!/usr/bin/env python3
import time
import math
from smbus2 import SMBus
import board
import busio
import adafruit_mmc56x3
import adafruit_bme280.basic as adafruit_bme280

# =========================
# I2C CONFIG
# =========================
I2C_BUS = 1
bus = SMBus(I2C_BUS)
i2c = busio.I2C(board.SCL, board.SDA)

# =========================
# DIRECCIONES I2C
# =========================
ADDR_MS5611 = 0x77
ADDR_MMC5603 = 0x30
ADDR_BME280 = 0x76
ADDR_INA226 = 0x40    # Default INA226
ADDR_MPU9250 = 0x68   # Acelerómetro/Giroscopio del GY-91

# =========================
# INIT SENSORES (Adafruit)
# =========================
mag = adafruit_mmc56x3.MMC5603(i2c)
bme = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=ADDR_BME280)
bme.sea_level_pressure = 850  # Ajustado para Arequipa

# =========================
# MS5611 (Tu estilo smbus)
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
# GY-91 (MPU9250) INIT
# =========================
def init_mpu9250():
    # Despertar el MPU9250 escribiendo 0x00 en el registro PWR_MGMT_1 (0x6B)
    bus.write_byte_data(ADDR_MPU9250, 0x6B, 0x00)
    time.sleep(0.1)

def read_mpu9250():
    # Leemos 14 bytes a partir del registro 0x3B (Accel X)
    # Esto trae Accel (6) + Temp (2) + Gyro (6) de una sola vez
    data = bus.read_i2c_block_data(ADDR_MPU9250, 0x3B, 14)
    
    def to_signed(h, l):
        v = (h << 8) | l
        return v if v < 32768 else v - 65536

    # Escalas por defecto: Accel = +/- 2g (16384 LSB/g), Gyro = +/- 250 dps (131 LSB/dps)
    ax = to_signed(data[0], data[1]) / 16384.0
    ay = to_signed(data[2], data[3]) / 16384.0
    az = to_signed(data[4], data[5]) / 16384.0
    
    gx = to_signed(data[8], data[9]) / 131.0
    gy = to_signed(data[10], data[11]) / 131.0
    gz = to_signed(data[12], data[13]) / 131.0
    
    return ax, ay, az, gx, gy, gz

init_mpu9250()

# =========================
# INA226 INIT
# =========================
def read_ina226():
    # Leer bloque de 2 bytes. INA226 usa formato Big-Endian
    def read_reg(reg):
        d = bus.read_i2c_block_data(ADDR_INA226, reg, 2)
        return (d[0] << 8) | d[1]
    
    # Voltaje de Bus (Registro 0x02) - 1.25 mV por bit
    raw_vbus = read_reg(0x02)
    vbus = raw_vbus * 0.00125

    # Voltaje de Shunt (Registro 0x01) - 2.5 uV por bit
    raw_shunt = read_reg(0x01)
    if raw_shunt > 32767:
        raw_shunt -= 65536
    vshunt = raw_shunt * 0.0000025

    # Corriente (I = V / R). Asumiendo módulo con resistencia shunt de 0.1 Ohmios.
    # Si tu módulo usa 0.01 Ohmios, cambia este valor a 0.01
    current = vshunt / 0.1 

    return vbus, current

# =========================
# LOOP PRINCIPAL
# =========================
try:
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
        pres_ms = d1 / 100.0  # Simplificado

        # -------- GY-91 (MPU9250) --------
        ax, ay, az, gx, gy, gz = read_mpu9250()

        # -------- INA226 --------
        vbus, current = read_ina226()
        power = vbus * current

        # =========================
        # PRINT DATOS
        # =========================
        print("========== DATOS ==========")
        print(f"BME280   -> T:{temp:.2f}C  P:{pres:.2f}hPa  H:{hum:.2f}%  Alt:{alt:.2f}m")
        print(f"MS5611   -> Pres RAW:{pres_ms:.2f}")
        print(f"MMC5603  -> X:{mx:.2f} Y:{my:.2f} Z:{mz:.2f} | Heading: {heading:.2f}°")
        print(f"GY91 Acc -> X:{ax:.2f}g Y:{ay:.2f}g Z:{az:.2f}g")
        print(f"GY91 Gyr -> X:{gx:.2f}°/s Y:{gy:.2f}°/s Z:{gz:.2f}°/s")
        print(f"INA226   -> Voltaje:{vbus:.2f}V  Corriente:{current:.3f}A  Potencia:{power:.3f}W")
        print("===========================\n")

        time.sleep(1)

except KeyboardInterrupt:
    print("\nLectura detenida por el usuario.")