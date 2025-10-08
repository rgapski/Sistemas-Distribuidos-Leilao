Pequenas introdução para o que deve ser feito e o que teremos nesse documento. Começando com o propósito geral desse documento, documentar e estruturar um plano de ação para desenvolver o sistema requisitado pela professora.  
Segue uma estruturação simplificada do que foi pedido:

Antes de começar o código, vamos revisar os conceitos principais:

* **Exclusão Mútua:** É a garantia de que, em um sistema com múltiplos processos, apenas um pode acessar um recurso crítico (a "Seção Crítica" ou SC) em um determinado momento. Isso evita inconsistências e conflitos.  
* **Algoritmo de Ricart e Agrawala:** É uma maneira de garantir a exclusão mútua em um sistema distribuído. A ideia central é:  
  1. **Pedido:** Quando um processo quer entrar na SC, ele envia uma mensagem de "pedido" com um carimbo de tempo (timestamp) para todos os outros processos.  
  2. **Resposta:** Um processo que recebe um pedido só envia uma resposta de "OK" se ele não estiver na SC e não quiser entrar. Se ele também quiser entrar, ele compara o timestamp do pedido recebido com o do seu próprio pedido: o menor vence, e o outro tem que esperar.  
  3. **Entrada:** Um processo só pode entrar na SC depois de receber "OK" de **todos** os outros processos.  
* **PyRO (Python Remote Objects):** É uma biblioteca que facilita a comunicação entre processos, mesmo que estejam em máquinas diferentes. Com ele, um processo pode chamar métodos de um objeto em outro processo como se fosse um objeto local. Ele cuida de toda a complexidade da comunicação de rede.

Agora como segunda parte desse documento irei falar sobre a estrutura e de como será o desenvolvimento.

**Planejamento da Implementação**

Vamos dividir o projeto em partes lógicas, seguindo os requisitos do trabalho. A estrutura central será uma classe `Peer` que conterá toda a lógica de um processo.

#### **Arquitetura Geral**

1. **Processo Peer (`Peer.py`):**  
   * Será uma classe Python que representa cada um dos quatro processos.  
   * Ela manterá seu estado interno (ex: `LIBERADO`, `QUERENDO_ENTRAR`, `DENTRO_DA_SC`).  
   * Ela terá métodos que poderão ser chamados remotamente por outros peers (ex: para receber um pedido de acesso).  
   * Ela conterá a lógica para enviar pedidos, gerenciar respostas, enviar *heartbeats* e detectar falhas.  
2. **Script de Execução (`main.py`):**  
   * Este script será responsável por iniciar um peer. Você o executará quatro vezes, uma para cada peer (ex: `python main.py PeerA`, `python main.py PeerB`, etc.).  
   * Ele cuidará da inicialização do PyRO, incluindo o **Servidor de Nomes**.  
   * Ele fornecerá uma interface de linha de comando simples para o usuário interagir com o peer (ex: para iniciar um pedido de acesso ao recurso).

#### **Plano de Desenvolvimento Passo a Passo**

Aqui está uma sequência lógica para construir sua aplicação:

**Passo 1: Estrutura Básica do Peer e Configuração do PyRO**

* **Objetivo:** Ter os processos se comunicando e se encontrando através do Servidor de Nomes.  
* **Ações:**  
  1. Crie a classe `Peer` e exponha-a para o PyRO com o decorador `@Pyro5.api.expose`.  
  2. No script principal, implemente a lógica para lidar com o Servidor de Nomes:  
     * Tente obter uma referência ao servidor.  
     * Se falhar (porque ele ainda não existe), inicie um novo servidor.  
  3. Cada peer, ao iniciar, deve se registrar no Servidor de Nomes com seu nome único (ex: "PeerA").  
  4. Depois de se registrar, cada peer deve procurar pelos outros três peers no Servidor de Nomes para obter uma referência (proxy) para eles.

**Passo 2: Implementação do Algoritmo de Ricart e Agrawala**

