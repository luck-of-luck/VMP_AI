"""Arquivo de teste com defeitos PLANTADOS (para calibrar o predador).

Nao e codigo real de producao. Cada bloco tem um bug conhecido, marcado.
O predador tem que achar estes e NAO inventar outros.
"""

import os
import hashlib
import subprocess


# BUG PLANTADO 1 (bandit B105/B603): segredo hardcoded + shell=True
API_KEY = "sk-live-9f2a8c1e4b7d3a6f0e5c2b9d8f1a4c7e"


def run_cmd(user_input):
    # BUG PLANTADO 2 (bandit B602/B605): shell com concatenacao -> injecao
    return subprocess.call("ls " + user_input, shell=True)


# BUG PLANTADO 3: comparacao de senha sem constante/tempo constante
def check(user, pwd):
    # BUG PLANTADO 4 (bandit B105): segredo em default arg
    def inner(token="hunter2_default_secret"):
        return token

    return inner() == pwd


# BUG PLANTADO 5: except generico engolindo erro
def parse(raw):
    try:
        return int(raw)
    except Exception:
        return 0


# BUG PLANTADO 6: sem verificacao de None antes de uso
def avg(values):
    total = sum(values)
    return total / len(values)  # len==0 -> ZeroDivisionError


# BUG PLANTADO 7: arquivo aberto sem fechar (recurso vazado)
def read_head(path):
    f = open(path)
    return f.readline()


# BUG PLANTADO 8: hash sem salt (MD5 e ainda pi)
def fingerprint(data):
    return hashlib.md5(data.encode()).hexdigest()


# BUG PLANTADO 9: sql injection por format
def find_user(conn, name):
    return conn.execute("SELECT * FROM users WHERE name = '%s'" % name)


# BUG PLANTADO 10 (code smell): variavel de nome enganoso (media nao e media)
def get_average_ratio(numerator, denominator):
    return numerator / denominator


# BUG PLANTADO 11: caminho de arquivo construido sem limite
def build_report(user_id):
    base = "/var/data/reports"
    return os.path.join(base, user_id + "/report.txt")
