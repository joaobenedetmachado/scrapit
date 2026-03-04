import pika
from scraper.config import RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USER, RABBITMQ_PASS

_QUEUE = "scrapers_queue"


def call_producer(directive: str):
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    params = pika.ConnectionParameters(RABBITMQ_HOST, RABBITMQ_PORT, "/", credentials)

    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=_QUEUE)
    channel.basic_publish(exchange="", routing_key=_QUEUE, body=directive)
    connection.close()
    print("sent!")
