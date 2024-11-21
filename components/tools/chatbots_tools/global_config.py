from typing import Optional

class GlobalConfig:
    global_db = None
    global_retriever = None

    @staticmethod
    def set_global_db(db_path: str):
        """设置全局数据库路径"""
        GlobalConfig.global_db = db_path

    @staticmethod
    def get_global_db() -> Optional[str]:
        """获取全局数据库路径"""
        return GlobalConfig.global_db

    @staticmethod
    def set_global_retriever(retriever):
        """设置全局检索器"""
        GlobalConfig.global_retriever = retriever

    @staticmethod
    def get_global_retriever():
        """获取全局检索器"""
        return GlobalConfig.global_retriever
