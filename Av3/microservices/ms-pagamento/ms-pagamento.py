# /microservices/ms_pagamento/ms-pagamento.py

import pika
import json
import threading
import requests
from flask import Flask, request, jsonify

# --- Configurações ---
RABBITMQ_HOST = '127.0.0.1'
RABBITMQ_USER = 'user'
RABBITMQ_PASS = 'password'
EXCHANGE_NAME = 'leilao_topic_exchange'

# URL do simulador que CRIAMOS no passo 4
SIMULADOR_URL = "http://127.0.0.1:5004/iniciar_pagamento" 

# --- Configuração do Flask ---
app = Flask(__name__)

# --- Lógica de Publicação (Thread-safe) ---

def publicar_evento(routing_key: str, evento: dict):
    """
    Publica um evento na exchange principal (Thread-safe).
    Cria uma nova conexão para cada publicação.
    """
    try:
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials))
        channel = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='topic')
        
        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=routing_key,
            body=json.dumps(evento),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        print(f"  --> [PUB] Evento '{routing_key}' publicado.")
        connection.close()
    except Exception as e:
        print(f"  [!] Erro ao publicar evento '{routing_key}': {e}")

# --- Endpoint REST (Recebe o Webhook do Simulador) ---

@app.route('/webhook/status', methods=['POST'])
def receber_webhook_status():
    """
    [cite_start]Recebe a notificação (webhook) do sistema de pagamento externo[cite: 74, 79].
    """
    dados_webhook = request.json
    print(f"\n[WEBHOOK] Recebido status: '{dados_webhook.get('status')}' para transação {dados_webhook.get('id_transacao')}")
    
    # Prepara o evento para o API Gateway
    evento_status = {
        "id_leilao": dados_webhook.get('id_leilao'),
        "id_comprador": dados_webhook.get('id_comprador'),
        "status": dados_webhook.get('status'), # 'aprovado' ou 'recusado' [cite: 75, 80]
        "valor": dados_webhook.get('valor')
    }
    
    # [cite_start]Publica o evento status_pagamento [cite: 75]
    publicar_evento('status_pagamento', evento_status)
    
    return jsonify({"status": "webhook recebido"}), 200

# --- Funções de Consumo RabbitMQ ---

def processar_leilao_vencedor(vencedor_info):
    """
    [cite_start]Chamado quando um evento 'leilao.vencedor' é consumido[cite: 70].
    """
    id_leilao = vencedor_info.get('id_leilao')
    print(f"\n[SUB] Recebido 'leilao.vencedor' para o leilão {id_leilao}")
    
    # Prepara os dados para enviar ao sistema de pagamento
    dados_pagamento = {
        "id_leilao": id_leilao,
        "id_vencedor": vencedor_info.get('id_vencedor'), # O PDF chama de 'ID do vencedor' [cite: 70]
        "valor": vencedor_info.get('valor'), # [cite: 70, 72]
        "moeda": "BRL", # [cite: 72]
        "informacoes_cliente": f"Cliente ID {vencedor_info.get('id_vencedor')}" # [cite: 72]
    }
    
    try:
        # [cite_start]1. Faz a requisição REST ao sistema externo [cite: 72]
        print(f"  ... Enviando requisição REST para Simulador em {SIMULADOR_URL}")
        response = requests.post(SIMULADOR_URL, json=dados_pagamento)
        response.raise_for_status() # Lança exceção se for erro HTTP (4xx ou 5xx)
        
        # [cite_start]2. Recebe o link de pagamento [cite: 73, 78]
        resposta_json = response.json()
        link_pagamento = resposta_json.get('link_pagamento')
        
        print(f"  ... Simulador retornou link: {link_pagamento}")
        
        # [cite_start]3. Publica o evento link_pagamento [cite: 73]
        evento_link = {
            "id_leilao": id_leilao,
            "id_vencedor": vencedor_info.get('id_vencedor'),
            "link_pagamento": link_pagamento
        }
        publicar_evento('link_pagamento', evento_link)
        
    except requests.exceptions.RequestException as e:
        print(f"  [!] ERRO ao contatar o Sistema de Pagamento Externo: {e}")
    except Exception as e:
        print(f"  [!] ERRO ao processar vencedor do leilão: {e}")

def callback_geral(ch, method, properties, body):
    routing_key = method.routing_key
    mensagem = json.loads(body.decode())
    
    if routing_key == 'leilao.vencedor':
        processar_leilao_vencedor(mensagem)
    
    ch.basic_ack(delivery_tag=method.delivery_tag)

def iniciar_consumidor_rabbitmq():
    """Roda em uma thread separada para consumir eventos do RabbitMQ."""
    print("[*] Iniciando thread de consumo RabbitMQ...")
    try:
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials))
        channel = connection.channel()

        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='topic')
        result = channel.queue_declare(queue='', exclusive=True)
        queue_name = result.method.queue

        # [cite_start]Este MS só precisa escutar por 'leilao.vencedor' [cite: 70]
        BINDING_KEYS = ['leilao.vencedor'] 
        
        for key in BINDING_KEYS:
            channel.queue_bind(exchange=EXCHANGE_NAME, queue=queue_name, routing_key=key)
        
        print(f'[*] MS Pagamento escutando por eventos: {BINDING_KEYS}.')
        channel.basic_consume(queue=queue_name, on_message_callback=callback_geral)
        channel.start_consuming()
    except Exception as e:
        print(f"[!] Thread RabbitMQ falhou: {e}")

# --- Ponto de entrada ---
if __name__ == '__main__':
    # Inicia o consumidor RabbitMQ em uma thread separada
    thread_rabbitmq = threading.Thread(target=iniciar_consumidor_rabbitmq)
    thread_rabbitmq.daemon = True # Permite que o programa feche
    thread_rabbitmq.start()
    
    # Inicia o servidor Flask na thread principal (porta 5003)
    print("[*] Iniciando servidor Flask (porta 5003) para Webhooks...")
    app.run(port=5003, debug=True, use_reloader=False)