* **Objetivo:** Implementar a lógica central de exclusão mútua.  
* **Ações:**  
1. **Estado do Peer:** Adicione atributos à classe `Peer` para gerenciar o estado (`state`), o relógio lógico (`clock`) e uma fila para pedidos pendentes (`request_queue`).  
2. Método Remoto `receber_pedido(timestamp, peer_id)`: Este é o coração do algoritmo. Quando um peer recebe uma chamada neste método, ele decide se responde "OK" imediatamente ou se adia a resposta com base no seu estado e no timestamp do pedido.  
3. **Método Local `solicitar_sc()`:** Este método será chamado quando o usuário quiser entrar na Seção Crítica. Ele deve:  
   * Mudar o estado para `QUERENDO_ENTRAR`.  
   * Atualizar seu relógio lógico.  
   * Enviar a mensagem de pedido (chamando  
      `receber_pedido` em todos os outros peers)  
   * Aguardar as respostas de todos.

**Passo 3: Adicionar Robustez com Heartbeats e Timeouts**

* **Objetivo:** Tornar o sistema tolerante a falhas, conforme solicitado.  
* **Ações:**

1. **Heartbeat (Detecção de Falhas):**	  
   * Crie um método remoto `receber_heartbeat()`. Quando chamado, ele simplesmente registra o tempo atual como a "última vez que o peer X foi visto".  
   * Inicie uma *thread* separada em cada peer que, a cada poucos segundos, chama `receber_heartbeat` em todos os outros peers.  
   * Inicie uma segunda *thread* que verifica periodicamente os tempos registrados. Se um peer não envia um heartbeat por muito tempo, ele é considerado falho e removido da lista de peers ativos.  
2. **Timeouts nos Pedidos:**  
* Ao enviar um pedido na função  
   `solicitar_sc()`, inicie um temporizador para cada peer de quem se espera uma resposta.  
* Se uma resposta não chegar dentro do tempo limite, considere o peer destinatário como falho e remova-o da lista de ativos.  
3. **Verificação de Atividade:** Antes de conceder permissão a um pedido, verifique se o solicitante ainda está ativo com base no último heartbeat recebido.

**Passo 4: Controle de Tempo de Acesso e Interface do Usuário**

* **Objetivo:** Finalizar os requisitos e criar uma forma de interagir com o sistema.  
* **Ações:**  
  1. **Tempo Limite na Seção Crítica:** Quando um peer finalmente entrar na SC, inicie um `threading.Timer`. Se o tempo expirar, o peer deve automaticamente liberar o recurso.  
  2. **Interface do Usuário:** No script `main.py`, crie um loop simples que aceite comandos do usuário, como `pedir` (para solicitar acesso à SC), `liberar` (para sair da SC manualmente) e `status` (para ver o estado atual).

Progredindo aqui vamos detalhar melhor agora todo o fluxo que faremos para desenvolver o que foi pedido.

## Parte 1 Detalhamento:

### **Estrutura e Configuração**

Imagine que você está prestes a executar o seu script pela primeira vez (por exemplo, `python main.py PeerA`). Aqui está a sequência exata de eventos que precisam acontecer nos bastidores, dividida em quatro etapas lógicas.

#### **1\. Ativação do "Ouvinte" (Daemon do PyRO)**

Antes de qualquer comunicação, cada processo precisa de um componente que fique constantemente "ouvindo" a rede, esperando por requisições de outros processos. No PyRO, isso é chamado de **Daemon**.

* **Ação:** A primeira coisa que seu script faz é criar e iniciar um Daemon. Pense nele como ligar o telefone do seu processo. Ele recebe um endereço (IP e porta) na máquina local e fica aguardando chamadas. Sem ele, o processo estaria isolado e surdo para o resto do sistema.

#### **2\. Lógica do Servidor de Nomes**

Agora que o processo pode ouvir, ele precisa de uma "agenda de contatos" para encontrar os outros. Este é o papel do **Servidor de Nomes**. Como só pode haver um, seu script precisa ser inteligente.

* **Ação:** O script tentará se conectar a um Servidor de Nomes que já esteja rodando.  
  * **Se falhar:** Isso significa que este é o primeiro processo a ser iniciado. Ele então assume a responsabilidade de criar o Servidor de Nomes e iniciá-lo.  
  * **Se tiver sucesso:** Ótimo, o servidor já existe. O processo simplesmente guarda a referência para poder usá-lo.  
