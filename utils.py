# utils.py

import socket # Importa a biblioteca de sockets para comunicação em rede.
import time # Importa a biblioteca de tempo, útil para timeouts (embora não usada diretamente nesta versão, é comum em networking).
import struct # Importa a biblioteca struct para empacotar e desempacotar dados em formatos binários.
import os # Importa a biblioteca de sistema operacional, usada para interagir com o sistema de arquivos (caminhos, tamanho de arquivos, etc.).
import zlib # Importa a biblioteca zlib para calcular o checksum CRC32, que verifica a integridade dos dados.

# --- Constantes do Protocolo ---
TIMEOUT = 2  # Define o tempo de espera (em segundos) por uma resposta (ACK) antes de considerar um pacote perdido.
WINDOW_SIZE = 5  # Define o tamanho da janela deslizante, ou seja, quantos pacotes podem ser enviados sem receber confirmação.
MAX_RETRIES = 5  # Define o número máximo de vezes que o remetente tentará reenviar um pacote ou janela antes de desistir.
CHUNK_SIZE = 1019  # Define o tamanho máximo dos dados em um pacote. Escolhido para que o pacote total (1019 + 9 de cabeçalho) não exceda o MTU comum de 1500 bytes.

def criar_pacote(tipo, seq, dados=b""):
    """Cria um pacote com cabeçalho (tipo, seq, checksum) e dados."""
    checksum = zlib.crc32(dados) & 0xffffffff  # Calcula o checksum CRC32 dos dados e aplica uma máscara para garantir que seja um inteiro de 32 bits sem sinal.
    cabecalho = struct.pack("!BII", tipo, seq, checksum)  # Empacota o tipo (1 byte), número de sequência (4 bytes) e checksum (4 bytes) em um formato binário de 9 bytes.
    return cabecalho + dados  # Retorna o cabeçalho concatenado com os dados do pacote.

def interpretar_pacote(pacote):
    """Interpreta um pacote, retornando cabeçalho e dados, e verificando o checksum."""
    if len(pacote) < 9: # Verifica se o pacote tem pelo menos o tamanho do cabeçalho.
        return None, None, None, None, None # Retorna None para todos os campos se o pacote for inválido ou curto demais.
    tipo, seq, recebido_checksum = struct.unpack("!BII", pacote[:9]) # Desempacota os primeiros 9 bytes do pacote para obter o tipo, sequência e checksum.
    dados = pacote[9:] # Extrai os dados, que são todo o conteúdo do pacote após o cabeçalho de 9 bytes.
    calculado_checksum = zlib.crc32(dados) & 0xffffffff # Calcula o checksum dos dados recebidos para verificação.
    return tipo, seq, dados, recebido_checksum, calculado_checksum # Retorna todas as partes do pacote interpretadas.

