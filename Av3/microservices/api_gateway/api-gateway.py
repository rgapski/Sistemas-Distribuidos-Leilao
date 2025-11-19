# /microservices/api_gateway/api-gateway.py

import pika
import json
import threading
import requests
import queue
import time
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

# --- Configurações ---
RABBITMQ_HOST = 'localhost'
RABBITMQ_USER = 'user'
RABBITMQ_PASS = 'password'
EXCHANGE_NAME = 'leilao_topic_exchange'

MS_LEILAO_URL = "http://localhost:5001"
MS_LANCE_URL = "http://localhost:5002"

BINDING_KEYS = ['lance.validado', 'lance.invalidado', 'leilao.vencedor', 'link_pagamento', 'status_pagamento']

app = Flask(__name__)
CORS(app)

# --- Gerenciamento SSE ---
clientes_sse = {}
clientes_lock = threading.Lock()

# --- Endpoints REST ---

@app.route('/leiloes', methods=['GET', 'POST'])
def gerenciar_leiloes():
    if request.method == 'POST':
        try:
            print(f"[Gateway] Encaminhando POST /leiloes para {MS_LEILAO_URL}")
            response = requests.post(f"{MS_LEILAO_URL}/leiloes", json=request.json)
            return jsonify(response.json()), response.status_code
        except requests.exceptions.RequestException as e:
            return jsonify({"erro": f"Erro MS Leilão: {e}"}), 503
            
    elif request.method == 'GET':
        try:
            print(f"[Gateway] Encaminhando GET /leiloes para {MS_LEILAO_URL}")
            response = requests.get(f"{MS_LEILAO_URL}/leiloes/ativos")
            return jsonify(response.json()), response.status_code
        except requests.exceptions.RequestException as e:
            return jsonify({"erro": f"Erro MS Leilão: {e}"}), 503

@app.route('/lance', methods=['POST'])
def efetuar_lance_proxy():
    dados = request.json
    
    id_usuario = dados.get('id_usuario')
    id_leilao = dados.get('id_leilao')
    
    if id_usuario and id_leilao:
        with clientes_lock:
            # Se o usuário está conectado ao SSE, adicionamos o interesse
            if id_usuario in clientes_sse:
                clientes_sse[id_usuario]['interesses'].add(id_leilao)
                print(f"[Auto-Follow] Usuário {id_usuario} inscrito automaticamente no leilão {id_leilao}")
                
    try:
        response = requests.post(f"{MS_LANCE_URL}/lance", json=dados)
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        if e.response is not None:
            return jsonify(e.response.json()), e.response.status_code
        return jsonify({"erro": f"Erro MS Lance: {e}"}), 503

@app.route('/notificacoes/registrar', methods=['POST'])
def registrar_interesse():
    dados = request.json
    id_usuario = dados.get('id_usuario')
    id_leilao = dados.get('id_leilao')
    if not id_usuario or id_leilao is None:
        return jsonify({"erro": "Dados incompletos"}), 400
    with clientes_lock:
        if id_usuario not in clientes_sse:
            return jsonify({"erro": "Usuário não conectado ao SSE"}), 400
        clientes_sse[id_usuario]['interesses'].add(id_leilao)
    return jsonify({"status": "ok"}), 200

@app.route('/notificacoes/cancelar', methods=['POST'])
def cancelar_interesse():
    dados = request.json
    with clientes_lock:
        uid = dados.get('id_usuario')
        if uid in clientes_sse:
            clientes_sse[uid]['interesses'].discard(dados.get('id_leilao'))
    return jsonify({"status": "ok"}), 200

@app.route('/eventos')
def sse_stream():
    id_usuario = request.args.get('id_usuario')
    if not id_usuario: return jsonify({"erro": "Faltou id_usuario"}), 400

    def event_generator(user_id):
        q = queue.Queue()
        with clientes_lock:
            clientes_sse[user_id] = {'queue': q, 'interesses': set()}
            print(f"[SSE] Cliente {user_id} conectado.")
        
        yield f"event: ping\ndata: {json.dumps({'msg': 'conexao_iniciada'})}\n\n"

        try:
            while True:
                msg = q.get()
                yield msg
        except GeneratorExit:
            with clientes_lock:
                if user_id in clientes_sse: del clientes_sse[user_id]
            print(f"[SSE] Cliente {user_id} desconectou.")

    return Response(event_generator(id_usuario), mimetype='text/event-stream')

# --- Consumidor RabbitMQ ---

def despachar_evento_sse(evento_tipo, dados):
    msg = f"event: {evento_tipo}\ndata: {json.dumps(dados)}\n\n"
    id_leilao = dados.get('id_leilao')
    destinatario = None
    
    if evento_tipo == 'lance_invalido': destinatario = dados.get('id_usuario')
    elif evento_tipo in ['link_pagamento', 'status_pagamento']: 
        destinatario = dados.get('id_vencedor') or dados.get('id_comprador')

    with clientes_lock:
        if destinatario and destinatario in clientes_sse:
            clientes_sse[destinatario]['queue'].put_nowait(msg)
        elif evento_tipo in ['novo_lance', 'vencedor_leilao'] and id_leilao is not None:
            for uid, info in clientes_sse.items():
                if id_leilao in info['interesses']:
                    info['queue'].put_nowait(msg)

def callback_rabbitmq(ch, method, properties, body):
    routing_key = method.routing_key
    dados = json.loads(body.decode())
    print(f"[Gateway SUB] Evento recebido: {routing_key}")
    
    mapa = {
        'lance.validado': 'novo_lance',
        'lance.invalidado': 'lance_invalido',
        'leilao.vencedor': 'vencedor_leilao',
        'link_pagamento': 'link_pagamento',
        'status_pagamento': 'status_pagamento'
    }
    
    if routing_key == 'lance.validado':
        try:
            id_leilao = dados.get('id_leilao')
            novo_valor = dados.get('valor')
            requests.patch(f"{MS_LEILAO_URL}/leiloes/{id_leilao}", json={"valor": novo_valor})
            print(f"[Gateway] Atualizou MS Leilão {id_leilao} com valor {novo_valor}")
        except Exception as e:
            print(f"[Gateway] Falha ao atualizar MS Leilão: {e}")

    if routing_key in mapa:
        despachar_evento_sse(mapa[routing_key], dados)
        
    ch.basic_ack(delivery_tag=method.delivery_tag)

def iniciar_consumidor():
    while True:
        try:
            creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            conn = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=creds))
            ch = conn.channel()
            ch.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='topic')
            q = ch.queue_declare(queue='', exclusive=True).method.queue
            for k in BINDING_KEYS: ch.queue_bind(exchange=EXCHANGE_NAME, queue=q, routing_key=k)
            
            print("[Gateway] Conectado ao RabbitMQ.")
            ch.basic_consume(queue=q, on_message_callback=callback_rabbitmq)
            ch.start_consuming()
        except Exception as e:
            print(f"[Gateway] Erro RabbitMQ: {e}. Reconectando em 5s...")
            time.sleep(5)

if __name__ == '__main__':
    threading.Thread(target=iniciar_consumidor, daemon=True).start()
    print("[*] API Gateway rodando na porta 5000 (com CORS)...")
    app.run(port=5000, debug=True, use_reloader=False)