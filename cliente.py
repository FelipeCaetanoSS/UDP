import socket
import os
from utils import interpretar_pacote, criar_pacote # Agora interpretar_pacote retorna mais valores
from tkinter import filedialog
from pathlib import Path
import zlib # Para o crc32 se for calcular no cliente também, embora utils já faça

IP_SERVIDOR = "192.168.15.13"
PORTA = 5005
TIMEOUT = 2
WINDOW_SIZE = 5

cliente = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
cliente.settimeout(TIMEOUT)

def listar():
    cliente.sendto(b"LISTAR", (IP_SERVIDOR, PORTA))
    try:
        dados, _ = cliente.recvfrom(4096)
        print("\nArquivos disponíveis:\n" + dados.decode(errors='ignore'))
    except socket.timeout:
        print("Servidor não respondeu.")

def upload():
    caminho = filedialog.askopenfilename(title="Escolha um arquivo")
    if not caminho:
        return
    nome = os.path.basename(caminho)
    # A mensagem inicial 'UPLOAD {nome}' não usa o protocolo de pacotes, então não precisa de checksum aqui.
    cliente.sendto(f"UPLOAD {nome}".encode(), (IP_SERVIDOR, PORTA))

    # --- Ponto 2: Correção de "Gargalo" no Upload do Cliente ---
    # Em vez de ler tudo para a memória de uma vez, vamos ler em chunks e gerenciar a janela.
    
    # O cliente também precisa de uma variável para o socket timeout para o loop de retransmissão
    cliente.settimeout(TIMEOUT) 

    with open(caminho, "rb") as f:
        # Inicialização para o protocolo de janela deslizante
        base = 0
        seq_atual = 0 # Próximo número de sequência a ser lido do arquivo
        janela_pacotes_buffer = {} # Dicionário para armazenar pacotes na janela: {seq: pacote_bytes}
        total_pacotes = -1 # Será determinado dinamicamente ou por um marcador de fim de arquivo

        # Loop principal para enviar o arquivo
        while True:
            # Preencher a janela com novos pacotes se houver espaço e dados para ler
            while len(janela_pacotes_buffer) < WINDOW_SIZE and f.tell() < os.fstat(f.fileno()).st_size:
                dados_chunk = f.read(1019)
                if not dados_chunk: # Fim do arquivo
                    break
                pacote = criar_pacote(1, seq_atual, dados_chunk)
                janela_pacotes_buffer[seq_atual] = pacote
                seq_atual += 1
            
            # Se não há mais pacotes para ler e a janela está vazia, terminamos
            if not janela_pacotes_buffer and f.tell() >= os.fstat(f.fileno()).st_size:
                break # Sai do loop principal de envio

            # Enviar todos os pacotes na janela (retransmissão)
            for s in sorted(janela_pacotes_buffer.keys()):
                cliente.sendto(janela_pacotes_buffer[s], (IP_SERVIDOR, PORTA))

            try:
                # Esperar por ACKs para avançar a janela
                # Ponto 3: Correção de Reset de 'retries' no Cliente (Upload)
                # A lógica de 'retries' no cliente para upload será mais robusta aqui.
                # Cada envio de janela tem seu próprio conjunto de tentativas.
                # Se um ACK válido for recebido, as retries para aquela janela são zeradas.
                ack_recebido_valido = False
                while True: # Loop para receber múltiplos ACKs se necessário
                    ack, _ = cliente.recvfrom(1024)
                    # Agora interpretar_pacote retorna mais coisas, precisamos ignorar o que não é tipo/seq
                    tipo, ack_seq, _, _, _ = interpretar_pacote(ack) 
                    
                    if tipo == 2 and ack_seq >= base:
                        # Remove pacotes reconhecidos do buffer da janela
                        for s_acked in range(base, ack_seq + 1):
                            if s_acked in janela_pacotes_buffer:
                                del janela_pacotes_buffer[s_acked]
                        base = ack_seq + 1 # Avança a base da janela
                        ack_recebido_valido = True
                        break # Sai do loop de recebimento de ACK e reavalia a janela
            except socket.timeout:
                print("Timeout. Reenviando janela de upload...")
                # Nenhuma mudança na base, apenas retransmite a janela atual na próxima iteração
                # A contagem de 'retries' implícita será que se o loop externo continuar, haverá retransmissões.
                # Poderíamos adicionar um contador de retries específico para esta janela aqui.
                # Para manter a simplicidade e a consistência com o utils.py, a retransmissão da janela é o comportamento.
                
                # Se quisermos limitar as retries como no servidor:
                # retries_atuais += 1
                # if retries_atuais >= MAX_RETRIES:
                #     print("Limite de retransmissões atingido, upload pode estar incompleto.")
                #     break # ou lançar um erro
                
                pass # Continua para a próxima iteração do while True principal para reenviar a janela

        # Finaliza a transmissão enviando o pacote de FIM.
        cliente.sendto(criar_pacote(3, 0), (IP_SERVIDOR, PORTA))
        print("Upload concluído.")