def enviar_arquivo(sock, addr, caminho_arquivo):
    """
    Função genérica para enviar um arquivo usando uma janela deslizante (Go-Back-N).
    Lê o arquivo em chunks para não carregar tudo na memória.
    Retorna True se o envio for bem-sucedido, False caso contrário.
    """
    try: # Inicia um bloco de tratamento de exceções para a abertura do arquivo.
        tamanho_arquivo = os.fstat(os.open(caminho_arquivo, os.O_RDONLY)).st_size # Obtém o tamanho do arquivo sem carregá-lo na memória.
    except FileNotFoundError: # Captura o erro se o arquivo não for encontrado.
        print(f"Erro: Arquivo '{caminho_arquivo}' não encontrado para envio.") # Informa ao usuário que o arquivo não existe.
        return False # Retorna False para indicar falha no envio.

    with open(caminho_arquivo, "rb") as f: # Abre o arquivo em modo de leitura binária ("rb"). O 'with' garante que o arquivo será fechado automaticamente.
        sock.settimeout(TIMEOUT) # Define o timeout no socket para as operações de recebimento de ACK.
        base = 0 # Inicializa a base da janela deslizante (o número de sequência do pacote mais antigo não confirmado).
        seq_atual = 0 # Inicializa o número de sequência do próximo pacote a ser criado.
        janela_pacotes_buffer = {}  # Cria um dicionário para armazenar os pacotes que estão na janela de envio: {seq: pacote_bytes}.
        retries = 0 # Inicializa o contador de tentativas de reenvio.

        while base < seq_atual or f.tell() < tamanho_arquivo: # Continua o loop enquanto houver pacotes não confirmados na janela ou dados a serem lidos do arquivo.
            # Preenche a janela com novos pacotes.
            while len(janela_pacotes_buffer) < WINDOW_SIZE and f.tell() < tamanho_arquivo: # Continua enquanto a janela não estiver cheia e houver dados no arquivo.
                dados_chunk = f.read(CHUNK_SIZE) # Lê um pedaço (chunk) do arquivo com o tamanho definido.
                if not dados_chunk: # Se não houver mais dados para ler, sai do loop de preenchimento.
                    break # Interrompe o loop de leitura.
                pacote = criar_pacote(1, seq_atual, dados_chunk) # Cria um pacote de dados (tipo 1) com o chunk lido.
                janela_pacotes_buffer[seq_atual] = pacote # Armazena o pacote no buffer da janela.
                seq_atual += 1 # Incrementa o número de sequência para o próximo pacote.
            
            if not janela_pacotes_buffer and f.tell() >= tamanho_arquivo: # Se o buffer da janela está vazio e todo o arquivo foi lido.
                break # Sai do loop principal, indicando que a transferência foi concluída.

            # Envia (ou reenvia) todos os pacotes na janela.
            for s in sorted(janela_pacotes_buffer.keys()): # Itera sobre os números de sequência dos pacotes na janela, em ordem.
                sock.sendto(janela_pacotes_buffer[s], addr) # Envia cada pacote para o endereço de destino.

            # Espera por um ACK (confirmação).
            try: # Inicia um bloco para tentar receber um ACK.
                ack_pacote, _ = sock.recvfrom(1024) # Tenta receber um pacote de até 1024 bytes do socket.
                tipo, ack_seq, _, _, _ = interpretar_pacote(ack_pacote) # Interpreta o pacote recebido, esperando que seja um ACK.
                
                if tipo == 2 and ack_seq >= base: # Verifica se é um pacote de ACK (tipo 2) e se a confirmação é válida (maior ou igual à base).
                    pacotes_confirmados = [s for s in janela_pacotes_buffer if s <= ack_seq] # Cria uma lista de todos os pacotes que foram confirmados pelo ACK cumulativo.
                    for s_acked in pacotes_confirmados: # Itera sobre os pacotes confirmados.
                        del janela_pacotes_buffer[s_acked] # Remove cada pacote confirmado do buffer da janela.
                    
                    base = ack_seq + 1 # Avança a base da janela para o próximo pacote após o último confirmado.
                    retries = 0  # Reseta o contador de tentativas, pois a comunicação está fluindo.
            except socket.timeout: # Captura a exceção de timeout se nenhum ACK for recebido a tempo.
                retries += 1 # Incrementa o contador de tentativas de reenvio.
                print(f"Timeout no envio. Tentativa {retries}/{MAX_RETRIES}. Reenviando janela a partir da base {base}...") # Informa ao usuário sobre o timeout.
                if retries >= MAX_RETRIES: # Verifica se o número máximo de tentativas foi atingido.
                    print("Erro: Limite de retransmissões atingido. O envio falhou.") # Informa que o envio falhou.
                    sock.sendto(criar_pacote(4, 0, b"Timeout no envio"), addr) # Envia um pacote de erro (tipo 4) para o receptor.
                    return False # Retorna False para indicar a falha.

    sock.sendto(criar_pacote(3, 0), addr) # Envia um pacote de FIM (tipo 3) para sinalizar o término da transmissão.
    print("Envio de arquivo concluído com sucesso.") # Imprime uma mensagem de sucesso.
    return True # Retorna True, indicando que o arquivo foi enviado com sucesso.


