# Fluxos Visuais dos Testes

## 🎯 TESTE 1: Acesso Básico (Sem Concorrência)

```
Tempo    PeerA                PeerB         PeerC         PeerD
─────────────────────────────────────────────────────────────────
t=0s     [LIBERADO]          [LIBERADO]    [LIBERADO]    [LIBERADO]
         |
         | "pedir"
         |
t=1s     [QUERENDO_ENTRAR]
         |
         ├──pedido(ts=1)────→ [recebe]
         |                    └─OK────────→
         |
         ├──pedido(ts=1)────────────────→ [recebe]
         |                                 └─OK────→
         |
         ├──pedido(ts=1)──────────────────────────→ [recebe]
         |                                           └─OK──→
         |
t=2s     [DENTRO_DA_SC] ✓
         | (timer: 15s)
         |
t=3s     | (usando recurso)
         |
t=15s    | (timer dispara)
         |
t=17s    [LIBERADO] ✗
```

**Resultado**: ✅ PeerA acessa SC sozinho e libera após 15s

---

## 🎯 TESTE 2: Concorrência Simples (2 Peers)

```
Tempo    PeerA                PeerB              
────────────────────────────────────────────────
t=0s     [LIBERADO]          [LIBERADO]
         |                    |
         | "pedir"            | "pedir"
         |                    |
t=1s     [QUERENDO]          [QUERENDO]
         ts=1                 ts=2
         |                    |
         ├──pedido(1)────────→ [recebe pedido(1)]
         |                    | ts_outro=1 < ts_meu=2
         |                    | → responde OK
         |                    └─OK────────────────→
         |                    |
         |←─pedido(2)─────────┤
         | [recebe pedido(2)]
         | ts_outro=2 > ts_meu=1
         | → NÃO responde (adia)
         | → adiciona à fila: [(2, PeerB)]
         |
t=2s     [DENTRO_DA_SC] ✓    [AGUARDANDO...]
         |                    (bloqueado esperando PeerA)
         |
t=3s     | (usando recurso)
         |
t=17s    [LIBERADO] ✗
         |
         | Processa fila: [(2, PeerB)]
         ├──OK(tardio)───────→
         |                    [DENTRO_DA_SC] ✓
         |
t=32s                         [LIBERADO] ✗
```

**Resultado**: ✅ PeerA entra primeiro (ts menor), PeerB aguarda

---

## 🎯 TESTE 3: Concorrência Máxima (4 Peers)

```
Tempo    PeerA       PeerB       PeerC       PeerD
─────────────────────────────────────────────────────
t=0s     "pedir"     "pedir"     "pedir"     "pedir"
         ts=1        ts=2        ts=3        ts=4
         |           |           |           |
t=1s     [QUERENDO]  [QUERENDO]  [QUERENDO]  [QUERENDO]
         |           |           |           |
         | Comparações de timestamp:
         | A vs B: 1<2 → A vence, B adia
         | A vs C: 1<3 → A vence, C adia
         | A vs D: 1<4 → A vence, D adia
         |
t=2s     [DENTRO] ✓  [AGUARDA]   [AGUARDA]   [AGUARDA]
         |
t=17s    [LIBERA] ✗
         └─→ Envia OKs para fila: [B, C, D]
         |           |
t=18s                [DENTRO] ✓  [AGUARDA]   [AGUARDA]
                     | (B tem ts=2, menor que C=3 e D=4)
                     |
t=33s                [LIBERA] ✗
                     └─→ Envia OKs
                     |           |
t=34s                            [DENTRO] ✓  [AGUARDA]
                                 | (C tem ts=3, menor que D=4)
                                 |
t=49s                            [LIBERA] ✗
                                 └─→ Envia OK
                                 |           |
t=50s                                        [DENTRO] ✓
                                             |
t=65s                                        [LIBERA] ✗
```

**Resultado**: ✅ Ordem de acesso: A → B → C → D (por timestamp)

---

## 🎯 TESTE 4: Desempate Alfabético

