import socket
import threading
import os
from utils import receber_arquivo, enviar_janela, criar_pacote # Importar criar_pacote

IP = "192.168.15.13"
PORTA = 5005
PASTA_ARQUIVOS = "arquivos_servidor"

os.makedirs(PASTA_ARQUIVOS, exist_ok=True)

def tratar_cliente(dados, endereco, sock):
    opcao = dados.decode(errors='ignore')
    if opcao == "LISTAR":
        arquivos = os.listdir(PASTA_ARQUIVOS)
        resposta = "\n".join(arquivos).encode()
        sock.sendto(resposta, endereco)

    elif opcao.startswith("UPLOAD"):
        partes = opcao.split()
        nome = "arquivo_recebido.bin"
        if len(partes) >= 2:
            nome = "_".join(partes[1:])
        receber_arquivo(sock, PASTA_ARQUIVOS, nome, endereco)
        print(f"Arquivo '{nome}' salvo com sucesso.")

    elif opcao.startswith("DOWNLOAD"):
        partes = opcao.split(maxsplit=1)
        if len(partes) < 2:
            # Ponto 4: Melhoria no Tratamento de Erro de Nome de Arquivo (Servidor)
            # Envia um pacote de ERRO (tipo 4) com uma mensagem.
            erro_msg = "Nome do arquivo não especificado."
            pacote_erro = criar_pacote(4, 0, erro_msg.encode())
            sock.sendto(pacote_erro, endereco)
            return
        _, nome = partes
        caminho = os.path.join(PASTA_ARQUIVOS, nome)
        if not os.path.exists(caminho):
            # Ponto 4: Melhoria no Tratamento de Erro de Nome de Arquivo (Servidor)
            # Envia um pacote de ERRO (tipo 4) com uma mensagem.
            erro_msg = f"Arquivo '{nome}' não encontrado no servidor."
            pacote_erro = criar_pacote(4, 0, erro_msg.encode())
            sock.sendto(pacote_erro, endereco)
            return

        with open(caminho, "rb") as f:
            conteudo_arquivo = f.read()
            # Ponto 4: Melhoria no Tratamento de MAX_RETRIES do Servidor (Download)
            # A função enviar_janela agora precisa lidar com o caso de falha.
            # Poderíamos ter um retorno booleano ou levantar uma exceção.
            # Por enquanto, a lógica interna do enviar_janela já envia um FIM.
            # A melhoria aqui é que o cliente agora sabe lidar com o pacote de ERRO.
            enviado_com_sucesso = enviar_janela(sock, conteudo_arquivo, endereco)
            if enviado_com_sucesso: # A `enviar_janela` precisa retornar algo
                print(f"Arquivo '{nome}' enviado.")
            else:
                print(f"Falha ao enviar o arquivo '{nome}' após múltiplas tentativas.")
                # O servidor pode enviar um pacote de ERRO aqui também, se desejar.
                erro_msg = f"Falha na transmissão do arquivo '{nome}'."
                pacote_erro = criar_pacote(4, 0, erro_msg.encode())
                sock.sendto(pacote_erro, endereco)


sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((IP, PORTA))
print(f"Servidor escutando em {IP}:{PORTA}")

while True:
    dados, endereco = sock.recvfrom(2048) # Aumentar buffer para pacotes maiores
    threading.Thread(target=tratar_cliente, args=(dados, endereco, sock)).start()