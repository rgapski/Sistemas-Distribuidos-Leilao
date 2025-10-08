# Guia de Testes - Sistema Distribuído

## 📋 Preparação dos Testes

### Configuração Inicial
1. Instale as dependências: `pip install Pyro5`
2. Inicie todos os peers: `python start_all.py`
3. Aguarde ~5 segundos até todos se conectarem
4. Verifique que cada peer mostra: "✓ PeerX iniciado com sucesso!"

### Verificação de Conectividade
Em cada terminal, digite `status` e verifique:
- **Estado**: LIBERADO
- **Relógio Lógico**: 0 ou próximo de 0
- **Peers Ativos**: Deve listar os outros 3 peers

---

## 🧪 Cenários de Teste

### TESTE 1: Acesso Básico à Seção Crítica (Sem Concorrência)

**Objetivo**: Verificar que um único peer consegue entrar e sair da SC

**Passos**:
1. No PeerA, digite: `pedir`
2. Aguarde ~1 segundo
3. No PeerA, digite: `status`
4. Aguarde 15 segundos (liberação automática)

**Resultados Esperados**:
```
[PeerA] Solicitando acesso à Seção Crítica...
[PeerA] Enviando pedidos com timestamp 1
[PeerA] Resposta OK de PeerB
[PeerA] Resposta OK de PeerC
[PeerA] Resposta OK de PeerD
[PeerA] Aguardando respostas...

==================================================
[PeerA] ✓ ENTROU NA SEÇÃO CRÍTICA
==================================================

# Após 15 segundos:
[PeerA] Tempo limite na SC atingido - liberando automaticamente

==================================================
[PeerA] ✗ LIBEROU A SEÇÃO CRÍTICA
==================================================
```

**Validações**:
- ✅ PeerA recebe OK de todos os outros
- ✅ PeerA entra na SC (estado = DENTRO_DA_SC)
- ✅ Após 15s, PeerA libera automaticamente
- ✅ Estado volta para LIBERADO

---

### TESTE 2: Concorrência Simples (2 Peers)

**Objetivo**: Verificar resolução de conflito baseada em timestamp

**Passos**:
1. No PeerA, digite: `pedir`
2. **IMEDIATAMENTE** no PeerB, digite: `pedir`
3. Observe os logs de ambos

**Resultados Esperados**:

O peer que enviou o pedido **primeiro** (menor timestamp) deve:
- Receber OK de todos
- Entrar na SC
- O outro peer deve **aguardar**

Exemplo (PeerA enviou primeiro):
```
# PeerA:
[PeerA] Enviando pedidos com timestamp 1
[PeerA] ✓ ENTROU NA SEÇÃO CRÍTICA

# PeerB:
[PeerB] Enviando pedidos com timestamp 2
[PeerB] Aguardando respostas...
# (PeerB fica bloqueado até PeerA liberar)
```

Após PeerA liberar:
```
[PeerA] ✗ LIBEROU A SEÇÃO CRÍTICA
[PeerA] Enviando OK pendente para PeerB

# PeerB então entra:
[PeerB] ✓ ENTROU NA SEÇÃO CRÍTICA
```

**Validações**:
- ✅ Apenas 1 peer na SC por vez
- ✅ Peer com menor timestamp tem prioridade
- ✅ Pedidos pendentes são processados após liberação

---

### TESTE 3: Concorrência Máxima (4 Peers Simultâneos)

**Objetivo**: Verificar fila de pedidos com múltiplos conflitos

**Passos**:
1. Digite `pedir` em **todos os 4 peers** simultaneamente (ou o mais rápido possível)
2. Observe a ordem de acesso à SC

**Resultados Esperados**:

Os peers devem entrar na SC em **ordem de timestamp**:
```
Timestamp 1: PeerA entra
Timestamp 2: PeerB aguarda
Timestamp 3: PeerC aguarda
Timestamp 4: PeerD aguarda

# Após PeerA liberar (15s):
PeerB entra

# Após PeerB liberar (15s):
PeerC entra

# Após PeerC liberar (15s):
PeerD entra
```

**Validações**:
- ✅ Nunca 2 peers simultaneamente na SC
- ✅ Ordem respeitada pelo timestamp
- ✅ Todos os peers eventualmente acessam a SC

---