```
Cenário: PeerC e PeerD solicitam EXATAMENTE ao mesmo tempo
         (ambos têm timestamp = 5)

Tempo    PeerC                PeerD              
────────────────────────────────────────────────
t=0s     [LIBERADO]          [LIBERADO]
         |                    |
         | "pedir"            | "pedir"
         |                    |
t=1s     [QUERENDO]          [QUERENDO]
         ts=5                 ts=5 (EMPATE!)
         |                    |
         ├──pedido(5)────────→ [recebe pedido(5)]
         |                    | ts_outro=5 == ts_meu=5
         |                    | Desempate: "PeerC" < "PeerD"
         |                    | → PeerC vence (alfabético)
         |                    | → responde OK
         |                    └─OK────────────────→
         |                    |
         |←─pedido(5)─────────┤
         | [recebe pedido(5)]
         | ts_outro=5 == ts_meu=5
         | Desempate: "PeerD" > "PeerC"
         | → PeerC vence (alfabético)
         | → NÃO responde (adia)
         | → adiciona à fila: [(5, PeerD)]
         |
t=2s     [DENTRO_DA_SC] ✓    [AGUARDANDO...]
         |
t=17s    [LIBERADO] ✗
         ├──OK───────────────→
         |                    [DENTRO_DA_SC] ✓
         |
t=32s                         [LIBERADO] ✗
```

**Resultado**: ✅ PeerC entra primeiro por ordem alfabética

---

## 🎯 TESTE 5: Detecção de Falha por Heartbeat

```
Tempo    PeerA                PeerB (vai falhar)    PeerC
──────────────────────────────────────────────────────────
t=0s     [LIBERADO]          [LIBERADO]            [LIBERADO]
         |                    |                      |
         | Heartbeats sendo trocados normalmente:
         |←─────HB────────────┤
         ├─────HB────────────→|
         |←─────HB──────────────────────────────────┤
         |
t=2s     últimos_HB:         últimos_HB:           últimos_HB:
         {B: 2s, C: 2s}      {A: 2s, C: 2s}        {A: 2s, B: 2s}
         |
t=3s     |                    💥 PEER B MORRE
         |                    X (processo encerrado)
         |
t=4s     (envia HB para B)
         ├──HB──────────X (timeout/erro)
         |
t=5s     últimos_HB:
         {B: 2s, C: 5s}
         | (B sem atualizar)
         |
t=6s     (envia HB para B)
         ├──HB──────────X (timeout/erro)
         |
t=8s     (envia HB para B)
         ├──HB──────────X (timeout/erro)
         |
t=9s     | Verificação de falhas:
         | tempo_atual=9s
         | B: último_HB=2s → 9-2=7s > 6s
         | ⚠ FALHA DETECTADA!
         |
         [remove PeerB]
         |
         últimos_HB:
         {C: 9s}
         |
         peers: {C: proxy}
```

**Resultado**: ✅ Falha detectada em ~7s, peer removido

---

## 🎯 TESTE 6: Falha Durante Requisição

```
Tempo    PeerA                PeerB (vai falhar)    PeerC
──────────────────────────────────────────────────────────
t=0s     [LIBERADO]          [LIBERADO]            [LIBERADO]
         |
         | "pedir"
         |
t=1s     [QUERENDO]
         ts=10
         |
         | Enviando pedidos com timeout=3s:
         |
         ├──pedido(10)───────→ [recebe]
         |                     └─OK────────────────→
         | (OK de B recebido)
         |
         ├──pedido(10)──────────────────────────→ [recebe]
         |                                         💥 C MORRE
         |                                         X
         |
         | (aguardando resposta de C...)
         |
t=2s     | (timeout rodando...)
         |
t=3s     | (timeout rodando...)
         |
t=4s     | TIMEOUT! (3s sem resposta de C)
         | [captura exceção]
         |
         | ⚠ Peer C removido (timeout)
         |
         respostas_necessarias: 1 (só B)
         respostas_recebidas: {B}
         |
         | Condição satisfeita! (1/1)
         |
t=5s     [DENTRO_DA_SC] ✓
         | (continua normalmente)
         |
t=20s    [LIBERADO] ✗
```

