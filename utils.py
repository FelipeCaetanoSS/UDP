import socket
import time
import struct
import os

# Configurações
TIMEOUT = 2  # Tempo limite para esperar ACKs
WINDOW_SIZE = 5  # Tamanho da janela deslizante
MAX_RETRIES = 5  # Tentativas máximas de reenvio

# Cria um pacote com cabeçalho (tipo + número de sequência) + dados
def criar_pacote(tipo, seq, dados=b""):
    cabecalho = struct.pack("!BI", tipo, seq)  # 1 byte tipo, 4 bytes sequência
    return cabecalho + dados

# Interpreta um pacote recebido, separando tipo, sequência e dados
def interpretar_pacote(pacote):
    tipo, seq = struct.unpack("!BI", pacote[:5])
    dados = pacote[5:]
    return tipo, seq, dados

# Envia todos os pacotes de um arquivo com janela deslizante
def enviar_janela(sock, dados, addr):
    pacotes = []
    seq = 0
    while dados:
        chunk = dados[:1019]
        dados = dados[1019:]
        pacotes.append(criar_pacote(1, seq, chunk))
        seq += 1

    base = 0
    total = len(pacotes)
    retries = 0
    acks = set()
    sock.settimeout(TIMEOUT)

    while base < total and retries < MAX_RETRIES:
        # Envia janela atual
        for i in range(base, min(base + WINDOW_SIZE, total)):
            sock.sendto(pacotes[i], addr)

        try:
            while True:
                ack, _ = sock.recvfrom(1024)
                tipo, ack_seq, _ = interpretar_pacote(ack)
                if tipo == 2:
                    acks.add(ack_seq)
                    if ack_seq >= base:
                        base = ack_seq + 1
                        retries = 0
        except socket.timeout:
            retries += 1
            print("Timeout. Reenviando janela...")

    sock.sendto(criar_pacote(3, 0), addr)  # FIM
