# /microservices/ms_leilao/main.py

import pika
import json
import time
from datetime import datetime, timedelta


# --- Configurações ---
RABBITMQ_HOST = 'localhost'
RABBITMQ_USER = 'user'
RABBITMQ_PASS = 'password'
EXCHANGE_NAME = 'leilao_topic_exchange' # Novo nome para nossa exchange principal

# --- Dados Fictícios de Leilão ---
# Lista de leilões pré-configurada
LEILOES = [
    {"id_leilao": 1, "descricao": "Notebook Gamer", "inicio": datetime.now() + timedelta(seconds=5), "fim": datetime.now() + timedelta(minutes=2), "status": "agendado"},
    {"id_leilao": 2, "descricao": "Smartphone 5G", "inicio": datetime.now() + timedelta(seconds=15), "fim": datetime.now() + timedelta(minutes=3), "status": "agendado"},
]

def publicar_evento(channel, routing_key: str, evento: dict):
    """
    Publica um evento na exchange principal, reutilizando o canal de conexão.
    """
    try:
        evento_serializavel = evento.copy()
        for key, value in evento_serializavel.items():
            if isinstance(value, datetime):
                evento_serializavel[key] = value.isoformat()

        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=routing_key,
            body=json.dumps(evento_serializavel),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        print(f" [x] Evento '{routing_key}' publicado.")
    except Exception as e:
        print(f"Erro ao publicar evento: {e}")

def main():
    print("MS Leilão iniciado...")
    
    try:
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials))
        channel = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='topic')
        
        while True:
            agora = datetime.now()
            for leilao in LEILOES:
                if leilao['status'] == 'agendado' and agora >= leilao['inicio']:
                    leilao['status'] = 'ativo'
                    # Passa o 'channel' existente para a função
                    publicar_evento(channel, 'leilao.iniciado', leilao)
                
                if leilao['status'] == 'ativo' and agora >= leilao['fim']:
                    leilao['status'] = 'encerrado'
                    publicar_evento(channel, 'leilao.finalizado', {"id_leilao": leilao['id_leilao']})

            time.sleep(1)
            
    except pika.exceptions.AMQPConnectionError as e:
        print(f"Erro de conexão com RabbitMQ: {e}")
    finally:
        if 'connection' in locals() and connection.is_open:
            connection.close()
            print("Conexão com RabbitMQ fechada.")

if __name__ == '__main__':
    main()