# cliente.py

import socket # Importa a biblioteca de sockets para a comunicação de rede.
import os # Importa a biblioteca do sistema operacional para manipulação de caminhos e nomes de arquivos.
from utils import enviar_arquivo, receber_arquivo # Importa as funções de alto nível do nosso protocolo do arquivo utils.py.
from tkinter import filedialog, Tk # Importa do Tkinter as ferramentas para criar uma caixa de diálogo de seleção de arquivo.
from pathlib import Path # Importa a classe Path para manipulação de caminhos de arquivo de forma moderna e multiplataforma.

# --- Configurações do Cliente ---
IP_SERVIDOR = "192.168.15.13" # Define o endereço IP do servidor. "127.0.0.1" é o localhost (a própria máquina).
PORTA = 5005 # Define a porta do servidor à qual o cliente irá se conectar. Deve ser a mesma do servidor.
TIMEOUT = 2 # Define um timeout padrão para operações do cliente (não usado diretamente aqui, mas em utils).

def listar(cliente_socket):
    """Pede a lista de arquivos ao servidor."""
    print("\nSolicitando lista de arquivos...") # Informa ao usuário a ação que está sendo executada.
    try: # Inicia um bloco para tratar exceções de rede, como timeouts.
        cliente_socket.settimeout(5) # Define um timeout de 5 segundos para esta operação específica.
        cliente_socket.sendto(b"LISTAR", (IP_SERVIDOR, PORTA)) # Envia o comando "LISTAR" em bytes para o endereço do servidor.
        dados, _ = cliente_socket.recvfrom(4096) # Espera receber uma resposta de até 4096 bytes do servidor.
        print("\n--- Arquivos Disponiveis no Servidor ---\n" + dados.decode(errors='ignore')) # Decodifica a resposta e a imprime.
        print("----------------------------------------") # Imprime uma linha para formatação.
    except socket.timeout: # Captura o erro se o servidor não responder a tempo.
        print("Erro: O servidor nao respondeu ao pedido de listagem.") # Informa o usuário sobre o timeout.
    except Exception as e: # Captura qualquer outro erro que possa ocorrer.
        print(f"Ocorreu um erro: {e}") # Exibe a mensagem de erro.

def upload(cliente_socket):
    """Pede ao usuário para escolher um arquivo e o envia para o servidor."""
    root = Tk() # Cria uma instância da janela principal do Tkinter.
    root.withdraw() # Esconde a janela principal, pois queremos apenas a caixa de diálogo.
    caminho = filedialog.askopenfilename(title="Escolha um arquivo para enviar") # Abre a caixa de diálogo para o usuário selecionar um arquivo.
    if not caminho: # Se o usuário fechar a caixa de diálogo sem selecionar um arquivo.
        print("Nenhum arquivo selecionado.") # Informa que a operação foi cancelada.
        return # Retorna e encerra a função.

    nome_arquivo = os.path.basename(caminho) # Extrai apenas o nome do arquivo do caminho completo.
    print(f"Preparando para enviar o arquivo: {nome_arquivo}") # Informa qual arquivo será enviado.

    cliente_socket.sendto(f"UPLOAD {nome_arquivo}".encode(), (IP_SERVIDOR, PORTA)) # Envia o comando "UPLOAD" seguido do nome do arquivo para o servidor.
    
    enviar_arquivo(cliente_socket, (IP_SERVIDOR, PORTA), caminho) # Chama a função utilitária para lidar com todo o processo de envio do arquivo.

def download(cliente_socket):
    """Pede um nome de arquivo e o baixa do servidor."""
    nome_arquivo = input("Digite o nome do arquivo para download: ") # Pede ao usuário para digitar o nome do arquivo desejado.
    if not nome_arquivo: # Verifica se o usuário digitou algo.
        print("Nome do arquivo nao pode ser vazio.") # Informa que o nome não pode ser vazio.
        return # Encerra a função.

    caminho_destino = os.path.join(str(Path.home()), "Downloads", os.path.basename(nome_arquivo)) # Constrói o caminho de destino na pasta de Downloads do usuário.
    print(f"Solicitando download de '{nome_arquivo}' para '{caminho_destino}'...") # Informa ao usuário sobre a ação.

    cliente_socket.sendto(f"DOWNLOAD {nome_arquivo}".encode(), (IP_SERVIDOR, PORTA)) # Envia o comando "DOWNLOAD" com o nome do arquivo para o servidor.
    
    if not receber_arquivo(cliente_socket, (IP_SERVIDOR, PORTA), caminho_destino): # Chama a função utilitária para receber o arquivo e verifica seu retorno.
        print(f"O download de '{nome_arquivo}' falhou.") # Se a função retornar False, informa que o download falhou.
    else: # Se a função retornar True.
        print(f"\nDownload completo! Arquivo salvo em:\n{caminho_destino}") # Informa que o download foi bem-sucedido e onde o arquivo foi salvo.

def main():
    """Função principal que executa o loop do menu do cliente."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as cliente: # Cria um socket UDP e usa 'with' para garantir que ele seja fechado ao final.
        while True: # Inicia o loop infinito do menu principal.
            print("\n===============================") # Imprime o cabeçalho do menu.
            print("Escolha uma opcao:") # Pede ao usuário para escolher uma ação.
            print("1. Listar arquivos no servidor") # Opção de listar arquivos.
            print("2. Fazer Upload de um arquivo") # Opção de upload.
            print("3. Fazer Download de um arquivo") # Opção de download.
            print("4. Sair") # Opção para fechar o cliente.
            print("===============================") # Imprime o rodapé do menu.
            opcao = input("Opcao: ") # Lê a escolha do usuário.

            if opcao == "1": # Se a opção for "1".
                listar(cliente) # Chama a função para listar arquivos.
            elif opcao == "2": # Se a opção for "2".
                upload(cliente) # Chama a função para fazer upload.
            elif opcao == "3": # Se a opção for "3".
                download(cliente) # Chama a função para fazer download.
            elif opcao == "4": # Se a opção for "4".
                print("Saindo...") # Informa que o programa está encerrando.
                break # Quebra o loop 'while' e encerra o programa.
            else: # Se a opção for qualquer outra coisa.
                print("Opcao invalida. Tente novamente.") # Informa que a escolha é inválida.

if __name__ == "__main__": # Garante que o script está sendo executado diretamente.
    main() # Chama a função principal para iniciar o cliente.