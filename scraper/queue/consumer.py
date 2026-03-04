import asyncio
import pika
from scraper.config import RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USER, RABBITMQ_PASS
from scraper.scrapers import grab_elements_by_directive
from scraper.storage.mongo import save_scraped

_QUEUE = "scrapers_queue"

_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)


def _callback(ch, method, properties, body):
    directive = body.decode()
    data = _loop.run_until_complete(grab_elements_by_directive(directive))
    result = save_scraped(data)
    print(result)


def start():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    params = pika.ConnectionParameters(RABBITMQ_HOST, RABBITMQ_PORT, "/", credentials)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=_QUEUE)
    channel.basic_consume(queue=_QUEUE, on_message_callback=_callback, auto_ack=True)
    print("waiting for messages... (Ctrl+C to quit)")
    channel.start_consuming()


if __name__ == "__main__":
    start()
