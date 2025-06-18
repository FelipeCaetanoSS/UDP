import socket
import os
from utils import criar_pacote, interpretar_pacote
from tkinter import filedialog
from pathlib import Path

IP_SERVIDOR = "192.168.91.238"  # IP do servidor
PORTA = 5005

cliente = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
cliente.settimeout(3)

def listar():
    cliente.sendto(b"LISTAR", (IP_SERVIDOR, PORTA))
    try:
        dados, _ = cliente.recvfrom(4096)
        print("\nArquivos disponíveis:\n" + dados.decode())
    except socket.timeout:
        print("Servidor não respondeu.")

def upload():
    caminho = filedialog.askopenfilename(title="Escolha um arquivo")
    if not caminho:
        return
    nome = os.path.basename(caminho)
    cliente.sendto(f"UPLOAD {nome}".encode(), (IP_SERVIDOR, PORTA))

    with open(caminho, "rb") as f:
        seq = 0
        while True:
            dados = f.read(1019)
            if not dados:
                break
            pacote = criar_pacote(1, seq, dados)
            cliente.sendto(pacote, (IP_SERVIDOR, PORTA))
            try:
                ack, _ = cliente.recvfrom(1024)
                tipo, ack_seq, _ = interpretar_pacote(ack)
                if tipo == 2 and ack_seq == seq:
                    seq += 1
                else:
                    f.seek(f.tell() - len(dados))  # retransmite
            except socket.timeout:
                print("Timeout. Reenviando pacote...")
                f.seek(f.tell() - len(dados))

    cliente.sendto(criar_pacote(3, 0), (IP_SERVIDOR, PORTA))
    print("Upload concluído.")

def download():
    nome = input("Digite o nome do arquivo para download: ")
    cliente.sendto(f"DOWNLOAD {nome}".encode(), (IP_SERVIDOR, PORTA))
    try:
        dados, _ = cliente.recvfrom(2048)
        if dados == b"ERRO":
            print("Arquivo não encontrado no servidor.")
            return

        # Prepara para salvar no diretório Downloads
        caminho_download = str(Path.home() / "Downloads" / nome)
        with open(caminho_download, "wb") as f:
            tipo, seq, payload = interpretar_pacote(dados)
            esperada = 0

            while tipo != 3:
                if tipo == 1 and seq == esperada:
                    f.write(payload)
                    ack = criar_pacote(2, seq)
                    cliente.sendto(ack, (IP_SERVIDOR, PORTA))
                    esperada += 1
                else:
                    ack = criar_pacote(2, esperada - 1)
                    cliente.sendto(ack, (IP_SERVIDOR, PORTA))

                pacote, _ = cliente.recvfrom(2048)
                tipo, seq, payload = interpretar_pacote(pacote)

        print(f"Download concluído. Arquivo salvo em: {caminho_download}")
    except socket.timeout:
        print("Timeout do servidor.")

while True:
    print("\n1. Listar arquivos\n2. Upload\n3. Download\n4. Sair")
    op = input("Escolha: ")
    if op == "1":
        listar()
    elif op == "2":
        upload()
    elif op == "3":
        download()
    elif op == "4":
        break
