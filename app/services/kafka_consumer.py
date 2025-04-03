import json
import threading
from kafka import KafkaConsumer
from app.models.schemas import KafkaMessage
from app.services.warehouse_service import process_message
import asyncio
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class KafkaConsumerService:
    def __init__(self, bootstrap_servers, topic, loop=None):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.consumer = None
        self.loop = loop or asyncio.get_event_loop()
        self.should_stop = False
        
    def start(self):
        """Запускает потребителя Kafka в отдельном потоке"""
        threading.Thread(target=self._consume, daemon=True).start()
        logger.info(f"Запущен Kafka-потребитель для темы {self.topic}")
        
    def stop(self):
        """Останавливает потребителя Kafka"""
        self.should_stop = True
        logger.info(f"Остановлен Kafka-потребитель для темы {self.topic}")
        
    def _consume(self):
        """Потребляет сообщения из Kafka и обрабатывает их"""
        try:
            self.consumer = KafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                group_id='warehouse-service',
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )
            
            for message in self.consumer:
                if self.should_stop:
                    break
                
                try:
                    kafka_message = KafkaMessage(**message.value)
                    future = asyncio.run_coroutine_threadsafe(
                        process_message(kafka_message), 
                        self.loop
                    )
                    result = future.result()  # Ждем результата обработки сообщения
                    
                    if result:
                        logger.info(f"Успешно обработано сообщение: {kafka_message.data.movement_id}")
                    else:
                        logger.warning(f"Не удалось обработать сообщение: {kafka_message.data.movement_id}")
                        
                except Exception as e:
                    logger.error(f"Ошибка при обработке сообщения Kafka: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка при подключении к Kafka: {e}")
            
        finally:
            if self.consumer:
                self.consumer.close() 