from typing import Optional, TypeVar, Generic, Any
from sqlmodel import SQLModel
from pydantic import BaseModel

from app.models.response_code import ResponseCode


# 定义数据类型变量
DataT = TypeVar("DataT")


class StandardResponse(SQLModel, Generic[DataT]):
    """
    统一响应格式模型
    {
        "code": 0 | non-zero,
        "data": any,
        "msg": str
    }
    """
    code: int
    data: Optional[DataT] = None
    msg: str = "success"


# 创建具体类型的响应模型别名，便于使用
SuccessResponse = StandardResponse[DataT]


# 工具函数用于创建标准响应
def success_response(data: Optional[DataT] = None, msg: str = "success") -> StandardResponse[DataT]:
    """创建成功响应"""
    return StandardResponse(code=ResponseCode.SUCCESS, data=data, msg=msg)


def error_response(code: int, msg: str = "error", data: Optional[Any] = None) -> StandardResponse[Any]:
    """创建错误响应"""
    return StandardResponse(code=code, data=data, msg=msg)