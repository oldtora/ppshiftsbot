"""Генерация 50 одноразовых ключей активации. Результат — в data/keys.txt и в БД."""
import asyncio
import secrets
import os
import sys

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import init_db, add_keys_batch

KEY_LENGTH = 16  # символов
KEY_COUNT = 50


def generate_keys(n: int = KEY_COUNT) -> list[str]:
    """Сгенерировать n уникальных ключей (буквы и цифры)."""
    keys = set()
    while len(keys) < n:
        keys.add(secrets.token_hex(KEY_LENGTH // 2)[:KEY_LENGTH])
    return list(keys)


async def main():
    await init_db()
    keys = generate_keys(KEY_COUNT)
    await add_keys_batch(keys)
    os.makedirs("data", exist_ok=True)
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "keys.txt")
    with open(path, "w", encoding="utf-8") as f:
        for k in keys:
            f.write(k + "\n")
    print(f"Создано {len(keys)} ключей. Файл: {path}")
    print("Примеры (первые 3):")
    for k in keys[:3]:
        print(f"  {k}")


if __name__ == "__main__":
    asyncio.run(main())
