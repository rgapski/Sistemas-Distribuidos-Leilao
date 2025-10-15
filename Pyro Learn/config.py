# Arquivo: config.py

# Nomes de todos os peers que participarão do sistema
TODOS_PEERS = ["PeerA", "PeerB", "PeerC", "PeerD"]

# --- Configurações de Tempo ---

# Intervalo em segundos para o envio de heartbeats
INTERVALO_HEARTBEAT = 2

# Tempo em segundos sem receber heartbeat para considerar um peer como morto
# DEVE ser maior que INTERVALO_HEARTBEAT (recomendado: 10x+ para tolerância a latência de rede/Pyro)
TIMEOUT_HEARTBEAT = 20

# Intervalo para verificação de heartbeats (pode ser maior que o envio)
INTERVALO_VERIFICACAO = 3

# Número de verificações consecutivas falhadas antes de marcar peer como morto (hysteresis)
# Isso evita falsos positivos devido a delays temporários de rede
VERIFICACOES_CONSECUTIVAS_FALHA = 3

# Tempo máximo em segundos que um peer pode permanecer na Seção Crítica
TEMPO_MAXIMO_SC = 10

# Timeout em segundos para esperar a resposta de um pedido individual a outro peer
TIMEOUT_PEDIDO_INDIVIDUAL = 5

# Atraso aleatório em segundos antes de enviar uma resposta "OK".
# Ajuda a simular condições de disputa de forma mais controlada.
MIN_DELAY_RESPOSTA = 0  # segundos
MAX_DELAY_RESPOSTA = 0  # segundos