**Resultado**: ✅ Sistema se adapta à falha, não trava esperando C

---

## 🎯 TESTE 7: Múltiplas Requisições na Fila

```
Cenário: PeerA na SC, B, C, D solicitam simultaneamente

Tempo    PeerA           PeerB          PeerC          PeerD
─────────────────────────────────────────────────────────────
t=0s     [DENTRO_DA_SC]  [LIBERADO]     [LIBERADO]     [LIBERADO]
         |
t=1s     |               "pedir"        "pedir"        "pedir"
         |               ts=20          ts=21          ts=22
         |               |              |              |
t=2s     |               [QUERENDO]     [QUERENDO]     [QUERENDO]
         |               |              |              |
         |←─pedido(20)───┤              |              |
         | [DENTRO_DA_SC]               |              |
         | → adia resposta              |              |
         | fila: [(20,B)]               |              |
         |                              |              |
         |←─pedido(21)──────────────────┤              |
         | → adia resposta                             |
         | fila: [(20,B), (21,C)]                      |
         |                                             |
         |←─pedido(22)────────────────────────────────┤
         | → adia resposta
         | fila: [(20,B), (21,C), (22,D)]
         | (ordenada por timestamp)
         |
t=5s     | (ainda usando recurso)
         |
t=15s    | (timer dispara)
         |
t=16s    [LIBERADO] ✗
         |
         | Processa fila em ordem:
         | for (ts, peer) in fila:
         |
         ├──OK───────────→ [DENTRO] ✓
         |                |
         ├──OK───────────────────────→ (aguarda B)
         |                             |
         ├──OK───────────────────────────────────→ (aguarda B,C)
         |
t=31s                    [LIBERA] ✗
                         ├──OK──────→ [DENTRO] ✓
                         |            |
                         ├──OK──────────────────→ (aguarda C)
                         |
t=46s                                [LIBERA] ✗
                                     ├──OK──────→ [DENTRO] ✓
                                     |
t=61s                                             [LIBERA] ✗
```

**Resultado**: ✅ Fila processada em ordem de timestamp: B → C → D

---

## 🎯 TESTE 8: Liberação Manual

```
Tempo    PeerA                
────────────────────────────
t=0s     [LIBERADO]
         |
         | "pedir"
         |
t=1s     [QUERENDO_ENTRAR]
         |
t=2s     [DENTRO_DA_SC] ✓
         |
         | timer iniciado (15s)
         |
t=3s     | (usando recurso)
         |
t=5s     | usuário digita "liberar"
         |
t=6s     [LIBERADO] ✗
         |
         | timer.cancel() ✓
         | (cancelou timer automático)
         |
         | Estado volta para LIBERADO
         | Fila processada (se houver)
```

**Resultado**: ✅ Liberação manual funciona, timer cancelado

---

## 📊 Resumo de Estados

### Estados Possíveis de um Peer:

```
┌─────────────┐
│  LIBERADO   │  ← Estado inicial
└──────┬──────┘
       │
       │ solicitar_sc()
       │
       ▼
┌─────────────────┐
│ QUERENDO_ENTRAR │  ← Aguardando respostas
└──────┬──────────┘
       │
       │ recebeu todos os OKs
       │
       ▼
┌─────────────┐
│ DENTRO_DA_SC│  ← Usando o recurso
└──────┬──────┘
       │
       │ liberar_sc() ou timeout
       │
       ▼
┌─────────────┐
│  LIBERADO   │  ← Volta ao início
└─────────────┘
```

---

## 🔄 Fluxo de Decisão: receber_pedido()

