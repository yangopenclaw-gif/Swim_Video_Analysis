import logging
from typing import Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)

ARCHIVE_PASSWORD = "ycz"


class ArchiveProtector:

    @staticmethod
    def verify_password(password: str) -> bool:
        return password == ARCHIVE_PASSWORD

    @staticmethod
    def require_password_if_archived(record, password: Optional[str] = None) -> None:
        if record.archived != 1:
            return
        if password is None or password == "":
            raise HTTPException(status_code=403, detail="需要密码验证")
        if not ArchiveProtector.verify_password(password):
            raise HTTPException(status_code=403, detail="密码错误")