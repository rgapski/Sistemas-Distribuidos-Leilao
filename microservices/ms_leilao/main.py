# /microservices/ms_leilao/main.py

import pika
import json
import time
from datetime import datetime, timedelta

# --- Configurações ---
RABBITMQ_HOST = 'localhost'
RABBITMQ_USER = 'user'
RABBITMQ_PASS = 'password'
QUEUE_NAME = 'leilao_iniciado'

# --- Dados Fictícios de Leilão ---
# Lista de leilões pré-configurada
LEILOES = [
    {"id_leilao": 1, "descricao": "Notebook Gamer", "inicio": datetime.now() + timedelta(seconds=5), "fim": datetime.now() + timedelta(minutes=2), "status": "agendado"},
    {"id_leilao": 2, "descricao": "Smartphone 5G", "inicio": datetime.now() + timedelta(seconds=15), "fim": datetime.now() + timedelta(minutes=3), "status": "agendado"},
]

def publicar_evento(queue_name: str, evento: dict):
    try:
        
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials))
        channel = connection.channel()
        channel.queue_declare(queue=queue_name, durable=True)
        
        # Converte datas para string antes de serializar
        evento_serializavel = evento.copy()
        for key, value in evento_serializavel.items():
            if isinstance(value, datetime):
                evento_serializavel[key] = value.isoformat()

        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(evento_serializavel),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        print(f" [x] Evento publicado na fila '{queue_name}': {evento['id_leilao']}")
        connection.close()
    except pika.exceptions.AMQPConnectionError as e:
        print(f"Erro de conexão com RabbitMQ: {e}")

def main():
    print("MS Leilão iniciado. Monitorando agendamentos...")
    while True:
        agora = datetime.now()
        for leilao in LEILOES:
            # Inicia leilão
            if leilao['status'] == 'agendado' and agora >= leilao['inicio']:
                leilao['status'] = 'ativo'
                publicar_evento('leilao_iniciado', leilao)
            
            # Finaliza leilão
            if leilao['status'] == 'ativo' and agora >= leilao['fim']:
                leilao['status'] = 'encerrado'
                publicar_evento('leilao_finalizado', {"id_leilao": leilao['id_leilao']})

        time.sleep(1) # Verifica a cada segundo

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('MS Leilão encerrado.')