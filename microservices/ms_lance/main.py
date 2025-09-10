# /microservices/ms_lance/main.py

import pika
import json
import os
import threading
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature

# --- Configurações ---
RABBITMQ_HOST = 'localhost'
RABBITMQ_USER = 'user'
RABBITMQ_PASS = 'password'
PUBLIC_KEYS_DIR = '.'
QUEUES_TO_CONSUME = ['lance_realizado', 'leilao_iniciado'] # Adicionaremos 'leilao_finalizado' depois
LANCE_VALIDADO_QUEUE = 'lance_validado'

# --- Estado Interno do Microsserviço ---
leiloes_ativos = {}
chaves_publicas = {}

# --- Lógica de Negócio ---

def carregar_chaves_publicas():
    """Carrega todas as chaves públicas .pem do diretório configurado."""
    print("Carregando chaves públicas...")
    for filename in os.listdir(PUBLIC_KEYS_DIR):
        if filename.endswith("_public_key.pem"):
            usuario_id = filename.replace("_public_key.pem", "")
            try:
                with open(os.path.join(PUBLIC_KEYS_DIR, filename), "rb") as key_file:
                    chaves_publicas[usuario_id] = serialization.load_pem_public_key(
                        key_file.read()
                    )
                print(f"  - Chave de '{usuario_id}' carregada.")
            except Exception as e:
                print(f"  - Falha ao carregar chave de '{usuario_id}': {e}")

def processar_lance_realizado(ch, method, properties, body):
    #... (lógica completa de validação)
    print("\n[lance_realizado] Lance recebido.")
    payload = json.loads(body.decode())
    dados = payload.get('dados', {})
    if not verificar_assinatura(payload):
        print("  --> Lance Descartado: Assinatura Inválida."); ch.basic_ack(delivery_tag=method.delivery_tag); return
    leilao_id = dados.get('id_leilao')
    if leilao_id not in leiloes_ativos or leiloes_ativos[leilao_id]['status'] != 'ativo':
        print(f"  --> Lance Descartado: Leilão {leilao_id} não está ativo."); ch.basic_ack(delivery_tag=method.delivery_tag); return
    valor_lance = dados.get('valor', 0)
    if valor_lance <= leiloes_ativos[leilao_id]['maior_lance']:
        print(f"  --> Lance Descartado: Valor não é maior."); ch.basic_ack(delivery_tag=method.delivery_tag); return
    
    print(f"  [✓] Lance VÁLIDO para o leilão {leilao_id}.")
    leiloes_ativos[leilao_id]['maior_lance'] = valor_lance
    leiloes_ativos[leilao_id]['vencedor'] = dados.get('id_usuario')
    publicar_evento('lance_validado', dados)
    ch.basic_ack(delivery_tag=method.delivery_tag)

def processar_leilao_iniciado(ch, method, properties, body):
    leilao = json.loads(body.decode()); leilao_id = leilao.get('id_leilao')
    if leilao_id:
        leiloes_ativos[leilao_id] = {"maior_lance": 0, "vencedor": None, "status": "ativo"}
        print(f"\n[leilao_iniciado] Leilão {leilao_id} ATIVO.")
    ch.basic_ack(delivery_tag=method.delivery_tag)

def processar_leilao_finalizado(ch, method, properties, body):
    leilao = json.loads(body.decode()); leilao_id = leilao.get('id_leilao')
    if leilao_id in leiloes_ativos:
        leiloes_ativos[leilao_id]['status'] = 'encerrado'
        vencedor = leiloes_ativos[leilao_id]['vencedor']
        valor = leiloes_ativos[leilao_id]['maior_lance']
        print(f"\n[leilao_finalizado] Leilão {leilao_id} ENCERRADO. Vencedor: {vencedor} com R${valor}")
        if vencedor:
            publicar_evento('leilao_vencedor', {"id_leilao": leilao_id, "vencedor": vencedor, "valor": valor})
    ch.basic_ack(delivery_tag=method.delivery_tag)

def verificar_assinatura(payload: dict) -> bool:
    #... (igual à versão anterior)
    try:
        dados = payload['dados']; assinatura_hex = payload['assinatura']
        assinatura_bytes = bytes.fromhex(assinatura_hex); usuario_id = dados['id_usuario']
        public_key = chaves_publicas.get(usuario_id)
        if not public_key: return False
        mensagem_bytes = json.dumps(dados, sort_keys=True).encode('utf-8')
        public_key.verify(assinatura_bytes, mensagem_bytes, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256())
        return True
    except: return False

def publicar_lance_validado(dados_lance: dict):
    """Publica a mensagem na fila 'lance_validado'."""
    try:
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST, port=15672, credentials=credentials))
        channel = connection.channel()
        channel.queue_declare(queue=LANCE_VALIDADO_QUEUE, durable=True)
        channel.basic_publish(
            exchange='',
            routing_key=LANCE_VALIDADO_QUEUE,
            body=json.dumps(dados_lance),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        print(f"  --> Evento publicado em '{LANCE_VALIDADO_QUEUE}'.")
        connection.close()
    except pika.exceptions.AMQPConnectionError as e:
        print(f"  [!] Erro ao publicar lance validado: {e}")

def start_consumer(queue_name: str, callback_func):
    #... (igual à versão anterior)
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials))
    channel = connection.channel()
    channel.queue_declare(queue=queue_name, durable=True)
    channel.basic_consume(queue=queue_name, on_message_callback=callback_func)
    print(f'[*] Consumidor iniciado para a fila "{queue_name}".')
    channel.start_consuming()

def publicar_evento(queue_name: str, evento: dict):
    #... (função auxiliar para publicar, igual à do ms_leilao)
    try:
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST, credentials=credentials))
        channel = connection.channel()
        channel.queue_declare(queue=queue_name, durable=True)
        channel.basic_publish(exchange='', routing_key=queue_name, body=json.dumps(evento), properties=pika.BasicProperties(delivery_mode=2))
        print(f"  --> Evento publicado em '{queue_name}'.")
        connection.close()
    except pika.exceptions.AMQPConnectionError as e:
        print(f"  [!] Erro ao publicar evento: {e}")

def main():
    carregar_chaves_publicas()
    callbacks = {
        'lance_realizado': processar_lance_realizado,
        'leilao_iniciado': processar_leilao_iniciado,
        'leilao_finalizado': processar_leilao_finalizado
    }
    threads = [threading.Thread(target=start_consumer, args=(q, cb)) for q, cb in callbacks.items()]
    for t in threads: t.start()
    print("MS Lance iniciado.")
    for t in threads: t.join()

if __name__ == '__main__':
    main()
