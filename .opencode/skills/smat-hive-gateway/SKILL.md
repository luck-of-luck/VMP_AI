---
name: smat-hive-gateway
description: Gateway Python que coleta UDP das colmeias e envia para API cloud.
version: 1.0.0
author: VORTEX AI + lucas
license: MIT
metadata:
  hermes:
    category: iot
    tags: [python, flask, udp, gateway, smat-hive, iot]
---

# Smat_Hive Gateway Skill

Gateway Python que roda no PC/Raspberry como hotspot `PROTON` e ponte entre mesh UDP 4210 e API Django `191.252.100.161`.

## Quando Usar

- Rodar central no campo (sem internet) coletando dados das colmeias
- Reencaminhar JSON das colmeias para cloud
- Criar hotspot automático no Linux
- Dashboard central Flask+SocketIO

## Pré-requisitos

```bash
pip install flask flask-socketio requests
# opcional: pip install flask-socketio[client]
```

## Como Usar

### Gateway mínimo UDP→API (`pyton-pc/UDP_dedicado.py`) — produção
```python
import socket, json, requests, logging
logging.basicConfig(level=logging.INFO)
URI_PRODUCAO="http://191.252.100.161:8080/api/iot/colmeia/dados" # sem barra final evita 404
HEADERS={"Content-Type":"application/json"}
UDP_IP="0.0.0.0"; UDP_PORT=4210

def enriquecer_payload(p):
    q=p.copy()
    q.setdefault("dispositivo_id","ESP32-S3-GATEWAY")
    q.setdefault("bateria_nivel",99)
    q.setdefault("sinal_rssi",-60)
    return q

def iniciar_receptor():
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    sock.bind((UDP_IP,UDP_PORT))
    print(f"Gateway Ativo {UDP_PORT}")
    while True:
        data,addr=sock.recvfrom(2048)
        payload=json.loads(data.decode())
        print(json.dumps(payload,indent=2))
        # envia para cloud
        r=requests.post(URI_PRODUCAO, json=enriquecer_payload(payload), headers=HEADERS, timeout=10)
        print("OK" if r.status_code in [200,201] else f"FAIL {r.status_code}: {r.text}")

if __name__=="__main__": iniciar_receptor()
```

**Corrigir 404:** testar com e sem `/` final; Django com `APPEND_SLASH=True` pode redirecionar.

### Dashboard Central (`pyton-pc/off-net/central_comando.py`)
```python
import socket, json, threading, time
from flask import Flask, render_template_string
from flask_socketio import SocketIO
UDP_IP="0.0.0.0"; UDP_PORT=4210; BROADCAST_IP="255.255.255.255"
colmeias_db={} # {id: {clicks, last_seen, ip}}
app=Flask(__name__); socketio=SocketIO(app, cors_allowed_origins='*')

def udp_receiver():
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    sock.bind((UDP_IP,UDP_PORT))
    while True:
        data,addr=sock.recvfrom(1024)
        msg=json.loads(data.decode())
        id_colmeia=msg.get('id') or msg.get('colmeia_identificador')
        if id_colmeia:
            msg['ip']=addr[0]; msg['last_seen']=time.time()
            colmeias_db[id_colmeia]=msg
            socketio.emit('update_table', {'data': colmeias_db})

def enviar_comando_udp(comando, target_id=None):
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
    payload={"cmd":comando, "target": target_id or "ALL"}
    sock.sendto(json.dumps(payload).encode(), (BROADCAST_IP,UDP_PORT))

# rota / com HTML table + socket.io + chart.js, e emit('comando_web') -> enviar_comando_udp
```

Inicia com thread daemon: `threading.Thread(target=udp_receiver, daemon=True).start(); socketio.run(app, host='0.0.0.0', port=5000)`

### Hotspot auto (`off-net/iniciar_tudo.py`)
```python
import subprocess, os, socket
# Linux nmcli
cmds=[
  "nmcli con delete PROTON",
  "nmcli con add type wifi ifname wlan0 con-name PROTON autoconnect yes ssid PROTON",
  "nmcli con modify PROTON 802-11-wireless.mode ap",
  "nmcli con modify PROTON wifi-sec.key-mgmt wpa-psk",
  "nmcli con modify PROTON wifi-sec.psk admin123",
  "nmcli con modify PROTON ipv4.method shared",
  "nmcli con up PROTON"
]
for c in cmds: subprocess.run(c, shell=True)
# descobre IP
s=socket.socket(); s.connect(('8.8.8.8',80)); ip=s.getsockname()[0]
print(f"Use no ESP32: http://{ip}:5000/api/receber")
# No Windows: ativar manualmente Hotspot Móvel com SSID PROTON / admin123

# API receive
from flask import Flask, request, jsonify
app=Flask(__name__)
@app.route('/api/receber', methods=['POST'])
def receber(): print(request.json); return jsonify(status="recebido"),200
app.run(host='0.0.0.0', port=5000)
```

Também há `central_proton2.py` (variante dark, 8 colunas, `last_seen<10s` = ONLINE).

## Referência Rápida

| Script | Função |
|---|---|
| `UDP_dedicado.py` | Gateway produção UDP→API com enriquecimento |
| `UDP_Dedicado2.py` | Variante headers |
| `envio_UDP.py` | Teste envia JSON random via UDP |
| `server_iot.py` | Template C struct `=BBBBBBH` (comentado) |
| `central_comando.py` | Dashboard SocketIO + comandos broadcast |
| `central_proton2.py` | Dashboard PROTON dark |
| `iniciar_tudo.py` | Hotspot nmcli + Flask API |
| `tete.HTML` | Dashboard minimal audit (na verdade .py) |

## Procedimento

1. No PC que será gateway: `pip install flask flask-socketio requests`.
2. Criar hotspot `PROTON/admin123` (nmcli Linux ou manual Windows).
3. Rodar `python UDP_dedicado.py` para só encaminhar, ou `python off-net/central_comando.py` para dashboard em `http://localhost:5000`.
4. Nos ESP32, apontar `ssid="PROTON"` e `udpPort=4210` (ou `server_url` com IP do PC descoberto via `obter_ip_local()`).
5. Ver logs `[RX] CLM-001 Temp=XX` e `SUCESSO!` no gateway.

## Pitfalls

- **Porta 4210 ocupada:** feche outros terminais Python; `OSError` indica conflito.
- **Firewall Windows:** libere UDP 4210 + TCP 5000.
- **JSON com espaço:** `"dispositivo id"` (com espaço) quebra `json.loads` em alguns parsers; gateway enriquecimento usa `dispositivo_id` com underline — normalize.
- **Broadcast não chega:** verifique `SO_BROADCAST=1` e `255.255.255.255` vs `192.168.X.255` (cálculo `bcast[3]=255`).
- **SocketIO CORS:** `cors_allowed_origins='*'` obrigatório senão navegador bloqueia.
