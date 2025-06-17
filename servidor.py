# servidor.py

import socket # Importa a biblioteca de sockets para a comunicação de rede.
import threading # Importa a biblioteca de threading para lidar com múltiplos clientes simultaneamente.
import os # Importa a biblioteca do sistema operacional para manipulação de arquivos e diretórios.
from utils import receber_arquivo, enviar_arquivo, criar_pacote # Importa as funções de utilidade do protocolo do arquivo utils.py.

# --- Configurações do Servidor ---
IP = "192.168.15.13"  # Define o IP para o servidor escutar. "0.0.0.0" significa que ele aceitará conexões de qualquer interface de rede.
PORTA = 5005 # Define a porta em que o servidor irá escutar por conexões.
PASTA_ARQUIVOS = "arquivos_servidor" # Define o nome da pasta onde os arquivos do servidor serão armazenados.

os.makedirs(PASTA_ARQUIVOS, exist_ok=True) # Cria a pasta de arquivos do servidor se ela ainda não existir.

def tratar_cliente(dados, endereco, sock):
    """Função executada por uma thread para lidar com uma requisição de cliente."""
    try: # Inicia um bloco para tratar possíveis erros de decodificação.
        opcao = dados.decode(errors='ignore') # Decodifica os dados recebidos (bytes) para uma string, ignorando erros.
    except Exception as e: # Captura qualquer exceção durante a decodificação.
        print(f"Erro ao decodificar mensagem de {endereco}: {e}") # Imprime o erro.
        return # Encerra a função da thread.

    print(f"Recebido '{opcao}' de {endereco}") # Imprime no console do servidor qual comando foi recebido e de quem.

    if opcao == "LISTAR": # Se o comando for "LISTAR".
        try: # Inicia um bloco para tratar erros ao acessar o sistema de arquivos.
            arquivos = os.listdir(PASTA_ARQUIVOS) # Obtém uma lista com os nomes dos arquivos na pasta do servidor.
            if not arquivos: # Verifica se a lista de arquivos está vazia.
                resposta = "Nenhum arquivo disponivel no servidor.".encode() # Prepara uma mensagem informando que não há arquivos.
            else: # Se houver arquivos.
                resposta = "\n".join(arquivos).encode() # Junta os nomes dos arquivos em uma única string, separados por quebra de linha, e a codifica para bytes.
            sock.sendto(resposta, endereco) # Envia a lista de arquivos (ou a mensagem) de volta para o cliente.
        except Exception as e: # Captura qualquer erro durante o processo.
            print(f"Erro ao listar arquivos: {e}") # Imprime o erro no console do servidor.
            sock.sendto(b"Erro ao processar a lista de arquivos.", endereco) # Envia uma mensagem de erro genérica ao cliente.

    elif opcao.startswith("UPLOAD"): # Se o comando começar com "UPLOAD".
        partes = opcao.split(maxsplit=1) # Divide a string do comando em no máximo duas partes (ex: "UPLOAD" e "nome.txt").
        if len(partes) < 2: # Verifica se o comando tem as duas partes necessárias.
            print(f"Comando UPLOAD inválido de {endereco}") # Informa sobre o comando malformado.
            return # Encerra a função.
        
        nome = os.path.basename(partes[1]) # Extrai apenas o nome do arquivo do caminho para evitar ataques de "path traversal".
        caminho_completo = os.path.join(PASTA_ARQUIVOS, nome) # Monta o caminho completo onde o arquivo será salvo.
        
        print(f"Iniciando recebimento do arquivo '{nome}' de {endereco}...") # Loga o início do recebimento.
        if receber_arquivo(sock, endereco, caminho_completo): # Chama a função utilitária para receber o arquivo.
            print(f"Arquivo '{nome}' salvo com sucesso de {endereco}.") # Se a função retornar True, loga o sucesso.
        else: # Se a função retornar False.
            print(f"Falha ao receber o arquivo '{nome}' de {endereco}.") # Loga a falha.

    elif opcao.startswith("DOWNLOAD"): # Se o comando começar com "DOWNLOAD".
        partes = opcao.split(maxsplit=1) # Divide o comando para obter o nome do arquivo.
        if len(partes) < 2: # Verifica se o nome do arquivo foi fornecido.
            erro_msg = "Nome do arquivo nao especificado.".encode() # Prepara uma mensagem de erro.
            sock.sendto(criar_pacote(4, 0, erro_msg), endereco) # Envia um pacote de erro (tipo 4) para o cliente.
            return # Encerra a função.

        nome = os.path.basename(partes[1]) # Extrai o nome do arquivo do comando para segurança.
        caminho_completo = os.path.join(PASTA_ARQUIVOS, nome) # Monta o caminho completo do arquivo no servidor.

        if not os.path.exists(caminho_completo): # Verifica se o arquivo solicitado realmente existe.
            erro_msg = f"Arquivo '{nome}' nao encontrado no servidor.".encode() # Prepara uma mensagem de erro informando que o arquivo não foi encontrado.
            sock.sendto(criar_pacote(4, 0, erro_msg), endereco) # Envia um pacote de erro (tipo 4) para o cliente.
            return # Encerra a função.
            
        print(f"Iniciando envio do arquivo '{nome}' para {endereco}...") # Loga o início do envio.
        if enviar_arquivo(sock, endereco, caminho_completo): # Chama a função utilitária para enviar o arquivo.
            print(f"Arquivo '{nome}' enviado com sucesso para {endereco}.") # Se o envio for bem-sucedido, loga a mensagem de sucesso.
        else: # Se o envio falhar.
            print(f"Falha ao enviar o arquivo '{nome}' para {endereco}.") # Loga a mensagem de falha.

def main():
    """Função principal que inicia o servidor."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Cria um socket UDP (SOCK_DGRAM) sobre IPv4 (AF_INET).
    try: # Inicia um bloco para garantir que o socket seja fechado em caso de erro.
        sock.bind((IP, PORTA)) # Associa (bind) o socket ao endereço IP e porta definidos.
        print(f"Servidor escutando em {IP}:{PORTA}") # Informa que o servidor está online e pronto para receber dados.

        while True: # Inicia o loop principal e infinito do servidor.
            dados, endereco = sock.recvfrom(2048) # Bloqueia a execução e espera por dados de um cliente. Recebe até 2048 bytes.
            thread = threading.Thread(target=tratar_cliente, args=(dados, endereco, sock)) # Cria uma nova thread para lidar com a requisição do cliente.
            thread.start() # Inicia a execução da thread.
    except Exception as e: # Captura qualquer exceção que possa ocorrer no servidor principal.
        print(f"Erro fatal no servidor: {e}") # Imprime a mensagem de erro fatal.
    finally: # Bloco que é executado sempre, independentemente de ter ocorrido erro ou não.
        sock.close() # Fecha o socket do servidor para liberar a porta.

if __name__ == "__main__": # Verifica se o script está sendo executado diretamente (não importado como um módulo).
    main() # Chama a função principal para iniciar o servidor.