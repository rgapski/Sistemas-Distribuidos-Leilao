# Arquivo: config.py

# Nomes de todos os peers que participarão do sistema
TODOS_PEERS = ["PeerA", "PeerB", "PeerC", "PeerD"]

# --- Configurações de Tempo ---

# Intervalo em segundos para o envio de heartbeats
INTERVALO_HEARTBEAT = 2

# Tempo em segundos sem receber heartbeat para considerar um peer como morto
TIMEOUT_HEARTBEAT = 6  # Deve ser maior que o intervalo

# Tempo máximo em segundos que um peer pode permanecer na Seção Crítica
TEMPO_MAXIMO_SC = 10

# Timeout em segundos para esperar a resposta de um pedido individual a outro peer
TIMEOUT_PEDIDO_INDIVIDUAL = 5

# Timeout geral em segundos para o processo de obter todas as permissões para a SC
TIMEOUT_GERAL_PEDIDO = 10