* **Resultado:** Ao final desta etapa, garantimos que existe um (e apenas um) Servidor de Nomes funcionando, e nosso processo atual tem um canal de comunicação com ele.

#### **3\. Registro na "Agenda"**

Com o Servidor de Nomes disponível, o processo precisa se anunciar para que os outros possam encontrá-lo.

* **Ação:** O processo cria sua própria instância do objeto `Peer` (a classe que conterá toda a sua lógica). Em seguida, ele registra esse objeto no Daemon (o "ouvinte" da etapa 1). O Daemon atribui um endereço PyRO único a este objeto. Finalmente, o processo contata o Servidor de Nomes e diz: "Olá, eu sou o 'PeerA' e meu endereço para contato é este aqui".

#### **4\. Descoberta dos Outros Processos**

Agora que nosso processo está devidamente registrado, a última parte é encontrar seus colegas.

* **Ação:** O processo pega a lista pré-definida de nomes ("PeerA", "PeerB", "PeerC", "PeerD"). Ele percorre essa lista e, para cada nome que não é o seu, ele pergunta ao Servidor de Nomes: "Qual é o endereço do 'PeerB'?".  
* **Proxy:** O Servidor de Nomes responde com o endereço (URI) de cada colega. Seu processo usa esse endereço para criar um objeto local chamado **Proxy**. Esse proxy se parece e se comporta exatamente como o objeto remoto, mas todas as chamadas de função que você faz nele são, na verdade, enviadas pela rede para o processo real.  
* **Resultado Final do Passo 1:** Ao final, seu processo terá um dicionário ou lista interna contendo os proxies para todos os outros peers ativos no sistema. A base de comunicação está pronta.

## Parte 2 Detalhamento:

### **Detalhamento do Passo 2: O Algoritmo de Exclusão Mútua**

O objetivo aqui é criar um sistema de "pedidos e permissões" para que um peer só entre na Seção Crítica (SC) quando tiver o consentimento de todos os outros.

#### **1\. Preparando o Peer para a Negociação**

Antes de começar a pedir e a receber permissões, cada peer precisa de algumas ferramentas internas para se organizar.

* **Ação:** Você irá adicionar novos atributos (variáveis) à sua classe `Peer`:  
  * Um **`estado`**: Para saber o que o peer está fazendo no momento. Os três estados possíveis são: `LIBERADO` (não quer o recurso), `QUERENDO_ENTRAR` (enviou um pedido e está esperando) e `DENTRO_DA_SC` (está usando o recurso).  
  * Um **`relogio_logico`**: Um simples contador numérico (um inteiro) que aumenta a cada evento importante. Este relógio é usado para criar o *timestamp* que decide a prioridade entre dois pedidos concorrentes.  
  * Uma **`fila_de_pedidos`**: Uma lista para guardar os pedidos de outros peers que chegaram enquanto o seu peer estava ocupado (seja dentro da SC ou esperando para entrar com um pedido de maior prioridade).

#### **2\. O Processo de Pedido de Acesso (Quando "EU" quero entrar)**

Esta é a sequência de ações que acontece quando o usuário digita o comando para que o seu peer tente acessar o recurso.

* **Ação:** Você irá criar um método chamado `solicitar_sc()` que fará o seguinte, nesta ordem:  
  1. **Muda o estado** para `QUERENDO_ENTRAR`.  
  2. **Incrementa o seu próprio `relogio_logico`**. O novo valor do relógio, junto com o nome do peer (ex: "PeerA"), formará o *timestamp* do pedido.  
  3. **Envia a mensagem de pedido** para *todos os outros peers*. Isso é feito chamando um método remoto (que vamos definir a seguir) em cada um dos proxies que você guardou no Passo 1\.  
  4. **Aguarda as respostas**. O peer fica "travado" nesta etapa, esperando receber uma mensagem de "OK" de cada um dos outros peers. Só depois de receber todos os "OKs" é que ele pode prosseguir.

