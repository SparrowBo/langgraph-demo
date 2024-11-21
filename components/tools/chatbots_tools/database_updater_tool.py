import os
import shutil
import sqlite3
import pandas as pd
import requests

class DatabaseUpdaterTool:
    def __init__(self, db_url=None, local_file=None, backup_file=None, overwrite=False):
        self.db_url = db_url or "https://storage.googleapis.com/benchmarks-artifacts/travel-db/travel2.sqlite"
        self.local_file = local_file or "travel2.sqlite"
        self.backup_file = backup_file or "travel2.backup.sqlite"
        self.overwrite = overwrite
        self._download_and_prepare_db()
    
    def _download_and_prepare_db(self):
        if self.overwrite or not os.path.exists(self.local_file):
            response = requests.get(self.db_url)
            response.raise_for_status()  # 确保请求成功
            with open(self.local_file, "wb") as f:
                f.write(response.content)
            # 备份数据库，以便在每个部分重置
            shutil.copy(self.local_file, self.backup_file)
    
    def update_dates(self, file_path=None, init_db=True):
        """将航班日期更新为当前时间，以便在教程中使用。"""
        if file_path is None:
            file_path = self.local_file
        if not init_db:
            return file_path
        shutil.copy(self.backup_file, file_path)
        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()
    
        tables = pd.read_sql(
            "SELECT name FROM sqlite_master WHERE type='table';", conn
        ).name.tolist()
        tdf = {}
        for t in tables:
            tdf[t] = pd.read_sql(f"SELECT * from {t}", conn)
    
        example_time = pd.to_datetime(
            tdf["flights"]["actual_departure"].replace("\\N", pd.NaT)
        ).max()
        current_time = pd.to_datetime("now").tz_localize(example_time.tz)
        time_diff = current_time - example_time
    
        tdf["bookings"]["book_date"] = (
            pd.to_datetime(tdf["bookings"]["book_date"].replace("\\N", pd.NaT), utc=True)
            + time_diff
        )
    
        datetime_columns = [
            "scheduled_departure",
            "scheduled_arrival",
            "actual_departure",
            "actual_arrival",
        ]
        for column in datetime_columns:
            tdf["flights"][column] = (
                pd.to_datetime(tdf["flights"][column].replace("\\N", pd.NaT)) + time_diff
            )
    
        for table_name, df in tdf.items():
            df.to_sql(table_name, conn, if_exists="replace", index=False)
        del df
        del tdf
        conn.commit()
        conn.close()
    
        return file_path
    
# from database_updater_tool import DatabaseUpdaterTool

# # 实例化工具类
# db_tool = DatabaseUpdaterTool()

# # 更新数据库日期
# updated_db = db_tool.update_dates()

# # 现在您可以使用 'updated_db'，这是更新后的数据库文件路径
# print(f"数据库已更新：{updated_db}")