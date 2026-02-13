int pinSensor = 2; 
int lectura = 0;

void setup() {
  pinMode(pinSensor, INPUT); 
  Serial.begin(9600);        
}

void loop() {
  lectura = digitalRead(pinSensor); // Leemos el sensor (0 o 1)
  
  if (lectura == LOW) { // Muchos de estos sensores envían LOW (0) cuando detectan
    Serial.println("¡Objeto/Línea DETECTADA!");
  } else {
    Serial.println("Nada...");
  }
  
  delay(200); // Pequeña pausa para poder leer el texto
}