def receber_arquivo(sock, addr, caminho_arquivo):
    """
    Função genérica para receber um arquivo.
    Retorna True se o recebimento for bem-sucedido, False caso contrário.
    """
    arquivo_aberto = False # Flag para controlar se o arquivo de destino já foi aberto.
    f = None # Variável para manter o objeto do arquivo.
    esperada = 0 # Número de sequência do próximo pacote esperado.
    
    sock.settimeout(TIMEOUT * (MAX_RETRIES + 1)) # Define um timeout mais longo no receptor para dar tempo ao remetente de esgotar suas tentativas.

    while True: # Inicia um loop infinito para receber pacotes.
        try: # Bloco para tratar exceções durante o recebimento.
            pacote, sender_addr = sock.recvfrom(2048) # Espera receber um pacote de até 2048 bytes.
            if sender_addr != addr: continue # Se o pacote veio de um endereço diferente do esperado, ignora-o e continua.

            tipo, seq, dados, recebido_checksum, calculado_checksum = interpretar_pacote(pacote) # Interpreta o pacote recebido.

            if tipo == 4: # Se for um pacote de ERRO (tipo 4).
                print(f"Erro recebido do servidor: {dados.decode(errors='ignore')}") # Exibe a mensagem de erro.
                if f: f.close() # Se o arquivo estiver aberto, fecha-o.
                if os.path.exists(caminho_arquivo): os.remove(caminho_arquivo) # Se o arquivo parcial foi criado, remove-o.
                return False # Retorna False, indicando falha no recebimento.
            if tipo == 3: # Se for um pacote de FIM (tipo 3).
                print("Recebido sinal de FIM da transmissão.") # Informa que o sinal de fim foi recebido.
                break # Sai do loop principal, pois a transmissão terminou.
            
            if tipo != 1: # Se o pacote não for de dados (tipo 1), ignora-o.
                continue # Volta para o início do loop para esperar o próximo pacote.

            # Abre o arquivo localmente apenas quando o primeiro pacote de dados válido chega.
            if not arquivo_aberto: # Verifica se o arquivo ainda não foi aberto.
                os.makedirs(os.path.dirname(caminho_arquivo), exist_ok=True) # Garante que o diretório de destino exista.
                f = open(caminho_arquivo, "wb") # Abre o arquivo para escrita em modo binário ("wb").
                arquivo_aberto = True # Marca o arquivo como aberto.

            if recebido_checksum != calculado_checksum: # Verifica se o checksum do pacote é válido.
                print(f"Checksum inválido para o pacote {seq}. Descartando.") # Informa sobre o checksum inválido.
                continue # Descarta o pacote corrompido e espera o reenvio.

            if seq == esperada: # Se o pacote recebido é o esperado.
                f.write(dados) # Escreve os dados do pacote no arquivo.
                ack = criar_pacote(2, seq) # Cria um pacote de ACK (tipo 2) para o pacote recebido.
                sock.sendto(ack, addr) # Envia o ACK de volta para o remetente.
                esperada += 1 # Incrementa o número de sequência esperado.
            elif seq < esperada: # Se o pacote é um duplicado (sequência menor que a esperada).
                ack = criar_pacote(2, seq) # Cria um ACK para este pacote duplicado.
                sock.sendto(ack, addr) # Reenvia o ACK para garantir que o remetente pare de reenviá-lo.
            else: # Se o pacote está fora de ordem (sequência maior que a esperada).
                ack_anterior = criar_pacote(2, esperada - 1) # Cria um ACK para o último pacote recebido em ordem.
                sock.sendto(ack_anterior, addr) # Envia este ACK para sinalizar ao remetente qual pacote está faltando (mecanismo do Go-Back-N).
        
        except socket.timeout: # Se o receptor não receber nada por um longo período.
            print("Timeout no receptor. O arquivo pode estar incompleto.") # Informa sobre o timeout.
            if f: f.close() # Fecha o arquivo se estiver aberto.
            return False # Retorna False, indicando falha.

    if f: f.close() # Após o loop, se o arquivo foi aberto, fecha-o.
    print("Recebimento de arquivo concluído.") # Informa que o processo terminou.
    return True # Retorna True para indicar sucesso.