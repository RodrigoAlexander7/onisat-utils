
#include "HX711.h"

// ==========================================
// --- CONFIGURACIÓN DE PINES ---
// ==========================================

// BALANZA
const int DOUT = A1;
const int CLK  = A0;
HX711 balanza;
float escala_balanza = 400245.029433;  // Ajusta con tu calibración

// SENSOR RPM
const byte pinSensor = 2;
const byte numAspas = 4;

// ==========================================
// --- PARÁMETROS ---
// ==========================================
//const unsigned long intervaloCalculo = 500;   // ms
//const unsigned long intervaloCalculo = 2000;   // ms
const unsigned long debounceMicros = 10000;   // 10 ms
const float gravedad = 9.81;                  // m/s²

// ==========================================
// --- VARIABLES GLOBALES ---
// ==========================================
volatile unsigned long contadorPulsos = 0;
volatile unsigned long ultimaVez = 0;

unsigned long tiempoAnterior = 0;

float masa = 0.0;
float pesoN = 0.0;

// ==========================================
// --- SETUP ---
// ==========================================
void setup() {

  Serial.begin(115200);

  // BALANZA
  balanza.begin(DOUT, CLK);
  balanza.set_scale(escala_balanza);
  balanza.tare(20);

  // SENSOR RPM
  pinMode(pinSensor, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(pinSensor), procesarPulso, FALLING);

  Serial.println("Sistema RPM + Masa + Peso (N) iniciado");
}

// ==========================================
// --- LOOP ---
// ==========================================
void loop() {

  unsigned long tiempoActual = millis();

  // ---- LECTURA NO BLOQUEANTE DE BALANZA ----
  if (balanza.is_ready()) {
    masa = balanza.get_units(1);  // kg
    //pesoN = masa * gravedad;     // Newton
    pesoN = masa;     // Newton
  }

  // ---- CÁLCULO CADA 500 ms ----
  if (tiempoActual - tiempoAnterior >= intervaloCalculo) {

    noInterrupts();
    unsigned long pulsos = contadorPulsos;
    contadorPulsos = 0;
    interrupts();

    float rpm = (pulsos * 60000.0) / (intervaloCalculo * numAspas);

    // ---- SALIDA COMPLETA ----
    Serial.print("{\"rpm\":");
    Serial.print(rpm, 2);
    Serial.print(",\"masa\":");
    float masita = masa-0.0365;
    Serial.print(masa, 4);
    Serial.print(",\"peso_N\":");
    Serial.print(pesoN, 4);
    Serial.println("}");

    tiempoAnterior = tiempoActual;
  }
}

// ==========================================
// --- INTERRUPCIÓN ---
// ==========================================
void procesarPulso() {

  unsigned long tiempoAhoraISR = micros();

  if (tiempoAhoraISR - ultimaVez > debounceMicros) {
    contadorPulsos++;
    ultimaVez = tiempoAhoraISR;
  }
}