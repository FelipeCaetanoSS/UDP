import socket
import time
import struct
import os
import zlib # Importar a biblioteca zlib para CRC

TIMEOUT = 2  # segundos
WINDOW_SIZE = 5
MAX_RETRIES = 5

def criar_pacote(tipo, seq, dados=b""):
    # Calcular o CRC32 dos dados
    checksum = zlib.crc32(dados) & 0xffffffff # Garante que seja unsigned
    # O cabeçalho agora inclui tipo, seq e checksum
    cabecalho = struct.pack("!BII", tipo, seq, checksum) # !BII: unsigned char, unsigned int, unsigned int
    return cabecalho + dados

def interpretar_pacote(pacote):
    # Desempacotar o cabeçalho (tipo, seq, checksum)
    tipo, seq, recebido_checksum = struct.unpack("!BII", pacote[:9]) # 9 bytes para BII
    dados = pacote[9:] # Dados começam após os 9 bytes do cabeçalho
    
    # Calcular o checksum dos dados recebidos para verificação
    calculado_checksum = zlib.crc32(dados) & 0xffffffff
    
    return tipo, seq, dados, recebido_checksum, calculado_checksum # Retornar o checksum para verificação

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
    sock.settimeout(TIMEOUT)

    while base < total and retries < MAX_RETRIES:
        for i in range(base, min(base + WINDOW_SIZE, total)):
            sock.sendto(pacotes[i], addr)

        try:
            while True:
                # O ACK agora também terá o novo formato do cabeçalho para interpretar
                ack, _ = sock.recvfrom(1024)
                # O ACK é tipo 2 e não tem dados, então interpretamos apenas o cabeçalho
                tipo, ack_seq, _, _, _ = interpretar_pacote(ack) # Ignoramos os checksums do ACK
                if tipo == 2 and ack_seq >= base:
                    base = ack_seq + 1
                    retries = 0
                    break # Saímos do loop interno para reavaliar a janela
        except socket.timeout:
            retries += 1
            print("Timeout. Reenviando janela...")

    # Mensagem de FIM (ainda usa tipo 3, seq 0, sem dados, mas com checksum no cabeçalho)
    # Se MAX_RETRIES for atingido, o servidor envia FIM, mas idealmente deveria enviar um ERRO
    # (Abordado no ponto 4)
    sock.sendto(criar_pacote(3, 0), addr)

def receber_arquivo(sock, pasta, nome, addr):
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, nome)
    with open(caminho, "wb") as f:
        esperada = 0
        while True:
            try: # Adiciona um try-except para o recvfrom para lidar com timeout no receptor também
                pacote, _ = sock.recvfrom(2048) # Aumentar buffer para pacotes maiores com checksum
            except socket.timeout:
                print("Timeout no receptor, arquivo pode estar incompleto.")
                # O que fazer aqui depende da política. Poderia enviar um NACK ou reACK do último válido.
                # Por simplicidade, neste caso, ele apenas espera e pode eventualmente quebrar o loop se o servidor parar de enviar.
                ack = criar_pacote(2, esperada - 1) # Reenvia o ACK do último pacote esperado
                sock.sendto(ack, addr)
                continue # Continua esperando

            tipo, seq, dados, recebido_checksum, calculado_checksum = interpretar_pacote(pacote)

            if tipo == 3: # FIM da transmissão
                break
            elif tipo == 1: # Pacote de dados
                if recebido_checksum == calculado_checksum: # Verifica o checksum
                    if seq == esperada:
                        f.write(dados)
                        ack = criar_pacote(2, seq)
                        sock.sendto(ack, addr)
                        esperada += 1
                    else: # Pacote fora de ordem ou duplicado (mas com checksum correto)
                        ack = criar_pacote(2, esperada - 1) # Pede o pacote anterior novamente
                        sock.sendto(ack, addr)
                else:
                    print(f"Checksum inválido para o pacote {seq}. Descartando e pedindo retransmissão.")
                    ack = criar_pacote(2, esperada - 1) # Pede o pacote anterior (já que este foi corrompido)
                    sock.sendto(ack, addr)
            # Pacotes de outros tipos (como ACK, se houvesse na recepção) seriam ignorados aqui.