import subprocess
import threading
import time
import sys
import os
import webbrowser
import signal

# --- 1. Define o diretório base (onde o orchestrator está) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Configurações de Cores ---
class Cores:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'

# --- 2. Lista de Serviços com caminhos dinâmicos ---
# Usa os.path.join para funcionar em Windows e Linux/Mac sem erro de barras
SERVICOS = [
    # Nome visual,  Caminho Completo (Pasta, Arquivo), Cor, Porta
    ("LEILAO   ", os.path.join(BASE_DIR, "ms-leilao", "ms-leilao.py"), Cores.GREEN, 5001),
    ("LANCE    ", os.path.join(BASE_DIR, "ms-lance", "ms-lance.py"), Cores.YELLOW, 5002),
    ("PAGAMENTO", os.path.join(BASE_DIR, "ms-pagamento", "ms-pagamento.py"), Cores.MAGENTA, 5003),
    # Atenção aqui: verifique se o arquivo dentro da pasta chama simulador_pagamento.py mesmo
    ("SIMULADOR", os.path.join(BASE_DIR, "simulador-pagamento", "simulador-pagamento.py"), Cores.RED, 5004),
    ("GATEWAY  ", os.path.join(BASE_DIR, "api-gateway", "api-gateway.py"), Cores.CYAN, 5000),
]

processos = []

def ler_output(nome, cor, process):
    """Lê a saída do processo linha por linha e imprime com prefixo"""
    for line in iter(process.stdout.readline, b''):
        linha_limpa = line.decode('utf-8', errors='replace').strip()
        if linha_limpa:
            print(f"{cor}[{nome}]{Cores.RESET} {linha_limpa}")

def iniciar_servico(nome, arquivo, cor):
    """Inicia um subprocesso Python"""
    # Verifica se o arquivo existe (agora com caminho absoluto)
    if not os.path.exists(arquivo):
        print(f"{Cores.RED}[ERRO]{Cores.RESET} Arquivo não encontrado: {arquivo}")
        # Dica de debug: mostra onde ele tentou procurar
        print(f"      Tentou procurar em: {arquivo}") 
        return None

    # Define a pasta de trabalho como a pasta onde o arquivo está
    pasta_do_servico = os.path.dirname(arquivo)

    # Inicia o processo
    cmd = [sys.executable, arquivo]
    
    # --- MUDANÇA AQUI: cwd=pasta_do_servico ---
    # Isso garante que o serviço rode "dentro" da pasta dele
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, cwd=pasta_do_servico)
    
    t = threading.Thread(target=ler_output, args=(nome, cor, p))
    t.daemon = True
    t.start()
    
    print(f"{Cores.BOLD}---> Iniciando {nome}...{Cores.RESET}")
    return p

def main():
    print(f"{Cores.BOLD}{'='*40}")
    print(f" ORQUESTRADOR DE SISTEMAS DISTRIBUÍDOS")
    print(f"{'='*40}{Cores.RESET}")

    # 1. Inicia os Microsserviços
    for nome, arquivo, cor, porta in SERVICOS:
        p = iniciar_servico(nome, arquivo, cor)
        if p:
            processos.append(p)
        time.sleep(1) # Pequena pausa para dar tempo de subir

    print(f"\n{Cores.BOLD}---> Todos os serviços iniciados.{Cores.RESET}")
    print(f"{Cores.BOLD}---> Pressione Ctrl+C para encerrar tudo.{Cores.RESET}\n")

    # 2. Abre o Frontend (opcional)
    try:
        # Ajustado para procurar dentro da pasta cliente_front
        caminho_front = os.path.join(BASE_DIR, "cliente_front", "index.html")
        
        if os.path.exists(caminho_front):
            print(f"---> Abrindo Frontend: {caminho_front}")
            webbrowser.open(f"file:///{caminho_front}")
        else:
            print(f"{Cores.YELLOW}[AVISO] Frontend não encontrado em: {caminho_front}{Cores.RESET}")
    except Exception:
        pass

    # 3. Loop principal (mantém o script rodando)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n\n{Cores.RED}{'='*40}")
        print(f" ENCERRANDO O SISTEMA...")
        print(f"{'='*40}{Cores.RESET}")
        encerrar_tudo()

def encerrar_tudo():
    """Mata todos os processos filhos"""
    for p in processos:
        try:
            p.terminate() # Tenta fechar suavemente
        except:
            pass
    print("Serviços finalizados. Até logo!")
    sys.exit(0)

if __name__ == '__main__':
    main()