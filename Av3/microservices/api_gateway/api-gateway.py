# /api_gateway/api-gateway.py

import pika
import json
import threading
import requests
import queue # Thread-safe queue
import time
from flask import Flask, request, jsonify, Response

# --- Configurações ---
RABBITMQ_HOST = 'localhost'
RABBITMQ_USER = 'user'
RABBITMQ_PASS = 'password'
EXCHANGE_NAME = 'leilao_topic_exchange'

# Endereços dos microsserviços
MS_LEILAO_URL = "http://localhost:5001"
MS_LANCE_URL = "http://localhost:5002"

# Eventos que o Gateway deve consumir do RabbitMQ
BINDING_KEYS = [
    'lance.validado',
    'lance.invalidado', #
    'leilao.vencedor',
    'link_pagamento', #
    'status_pagamento' #
]

# --- Configuração do Flask ---
app = Flask(__name__)

# --- Gerenciador de Conexões SSE ---
# Armazena as conexões SSE ativas e os interesses de cada cliente
# Estrutura: { 'id_usuario': {'queue': queue.Queue(), 'interesses': set()} }
clientes_sse = {}
clientes_lock = threading.Lock() # Lock para proteger o dicionário

# --- Endpoints REST (Proxy) ---

@app.route('/leiloes', methods=['POST'])
def criar_leilao_proxy():
    """ Encaminha a criação de leilão para o MS Leilão """
    try:
        response = requests.post(f"{MS_LEILAO_URL}/leiloes", json=request.json)
        response.raise_for_status()
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"erro": f"Erro ao contatar MS Leilão: {e}"}), 503

@app.route('/leiloes', methods=['GET'])
def consultar_leiloes_proxy():
    """ Encaminha a consulta de leilões para o MS Leilão """
    try:
        # O nome correto do endpoint no MS Leilão é /leiloes/ativos
        response = requests.get(f"{MS_LEILAO_URL}/leiloes/ativos") 
        response.raise_for_status()
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"erro": f"Erro ao contatar MS Leilão: {e}"}), 503

@app.route('/lance', methods=['POST'])
def efetuar_lance_proxy():
    """ Encaminha a tentativa de lance para o MS Lance """
    try:
        response = requests.post(f"{MS_LANCE_URL}/lance", json=request.json)
        response.raise_for_status()
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        # O MS-Lance retorna 400 para lance inválido, o que pode cair aqui
        if e.response is not None:
            return jsonify(e.response.json()), e.response.status_code
        return jsonify({"erro": f"Erro ao contatar MS Lance: {e}"}), 503

# --- Endpoints REST (Gerenciamento de Notificações) ---

@app.route('/notificacoes/registrar', methods=['POST'])
def registrar_interesse():
    """
    Registra o interesse de um usuário em um leilão.
    JSON: {"id_usuario": "user1", "id_leilao": 1}
    """
    dados = request.json
    id_usuario = dados.get('id_usuario')
    id_leilao = dados.get('id_leilao')
    
    if not id_usuario or id_leilao is None:
        return jsonify({"erro": "id_usuario e id_leilao são obrigatórios"}), 400
        
    with clientes_lock:
        if id_usuario not in clientes_sse:
            # Se o usuário não tem uma conexão SSE, não podemos registrar interesse
            return jsonify({"erro": "Usuário não possui conexão SSE ativa"}), 400
        
        clientes_sse[id_usuario]['interesses'].add(id_leilao)
    
    print(f"[Interesse] Usuário {id_usuario} agora segue o leilão {id_leilao}")
    return jsonify({"status": f"Interesse registrado no leilão {id_leilao}"}), 200

@app.route('/notificacoes/cancelar', methods=['POST'])
def cancelar_interesse():
    """
    Remove o interesse de um usuário em um leilão.
    JSON: {"id_usuario": "user1", "id_leilao": 1}
    """
    dados = request.json
    id_usuario = dados.get('id_usuario')
    id_leilao = dados.get('id_leilao')

    with clientes_lock:
        if id_usuario in clientes_sse:
            clientes_sse[id_usuario]['interesses'].discard(id_leilao) #
    
    print(f"[Interesse] Usuário {id_usuario} cancelou interesse no leilão {id_leilao}")
    return jsonify({"status": f"Interesse removido do leilão {id_leilao}"}), 200

# --- Endpoint SSE (Server-Sent Events) ---

