# /microservices/ms_lance/main.py

import pika
import json
import threading
from flask import Flask, request, jsonify

# --- Configurações ---
RABBITMQ_HOST = '127.0.0.1'
RABBITMQ_USER = 'user'
RABBITMQ_PASS = 'password'
EXCHANGE_NAME = 'leilao_topic_exchange'
# BINDING_KEYS agora escuta apenas o ciclo de vida do leilão
BINDING_KEYS = ['leilao.iniciado', 'leilao.finalizado'] 

# --- Configuração do Flask ---
app = Flask(__name__)

# --- Estado Interno e Threading ---
leiloes_ativos = {}
leiloes_lock = threading.Lock() # Lock para proteger o dicionário

# --- Funções de Lógica de Negócio ---

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

# --- Endpoints da API REST ---

@app.route('/lance', methods=['POST'])
def efetuar_lance(): # 
    """
    Recebe um novo lance via REST.
    JSON esperado: {"id_leilao": int, "id_usuario": str, "valor": float}
    """
    dados = request.json
    leilao_id = dados.get('id_leilao')
    valor_lance = dados.get('valor', 0)
    usuario_id = dados.get('id_usuario')
    
    print(f"\n[REST] Recebida tentativa de lance de {usuario_id} no leilão {leilao_id} por R${valor_lance}")

    with leiloes_lock: # Protege o acesso ao dicionário
        leilao_info = leiloes_ativos.get(leilao_id)

        # Validação 1: Leilão existe e está ativo?
        if not leilao_info or leilao_info['status'] != 'ativo': 
            print(f"  --> Lance Inválido: Leilão {leilao_id} não está ativo.")
            publicar_evento('lance.invalidado', dados) # 
            return jsonify({"erro": "Leilão não está ativo"}), 400

        # Validação 2: Valor do lance é maior?
        maior_lance_atual = leilao_info.get('maior_lance', 0)
        if valor_lance <= maior_lance_atual: 
            print(f"  --> Lance Inválido: Valor R${valor_lance} não é maior que R${maior_lance_atual}.")
            publicar_evento('lance.invalidado', dados) # 
            return jsonify({"erro": f"Valor do lance deve ser maior que R${maior_lance_atual}"}), 400
        
        # Lance Válido!
        print(f"  [X] Lance VÁLIDO de {usuario_id} no valor de R${valor_lance}.")
        leilao_info['maior_lance'] = valor_lance
        leilao_info['vencedor'] = usuario_id
        
        # Publica o evento de lance validado
        publicar_evento('lance.validado', dados) 

    return jsonify({"status": "Lance aceito"}), 200

# --- Funções de Consumo RabbitMQ ---

def processar_leilao_iniciado(leilao):
    leilao_id = leilao.get('id_leilao')
    if leilao_id:
        with leiloes_lock: # Protege o acesso
            leiloes_ativos[leilao_id] = {
                "maior_lance": leilao.get('valor_inicial', 0), # Usa o valor inicial como base
                "vencedor": None, 
                "status": "ativo"
            }
        print(f"\n[SUB] Leilão {leilao_id} ({leilao.get('descricao')}) agora está ATIVO.")

def processar_leilao_finalizado(leilao):
    leilao_id = leilao.get('id_leilao')
    
    with leiloes_lock: # Protege o acesso
        if leilao_id in leiloes_ativos:
            leilao_info = leiloes_ativos[leilao_id]
            leilao_info['status'] = 'encerrado'
            vencedor = leilao_info.get('vencedor')
            valor = leilao_info.get('maior_lance', 0)
            
            print(f"\n[SUB] Leilão {leilao_id} ENCERRADO.")
            
            # Se houver vencedor, publica o evento
            if vencedor:
                print(f"  - Vencedor: {vencedor} com R${valor:.2f}")
                evento_vencedor = {
                    "id_leilao": leilao_id, 
                    "id_vencedor": vencedor, 
                    "valor": valor 
                }
                publicar_evento('leilao.vencedor', evento_vencedor)
                print("  - Leilão terminou sem lances/vencedor.")

def callback_geral(ch, method, properties, body):
    routing_key = method.routing_key
    mensagem = json.loads(body.decode())
    
    if routing_key == 'leilao.iniciado':
        processar_leilao_iniciado(mensagem)
    elif routing_key == 'leilao.finalizado':
        processar_leilao_finalizado(mensagem)
    
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

        for key in BINDING_KEYS:
            channel.queue_bind(exchange=EXCHANGE_NAME, queue=queue_name, routing_key=key)
        
        print(f'[*] MS Lance escutando por eventos: {BINDING_KEYS}.')
        channel.basic_consume(queue=queue_name, on_message_callback=callback_geral)
        channel.start_consuming()
    except Exception as e:
        print(f"[!] Thread RabbitMQ falhou: {e}")

# --- Ponto de entrada ---
if __name__ == '__main__':
    # Inicia o consumidor RabbitMQ em uma thread separada
    thread_rabbitmq = threading.Thread(target=iniciar_consumidor_rabbitmq)
    thread_rabbitmq.daemon = True # Permite que o programa feche mesmo se a thread estiver rodando
    thread_rabbitmq.start()
    
    # Inicia o servidor Flask na thread principal
    print("[*] Iniciando servidor Flask (porta 5002)...")
    app.run(port=5002, debug=True, use_reloader=False)