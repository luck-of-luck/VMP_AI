---
name: smat-hive-dashboard
description: Dashboards locais e controle RGB/OTA para Smat_Hive.
version: 1.0.0
author: VORTEX AI + lucas
license: MIT
metadata:
  hermes:
    category: iot
    tags: [esp32, webserver, dashboard, chartjs, ota, rgb, neopixel]
---

# Smat_Hive Dashboard Skill

Cria dashboards locais nos ESP32 (AP `ADMIN`) e controle RGB + OTA.

## Quando Usar

- Mostrar telemetria em tempo real sem internet (AP local)
- Gráfico histórico de temperatura
- Controlar LEDs RGB de múltiplos ESPs via web
- Atualizar firmware via WiFi (OTA)

## Pré-requisitos

- Libs: `WiFi`, `WebServer`, `HTTPClient`, `Adafruit_NeoPixel`, `time.h`, `ArduinoOTA`
- AP local `ADMIN/admin123` IP fixo `192.168.4.1`

## Como Usar

### Dashboard simples refresh (`comSite/comSite.ino`)
```cpp
#include <WiFi.h>
#include <WebServer.h>
WebServer server(80);
const char* ssid="ADMIN"; const char* password="admin123";
float temp,hum,press,ruido_dB;
void handleRoot(){
  String html="<!DOCTYPE html><meta http-equiv=\"refresh\" content=\"5\">";
  html+="<style>body{font-family:Arial;text-align:center} .card{background:white;padding:20px;margin:10px auto;width:400px;box-shadow:0 4px 8px rgba(0,0,0,0.1)}</style>";
  html+="<h1>Colmeia CLM-01</h1>";
  html+="<div class=\"card\">Temp <b>"+String(temp,1)+" °C</b></div>";
  html+="<div class=\"card\">Umid <b>"+String(hum,1)+" %</b></div>";
  server.send(200,"text/html",html);
}
void setup(){ WiFi.softAP(ssid,password); server.on("/",handleRoot); server.begin(); }
void loop(){ server.handleClient(); if(millis()-ultimoUpdate>2000){ temp=bme.readTemperature(); /*...*/ } }
```
Polling via `meta refresh 5s`.

### Dashboard moderno com gráfico (`comsiteeHHistorico` e `APInternetRelOgio`)
- `INDEX_HTML[] PROGMEM = R"rawliteral(...)"` dark theme `#1e1e2f`, cards `value #f39c12`
- Clock NTP: `configTime(gmtOffset_sec, daylightOffset_sec, ntpServer)` + `getLocalTime(&timeinfo)`
- JS:
```js
const maxPoints=40; let tempHistory=[];
function drawChart(id,data,color){
  const c=document.getElementById(id), ctx=c.getContext('2d');
  ctx.clearRect(0,0,c.width,c.height);
  if(data.length<2) return;
  const min=Math.min(...data)-1, max=Math.max(...data)+1;
  const dx=c.width/(maxPoints-1), dy=c.height/(max-maxPoints?);
  ctx.beginPath(); ctx.strokeStyle=color; ctx.lineWidth=3;
  data.forEach((v,i)=>{ const x=i*dx, y=c.height-((v-min)*dy); if(i==0) ctx.moveTo(x,y); else ctx.lineTo(x,y); });
  ctx.stroke();
}
setInterval(()=> fetch('/api/dados').then(r=>r.json()).then(j=>{
  document.getElementById('t_val').innerText=j.t.toFixed(1);
  tempHistory.push(j.t); if(tempHistory.length>maxPoints) tempHistory.shift();
  drawChart('tempChart',tempHistory,'#f39c12');
  document.getElementById('hora_val').innerText=j.hora;
}),2000);
```
Endpoint ESP:
```cpp
server.on("/api/dados", [](){
  StaticJsonDocument<200> doc;
  doc["t"]=temp; doc["h"]=hum; doc["p"]=press; doc["r"]=ruido_dB;
  char horaStr[20]; struct tm timeinfo; getLocalTime(&timeinfo); strftime(horaStr,20,"%H:%M:%S",&timeinfo); doc["hora"]=horaStr;
  String out; serializeJson(doc,out); server.send(200,"application/json",out);
});
server.on("/", [](){ server.send_P(200,"text/html",INDEX_HTML); });
```
Também `WebServer 80 + dual STA`: `WiFi.softAP(ap_ssid,ap_password); WiFi.begin(sta_ssid,sta_password);`