#### **3\. A Lógica de Resposta (Quando "OUTRO" peer pede para entrar)**

Esta é a parte mais crítica e define como um peer reage ao pedido de outro.

* **Ação:** Você irá criar um método remoto (exposto com o decorador do PyRO) chamado `receber_pedido(timestamp_do_outro, nome_do_outro)`. Quando este método é chamado por outro peer, ele executa a seguinte lógica de decisão:  
  1. **Primeiro, ele atualiza seu próprio relógio lógico**, ajustando-o para ser o maior valor entre o seu relógio atual e o *timestamp* do pedido que acabou de chegar. Isso mantém os relógios do sistema sincronizados.  
  2. **Depois, ele verifica seu próprio estado:**  
     * **Se o estado é `LIBERADO`**: Ele não quer e não está usando o recurso. Portanto, ele responde "OK" imediatamente para o solicitante.  
     * **Se o estado é `DENTRO_DA_SC`**: Ele está ocupado. Ele não responde "OK". Em vez disso, ele adiciona o pedido à sua `fila_de_pedidos` para responder mais tarde, quando sair da SC.  
     * **Se o estado é `QUERENDO_ENTRAR`**: Este é o caso de um conflito\! Ele também quer entrar. A decisão é tomada comparando o seu próprio *timestamp* de pedido com o *timestamp* do pedido que chegou.  
       * Se o seu *timestamp* for **menor** (ou seja, seu pedido é mais antigo), ele tem a prioridade. Ele não responde "OK" e adiciona o outro pedido à sua `fila_de_pedidos`.  
       * Se o *timestamp* do outro for **menor**, o outro tem a prioridade. Ele responde "OK" imediatamente.

## Parte 3 Detalhamento: 

### **Detalhamento do Passo 3: Adicionando Robustez**

O objetivo aqui é duplo: detectar proativamente quando um peer falha (heartbeats) e parar de esperar por um peer que já pode ter falhado (timeouts). A maior parte desta lógica rodará em *threads* separadas para não travar o programa principal.

#### **1\. Implementando o Mecanismo de Heartbeat**

O *heartbeat* é um sinal de "estou vivo" que os peers trocam entre si. Para implementá-lo, você precisará de três componentes que trabalham juntos.

* **Ação 1: O Receptor de Heartbeat**  
  * Crie um novo método remoto na classe `Peer`, chamado `receber_heartbeat()`. A única função deste método é registrar o tempo atual associado ao peer que o chamou. Você precisará de um dicionário para isso, algo como `ultimos_heartbeats = {"PeerB": [timestamp], "PeerC": [timestamp]}`.  
* **Ação 2: O Emissor de Heartbeat (Thread 1\)**  
  * Dentro da sua classe `Peer`, inicie uma *thread* dedicada a enviar os *heartbeats*. Esta *thread* entrará em um loop infinito que, a cada poucos segundos (por exemplo, 2 segundos):  
    1. Percorre a lista de proxies dos outros peers.  
    2. Chama o método `receber_heartbeat()` em cada um deles.  
* **Ação 3: O Verificador de Atividade (Thread 2\)**  
  * Inicie uma segunda *thread* dedicada a monitorar a saúde dos outros. Esta *thread* também entra em um loop que, a cada intervalo de tempo um pouco maior (por exemplo, 5 segundos):  
    1. Percorre o dicionário `ultimos_heartbeats`.  
    2. Verifica se o *timestamp* de algum peer é muito antigo (por exemplo, mais de 5 segundos atrás).  
    3. Se encontrar um peer "silencioso", ele é considerado falho. O seu processo deve então removê-lo da sua lista de peers ativos, para não tentar mais se comunicar com ele.

#### **2\. Implementando Timeouts nos Pedidos**

Esperar para sempre por uma resposta de um peer que pode ter falhado é uma receita para o bloqueio do sistema. Os *timeouts* evitam isso.

