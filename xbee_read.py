import serial

ser = serial.Serial(
    port="/dev/ttyUSB0",
    baudrate=9600,
    timeout=1
)

print("Listening for data...")

while True:
    data = ser.read(1) 
    if data:
        print(data[0]) 