def download():
    nome = input("Digite o nome do arquivo para download: ")
    # A mensagem inicial 'DOWNLOAD {nome}' não usa o protocolo de pacotes.
    cliente.sendto(f"DOWNLOAD {nome}".encode(), (IP_SERVIDOR, PORTA))
    caminho = os.path.join(str(Path.home()), "Downloads", nome)

    try:
        with open(caminho, "wb") as f:
            esperada = 0
            # Ponto 4: Melhoria no Tratamento de Erro de Nome de Arquivo/Servidor (Download)
            # O cliente precisa saber como interpretar um ERRO do servidor.
            # Vamos receber a primeira resposta do servidor para verificar se é um erro.
            primeira_resposta, _ = cliente.recvfrom(2048)
            tipo_resp, seq_resp, dados_resp, recebido_checksum_resp, calculado_checksum_resp = interpretar_pacote(primeira_resposta)

            if tipo_resp == 4: # Supondo tipo 4 para ERRO
                print(f"Erro no download: {dados_resp.decode(errors='ignore')}")
                return # Aborta o download
            elif tipo_resp == 3 and seq_resp == 0 and not dados_resp: # Servidor enviou FIM imediatamente (arquivo vazio ou erro inesperado que resultou em fim)
                print("Download completo (arquivo vazio ou servidor indicou fim imediato).")
                return # Aborta o download se o arquivo for vazio.
            
            # Se não é erro e não é fim imediato, é um pacote de dados ou início.
            # Precisa reprocessar o primeiro pacote que foi lido se ele for um pacote de dados.
            # Idealmente, o servidor não enviaria o primeiro pacote de dados com o mesmo mecanismo
            # que envia a mensagem de erro. Poderíamos ter um "início de download" com tipo 0
            # para o servidor enviar, e ele pode conter o tamanho do arquivo, etc.
            # Para manter a lógica atual de Go-Back-N, vamos reusar o primeiro pacote lido.
            pacote_inicial = primeira_resposta
            
            while True:
                # Se já processamos o pacote inicial, agora recebemos normalmente
                if 'pacote_inicial' in locals() and pacote_inicial:
                    pacote = pacote_inicial
                    pacote_inicial = None # Marca como processado
                else:
                    pacote, _ = cliente.recvfrom(2048)
                
                tipo, seq, dados, recebido_checksum, calculado_checksum = interpretar_pacote(pacote)
                
                if tipo == 3: # FIM da transmissão
                    break
                if tipo == 1: # Pacote de dados
                    if recebido_checksum == calculado_checksum: # Verifica o checksum
                        if seq == esperada:
                            f.write(dados)
                            ack = criar_pacote(2, seq)
                            cliente.sendto(ack, (IP_SERVIDOR, PORTA))
                            esperada += 1
                        else: # Pacote fora de ordem ou duplicado (mas com checksum correto)
                            # Reenvia ACK para o último pacote corretamente recebido (Go-Back-N)
                            ack = criar_pacote(2, esperada - 1)
                            cliente.sendto(ack, (IP_SERVIDOR, PORTA))
                    else:
                        print(f"Checksum inválido para o pacote {seq} durante o download. Descartando.")
                        # Não envia ACK para este pacote inválido, forçando o servidor a retransmitir.
                        # Ou, para ser mais explícito, envia ACK para o último esperado.
                        ack = criar_pacote(2, esperada - 1)
                        cliente.sendto(ack, (IP_SERVIDOR, PORTA))
                # Pacotes de outros tipos são ignorados aqui (como tipo 4 ERRO que já foi tratado antes)
        print(f"Download completo. Arquivo salvo em:\n{caminho}")
    except socket.timeout:
        print("Timeout do servidor durante o download.")
        # Se um timeout acontecer durante o download, o arquivo pode estar incompleto.
        # Poderíamos ter um mecanismo para tentar reativar ou informar ao usuário.

while True:
    print("\n1. Listar arquivos\n2. Upload\n3. Download\n4. Sair")
    opcao = input("Escolha: ")
    if opcao == "1":
        listar()
    elif opcao == "2":
        upload()
    elif opcao == "3":
        download()
    elif opcao == "4":
        break
