# Sistema de Exclusão Mútua Distribuída - Ricart-Agrawala

Implementação do algoritmo de Ricart-Agrawala para exclusão mútua distribuída em Python usando Pyro5. O sistema permite que múltiplos peers coordenem o acesso a uma seção crítica de forma distribuída, sem a necessidade de um servidor central.

## Instalação

### Requisitos

- Python 3.7 ou superior
- Pyro5

### Instalando Dependências

```bash
pip install Pyro5
```

### Obtendo o Projeto

Baixe ou clone os arquivos do projeto:
- `config.py` - Configurações do sistema
- `peer.py` - Implementação do peer
- `main.py` - Script de inicialização

## Estrutura do Projeto

### `config.py`
Arquivo de configuração central com os parâmetros do sistema:
- `TODOS_PEERS`: Lista com os nomes de todos os peers que participarão do sistema
- `INTERVALO_HEARTBEAT`: Intervalo em segundos para envio de heartbeats (padrão: 2s)
- `TIMEOUT_HEARTBEAT`: Tempo sem heartbeat para considerar peer morto (padrão: 10s)
- `TEMPO_MAXIMO_SC`: Tempo máximo que um peer pode permanecer na seção crítica (padrão: 10s)
- `TIMEOUT_PEDIDO`: Timeout para espera de resposta de pedidos (padrão: 5s)

### `peer.py`
Implementação completa do peer, contendo:
- Lógica do algoritmo de Ricart-Agrawala
- Sistema de detecção de falhas via heartbeats
- Descoberta automática de peers via nameserver
- Gerenciamento de threads para comunicação assíncrona

### `main.py`
Script principal para inicialização dos peers:
- Verifica/inicia o servidor de nomes Pyro5
- Registra o peer no nameserver
- Gerencia a interface de linha de comando

## Como Usar

### 1. Iniciar o Sistema

O nameserver é iniciado automaticamente, mas você pode iniciá-lo manualmente se preferir:

```bash
python -m Pyro5.nameserver -n 127.0.0.1
```

### 2. Iniciar os Peers

Em terminais separados, inicie cada peer com seu nome:

```bash
# Terminal 1
python main.py PeerA

# Terminal 2
python main.py PeerB

# Terminal 3
python main.py PeerC

# Terminal 4
python main.py PeerD
```

### 3. Comandos Disponíveis

Após iniciar um peer, você pode usar os seguintes comandos:

- `pedir` - Solicita acesso à seção crítica
- `liberar` - Libera a seção crítica manualmente (também é liberada automaticamente)
- `status` - Mostra o estado atual do peer (estado, relógio lógico, peers ativos)
- `peers` - Lista os peers ativos no momento
- `sair` - Encerra o peer

### Exemplo de Sessão

```
PeerA> pedir
[14:30:15.123][PeerA] ==================================================
[14:30:15.123][PeerA] SOLICITANDO SC (ts=1)
[14:30:15.123][PeerA] ==================================================
[14:30:15.234][PeerA] ✓ OK de PeerB (1/3)
[14:30:15.245][PeerA] ✓ OK de PeerC (2/3)
[14:30:15.256][PeerA] ✓ OK de PeerD (3/3)
[14:30:15.256][PeerA] ✓ Tenho todos os OKs!
[14:30:15.256][PeerA] ==================================================
[14:30:15.256][PeerA] 🔒 ENTREI NA SEÇÃO CRÍTICA!
[14:30:15.256][PeerA] ==================================================

PeerA> liberar
[14:30:20.123][PeerA] ==================================================
[14:30:20.123][PeerA] SAINDO DA SC
[14:30:20.123][PeerA] ==================================================
```

## Configuração

### Ajustando Parâmetros

Edite `config.py` para modificar o comportamento do sistema:

**Lista de Peers:**
```python
TODOS_PEERS = ["PeerA", "PeerB", "PeerC", "PeerD"]
```
Adicione ou remova peers conforme necessário. Todos os peers devem usar a mesma lista.

