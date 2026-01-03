import pika

def call_producer(directive):
    credentials = pika.PlainCredentials('joao', '123')
    params = pika.ConnectionParameters('localhost', 5672, '/', credentials)

    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    channel.queue_declare(queue='scrapers_queue')
    channel.basic_publish(
        exchange='',
        routing_key='scrapers_queue',
        body=directive
    )

    print("sended!")
    connection.close()  

