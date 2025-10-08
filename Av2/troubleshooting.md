# Troubleshooting - Solução de Problemas

## 🔧 Problemas Comuns e Soluções

### ❌ Erro: "Cannot locate nameserver"

**Sintoma:**
```
Pyro5.errors.NamingError: Cannot locate nameserver
```

**Causa:** O Servidor de Nomes não foi iniciado ou morreu.

**Solução:**
1. Certifique-se que pelo menos um peer está rodando
2. O primeiro peer a iniciar cria o servidor de nomes automaticamente
3. Se todos os peers morreram, reinicie com `python start_all.py`

**Solução Alternativa:**
```bash
# Inicie o servidor de nomes manualmente:
python -m Pyro5.nameserver
```

---

### ❌ Erro: "Connection refused" ou "Connection timeout"

**Sintoma:**
```
Pyro5.errors.CommunicationError: cannot connect
```

**Causa:** Um peer não está acessível (morreu, firewall, etc.)

**Solução:**
1. Verifique se todos os peers estão rodando
2. No Linux/Mac: verifique firewall
   ```bash
   # Ubuntu/Debian
   sudo ufw status
   sudo ufw allow 9090/tcp  # Porta padrão PyRO
   ```
3. No Windows: verifique Windows Firewall
4. Execute `python test_scenarios.py` → Teste 3 para ver peers ativos

---

### ❌ Peer trava em "Aguardando respostas..."

**Sintoma:**
```
[PeerA] Aguardando respostas...
(peer fica travado indefinidamente)
```

**Causa Possível 1:** Outro peer morreu antes de responder

**Solução:**
- Aguarde o timeout (~10s)
- O sistema deve detectar automaticamente e continuar
- Se não funcionar, verifique se o heartbeat está rodando

**Causa Possível 2:** Deadlock (BUG - não deveria acontecer!)

**Debug:**
1. Em outro terminal, conecte ao peer travado:
   ```python
   import Pyro5.api
   ns = Pyro5.api.locate_ns()
   peer = Pyro5.api.Proxy(ns.lookup("PeerA"))
   print(peer.obter_status())
   ```
2. Verifique o estado e peers ativos
3. Se for bug, reporte com logs completos

---

### ❌ "Peer não encontrado" ao executar test_scenarios.py

**Sintoma:**
```
❌ PeerA não encontrado. Certifique-se que todos os peers estão rodando.
```

**Causa:** Peers não foram iniciados ou demoraram para se registrar.

**Solução:**
1. Execute `python start_all.py`
2. Aguarde 5-10 segundos antes de rodar os testes
3. Verifique manualmente:
   ```bash
   python -c "import Pyro5.api; ns=Pyro5.api.locate_ns(); print(ns.list())"
   ```
   Deve mostrar: `{PeerA, PeerB, PeerC, PeerD}`

---

### ❌ Múltiplos peers na SC simultaneamente (CRÍTICO!)

**Sintoma:**
```
STATUS DO PeerA: DENTRO_DA_SC
STATUS DO PeerB: DENTRO_DA_SC  ← PROBLEMA!
```

**Causa:** Bug no algoritmo ou race condition.

**Debug Imediato:**
1. Capture os logs de TODOS os peers
2. Verifique os timestamps dos pedidos:
   ```
   [PeerA] Enviando pedidos com timestamp X
   [PeerB] Enviando pedidos com timestamp Y
   ```
3. Verifique as respostas:
   ```
   [PeerA] Resposta OK de PeerB  ← B deveria ter adiado?
   [PeerB] Resposta OK de PeerA  ← A deveria ter adiado?
   ```

**Solução:**
- Este é um bug crítico que quebra a exclusão mútua
- Não deveria acontecer com a implementação atual
- Se acontecer, reporte imediatamente com logs completos

---

### ❌ Heartbeat não está funcionando

**Sintoma:**
```
# Nenhuma mensagem de falha após matar um peer
# Peer morto continua aparecendo em "Peers Ativos"
```

**Verificação:**
1. Verifique se as threads foram iniciadas:
   ```
   [PeerA] Thread de heartbeat iniciada
   [PeerA] Thread de verificação de falhas iniciada
   ```
2. Se não aparecerem, há problema na inicialização