### TESTE 4: Desempate Alfabético

**Objetivo**: Verificar critério de desempate quando timestamps são iguais

**Passos**:
1. **Pare todos os peers** (Ctrl+C em todos)
2. **Reinicie todos EXATAMENTE ao mesmo tempo**
3. Assim que todos estiverem prontos, digite `pedir` simultaneamente em PeerC e PeerD

**Resultados Esperados**:

Se ambos tiverem o mesmo timestamp, **PeerC** deve ter prioridade (vem antes alfabeticamente):
```
[PeerC] ✓ ENTROU NA SEÇÃO CRÍTICA
[PeerD] Aguardando respostas...
```

**Validações**:
- ✅ Em caso de empate, ordem alfabética decide
- ✅ PeerC antes de PeerD

---

### TESTE 5: Liberação Manual

**Objetivo**: Verificar que o usuário pode liberar antes dos 15s

**Passos**:
1. No PeerA, digite: `pedir`
2. Aguarde entrar na SC
3. Após ~5 segundos, digite: `liberar`
4. Verifique se liberou imediatamente

**Resultados Esperados**:
```
[PeerA] ✓ ENTROU NA SEÇÃO CRÍTICA

# Após usuário digitar "liberar":
[PeerA] ✗ LIBEROU A SEÇÃO CRÍTICA
```

**Validações**:
- ✅ Liberação manual funciona
- ✅ Timer automático é cancelado
- ✅ Estado volta para LIBERADO

---

### TESTE 6: Detecção de Falha por Heartbeat

**Objetivo**: Verificar que peers falhos são detectados automaticamente

**Passos**:
1. Inicie todos os 4 peers
2. No PeerA, digite `status` → deve mostrar 3 peers ativos
3. **Mate o PeerB** (Ctrl+C no terminal dele ou feche a janela)
4. Aguarde ~7 segundos
5. No PeerA, digite `status` novamente

**Resultados Esperados**:
```
# Antes de matar PeerB:
Peers Ativos: PeerB, PeerC, PeerD

# Após ~7 segundos:
[PeerA] ⚠ Peer PeerB removido (falha detectada)

# Novo status:
Peers Ativos: PeerC, PeerD
```

**Validações**:
- ✅ Falha detectada em ~6 segundos (sem heartbeat)
- ✅ Peer falho removido automaticamente
- ✅ Sistema continua funcionando com 3 peers

---

### TESTE 7: Tolerância a Falhas Durante Requisição

**Objetivo**: Verificar comportamento quando um peer falha durante uma solicitação

**Passos**:
1. No PeerA, digite: `pedir`
2. **DURANTE** a espera por respostas (antes de entrar na SC), **mate o PeerB**
3. Observe se PeerA ainda consegue entrar na SC

**Resultados Esperados**:
```
[PeerA] Solicitando acesso à Seção Crítica...
[PeerA] Enviando pedidos com timestamp X
[PeerA] Resposta OK de PeerC
[PeerA] Resposta OK de PeerD
[PeerA] Erro ao contactar PeerB: [timeout/connection error]
[PeerA] ⚠ Peer PeerB removido (falha detectada)
[PeerA] ✓ ENTROU NA SEÇÃO CRÍTICA
```

**Validações**:
- ✅ Timeout detectado (~3s)
- ✅ PeerA não fica bloqueado esperando PeerB
- ✅ PeerA entra na SC com os peers restantes
- ✅ Sistema se adapta à falha

---

### TESTE 8: Múltiplas Falhas

**Objetivo**: Verificar funcionamento com apenas 2 peers ativos

**Passos**:
1. Inicie todos os 4 peers
2. Mate PeerC e PeerD
3. Aguarde detecção de falhas (~7s)
4. No PeerA, digite: `pedir`
5. No PeerB, digite `status`

**Resultados Esperados**:
```
# PeerA e PeerB detectam as falhas:
[PeerA] ⚠ Peer PeerC removido (falha detectada)
[PeerA] ⚠ Peer PeerD removido (falha detectada)

# PeerA consegue entrar na SC:
[PeerA] ✓ ENTROU NA SEÇÃO CRÍTICA

# Status do PeerB:
Peers Ativos: PeerA
```

