---
name: smat-hive-mesh
description: Rede mesh WiFi/LoRa com fallback e deep sleep para colmeias.
version: 1.0.0
author: VORTEX AI + lucas
license: MIT
metadata:
  hermes:
    category: iot
    tags: [esp32, lora, wifi, mesh, udp, deepsleep, heltec]
---

# Smat_Hive Mesh Skill

Gerencia comunicação redundante do Smat_Hive: WiFi STA/AP, UDP Broadcast Mesh, LoRa 915MHz, e fallback com DeepSleep + RTC buffer.

## Quando Usar

- Nó em campo precisa enviar dados sem internet (mesh)
- Escolher entre WiFi mesh vs LoRa mesh vs SD fallback
- Implementar deep sleep 300s com `RTC_DATA_ATTR` buffer
- Debug de perda de pacotes / loop infinito mesh

## Pré-requisitos

- Heltec V3 com `RadioLib` + `heltec_unofficial`
- Libs: `WiFi`, `HTTPClient`, `WiFiUdp`, `ArduinoJson`, `deque` (C++ STL)
- Gateway Python escutando UDP 4210

## Como Usar

### Padrão 1 — WiFi Mesh sem LoRa (`Sem_lora/finalizado-1.ino`)
```cpp
#include <WiFiUdp.h>
#include <deque>
struct MeshEnvelope { int originID; char json[512]; };
std::deque<MeshEnvelope> bufferGlobal;
const size_t MAX_BUFFER=10;
WiFiUDP udp;
const char* ssid="PROTON"; const char* pass="admin123";
const char* server_url="http://191.252.100.161:8080/api/iot/colmeia/dados/";
int udpPort=4210;

void processarDrenagem(){
  if(bufferGlobal.empty()) return;
  if(WiFi.status()==WL_CONNECTED){
    HTTPClient http;
    while(!bufferGlobal.empty()){
      auto item=bufferGlobal.front();
      http.begin(server_url); http.addHeader("Content-Type","application/json");
      int code=http.POST(item.json);
      if(code==200||code==201) bufferGlobal.pop_front();
      else { http.end(); break; }
      http.end();
    }
  }
  if(!bufferGlobal.empty()){ // sem internet → broadcast
    IPAddress bcast=WiFi.localIP(); bcast[3]=255;
    while(!bufferGlobal.empty()){
      auto item=bufferGlobal.front();
      udp.beginPacket(bcast, udpPort);
      udp.write((uint8_t*)&item, sizeof(MeshEnvelope));
      udp.endPacket(); bufferGlobal.pop_front();
    }
  }
}
void loop(){
  int sz=udp.parsePacket();
  if(sz==sizeof(MeshEnvelope)){
    MeshEnvelope r; udp.read((uint8_t*)&r,sizeof(r));
    if(r.originID > LOCAL_ID){ // anti-loop: só retransmite IDs maiores
      bufferGlobal.push_back(r);
      if(bufferGlobal.size()>MAX_BUFFER) bufferGlobal.pop_front();
    }
  }
  // a cada 10s gera localEnv e chama processarDrenagem()
}
```

### Padrão 2 — WiFi → LoRa fallback + DeepSleep (`Com_Lora/wifi-Lora-sensores-deepsleep`)
```cpp
#define uS_TO_S_FACTOR 1000000ULL
#define TIME_TO_SLEEP 300
RTC_DATA_ATTR MeshEnvelope bufferGlobal[5];
RTC_DATA_ATTR int bufferCount=0;
RTC_DATA_ATTR int bootCount=0;
void setup(){
  bootCount++;
  // gera doc json random + push bufferGlobal[bufferCount++]
  WiFi.begin(ssid,pass);
  int tries=0; while(WiFi.status()!=WL_CONNECTED && tries<12){ delay(500); tries++; }
  if(WiFi.status()==WL_CONNECTED){
    for(int i=0;i<bufferCount;i++){ HTTPClient http; http.begin(server_url); http.POST(bufferGlobal[i].json); http.end(); }
    bufferCount=0;
  } else {
    WiFi.disconnect(true); WiFi.mode(WIFI_OFF); delay(200);
    int state=radio.begin(915.0,125.0,9,7,0x12,10,8,1.6);
    if(state==RADIOLIB_ERR_NONE) for(int i=0;i<bufferCount;i++) radio.transmit(bufferGlobal[i].json);
    bufferCount=0;
  }
  esp_sleep_enable_timer_wakeup(TIME_TO_SLEEP*uS_TO_S_FACTOR);
  esp_deep_sleep_start();
}
void loop(){}
```

