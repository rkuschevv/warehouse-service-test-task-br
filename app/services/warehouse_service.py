from app.models.schemas import KafkaMessage, MovementInfo, WarehouseState
from app.models.database import database, warehouse_states, movements
from datetime import datetime
from sqlalchemy import and_, select
import logging

logger = logging.getLogger(__name__)

async def process_message(message: KafkaMessage):
    """Обрабатывает сообщение из Kafka и обновляет состояние склада"""
    try:
        movement_data = message.data
        warehouse_id = movement_data.warehouse_id
        product_id = movement_data.product_id
        quantity = movement_data.quantity
        event = movement_data.event
        movement_id = movement_data.movement_id
        timestamp = movement_data.timestamp
        
        # Проверяем текущее состояние склада
        current_state = await get_warehouse_state(warehouse_id, product_id)
        
        if event == "departure":
            # Проверяем, есть ли достаточное количество товара для отправки
            if current_state.quantity < quantity:
                logger.error(f"Недостаточно товара на складе {warehouse_id} для продукта {product_id}. Требуется: {quantity}, доступно: {current_state.quantity}")
                return False
            
            # Обновляем количество товара на складе
            new_quantity = current_state.quantity - quantity
            await update_warehouse_state(warehouse_id, product_id, new_quantity)
            
            # Обновляем информацию о перемещении
            await update_movement_departure(movement_id, warehouse_id, product_id, timestamp, quantity)
            
        elif event == "arrival":
            # Обновляем количество товара на складе
            new_quantity = current_state.quantity + quantity
            await update_warehouse_state(warehouse_id, product_id, new_quantity)
            
            # Обновляем информацию о перемещении
            await update_movement_arrival(movement_id, warehouse_id, product_id, timestamp, quantity)
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}")
        return False

async def get_warehouse_state(warehouse_id: str, product_id: str) -> WarehouseState:
    """Получает текущее состояние склада для указанного товара"""
    query = select([warehouse_states]).where(
        and_(
            warehouse_states.c.warehouse_id == warehouse_id,
            warehouse_states.c.product_id == product_id
        )
    )
    
    result = await database.fetch_one(query)
    
    if not result:
        return WarehouseState(
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity=0
        )
    
    return WarehouseState(
        warehouse_id=result["warehouse_id"],
        product_id=result["product_id"],
        quantity=result["quantity"]
    )

async def update_warehouse_state(warehouse_id: str, product_id: str, quantity: int):
    """Обновляет состояние склада"""
    state_id = f"{warehouse_id}:{product_id}"
    
    # Проверяем, существует ли уже запись для этого склада и товара
    query = select([warehouse_states]).where(
        and_(
            warehouse_states.c.warehouse_id == warehouse_id,
            warehouse_states.c.product_id == product_id
        )
    )
    
    result = await database.fetch_one(query)
    
    if result:
        # Обновляем существующую запись
        query = warehouse_states.update().where(
            warehouse_states.c.id == state_id
        ).values(quantity=quantity)
    else:
        # Создаем новую запись
        query = warehouse_states.insert().values(
            id=state_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity=quantity
        )
    
    await database.execute(query)

async def update_movement_departure(movement_id: str, warehouse_id: str, product_id: str, timestamp: datetime, quantity: int):
    """Обновляет информацию о перемещении при отправке товара"""
    # Проверяем, существует ли уже запись для этого перемещения
    query = select([movements]).where(movements.c.movement_id == movement_id)
    movement = await database.fetch_one(query)
    
    if movement:
        # Обновляем существующую запись
        values = {
            "source_warehouse": warehouse_id,
            "departure_time": timestamp,
            "departure_quantity": quantity
        }
        
        # Если уже есть информация о прибытии, вычисляем разницу во времени и количестве
        if movement["arrival_time"]:
            time_diff = (movement["arrival_time"] - timestamp).total_seconds()
            quantity_diff = movement["arrival_quantity"] - quantity
            
            values["time_difference_seconds"] = time_diff
            values["quantity_difference"] = quantity_diff
        
        query = movements.update().where(
            movements.c.movement_id == movement_id
        ).values(**values)
    else:
        # Создаем новую запись
        query = movements.insert().values(
            movement_id=movement_id,
            source_warehouse=warehouse_id,
            product_id=product_id,
            departure_time=timestamp,
            departure_quantity=quantity
        )
    
    await database.execute(query)

async def update_movement_arrival(movement_id: str, warehouse_id: str, product_id: str, timestamp: datetime, quantity: int):
    """Обновляет информацию о перемещении при прибытии товара"""
    # Проверяем, существует ли уже запись для этого перемещения
    query = select([movements]).where(movements.c.movement_id == movement_id)
    movement = await database.fetch_one(query)
    
    if movement:
        # Обновляем существующую запись
        values = {
            "destination_warehouse": warehouse_id,
            "arrival_time": timestamp,
            "arrival_quantity": quantity
        }
        
        # Если уже есть информация об отправке, вычисляем разницу во времени и количестве
        if movement["departure_time"]:
            time_diff = (timestamp - movement["departure_time"]).total_seconds()
            quantity_diff = quantity - movement["departure_quantity"]
            
            values["time_difference_seconds"] = time_diff
            values["quantity_difference"] = quantity_diff
        
        query = movements.update().where(
            movements.c.movement_id == movement_id
        ).values(**values)
    else:
        # Создаем новую запись
        query = movements.insert().values(
            movement_id=movement_id,
            destination_warehouse=warehouse_id,
            product_id=product_id,
            arrival_time=timestamp,
            arrival_quantity=quantity
        )
    
    await database.execute(query)

async def get_movement_info(movement_id: str) -> MovementInfo:
    """Получает информацию о перемещении по его ID"""
    query = select([movements]).where(movements.c.movement_id == movement_id)
    result = await database.fetch_one(query)
    
    if not result:
        return None
    
    return MovementInfo(
        movement_id=result["movement_id"],
        source_warehouse=result["source_warehouse"],
        destination_warehouse=result["destination_warehouse"],
        product_id=result["product_id"],
        departure_time=result["departure_time"],
        arrival_time=result["arrival_time"],
        time_difference_seconds=result["time_difference_seconds"],
        departure_quantity=result["departure_quantity"],
        arrival_quantity=result["arrival_quantity"],
        quantity_difference=result["quantity_difference"]
    ) 