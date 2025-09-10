# /microservices/ms_notificacao/main.py
import pika
import json

RABBITMQ_HOST = 'localhost'
RABBITMQ_USER = 'user'
RABBITMQ_PASS = 'password'
QUEUES_TO_CONSUME = ['lance_validado', 'leilao_vencedor']

def main():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials))
    channel = connection.channel()

    def callback(ch, method, properties, body):
        mensagem = json.loads(body.decode())
        leilao_id = mensagem.get('id_leilao')
        if not leilao_id:
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        notification_queue = f'leilao_{leilao_id}'
        channel.queue_declare(queue=notification_queue, durable=True)
        channel.basic_publish(exchange='', routing_key=notification_queue, body=body, properties=pika.BasicProperties(delivery_mode=2))
        
        print(f" [x] Evento '{method.routing_key}' para leilão {leilao_id} roteado para '{notification_queue}'")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    for queue_name in QUEUES_TO_CONSUME:
        channel.queue_declare(queue=queue_name, durable=True)
        channel.basic_consume(queue=queue_name, on_message_callback=callback)

    print('[*] MS Notificação iniciado.')
    channel.start_consuming()

if __name__ == '__main__':
    main()