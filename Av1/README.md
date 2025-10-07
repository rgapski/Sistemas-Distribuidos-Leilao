# **Sistema de Leilão com Microsserviços em Python**

Este projeto implementa um sistema de leilão em tempo real utilizando uma arquitetura de microsserviços. A comunicação entre os componentes é totalmente assíncrona, orquestrada pelo message broker RabbitMQ, garantindo desacoplamento, escalabilidade e resiliência.

As principais tecnologias e conceitos utilizados são:

* **Arquitetura de Microsserviços:** O sistema é dividido em serviços menores e independentes, cada um com uma responsabilidade única.  
* **Mensageria Assíncrona com RabbitMQ:** Os serviços se comunicam exclusivamente através de filas e exchanges, sem nunca se conhecerem diretamente.  
* **Python:** Linguagem de programação utilizada para todos os componentes.  
* **Assinatura Digital (`cryptography`):** Os lances são assinados digitalmente pelo cliente para garantir autenticidade e não repúdio.  
* **Interface de Terminal (`Textual`):** Os clientes interagem com o sistema através de uma rica interface de usuário baseada em texto (TUI), que opera em tempo real.  
* **Sincronização de Tempo (`ntplib`):** Os timestamps dos lances são gerados a partir de servidores NTP para garantir uma fonte de tempo neutra e confiável, resolvendo disputas de lances concorrentes.

## **Arquitetura do Sistema**

O sistema é composto por 4 serviços principais que interagem através do RabbitMQ:

* **Cliente TUI (`app.py`):** A interface do usuário. Permite que múltiplos usuários (ex: `cliente_alpha`, `cliente_beta`) visualizem leilões, submetam lances assinados e recebam notificações em tempo real.  
* **MS Leilão (`ms_leilao`):** Gerencia o ciclo de vida dos leilões. É responsável por publicar eventos quando um leilão começa (`leilao.iniciado`) e quando termina (`leilao.finalizado`), com base em horários pré-configurados e sincronizados com NTP.  
* **MS Lance (`ms_lance`):** O cérebro do sistema. Ele processa os lances recebidos, valida a assinatura digital com a chave pública do cliente, verifica as regras de negócio (leilão ativo, valor do lance) e determina o vencedor ao final.  
* **MS Notificação (`ms_notificacao`):** Atua como um roteador de eventos. Ele escuta eventos de lances validados e de vencedores e os republica em tópicos específicos para cada leilão, garantindo que apenas os clientes interessados recebam as notificações.

### **Fluxo de Comunicação (Simplificado)**

* **Comandos (1-para-1):**  
  * `Cliente` \-\> `[Fila: lance_realizado]` \-\> `MS Lance`  
* **Eventos (1-para-muitos via Topic Exchange):**  
  * `MS Leilão` \-\> `[Exchange]` \-\> `MS Lance`, `Cliente`  
  * `MS Lance` \-\> `[Exchange]` \-\> `MS Notificação`  
  * `MS Notificação` \-\> `[Exchange]` \-\> `Clientes interessados`

## **Estrutura de Arquivos**
```plaintext
/leilao\_python/  
|  
|-- cliente\_tui/  
|   |-- app.py             \# Código da interface de usuário interativa (TUI).  
|   |-- app.css            \# Folha de estilos para a TUI.  
|   |-- gerar\_chaves.py    \# Script para gerar pares de chaves pública/privada para os clientes.  
|  
|-- microservices/  
|   |-- ms\_leilao/         \# Microsserviço que gerencia o ciclo de vida dos leilões.  
|   |-- ms\_lance/          \# Microsserviço que processa e valida os lances.  
|   |-- ms\_notificacao/    \# Microsserviço que roteia as notificações.  
|  
|-- docker-compose.yml     \# Arquivo para iniciar o container do RabbitMQ.  
|-- requirements.txt       \# Dependências Python do projeto.  
|-- iniciar\_tudo.bat       \# Script para automatizar a inicialização de todos os serviços no Windows.  
|-- README.md              \# Este arquivo.
```
## **Pré-requisitos**

Antes de executar, garanta que você tenha os seguintes softwares instalados:

* **Python 3.8+**  
* **Docker** e **Docker Compose**

Bibliotecas Python: Instale-as executando o seguinte comando na raiz do projeto:  
```plaintext
pip install \-r requirements.txt
```

## **Como Executar**

Siga estes passos para colocar todo o sistema no ar.

### **Passo 1: Iniciar o Message Broker**

O RabbitMQ roda em um container Docker. Para iniciá-lo, execute o seguinte comando no terminal, na raiz do projeto:
```plaintext
docker-compose up \-d
```

### **Passo 2: Gerar Chaves Criptográficas para os Clientes**

Cada cliente precisa de um par de chaves para assinar seus lances.

1. Navegue até o diretório do cliente: `cd cliente_tui`

Execute o script para gerar as chaves (ex: para `cliente_alpha` e `cliente_beta`):  
\# Edite o arquivo gerar_chaves.py para gerar para cada cliente e execute
```plaintext  
python gerar_chaves.py 
```
### **Passo 3: Iniciar Todos os Serviços**

A maneira mais fácil é usar o script de automação.

* **No Windows:** Dê um duplo-clique no arquivo `iniciar_tudo.bat`.

Isso abrirá 5 janelas de terminal separadas, uma para cada componente do sistema (2 clientes e 3 microsserviços).

#### **(Alternativa) Execução Manual**

Se preferir, você pode iniciar cada componente manualmente em seu próprio terminal:

1. **Terminal 1 (MS Leilão):** `cd microservices/ms_leilao && python main.py`  
2. **Terminal 2 (MS Lance):** `cd microservices/ms_lance && python main.py`  
3. **Terminal 3 (MS Notificação):** `cd microservices/ms_notificacao && python main.py`  
4. **Terminal 4 (Cliente Alpha):** `cd cliente_tui && python app.py cliente_alpha`  
5. **Terminal 5 (Cliente Beta):** `cd cliente_tui && python app.py cliente_beta`