* **Ação:** Modifique o método `solicitar_sc()` do Passo 2\.  
  1. Quando você envia a mensagem de pedido para os outros peers, em vez de esperar indefinidamente pelas respostas, você fará as chamadas remotas de uma forma que inclua um *timeout* (o PyRO permite isso).  
  2. Se a chamada para um peer específico (ex: PeerC) estourar o tempo limite, o seu processo deve capturar essa exceção.  
  3. Ao capturar a exceção de *timeout*, seu processo deve imediatamente considerar o PeerC como falho e removê-lo da sua lista de peers ativos.

#### **3\. Verificação Final de Atividade**

Esta é uma camada extra de segurança para garantir que você não conceda acesso a um "fantasma".

* **Ação:** Modifique o método `receber_pedido()` do Passo 2\.  
  * Antes de responder "OK" a um pedido, adicione uma verificação final: consulte seu dicionário `ultimos_heartbeats` para garantir que o peer solicitante enviou um *heartbeat* recentemente. Se ele estiver marcado como "falho" ou seu último *heartbeat* for muito antigo, você simplesmente ignora o pedido dele.

## Parte 4 Detalhamento: 

### **Detalhamento do Passo 4: Finalização e Interface do Usuário**

Com a lógica de exclusão mútua e a robustez já planejadas, agora vamos nos concentrar em como o processo se comporta quando está usando o recurso e como o usuário irá interagir com o sistema.

#### **1\. Implementando o Controle de Tempo de Acesso**

O trabalho exige que um peer não possa monopolizar o recurso indefinidamente. Ele deve liberá-lo automaticamente após um tempo.

* **Ação:** Você irá modificar a sequência de eventos que acontece logo após um peer obter todas as permissões e estar prestes a entrar na Seção Crítica (SC).  
  1. No momento exato em que o peer entra na SC, ele deve **mudar seu estado** para `DENTRO_DA_SC` e, imediatamente, **iniciar um temporizador**. A biblioteca `threading` do Python tem uma classe `Timer` perfeita para isso. Você pode configurá-la, por exemplo, para disparar uma função após 10 segundos.  
  2. A função que o `Timer` irá chamar será um método que você criará, chamado `liberar_sc_automaticamente()`.  
  3. Este método fará duas coisas: primeiro, verificará se o peer ainda está na SC (para o caso de o usuário já ter liberado manualmente) e, se estiver, ele chamará o método principal de liberação do recurso.

#### **2\. Implementando a Liberação do Recurso**

Quando um peer sai da SC (seja por tempo ou por comando do usuário), ele precisa avisar aos outros que o recurso está livre.

* **Ação:** Você irá criar um método `liberar_sc()`. Esta função é crucial e deve executar as seguintes tarefas:  
  1. **Mudar o estado** de volta para `LIBERADO`.  
  2. Percorrer a sua **`fila_de_pedidos`** (onde estão os pedidos que chegaram enquanto ele estava ocupado).  
  3. Para cada pedido na fila, ele agora enviará a resposta "OK" que estava pendente. Isso desbloqueará os outros peers que estavam esperando.  
  4. Por fim, a fila de pedidos deve ser esvaziada.

#### **3\. Criando a Interface do Usuário**

O usuário precisa de uma forma de dar comandos ao processo. Uma interface de linha de comando simples é o suficiente.

* **Ação:** No seu script principal (`main.py`), após toda a inicialização do PyRO e do peer, você iniciará uma *thread* separada para a interface do usuário.  
  1. Esta *thread* entrará em um loop `while True`, que ficará constantemente esperando o usuário digitar um comando.  
  2. O loop irá ler a entrada do usuário (ex: `input()`).  
  3. Com base no comando digitado, ele chamará o método correspondente no objeto `Peer`.  
     * Se o usuário digitar **`pedir`**, a *thread* chamará o método `solicitar_sc()`.  
     * Se o usuário digitar **`liberar`**, ela chamará o método `liberar_sc()`.  
     * Se o usuário digitar **`status`**, ela pode imprimir o estado atual do peer (ex: `LIBERADO`, `QUERENDO_ENTRAR`), seu relógio lógico e a lista de peers ativos.

Com estas ações, você terá um sistema completo que atende a todos os requisitos do trabalho: uma lógica de exclusão mútua robusta, controle de tempo e uma maneira de interagir com o programa.

