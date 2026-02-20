FROM python:3.10-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование файлов бота
COPY . .

# Создание директории для JSON файлов
RUN mkdir -p /app/data

# Установка переменных окружения
ENV PYTHONUNBUFFERED=1

# Запуск бота
CMD ["python", "main.py"] 