**Debug:**
```python
# No main.py, adicione prints:
peer.iniciar_heartbeat()
print("Heartbeat iniciado OK")
peer.iniciar_verificacao_falhas()
print("Verificação iniciada OK")
```

**Solução:**
- Verifique se `daemon=True` está nas threads
- Verifique se não há exceções não tratadas nas threads
- Adicione try-except nos métodos das threads para ver erros

---

### ❌ "RecursionError: maximum recursion depth exceeded"

**Sintoma:**
```
RecursionError: maximum recursion depth exceeded
```

**Causa:** Loop infinito de pedidos (não deveria acontecer).

**Solução Temporária:**
```bash
# Mate todos os peers
pkill -f "python main.py"

# Limpe o servidor de nomes
python -c "import Pyro5.api; ns=Pyro5.api.locate_ns(); [ns.remove(x) for x in ns.list()]"

# Reinicie
python start_all.py
```

---

### ⚠️ Terminal muito poluído com logs

**Solução 1: Redirecionar para arquivo**
```bash
python main.py PeerA > peerA.log 2>&1
```

**Solução 2: Reduzir verbosidade (editar Peer.py)**
```python
# Comente os prints desnecessários:
# print(f"[{self.nome}] Heartbeat recebido de {nome_peer}")
```

**Solução 3: Usar logging estruturado**
```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Substituir prints por:
logger.info(f"[{self.nome}] Mensagem")
```

---

### ❌ start_all.py não abre terminais (Linux)

**Sintoma:**
```
⚠ Nenhum terminal compatível encontrado
```

**Causa:** Nenhum dos emuladores de terminal testados está instalado.

**Solução:**
```bash
# Instale um terminal:
sudo apt install gnome-terminal  # Ubuntu/Debian
sudo apt install xterm           # Alternativa leve
sudo pacman -S konsole           # Arch Linux

# Ou inicie manualmente:
python main.py PeerA &
python main.py PeerB &
python main.py PeerC &
python main.py PeerD &
```

---

### ❌ PyRO muito lento / alta latência

**Sintomas:**
- Pedidos demoram muito (>5s)
- Heartbeats atrasados

**Possíveis Causas:**
1. **Rede local lenta**
2. **DNS lookup lento**
3. **Serialização de objetos grandes**

**Soluções:**

**1. Use IP direto ao invés de localhost:**
```python
# Em main.py e Peer.py, troque:
daemon = Pyro5.api.Daemon(host='localhost')
# Por:
daemon = Pyro5.api.Daemon(host='127.0.0.1')
```

**2. Desabilite IPv6 se não usar:**
```bash
# Linux
sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1
```

**3. Reduza timeouts para testes rápidos:**
```python
# Em Peer.py:
proxy._pyroTimeout = 1.0  # ao invés de 3.0
```

---

## 🐛 Debugging Avançado

### Habilitar Logs do PyRO

```python
# No início do main.py:
import logging
logging.getLogger("Pyro5").setLevel(logging.DEBUG)
logging.basicConfig()
```

Vai mostrar:
- Todas as chamadas remotas
- Problemas de serialização
- Conexões de rede

---

### Inspecionar Estado Interno de um Peer

```python
import Pyro5.api

ns = Pyro5.api.locate_ns()
peer = Pyro5.api.Proxy(ns.lookup("PeerA"))

# Obter status completo
status = peer.obter_status()
print(f"Estado: {status['estado']}")
print(f"Relógio: {status['relogio']}")
print(f"Peers: {status['peers_ativos']}")

# Forçar liberação (se travado)
try:
    peer.liberar_sc()
    print("Liberação forçada com sucesso")
except Exception as e:
    print(f"Erro: {e}")
```

---

### Testar Conexão Manualmente

```python
import Pyro5.api

# Teste 1: Servidor de Nomes
try:
    ns = Pyro5.api.locate_ns()
    print("✓ Servidor de Nomes OK")
    print(f"  Peers registrados: {list(ns.list().keys())}")
except Exception as e:
    print(f"✗ Erro no Servidor de Nomes: {e}")

# Teste 2: Conexão com Peer
try:
    uri = ns.lookup("PeerA")
    peer = Pyro5.api.Proxy(uri)
    peer._pyroBind()  # Força conexão
    print("✓ Conexão com PeerA OK")
except Exception as e:
    print(f"✗ Erro ao conectar PeerA: {e}")
```

