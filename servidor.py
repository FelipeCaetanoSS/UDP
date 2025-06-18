import socket
import threading
import os
from utils import criar_pacote, interpretar_pacote, enviar_janela

IP = "192.168.91.238"  # IP da sua máquina
PORTA = 5005
PASTA_ARQUIVOS = "arquivos_servidor"
os.makedirs(PASTA_ARQUIVOS, exist_ok=True)

def tratar_cliente(dados, endereco, sock):
    try:
        opcao = dados.decode()
        if opcao == "LISTAR":
            arquivos = os.listdir(PASTA_ARQUIVOS)
            resposta = "\n".join(arquivos).encode()
            sock.sendto(resposta, endereco)

        elif opcao.startswith("UPLOAD"):
            partes = opcao.split()
            nome = "_".join(partes[1:]) or "arquivo_recebido.bin"
            caminho = os.path.join(PASTA_ARQUIVOS, nome)
            with open(caminho, "wb") as f:
                esperada = 0
                while True:
                    pacote, _ = sock.recvfrom(2048)
                    tipo, seq, dados = interpretar_pacote(pacote)

                    if tipo == 3:
                        break
                    elif tipo == 1 and seq == esperada:
                        f.write(dados)
                        ack = criar_pacote(2, seq)
                        sock.sendto(ack, endereco)
                        esperada += 1
                    else:
                        ack = criar_pacote(2, esperada - 1)
                        sock.sendto(ack, endereco)
            print(f"✔ Arquivo '{nome}' salvo em '{PASTA_ARQUIVOS}'.")

        elif opcao.startswith("DOWNLOAD"):
            partes = opcao.split(maxsplit=1)
            if len(partes) < 2:
                sock.sendto(b"ERRO", endereco)
                return
            nome = partes[1]
            caminho = os.path.join(PASTA_ARQUIVOS, nome)
            if not os.path.exists(caminho):
                sock.sendto(b"ERRO", endereco)
                return

            with open(caminho, "rb") as f:
                dados = f.read()
                enviar_janela(sock, dados, endereco)
            print(f"✔ Arquivo '{nome}' enviado para {endereco}.")

    except Exception as e:
        print(f"Erro no cliente {endereco}: {e}")

# Inicializa o servidor
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((IP, PORTA))
print(f"Servidor escutando em {IP}:{PORTA}")

while True:
    dados, endereco = sock.recvfrom(2048)
    threading.Thread(target=tratar_cliente, args=(dados, endereco, sock)).start()
