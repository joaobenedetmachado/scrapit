import pika
import db_utils
from utils import grab_elements_by_directive
import asyncio

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def callback(ch, method, properties, body):
    mensagem = body.decode()
    data = loop.run_until_complete(grab_elements_by_directive(mensagem))
    res = db_utils.save_scraped(data)
    print(res)

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

channel.queue_declare(queue='scrapers_queue')

channel.basic_consume(queue='scrapers_queue',
                      on_message_callback=callback,
                      auto_ack=True)

print("waiting for body req... (Ctrl+C to quit)")
channel.start_consuming()
