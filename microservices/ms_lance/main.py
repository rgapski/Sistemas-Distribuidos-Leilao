# /microservices/ms_lance/main.py

import pika
import json
import os
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# --- Configurações ---
RABBITMQ_HOST = 'localhost'
RABBITMQ_USER = 'user'
RABBITMQ_PASS = 'password'
PUBLIC_KEYS_DIR = 'cliente_tui' # Diretório onde as chaves públicas estão
EXCHANGE_NAME = 'leilao_topic_exchange'
BINDING_KEYS = ['leilao.iniciado', 'leilao.finalizado', 'lance.realizado'] # Tópicos que este MS escuta

# --- Estado Interno do Microsserviço ---
leiloes_ativos = {}
chaves_publicas = {}
# Canal de comunicação com RabbitMQ para ser reutilizado
rabbit_channel = None 

# --- Funções de Lógica de Negócio ---

def carregar_chaves_publicas():
    print("Carregando chaves públicas...")
    for filename in os.listdir(PUBLIC_KEYS_DIR):
        if filename.endswith("_public_key.pem"):
            usuario_id = filename.replace("_public_key.pem", "")
            try:
                with open(os.path.join(PUBLIC_KEYS_DIR, filename), "rb") as key_file:
                    chaves_publicas[usuario_id] = serialization.load_pem_public_key(key_file.read())
                print(f"  - Chave de '{usuario_id}' carregada.")
            except Exception as e:
                print(f"  - Falha ao carregar chave de '{usuario_id}': {e}")

def verificar_assinatura(payload: dict) -> bool:
    try:
        dados = payload['dados']
        assinatura_hex = payload['assinatura']
        assinatura_bytes = bytes.fromhex(assinatura_hex)
        usuario_id = dados['id_usuario']
        public_key = chaves_publicas.get(usuario_id)
        if not public_key:
            print(f"  --> Assinatura Inválida: Chave pública para '{usuario_id}' não encontrada.")
            return False
        
        mensagem_bytes = json.dumps(dados, sort_keys=True).encode('utf-8')
        public_key.verify(
            assinatura_bytes, 
            mensagem_bytes, 
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH), 
            hashes.SHA256()
        )
        return True
    except Exception as e:
        print(f"  --> Exceção ao verificar assinatura: {e}")
        return False

def publicar_evento(routing_key: str, evento: dict):
    global rabbit_channel
    if not rabbit_channel:
        print("  [!] Erro: Canal RabbitMQ não está disponível para publicação.")
        return
    try:
        rabbit_channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=routing_key,
            body=json.dumps(evento),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        print(f"  --> Evento '{routing_key}' publicado com sucesso.")
    except pika.exceptions.AMQPError as e:
        print(f"  [!] Erro ao publicar evento '{routing_key}': {e}")

def processar_lance_realizado(dados_lance_com_assinatura):
    print("\n[lance.realizado] Processando lance recebido.")
    dados = dados_lance_com_assinatura.get('dados', {})

    if not verificar_assinatura(dados_lance_com_assinatura):
        print("  --> Lance Descartado: Assinatura Inválida.")
        return

    leilao_id = dados.get('id_leilao')
    if leilao_id not in leiloes_ativos or leiloes_ativos[leilao_id]['status'] != 'ativo':
        print(f"  --> Lance Descartado: Leilão {leilao_id} não está ativo.")
        return

    valor_lance = dados.get('valor', 0)
    if valor_lance <= leiloes_ativos[leilao_id].get('maior_lance', 0):
        print(f"  --> Lance Descartado: Valor R${valor_lance} não é maior que o lance atual de R${leiloes_ativos[leilao_id].get('maior_lance', 0)}.")
        return
    
    print(f"  [✓] Lance VÁLIDO de {dados.get('id_usuario')} no valor de R${valor_lance} para o leilão {leilao_id}.")
    leiloes_ativos[leilao_id]['maior_lance'] = valor_lance
    leiloes_ativos[leilao_id]['vencedor'] = dados.get('id_usuario')
    publicar_evento('lance.validado', dados)

def processar_leilao_iniciado(leilao):
    leilao_id = leilao.get('id_leilao')
    if leilao_id:
        leiloes_ativos[leilao_id] = {"maior_lance": 0, "vencedor": None, "status": "ativo"}
        print(f"\n[leilao.iniciado] Leilão {leilao_id} ({leilao.get('descricao')}) agora está ATIVO.")

def processar_leilao_finalizado(leilao):
    leilao_id = leilao.get('id_leilao')
    if leilao_id in leiloes_ativos:
        leiloes_ativos[leilao_id]['status'] = 'encerrado'
        vencedor = leiloes_ativos[leilao_id].get('vencedor')
        valor = leiloes_ativos[leilao_id].get('maior_lance', 0)
        
        print(f"\n[leilao.finalizado] Leilão {leilao_id} ENCERRADO.")
        if vencedor:
            print(f"  - Vencedor: {vencedor} com R${valor:.2f}")
            publicar_evento('leilao.vencedor', {"id_leilao": leilao_id, "vencedor": vencedor, "valor": valor})
        else:
            print("  - Leilão terminou sem lances.")

def callback_geral(ch, method, properties, body):
    routing_key = method.routing_key
    mensagem = json.loads(body.decode())
    
    if routing_key == 'leilao.iniciado':
        processar_leilao_iniciado(mensagem)
    elif routing_key == 'leilao.finalizado':
        processar_leilao_finalizado(mensagem)
    elif routing_key == 'lance.realizado':
        processar_lance_realizado(mensagem)
    else:
        print(f"  [!] Mensagem recebida com chave desconhecida: {routing_key}")
        
    ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    global rabbit_channel
    carregar_chaves_publicas()
    
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials))
    rabbit_channel = connection.channel()

    rabbit_channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='topic')
    result = rabbit_channel.queue_declare(queue='', exclusive=True)
    queue_name = result.method.queue

    for key in BINDING_KEYS:
        rabbit_channel.queue_bind(exchange=EXCHANGE_NAME, queue=queue_name, routing_key=key)
    
    print(f'[*] MS Lance iniciado. Escutando por eventos: {BINDING_KEYS}.')
    rabbit_channel.basic_consume(queue=queue_name, on_message_callback=callback_geral)
    
    try:
        rabbit_channel.start_consuming()
    except KeyboardInterrupt:
        print("Encerrando MS Lance.")
        connection.close()

if __name__ == '__main__':
    main()