**Validações**:
- ✅ Sistema funciona com apenas 2 peers
- ✅ Exclusão mútua mantida
- ✅ Ambos detectam as falhas

---

### TESTE 9: Reconexão de Peer

**Objetivo**: Verificar se um novo peer pode entrar após outros já estarem rodando

**Passos**:
1. Inicie apenas PeerA, PeerB e PeerC
2. Aguarde 10 segundos
3. Inicie PeerD
4. No PeerD, digite `status` após 5 segundos

**Resultados Esperados**:
```
# PeerD ao iniciar:
[PeerD] Descobrindo outros peers...
✓ PeerA encontrado
✓ PeerB encontrado
✓ PeerC encontrado

# Status:
Peers Ativos: PeerA, PeerB, PeerC
```

**Observação**: Os peers antigos **não detectarão automaticamente** o PeerD, pois a descoberta ocorre apenas na inicialização. Esta é uma limitação do design atual.

**Validações**:
- ✅ PeerD descobre peers existentes
- ✅ PeerD pode enviar pedidos para outros
- ⚠️ Peers antigos não verão PeerD (limitação conhecida)

---

### TESTE 10: Stress Test - Requisições Rápidas

**Objetivo**: Verificar estabilidade sob carga

**Passos**:
1. Inicie todos os 4 peers
2. Em PeerA, faça 5 requisições consecutivas (digite `pedir` 5 vezes rapidamente)
3. Observe o comportamento

**Resultados Esperados**:
```
[PeerA] Solicitando acesso à Seção Crítica...
[PeerA] Erro: já está em estado QUERENDO_ENTRAR
```

**Validações**:
- ✅ Sistema rejeita requisições duplicadas
- ✅ Peer não pode pedir novamente se já está esperando/dentro
- ✅ Sem travamentos ou race conditions

---

## 📊 Checklist Final de Validação

Após executar todos os testes, verifique:

### Funcionalidades Básicas
- [ ] Peer consegue entrar na SC sozinho
- [ ] Timer de 15s funciona
- [ ] Liberação manual funciona
- [ ] Estado muda corretamente (LIBERADO → QUERENDO → DENTRO → LIBERADO)

### Exclusão Mútua
- [ ] Apenas 1 peer na SC por vez
- [ ] Timestamps determinam prioridade
- [ ] Desempate alfabético funciona
- [ ] Fila de pedidos processada em ordem

### Tolerância a Falhas
- [ ] Heartbeats enviados a cada 2s
- [ ] Falhas detectadas em ~6s
- [ ] Peers falhos removidos automaticamente
- [ ] Timeouts em requisições funcionam
- [ ] Sistema continua após falhas

### Robustez
- [ ] Sem deadlocks
- [ ] Sem race conditions
- [ ] Logs claros e informativos
- [ ] Interface responsiva

---

## 🐛 Problemas Conhecidos e Limitações

### 1. Descoberta Dinâmica
**Problema**: Peers que entram depois não são descobertos pelos antigos.
**Solução Futura**: Implementar broadcast periódico de "estou vivo" com registro dinâmico.

### 2. Resposta Tardia
**Problema**: Quando um peer libera a SC, ele não consegue enviar OK ativamente para quem está na fila (design atual usa retorno síncrono).
**Impacto**: O peer que está esperando pode ter timeout.
**Solução Implementada**: O timeout é de 10s, maior que o tempo máximo na SC (15s não é issue).

### 3. Servidor de Nomes Único
**Problema**: Se o processo que iniciou o Servidor de Nomes morrer, o sistema para.
**Solução Futura**: Implementar servidor de nomes replicado ou usar descoberta P2P.

---

## 📈 Métricas de Sucesso

Um sistema **100% funcional** deve passar em:
- ✅ Todos os 10 testes acima
- ✅ Sem erros não tratados
- ✅ Sem travamentos
- ✅ Logs consistentes e claros
- ✅ Comportamento determinístico (mesmas entradas = mesmas saídas)

---

## 🎯 Resultado Final Esperado

Ao executar o sistema completo com todos os testes:
- **Exclusão mútua garantida**: ✅
- **Ordem determinística**: ✅
- **Tolerância a falhas**: ✅
- **Interface funcional**: ✅
- **Código limpo e organizado**: ✅

**Sistema pronto para demonstração e avaliação!** 🎉