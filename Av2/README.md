# Sistema Distribuído - Algoritmo de Ricart e Agrawala

Implementação de exclusão mútua distribuída com tolerância a falhas usando PyRO5.

## Instalação

```bash
pip install -r requirements.txt
```

## Execução

### Opção 1: Iniciar todos os peers automaticamente

```bash
python start_all.py
```

### Opção 2: Iniciar peers manualmente

Abra 4 terminais diferentes e execute:

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

## Comandos Disponíveis

Após iniciar um peer, você pode usar os seguintes comandos:

- `pedir` - Solicita acesso à Seção Crítica
- `liberar` - Libera a Seção Crítica manualmente (antes dos 15s)
- `status` - Mostra o estado atual do peer
- `sair` - Encerra o peer

## Estrutura do Projeto

```
├── Peer.py         # Classe principal com a lógica do algoritmo
├── main.py         # Script de inicialização de um peer
├── start_all.py    # Script para iniciar todos os peers
└── requirements.txt # Dependências do projeto
```

## Características Implementadas

✅ Algoritmo de Ricart e Agrawala  
✅ Relógios lógicos de Lamport  
✅ Exclusão mútua distribuída  
✅ Heartbeats para detecção de falhas  
✅ Timeouts em requisições  
✅ Tempo máximo na Seção Crítica (15s)  
✅ Interface de linha de comando  

## Parâmetros Configurados

- **Timeout de requisições**: 3 segundos
- **Intervalo de heartbeat**: 2 segundos
- **Detecção de falha**: 6 segundos sem heartbeat
- **Tempo máximo na SC**: 15 segundos