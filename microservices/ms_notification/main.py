# /microservices/ms_notificacao/main.py
import pika
import json

# --- Configurações ---
RABBITMQ_HOST = 'localhost'
RABBITMQ_USER = 'user'
RABBITMQ_PASS = 'password'
EXCHANGE_NAME = 'leilao_topic_exchange'
BINDING_KEYS = ['lance.validado', 'leilao.vencedor'] # Tópicos que este MS escuta


def main():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials))
    channel = connection.channel()

    # Garante que a exchange existe
    channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='topic')
    
    # Cria uma fila exclusiva para este consumidor
    result = channel.queue_declare(queue='', exclusive=True)
    queue_name = result.method.queue

    # Faz o bind da fila aos tópicos de interesse
    for key in BINDING_KEYS:
        channel.queue_bind(exchange=EXCHANGE_NAME, queue=queue_name, routing_key=key)

    def callback(ch, method, properties, body):
        """Recebe um evento e o republica com uma routing key de notificação."""
        mensagem = json.loads(body.decode())
        leilao_id = mensagem.get('id_leilao')
        
        if not leilao_id:
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # Determina o tipo de notificação a partir da routing key original
        evento_original = method.routing_key
        # Ex: 'lance.validado' -> 'notificacao.lance'
        # Ex: 'leilao.vencedor' -> 'notificacao.vencedor'
        tipo_notificacao = evento_original.replace('.', '.').split('.')[0] # lance ou leilao
        
        # Cria uma nova routing key específica para a notificação deste leilão
        # Ex: notificacao.lance.1 ou notificacao.vencedor.1
        nova_routing_key = f"notificacao.{tipo_notificacao}.{leilao_id}"
        
        # Republica a mensagem original na mesma exchange, mas com a nova routing key
        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=nova_routing_key,
            body=body, # Reenvia o corpo original da mensagem
            properties=pika.BasicProperties(delivery_mode=2)
        )
        
        print(f" [x] Evento '{evento_original}' roteado como '{nova_routing_key}'")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=queue_name, on_message_callback=callback)

    print(f'[*] MS Notificação iniciado. Roteando eventos de {BINDING_KEYS}.')
    channel.start_consuming()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('MS Notificação encerrado.')