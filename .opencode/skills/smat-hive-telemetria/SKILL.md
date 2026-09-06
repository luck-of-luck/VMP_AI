---
name: smat-hive-telemetria
description: Telemetria de colmeia com ESP32, BME280 e MAX9814 para Smat_Hive.
version: 1.0.0
author: VORTEX AI + lucas
license: MIT
metadata:
  hermes:
    category: iot
    tags: [esp32, bme280, max9814, heltec, smart-hive, sensores]
---

# Smat_Hive Telemetria Skill

Domina leitura de sensores do projeto Smat_Hive: BME280 (temp/umidade/pressão) e MAX9814 (ruído dB) no Heltec WiFi LoRa 32 V3/S3.

## Quando Usar

- Ler BME280/BMP280 via I2C nos pinos 41/42 do Heltec V3
- Calcular ruído em dB a partir do MAX9814
- Debugar valores de sensores em campo
- Criar novo nó de telemetria que vai para `Implementar no campo/`

## Pré-requisitos

- Heltec WiFi LoRa 32 V3 ou ESP32-S3 DevKit
- Libs: `Adafruit_BME280`, `Adafruit_Sensor`, `Adafruit_NeoPixel`, `heltec_unofficial`, `Wire`
- Fiação: BME SDA=41 SCL=42 VCC=3.3V, MAX9814 OUT -> GPIO5 (ou GPIO1 em variantes S3), NeoPixel 48

## Como Usar

### BME280 mínimo (de `senssores/BME/BME.ino`)
```cpp
#include <Wire.h>
#include <Adafruit_BME280.h>
#define I2C_SDA 41
#define I2C_SCL 42
Adafruit_BME280 bme;
void setup(){
  Wire.begin(I2C_SDA, I2C_SCL);
  if(!bme.begin(0x76, &Wire)) bme.begin(0x77, &Wire);
  // Para Wire1 (quando OLED usa Wire): Wire1.setPins(41,42); bme.begin(0x76, &Wire1);
}
void loop(){
  float t = bme.readTemperature();
  float p = bme.readPressure()/100.0F;
  float h = bme.readHumidity();
}
```

**Ponto crítico:** Em nós com OLED (`heltec_unofficial`), use `Wire1` para BME para evitar conflito I2C (ver `comSD/exetoPeso`).

Configuração premium (de `exetoPeso.ino`):
```cpp
bme.setSampling(Adafruit_BME280::MODE_NORMAL,
  Adafruit_BME280::SAMPLING_X2,   // temp
  Adafruit_BME280::SAMPLING_X16,  // pressão
  Adafruit_BME280::SAMPLING_X1,   // umidade
  Adafruit_BME280::FILTER_X16,
  Adafruit_BME280::STANDBY_MS_500);
analogReadResolution(12);
```

### MAX9814 ruído (de `senssores/max9814/max9814.ino`)
```cpp
#define MIC_PIN 5 // ou 1 no S3
float lerDecibeis(){
  unsigned long start=millis();
  unsigned int sMax=0, sMin=4095, s;
  while(millis()-start < 50){
    s=analogRead(MIC_PIN);
    if(s<4095){ sMax=max(sMax,s); sMin=min(sMin,s); }
  }
  float vpp=((sMax - sMin)*3.3)/4095.0;
  if(vpp<0.01) vpp=0.01;
  return (20.0*log10(vpp))+70.0; // dB calibrado campo
}
// Variante simples P-P volts: vpp sem log, ou map peakToPeak 0-800 -> estágios cores (ver teste ruido)
```

### Combo (de `senssores/Bme+max/teste/teste.ino`)
- Janela 50ms, `sampleWindow=50`, imprime barra `map(peakToPeak,0,2000,0,20)` com `====`.

## Referência Rápida

| Arquivo origem | O que copia |
|---|---|
| `senssores/BME/BME.ino` | driver BME mínimo |
| `senssores/max9814/max9814.ino` | MAX9814 peak-to-peak |
| `senssores/Bme+max/teste/teste.ino` | combo + barra visual |
| `Implementar no campo/testando/teste ruido/sketch_mar25a` | 5 estágios LED por intensidade |
| `comSD/exetoPeso/exetoPeso.ino` | BME Wire1 + heltec_ve(true) power gate |

## Procedimento

1. Testar isolado: flashear `BME.ino` → ver Serial `Temperatura: XX C` e `Pressão: YY hPa`.
2. Testar microfone: `max9814.ino` → abrir Serial Plotter → bater palma vê `P-P_Volts`.
3. Integrar: copiar `lerDecibeis()` + `Wire.begin` no nó final (`APInternetRelOgio` pattern).
4. Calibrar dB: ajustar `+70.0` offset e `silencio` baseline conforme ambiente.
5. Validar deepSleep: garantir `analogReadResolution(12)` antes de ler.

## Pitfalls

- **GPIO errado:** Heltec V3 usa 5, S3 variantes usam 1 — confira `MIC_PIN` no sketch que vai copiar.
- **Wire vs Wire1:** Se OLED branco/conflito, mude BME para `Wire1`.
- **Alimentação VEXT:** Sem `heltec_ve(true); delay(2000);` o microfone fica sem energia na V3.
- **isnan check:** Sempre `if(isnan(temp)) temp=0.0;` antes de serializar JSON.
