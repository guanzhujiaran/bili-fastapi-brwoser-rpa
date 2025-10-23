from fastapi import Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from app.models.response import StandardResponse
from app.models.response_code import ResponseCode


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """处理HTTP异常，如404等"""
    if exc.status_code == 404:
        response = StandardResponse(
            code=ResponseCode.NOT_FOUND,
            data=None,
            msg="API endpoint not found"
        )
    else:
        # 对于其他HTTP异常，也进行统一包装
        response = StandardResponse(
            code=exc.status_code,
            data=None,
            msg=exc.detail or "Error occurred"
        )

    return JSONResponse(
        content=response.model_dump(),
        status_code=exc.status_code
    )

