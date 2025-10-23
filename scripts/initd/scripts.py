from sqlmodel import create_engine, SQLModel

from app.config import settings
from app.models.RPA_browser.models import UserBrowserInfo

def create_tables():
    engin = create_engine(
        url=settings.mysql_browser_info_url.replace('aiomysql', 'pymysql')  # 这里用的是同步创建数据库表的方法，毕竟只需要运行一次
    )
    SQLModel.metadata.create_all(engin)


if __name__ == '__main__':
    create_tables()
