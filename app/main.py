from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel
from typing import Optional, Dict, List, Callable
import logging
from functools import lru_cache
import time
import json

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Сервис мониторинга состояния складов",
    description="Микросервис для мониторинга состояния складов",
    version="1.0.0",
)

# Временное хранилище данных (в реальном приложении заменить на базу данных)
warehouses = {}
movements = {}
request_metrics = {
    "total_requests": 0,
    "success_requests": 0,
    "error_requests": 0,
    "avg_response_time": 0
}

class WarehouseState(BaseModel):    
    warehouse_id: str
    product_id: str
    quantity: int

class MovementInfo(BaseModel):
    movement_id: str
    source_warehouse: Optional[str] = None
    destination_warehouse: Optional[str] = None
    product_id: str
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    time_difference_seconds: Optional[float] = None
    departure_quantity: Optional[int] = None
    arrival_quantity: Optional[int] = None
    quantity_difference: Optional[int] = None

class Metrics(BaseModel):
    total_requests: int
    success_requests: int
    error_requests: int
    avg_response_time: float

# Middleware для мониторинга запросов и логирования
@app.middleware("http")
async def monitor_requests(request: Request, call_next: Callable) -> Response:
    start_time = time.time()
    response = None
    
    # Увеличиваем счетчик общего количества запросов
    request_metrics["total_requests"] += 1
    
    try:
        response = await call_next(request)
        
        # Если запрос успешный, увеличиваем счетчик успешных запросов
        if response.status_code < 400:
            request_metrics["success_requests"] += 1
        else:
            request_metrics["error_requests"] += 1
            
        # Логируем информацию о запросе
        process_time = time.time() - start_time
        
        # Обновляем среднее время ответа
        current_avg = request_metrics["avg_response_time"]
        total_requests = request_metrics["total_requests"]
        request_metrics["avg_response_time"] = (current_avg * (total_requests - 1) + process_time) / total_requests
        
        logger.info(f"{request.method} {request.url.path} {response.status_code} {process_time:.4f}s")
        
        return response
    except Exception as e:
        # Если произошла ошибка, увеличиваем счетчик ошибок
        request_metrics["error_requests"] += 1
        
        # Логируем ошибку
        logger.error(f"Ошибка при обработке запроса {request.method} {request.url.path}: {str(e)}")
        
        # Если не был создан ответ, создаем ответ с ошибкой
        if response is None:
            response = Response(content=json.dumps({"detail": str(e)}), status_code=500, media_type="application/json")
            
        return response

# Добавляем кэширование для улучшения производительности
@lru_cache(maxsize=100)
def get_movement_cached(movement_id: str) -> Optional[MovementInfo]:
    """Кэшируемая функция для получения информации о перемещении"""
    return movements.get(movement_id)

@lru_cache(maxsize=100)
def get_warehouse_state_cached(warehouse_key: str) -> Optional[WarehouseState]:
    """Кэшируемая функция для получения состояния склада"""
    return warehouses.get(warehouse_key)

@app.get("/api/movements/{movement_id}", response_model=MovementInfo)
async def read_movement(movement_id: str):
    """
    Получение информации о перемещении товара по ID
    """
    movement = get_movement_cached(movement_id)
    if movement is None:
        # Если данных нет в кэше, пробуем получить напрямую
        movement = movements.get(movement_id)
        if movement is None:
            raise HTTPException(status_code=404, detail="Перемещение не найдено")
    return movement

@app.get("/api/warehouses/{warehouse_id}/products/{product_id}", response_model=WarehouseState)
async def read_warehouse_state(warehouse_id: str, product_id: str):
    """
    Получение информации о текущем запасе товара на складе
    """
    warehouse_key = f"{warehouse_id}:{product_id}"
    state = get_warehouse_state_cached(warehouse_key)
    if state is None:
        # Если данных нет в кэше, возвращаем нулевое количество
        return WarehouseState(warehouse_id=warehouse_id, product_id=product_id, quantity=0)
    return state

@app.get("/api/metrics", response_model=Metrics)
async def get_metrics():
    """
    Получение метрик производительности API
    """
    return request_metrics

@app.get("/")
async def root():
    return {"message": "Сервис мониторинга состояния складов"}

@app.get("/health")
async def health_check():
    """Проверка состояния приложения"""
    return {"status": "ok"}

# Функция для очистки кэша при обновлении данных
def invalidate_cache():
    """Очищает кэш"""
    get_movement_cached.cache_clear()
    get_warehouse_state_cached.cache_clear()
    logger.info("Кэш очищен")

# Для тестирования добавим тестовые данные
@app.on_event("startup")
async def startup_event():
    logger.info("Запуск приложения...")
    
    # Добавляем тестовое перемещение
    movement_id = "test-movement-1"
    movements[movement_id] = MovementInfo(
        movement_id=movement_id,
        source_warehouse="WH-1",
        destination_warehouse="WH-2",
        product_id="PROD-1",
        departure_time="2023-04-01T10:00:00",
        arrival_time="2023-04-01T12:00:00",
        time_difference_seconds=7200.0,
        departure_quantity=50,
        arrival_quantity=50,
        quantity_difference=0
    )
    
    # Добавляем тестовое состояние склада
    warehouse_key = "WH-1:PROD-1"
    warehouses[warehouse_key] = WarehouseState(
        warehouse_id="WH-1",
        product_id="PROD-1",
        quantity=100
    )
    
    # Добавляем еще один тестовый склад
    warehouse_key = "WH-2:PROD-1"
    warehouses[warehouse_key] = WarehouseState(
        warehouse_id="WH-2",
        product_id="PROD-1",
        quantity=50
    )
    
    logger.info("Приложение запущено")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Приложение остановлено")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True) 