---

## 📊 Logs Esperados vs Problemáticos

### ✅ Logs Normais (OK)

```
[PeerA] Iniciando...
✓ Daemon rodando em PYRO:obj_xxx@127.0.0.1:9090
✓ PeerB encontrado
✓ PeerC encontrado
✓ PeerD encontrado
[PeerA] Thread de heartbeat iniciada
[PeerA] Thread de verificação de falhas iniciada
✓ PeerA iniciado com sucesso!
```

### ❌ Logs Problemáticos

```
[PeerA] Erro ao contactar PeerB: timeout  ← Problema de rede
[PeerA] Peer PeerC removido (falha detectada)  ← OK se C morreu
[PeerA] ⚠ Peer PeerD removido (falha detectada)  ← Suspeito se D estava OK
RecursionError: maximum recursion depth  ← BUG CRÍTICO
Traceback (most recent call last):  ← Exceção não tratada
```

---

## 🔍 Checklist de Diagnóstico

Quando algo der errado, siga esta ordem:

1. **Verificar infraestrutura:**
   - [ ] PyRO5 instalado? `pip show Pyro5`
   - [ ] Servidor de Nomes rodando? `python -m Pyro5.nameserver`
   - [ ] Firewall bloqueando? Teste portas

2. **Verificar peers:**
   - [ ] Todos os 4 peers rodando?
   - [ ] Peers registrados no NS? Use script de teste
   - [ ] Logs mostram inicialização completa?

3. **Verificar conectividade:**
   - [ ] Peers se descobriram mutuamente?
   - [ ] Heartbeats funcionando?
   - [ ] Timeouts razoáveis?

4. **Verificar comportamento:**
   - [ ] Estados corretos (LIBERADO/QUERENDO/DENTRO)?
   - [ ] Relógios incrementando?
   - [ ] Exclusão mútua mantida?

5. **Se tudo falhar:**
   - [ ] Mate tudo: `pkill -f "python main.py"`
   - [ ] Limpe NS: Remova registros antigos
   - [ ] Reinicie do zero
   - [ ] Se persistir: é bug - reporte!

---

## 🆘 Quando Reportar um Bug

Se após seguir todos os passos acima o problema persistir, reporte com:

1. **Descrição do problema**: O que deveria acontecer vs o que aconteceu
2. **Passos para reproduzir**: Sequência exata de comandos
3. **Logs completos**: De TODOS os peers envolvidos
4. **Ambiente**:
   ```
   SO: Windows/Linux/Mac
   Python: 3.x
   PyRO5: 5.14
   ```
5. **Status dos peers**: Output de `obter_status()` de cada um

---

## 💡 Dicas de Prevenção

### Boas Práticas:

✅ **Sempre inicie todos os peers juntos**
- Use `start_all.py`
- Aguarde 5s antes de interagir

✅ **Não mate peers durante operações críticas**
- Deixe a SC ser liberada naturalmente
- Use comando `sair` ao invés de Ctrl+C direto

✅ **Monitore os logs**
- Fique de olho em mensagens de erro
- Investigue heartbeats perdidos

✅ **Teste incrementalmente**
- Primeiro: 1 peer sozinho (Teste 1)
- Depois: 2 peers concorrentes (Teste 2)
- Por último: 4 peers (Teste 3)

✅ **Use os scripts de teste**
- `test_scenarios.py` automatiza validações
- Mais confiável que testes manuais

---

## 🎓 Para Apresentação/Demonstração

### Preparação (5 min antes):

1. ✅ Teste o ambiente:
   ```bash
   python test_scenarios.py
   # Rode Teste 3 (status) para confirmar tudo OK
   ```

2. ✅ Prepare terminais visíveis:
   - Organize em grid 2x2
   - Fonte grande para visualização
   - Fundo claro se projetor for ruim

3. ✅ Tenha backup:
   - Gravação de tela funcionando
   - Screenshots dos resultados esperados
   - Logs salvos de execução bem-sucedida

### Durante Demonstração:

1. 🎬 **Mostre inicialização:**
   ```bash
   python start_all.py
   ```
   Explique o que está acontecendo

2. 🎬 **Teste simples primeiro:**
   - Peer