**Timeouts:**
```python
INTERVALO_HEARTBEAT = 2  # Heartbeats a cada 2 segundos
TIMEOUT_HEARTBEAT = 10   # Considera morto após 10 segundos sem heartbeat
TEMPO_MAXIMO_SC = 10     # Libera SC automaticamente após 10 segundos
TIMEOUT_PEDIDO = 5       # Timeout de 5 segundos para pedidos
```

**Recomendações:**
- `TIMEOUT_HEARTBEAT` deve ser maior que `INTERVALO_HEARTBEAT` (idealmente 5x ou mais)
- `TEMPO_MAXIMO_SC` deve ser suficiente para a operação crítica que você está protegendo
- `TIMEOUT_PEDIDO` deve ser maior que a latência esperada da rede

## Arquitetura/Como Funciona

### Algoritmo de Ricart-Agrawala

O sistema implementa o algoritmo de Ricart-Agrawala, que garante exclusão mútua distribuída através de:

1. **Relógio Lógico de Lamport**: Cada peer mantém um relógio lógico que é incrementado a cada evento e sincronizado com mensagens recebidas.

2. **Pedido de Acesso**: Quando um peer quer entrar na seção crítica:
   - Incrementa seu relógio lógico
   - Envia pedido com timestamp para todos os peers ativos
   - Aguarda resposta "OK" de todos

3. **Resposta a Pedidos**: Ao receber um pedido, um peer:
   - **Concede imediatamente** se estiver LIBERADO ou se seu próprio pedido tem prioridade menor
   - **Adia a resposta** se estiver na SC ou se seu pedido tem prioridade maior
   - Prioridade determinada por: (timestamp, nome_peer) - menor timestamp tem prioridade

4. **Entrada na SC**: Um peer entra na seção crítica quando recebe OK de todos os peers necessários.

5. **Liberação**: Ao sair da SC, o peer envia OK para todos os pedidos adiados.

### Detecção de Falhas

O sistema implementa detecção de falhas através de heartbeats:

- **Envio de Heartbeats**: Cada peer envia heartbeats periódicos (via Pyro5) para todos os peers conhecidos
- **Verificação**: Uma thread verifica periodicamente se algum peer parou de enviar heartbeats
- **Marcação de Morto**: Peers sem heartbeat por mais de `TIMEOUT_HEARTBEAT` são marcados como mortos
- **Adaptação**: Quando um peer é detectado como morto durante uma solicitação, ele é removido da lista de peers necessários, permitindo que o algoritmo continue

### Comunicação entre Peers

A comunicação usa Pyro5 (Python Remote Objects):

1. **Descoberta de Peers**: 
   - Thread de descoberta consulta o nameserver periodicamente
   - Armazena URIs diretas dos peers (evita lookups repetidos)
   - Usa `127.0.0.1` explicitamente para evitar atrasos de DNS reverso

2. **Chamadas Remotas**:
   - `receber_pedido(timestamp, nome)`: Recebe solicitação de acesso à SC
   - `receber_resposta(nome)`: Recebe confirmação "OK" (@oneway - assíncrono)
   - `receber_heartbeat(nome)`: Recebe heartbeat de outro peer (@oneway)

3. **Threads Paralelas**:
   - Thread de descoberta: Busca novos peers no nameserver
   - Thread de heartbeat: Envia heartbeats para peers conhecidos
   - Thread de verificação: Detecta peers mortos
   - Threads auxiliares: Envio assíncrono de pedidos e respostas

### Estados do Peer

Cada peer pode estar em um de três estados:

- **LIBERADO**: Não está tentando acessar nem está na SC
- **QUERENDO**: Solicitou acesso e está aguardando respostas
- **NA_SC**: Está dentro da seção crítica

A transição entre estados segue o protocolo do algoritmo de Ricart-Agrawala, garantindo exclusão mútua mesmo em cenários de falhas.