### Padrão 3 — Com SD (`comSD/exetoPeso/exetoPeso.ino`)
- SD FSPI `spiSD.begin(SCK,MISO,MOSI,CS); SD.begin(CS,spiSD,4000000)`
- `gravarNoSD(SD,"/dados_colmeia.txt", csv)` com header se arquivo não existe
- CSV: `BootID,CLM-01,temp,hum,press,ruido`
- `heltec_ve(true)` antes de ler sensores, `heltec_ve(false)` antes de dormir

### LoRa ponto-a-ponto (`ESP32_LoRa/envioJSoN`)
- V2 emissor: `SX1276 NSS18 DIO0 26 NRST14 DIO1 35 VEXT21`, `radio.begin(915.0)` + `radio.transmit(jsonOutput)`
- V3 receptor: `heltec_setup(); radio.begin(915,125,9,7,0x12,10,8,1.6)` + `radio.receive(str)` + `deserializeJson`

### Cores diagnóstico (LED 48)
- Ciano `0,255,255` gerou dado local | Amarelo `255,255,0` recebeu mesh | Azul `0,0,255` TX broadcast/LoRa | Verde OK | Vermelho falha HTTP

## Referência Rápida

| Arquivo | Padrão |
|---|---|
| `Com_Lora/wifi-Lora-sensores-deepsleep` | RTC + LoRa fallback + deepSleep |
| `Sem_lora/finalizado-1` | WiFi mesh deque sem LoRa |
| `comSD/exetoPeso` | BME Wire1 + SD + LoRa |
| `Prototipo-de-rede/teste1` | Mesh deque 512 sem deepSleep |
| `prototipo de brodast/colmeia_node` | Botão click broadcast |
| `ESP32_LoRa/envioJSoN/*` | LoRa JSON V2->V3 |
| `ESP32_LoRa/ping pong/*` | LoRa.h ping-pong callback |

## Procedimento

1. Escolher topologia: `<1km e com WiFi` → Sem_lora ; `>1km sem WiFi` → Com_Lora deepSleep ; `precisa log offline` → comSD.
2. Definir `LOCAL_ID` único crescente (1=central/gateway, n=mais distante) para regra `originID>LOCAL_ID`.
3. Configurar `server_url` — com barra final para Django (`/dados/`) ou sem para evitar 404 (testar).
4. Testar drenagem: ligar 2 nós, bloquear WiFi no 1→ ver `radio.receive` no 2 e `udp.parsePacket` no gateway.
5. Medir consumo: com deepSleep deve ficar ~10uA; sem `heltec_ve(false)` fica 50mA.

## Pitfalls

- **Loop mesh:** sem `originID>LOCAL_ID` o broadcast infinito inunda rede.
- **Tamanho struct:** `udp.parsePacket()==sizeof(MeshEnvelope)` — se JSON >240 chars trunca; use 512 no campo.
- **RTC limite:** `RTC_DATA_ATTR` máx ~8KB em V3; buffer[5][240] ok, buffer[20][512] estoura.
- **WiFi timeout:** 6s é mínimo; em campo com sinal fraco aumente para 12 tentativas.
- **LoRa vs WiFi power:** desligar WiFi antes de `radio.begin` senão pico de corrente reinicia.
