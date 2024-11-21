import sqlite3
from datetime import date, datetime
from typing import Optional, Union
from components.tools.chatbots_tools.global_config import GlobalConfig
from langchain_core.tools import tool

class CarRentalServiceTool:
    def __init__(self, db_path: str):
        GlobalConfig.set_global_db(db_path)

    @tool
    def search_car_rentals(
        location: Optional[str] = None,
        name: Optional[str] = None,
        price_tier: Optional[str] = None,
        start_date: Optional[Union[datetime, date]] = None,
        end_date: Optional[Union[datetime, date]] = None,
    ) -> list[dict]:
        """
        根据位置、名称、价格等级、开始日期和结束日期搜索汽车租赁。

        Args:
            location (Optional[str]): 汽车租赁的地点。默认为 None。
            name (Optional[str]): 汽车租赁公司的名称。默认为 None。
            price_tier (Optional[str]): 汽车租赁的价格等级。默认为 None。
            start_date (Optional[Union[datetime, date]]): 汽车租赁的开始日期。默认为 None。
            end_date (Optional[Union[datetime, date]]): 汽车租赁的结束日期。默认为 None。

        Returns:
            list[dict]: 匹配搜索条件的汽车租赁字典列表。
        """
        conn = sqlite3.connect(GlobalConfig.get_global_db())
        cursor = conn.cursor()

        query = "SELECT * FROM car_rentals WHERE 1=1"
        params = []

        if location:
            query += " AND location LIKE ?"
            params.append(f"%{location}%")
        if name:
            query += " AND name LIKE ?"
            params.append(f"%{name}%")
        # 在教程中，我们允许匹配任何日期和价格等级。
        # （因为我们的示例数据集数据有限）
        cursor.execute(query, params)
        results = cursor.fetchall()
        column_names = [column[0] for column in cursor.description]

        conn.close()

        return [dict(zip(column_names, row)) for row in results]

    @tool
    def book_car_rental(rental_id: int) -> str:
        """
        通过其ID预订汽车租赁。

        Args:
            rental_id (int): 要预订的汽车租赁的ID。

        Returns:
            str: 指示汽车租赁是否成功预订的消息。
        """
        conn = sqlite3.connect(GlobalConfig.get_global_db())
        cursor = conn.cursor()

        cursor.execute("UPDATE car_rentals SET booked = 1 WHERE id = ?", (rental_id,))
        conn.commit()

        if cursor.rowcount > 0:
            conn.close()
            return f"Car rental {rental_id} successfully booked."
        else:
            conn.close()
            return f"No car rental found with ID {rental_id}."

    @tool
    def update_car_rental(
        rental_id: int,
        start_date: Optional[Union[datetime, date]] = None,
        end_date: Optional[Union[datetime, date]] = None,
    ) -> str:
        """
        通过其ID更新汽车租赁的开始和结束日期。

        Args:
            rental_id (int): 要更新的汽车租赁的ID。
            start_date (Optional[Union[datetime, date]]): 新的开始日期。默认为 None。
            end_date (Optional[Union[datetime, date]]): 新的结束日期。默认为 None。

        Returns:
            str: 指示汽车租赁是否成功更新的消息。
        """
        conn = sqlite3.connect(GlobalConfig.get_global_db())
        cursor = conn.cursor()

        if start_date:
            cursor.execute(
                "UPDATE car_rentals SET start_date = ? WHERE id = ?",
                (start_date, rental_id),
            )
        if end_date:
            cursor.execute(
                "UPDATE car_rentals SET end_date = ? WHERE id = ?", (end_date, rental_id)
            )

        conn.commit()

        if cursor.rowcount > 0:
            conn.close()
            return f"Car rental {rental_id} successfully updated."
        else:
            conn.close()
            return f"No car rental found with ID {rental_id}."

    @tool
    def cancel_car_rental(rental_id: int) -> str:
        """
        通过其ID取消汽车租赁。

        Args:
            rental_id (int): 要取消的汽车租赁的ID。

        Returns:
            str: 指示汽车租赁是否成功取消的消息。
        """
        conn = sqlite3.connect(GlobalConfig.get_global_db())
        cursor = conn.cursor()

        cursor.execute("UPDATE car_rentals SET booked = 0 WHERE id = ?", (rental_id,))
        conn.commit()

        if cursor.rowcount > 0:
            conn.close()
            return f"Car rental {rental_id} successfully cancelled."
        else:
            conn.close()
            return f"No car rental found with ID {rental_id}."

# from car_rental_service_tool import CarRentalServiceTool

# # 初始化工具类，提供您的SQLite数据库路径
# db_path = '您的数据库路径/travel2.sqlite'
# car_rental_tool = CarRentalServiceTool(db_path)

# # 搜索汽车租赁
# available_rentals = car_rental_tool.search_car_rentals(
#     location='New York',
#     name='Budget',
#     price_tier='Economy',
#     start_date='2023-10-01',
#     end_date='2023-10-07'
# )
# print(available_rentals)

# # 预订汽车租赁
# booking_result = car_rental_tool.book_car_rental(rental_id=1)
# print(booking_result)

# # 更新汽车租赁日期
# update_result = car_rental_tool.update_car_rental(
#     rental_id=1,
#     start_date='2023-10-02',
#     end_date='2023-10-08'
# )
# print(update_result)

# # 取消汽车租赁
# cancel_result = car_rental_tool.cancel_car_rental(rental_id=1)
# print(cancel_result)