@app.route('/eventos')
def sse_stream():
    """
    Mantém a conexão SSE com o cliente.
    Requer um parâmetro ?id_usuario=...
    """
    id_usuario = request.args.get('id_usuario')
    if not id_usuario:
        return jsonify({"erro": "Parâmetro id_usuario é obrigatório"}), 400

    def event_generator(id_usuario):
        q = queue.Queue()
        with clientes_lock:
            # Registra o cliente com sua fila e um set vazio de interesses
            clientes_sse[id_usuario] = {'queue': q, 'interesses': set()}
            print(f"[SSE] Cliente {id_usuario} conectado.")
        
        try:
            while True:
                # Espera por uma mensagem na fila
                evento_formatado = q.get()
                yield evento_formatado
        except GeneratorExit: # Ocorre quando o cliente desconecta
            pass
        finally:
            # Limpa o cliente da lista
            with clientes_lock:
                del clientes_sse[id_usuario]
                print(f"[SSE] Cliente {id_usuario} desconectado. Limpeza realizada.")

    return Response(event_generator(id_usuario), mimetype='text/event-stream')

# --- Lógica de Consumo RabbitMQ ---

def formatar_sse(evento_tipo: str, dados_json: str) -> str:
    """ Formata os dados no padrão Server-Sent Events """
    return f"event: {evento_tipo}\ndata: {dados_json}\n\n"

def despachar_evento_sse(evento_tipo: str, dados: dict):
    """
    Envia o evento para as filas SSE dos clientes corretos.
    """
    dados_json = json.dumps(dados)
    evento_formatado = formatar_sse(evento_tipo, dados_json)
    
    id_leilao = dados.get('id_leilao')
    
    # Eventos pessoais (enviados para um usuário específico)
    id_destinatario = None
    if evento_tipo == 'lance_invalido':
        id_destinatario = dados.get('id_usuario')
    elif evento_tipo in ['link_pagamento', 'status_pagamento']:
        id_destinatario = dados.get('id_vencedor') or dados.get('id_comprador')
        
    with clientes_lock:
        if id_destinatario:
            # Envio direto para um usuário
            if id_destinatario in clientes_sse:
                try:
                    clientes_sse[id_destinatario]['queue'].put_nowait(evento_formatado)
                    print(f"[SSE->] Evento pessoal '{evento_tipo}' enviado para {id_destinatario}")
                except queue.Full:
                    print(f"[SSE!] Fila para {id_destinatario} cheia. Evento descartado.")
        
        # Eventos públicos de leilão (broadcast para interessados)
        elif evento_tipo in ['novo_lance', 'vencedor_leilao'] and id_leilao is not None:
            for id_usuario, info in clientes_sse.items():
                if id_leilao in info['interesses']:
                    try:
                        info['queue'].put_nowait(evento_formatado)
                        print(f"[SSE->] Evento de leilão '{evento_tipo}' (Leilão {id_leilao}) enviado para {id_usuario}")
                    except queue.Full:
                        print(f"[SSE!] Fila para {id_usuario} cheia. Evento descartado.")

def callback_rabbitmq(ch, method, properties, body):
    routing_key = method.routing_key
    dados = json.loads(body.decode())
    
    print(f"\n[SUB] Gateway recebeu evento: {routing_key}")
    
    # Mapeia as routing keys para os nomes de eventos SSE
    if routing_key == 'lance.validado':
        despachar_evento_sse('novo_lance', dados) #
    elif routing_key == 'lance.invalidado':
        despachar_evento_sse('lance_invalido', dados) #
    elif routing_key == 'leilao.vencedor':
        despachar_evento_sse('vencedor_leilao', dados) #
    elif routing_key == 'link_pagamento':
        despachar_evento_sse('link_pagamento', dados) #
    elif routing_key == 'status_pagamento':
        despachar_evento_sse('status_pagamento', dados) #
        
    ch.basic_ack(delivery_tag=method.delivery_tag)

def iniciar_consumidor_rabbitmq():
    """Roda em uma thread separada para consumir eventos do RabbitMQ."""
    print("[*] Iniciando thread de consumo RabbitMQ para o Gateway...")
    while True: # Loop de reconexão
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials))
            channel = connection.channel()
            channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='topic')
            result = channel.queue_declare(queue='', exclusive=True)
            queue_name = result.method.queue

            for key in BINDING_KEYS:
                channel.queue_bind(exchange=EXCHANGE_NAME, queue=queue_name, routing_key=key)
            
            print(f'[*] Gateway escutando por eventos: {BINDING_KEYS}.')
            channel.basic_consume(queue=queue_name, on_message_callback=callback_rabbitmq)
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as e:
            print(f"[!] Conexão RabbitMQ perdida. Tentando reconectar em 5s... Erro: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"[!] Thread RabbitMQ do Gateway falhou: {e}")
            time.sleep(5) # Evita loop de falha rápido

# --- Ponto de entrada ---
if __name__ == '__main__':
    # Inicia o consumidor RabbitMQ em uma thread separada
    thread_rabbitmq = threading.Thread(target=iniciar_consumidor_rabbitmq)
    thread_rabbitmq.daemon = True
    thread_rabbitmq.start()
    
    # Inicia o servidor Flask na thread principal (porta 5000)
    print("[*] Iniciando API Gateway (porta 5000)...")
    app.run(port=5000, debug=True, use_reloader=False)