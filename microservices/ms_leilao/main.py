# /microservices/ms_leilao/main.py

import pika
import json
import time
import datetime

# --- Configurações ---
RABBITMQ_HOST = 'localhost'
QUEUE_NAME = 'leilao_iniciado'

# --- Dados Fictícios de Leilão ---
leilao_exemplo = {
    "id_leilao": 1,
    "descricao": "Notebook Gamer de Última Geração",
    "inicio": (datetime.datetime.now() + datetime.timedelta(seconds=5)).isoformat(),
    "fim": (datetime.datetime.now() + datetime.timedelta(minutes=10)).isoformat()
}

def conectar_e_publicar():
    """Conecta ao RabbitMQ e publica uma mensagem."""
    try:
        # Conexão com o RabbitMQ
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()

        # Declara a fila (garante que ela exista)
        # durable=True faz a fila sobreviver a reinicializações do RabbitMQ
        channel.queue_declare(queue=QUEUE_NAME, durable=True)

        # Converte o dicionário Python para uma string JSON
        mensagem = json.dumps(leilao_exemplo)

        # Publica a mensagem na fila
        channel.basic_publish(
            exchange='',          # Exchange padrão
            routing_key=QUEUE_NAME, # O nome da fila
            body=mensagem,
            properties=pika.BasicProperties(
                delivery_mode=2,  # Torna a mensagem persistente
            ))
        
        print(f" [x] Enviado para a fila '{QUEUE_NAME}': {mensagem}")

        # Fecha a conexão
        connection.close()

    except pika.exceptions.AMQPConnectionError as e:
        print(f"Erro ao conectar ao RabbitMQ: {e}")
        print("Verifique se o container do RabbitMQ está rodando. ('docker-compose up -d')")

if __name__ == '__main__':
    print("MS Leilão iniciado. Publicando um novo leilão em 5 segundos...")
    time.sleep(5) # Simula o tempo até o início do leilão
    
    conectar_e_publicar()
    print("Mensagem publicada. O serviço será encerrado.")