// Puente transparente entre PC <-> Arduino <-> XBee
// Asume una placa con Serial1 (por ejemplo Mega/Leonardo según el modelo)

void setup() {
  Serial.begin(115200);   // USB hacia el PC
  Serial1.begin(115200);  // UART hacia el XBee
}

void loop() {
  // PC -> XBee
  while (Serial.available() > 0) {
    Serial1.write(Serial.read());
  }

  // XBee -> PC
  while (Serial1.available() > 0) {
    Serial.write(Serial1.read());
  }
}