```
                   receber_pedido(ts_outro, peer_outro)
                              │
                              ▼
                   ┌──────────────────┐
                   │ Atualiza relógio │
                   │ clock = max(...)  │
                   └────────┬─────────┘
                            │
                            ▼
                   ┌────────────────────┐
                   │ Qual meu estado?   │
                   └─┬──────────┬──────┬┘
                     │          │      │
        ┌────────────┘          │      └────────────┐
        ▼                       ▼                   ▼
   LIBERADO              DENTRO_DA_SC         QUERENDO_ENTRAR
        │                       │                   │
        │                       │                   │
        ▼                       ▼                   ▼
  ┌─────────┐           ┌─────────────┐     ┌────────────────┐
  │ Retorna │           │ Adia (fila) │     │ Compara ts     │
  │   OK    │           │ Retorna False│     └────┬───────┬───┘
  └─────────┘           └─────────────┘          │       │
                                                  │       │
                                    ts_outro < ts_meu    ts_outro > ts_meu
                                         │                    │
                                         ▼                    ▼
                                   ┌─────────┐        ┌─────────────┐
                                   │ Retorna │        │ Adia (fila) │
                                   │   OK    │        │ Retorna False│
                                   └─────────┘        └─────────────┘
                                         
                                   (se ts_outro == ts_meu:
                                    desempate alfabético)
```

---

## 🎭 Cenários de Erro e Recuperação

### Cenário 1: Deadlock Impossível
```
Por quê não há deadlock?
- Sempre há um "vencedor" por timestamp
- Desempate alfabético garante decisão
- Peer com menor timestamp SEMPRE recebe OKs
```

### Cenário 2: Starvation Impossível
```
Por quê não há starvation?
- Fila ordenada por timestamp (FIFO temporal)
- Todos os pedidos são eventualmente processados
- Ninguém pode "furar" a fila
```

### Cenário 3: Particionamento de Rede
```
Se a rede particionar:
- Peers em cada partição continuam funcionando
- Exclusão mútua mantida dentro de cada partição
- Ao reconectar: timestamps garantem ordem global
```

---

## ✅ Checklist de Comportamentos Esperados

### Durante Operação Normal:
- [ ] Apenas 1 peer na SC por vez
- [ ] Relógios lógicos sempre crescentes
- [ ] Heartbeats a cada 2s
- [ ] Logs claros e informativos
- [ ] Interface responsiva

### Durante Falhas:
- [ ] Timeouts detectados em ~3s
- [ ] Falhas de heartbeat em ~6s
- [ ] Sistema continua com N-1 peers
- [ ] Sem travamentos ou deadlocks
- [ ] Mensagens de erro informativas

### Durante Concorrência:
- [ ] Ordem determinística por timestamp
- [ ] Desempate alfabético funciona
- [ ] Fila processada corretamente
- [ ] Sem race conditions
- [ ] Resultados consistentes

---

## 🎯 Métricas de Performance Esperadas

| Métrica | Valor Esperado | Observação |
|---------|----------------|------------|
| Tempo para entrar na SC (sem concorrência) | < 2s | Latência de rede + processamento |
| Tempo para detectar falha | ~6-7s | Configurável (heartbeat interval) |
| Timeout de requisição | 3s | Configurável |
| Tempo máximo na SC | 15s | Configurável |
| Overhead de heartbeat | Mínimo | Thread assíncrona |
| Throughput de pedidos | Sequencial | Um peer por vez (por design) |

---

## 🚀 Comandos Rápidos para Testes

```bash
# 1. Iniciar sistema
python start_all.py

# 2. Em outro terminal, executar testes automatizados
python test_scenarios.py

# 3. Ou testar manualmente nos terminais dos peers:
# Terminal PeerA: pedir
# Terminal PeerB: pedir
# Observar exclusão mútua

# 4. Testar falha:
# Matar um peer (Ctrl+C)
# Aguardar ~7s
# Observar detecção nos outros peers
```

---

## 📈 Resultado Final Esperado

### Sistema 100% Funcional:
✅ **Exclusão Mútua**: Garantida por timestamps  
✅ **Tolerância a Falhas**: Heartbeats + timeouts  
✅ **Ordem Determinística**: Relógios lógicos  
✅ **Sem Deadlock**: Timestamp sempre decide  
✅ **Sem Starvation**: Fila FIFO temporal  
✅ **Interface Clara**: Comandos intuitivos  
✅ **Logs Informativos**: Debugging fácil  

**Sistema pronto para demonstração e avaliação acadêmica!** 🎓✨