### Controle RGB via UDP binário (complexo 2 PRO)
- Mestre AP `ESP_MASTER_PRO` + `WiFiUdp` broadcast `ControlPacket` 8 bytes `struct pack =BBBBBBH`
```cpp
enum CommandType{CMD_OFF=0,CMD_STATIC=1,CMD_ANIM=2}; enum AnimMode{ANIM_NONE=0,ANIM_RAINBOW=1,ANIM_PULSE=2};
#pragma pack(push,1)
struct ControlPacket{ uint8_t command,r,g,b,brightness,animMode; uint16_t speed; };
#pragma pack(pop)
void sendBroadcast(ControlPacket &pkt){ udp.beginPacket(broadcastIP,4210); udp.write((uint8_t*)&pkt,sizeof(pkt)); udp.endPacket(); }
// Web handler
server.on("/api", [](){
  ControlPacket pkt; String cmd=server.arg("cmd");
  if(cmd=="OFF") pkt.command=CMD_OFF;
  else if(cmd=="STATIC"){ pkt.command=CMD_STATIC; pkt.r=server.arg("r").toInt(); pkt.g=server.arg("g").toInt(); pkt.b=server.arg("b").toInt(); }
  else if(cmd=="ANIM"){ pkt.command=CMD_ANIM; pkt.animMode=server.arg("mode").toInt(); pkt.speed=server.arg("speed").toInt(); }
  sendBroadcast(pkt); server.send(200,"text/plain","OK");
});
```
- Escravo `WiFi.mode(WIFI_STA); udp.begin(4210); parsePacket==sizeof(pkt)` + FSM 60fps `renderFrame()`:
```cpp
uint32_t wheel(byte p){ p=255-p; if(p<85) return led.Color(255-p*3,0,p*3); if(p<170) return led.Color(0,(p-85)*3,255-(p-85)*3); return led.Color((p-170)*3,255-(p-170)*3,0); }
void renderFrame(){
  if(millis()-lastFrame<16) return;
  if(state.currentCmd==CMD_ANIM && state.currentAnim==ANIM_RAINBOW){
    uint8_t hue=(millis()/state.speed)%256; led.setPixelColor(0,wheel(hue));
  } else if(state.currentCmd==CMD_STATIC) led.setPixelColor(0,led.Color(state.r,state.g,state.b));
  led.show();
}
```

### Controle RGB via HTTP REST (3esp mestre)
- Registro: `GET /register?name=ESP1` → `devices[20]` com `lastSeen`, stale 30s
- Dispatch: `HTTPClient http; http.begin("http://"+ip+"/set?r&g&b")`

### OTA (`Teste OTA/`)
```cpp
#include <ArduinoOTA.h>
const char* ssid="QUARTO104"; const char* pass="Thefato104";
void setup(){
  WiFi.begin(ssid,pass); while(WiFi.status()!=WL_CONNECTED) delay(500);
  ArduinoOTA.setHostname("ESP32-DevKit-Quarto104");
  ArduinoOTA.onStart([](){ String t=(ArduinoOTA.getCommand()==U_FLASH)?"sketch":"filesystem"; Serial.println("OTA:"+t); });
  ArduinoOTA.onProgress([](unsigned p,unsigned t){ Serial.printf("%u%%\r",(p/(t/100))); });
  ArduinoOTA.onError([](ota_error_t e){ Serial.printf("Erro %u",e); });
  ArduinoOTA.begin();
  // + WebServer LED 25
  server.on("/on",[](){ digitalWrite(25,HIGH); server.send(200,"text/html",getHTML()); });
}
void loop(){ ArduinoOTA.handle(); server.handleClient(); }
```

## Referência Rápida

| Arquivo | Dashboard |
|---|---|
| `comSite.ino` | refresh 5s simples |
| `comsiteeHHistorico.ino` | chart.js dark 40 pts |
| `APInternetRelOgio.ino` | chart + NTP GMT-3 + dual WiFi |
| `Controle_de_RGB_site` | RGB simples |
| `complexo1/RGB-mestre` | color picker + broadcast |
| `complexo2/mestre+escravo` | UDP binário PRO |
| `Controle-RGB+ip=3esp` | HTTP register/dispatch |
| `wi-fi/rede_com_site_simples` | hello world AP |
| `Teste OTA/OTA` | OTA puro |
| `TesteLED_WEB` | OTA+Web LED25 |

## Procedimento

1. Para telemetria: copie `APInternetRelOgio` como base, ajuste `ap_ssid` e `LOCAL_ID`.
2. Para só mostrar dados: use `comSite` se JS não precisa, ou `comsiteeHHistorico` se precisa gráfico offline.
3. Para RGB: escolha UDP broadcast se <10 nodes e pouca latência, ou HTTP se precisa confirmar entrega.
4. OTA: sempre `ArduinoOTA.handle()` no loop antes de `server.handleClient()`.

## Pitfalls

- **PROGMEM:** `INDEX_HTML` grande → use `server.send_P` não `send`.
- **Clock NTP:** sem internet `getLocalTime` falha; mostre `--:--:--`.
- **Color scaling:** `applyColor(r*br/255)` senão brilho 255 estoura NeoPixel.
- **OTA hostname duplicado:** 2 ESPs com mesmo hostname aparecem só 1 na IDE → use `ESP32-CLM-01`.
- **Blocking anim:** `delay` no `handleAnim` trava WebServer → use FSM não-bloqueante como complexo2.
