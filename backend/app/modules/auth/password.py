import asyncio
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


async def hash_password(password: str) -> str:
    """在线程池中执行 Argon2id 哈希，避免阻塞事件循环。"""

    return await asyncio.to_thread(_hasher.hash, password)


async def verify_password(password_hash: str, password: str) -> bool:
    """在线程池中验证密码。"""

    try:
        return await asyncio.to_thread(_hasher.verify, password_hash, password)
    except VerifyMismatchError:
        return False
