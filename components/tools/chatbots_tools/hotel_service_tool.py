import sqlite3
from datetime import date, datetime
from typing import Optional, Union
from components.tools.chatbots_tools.global_config import GlobalConfig
from langchain_core.tools import tool

class HotelServiceTool:
    def __init__(self, db_path: str):
        GlobalConfig.set_global_db(db_path)
        
    @tool
    def search_hotels(
        location: Optional[str] = None,
        name: Optional[str] = None,
        price_tier: Optional[str] = None,
        checkin_date: Optional[Union[datetime, date]] = None,
        checkout_date: Optional[Union[datetime, date]] = None,
    ) -> list[dict]:
        """
        根据位置、名称、价格等级、入住日期和退房日期搜索酒店。

        Args:
            location (Optional[str]): 酒店的位置。默认为 None。
            name (Optional[str]): 酒店的名称。默认为 None。
            price_tier (Optional[str]): 酒店的价格等级。默认为 None。示例：Midscale, Upper Midscale, Upscale, Luxury
            checkin_date (Optional[Union[datetime, date]]): 酒店的入住日期。默认为 None。
            checkout_date (Optional[Union[datetime, date]]): 酒店的退房日期。默认为 None。

        Returns:
            list[dict]: 匹配搜索条件的酒店字典列表。
        """
        conn = sqlite3.connect(GlobalConfig.get_global_db())
        cursor = conn.cursor()

        query = "SELECT * FROM hotels WHERE 1=1"
        params = []

        if location:
            query += " AND location LIKE ?"
            params.append(f"%{location}%")
        if name:
            query += " AND name LIKE ?"
            params.append(f"%{name}%")
        # 为了本教程的目的，我们允许匹配任何日期和价格等级。
        cursor.execute(query, params)
        results = cursor.fetchall()
        column_names = [column[0] for column in cursor.description]

        conn.close()

        return [dict(zip(column_names, row)) for row in results]

    @tool
    def book_hotel(hotel_id: int) -> str:
        """
        通过酒店ID预订酒店。

        Args:
            hotel_id (int): 要预订的酒店的ID。

        Returns:
            str: 指示酒店是否成功预订的消息。
        """
        conn = sqlite3.connect(GlobalConfig.get_global_db())
        cursor = conn.cursor()

        cursor.execute("UPDATE hotels SET booked = 1 WHERE id = ?", (hotel_id,))
        conn.commit()

        if cursor.rowcount > 0:
            conn.close()
            return f"Hotel {hotel_id} successfully booked."
        else:
            conn.close()
            return f"No hotel found with ID {hotel_id}."

    @tool
    def update_hotel(
        hotel_id: int,
        checkin_date: Optional[Union[datetime, date]] = None,
        checkout_date: Optional[Union[datetime, date]] = None,
    ) -> str:
        """
        通过酒店ID更新酒店的入住和退房日期。

        Args:
            hotel_id (int): 要更新的酒店的ID。
            checkin_date (Optional[Union[datetime, date]]): 新的入住日期。默认为 None。
            checkout_date (Optional[Union[datetime, date]]): 新的退房日期。默认为 None。

        Returns:
            str: 指示酒店是否成功更新的消息。
        """
        conn = sqlite3.connect(GlobalConfig.get_global_db())
        cursor = conn.cursor()

        if checkin_date:
            cursor.execute(
                "UPDATE hotels SET checkin_date = ? WHERE id = ?", (checkin_date, hotel_id)
            )
        if checkout_date:
            cursor.execute(
                "UPDATE hotels SET checkout_date = ? WHERE id = ?",
                (checkout_date, hotel_id),
            )

        conn.commit()

        if cursor.rowcount > 0:
            conn.close()
            return f"Hotel {hotel_id} successfully updated."
        else:
            conn.close()
            return f"No hotel found with ID {hotel_id}."

    @tool
    def cancel_hotel(hotel_id: int) -> str:
        """
        通过酒店ID取消酒店预订。

        Args:
            hotel_id (int): 要取消的酒店的ID。

        Returns:
            str: 指示酒店是否成功取消的消息。
        """
        conn = sqlite3.connect(GlobalConfig.get_global_db())
        cursor = conn.cursor()

        cursor.execute("UPDATE hotels SET booked = 0 WHERE id = ?", (hotel_id,))
        conn.commit()

        if cursor.rowcount > 0:
            conn.close()
            return f"Hotel {hotel_id} successfully cancelled."
        else:
            conn.close()
            return f"No hotel found with ID {hotel_id}."

# from hotel_service_tool import HotelServiceTool

# # 初始化工具类，提供您的SQLite数据库路径
# db_path = '您的数据库路径/travel2.sqlite'
# hotel_tool = HotelServiceTool(db_path)

# # 搜索酒店
# available_hotels = hotel_tool.search_hotels(
#     location='New York',
#     name='Hilton',
#     price_tier='Luxury',
#     checkin_date='2023-10-01',
#     checkout_date='2023-10-05'
# )
# print(available_hotels)

# # 预订酒店
# booking_result = hotel_tool.book_hotel(hotel_id=1)
# print(booking_result)

# # 更新酒店预订日期
# update_result = hotel_tool.update_hotel(
#     hotel_id=1,
#     checkin_date='2023-10-02',
#     checkout_date='2023-10-06'
# )
# print(update_result)

# # 取消酒店预订
# cancel_result = hotel_tool.cancel_hotel(hotel_id=1)
# print(cancel_result)
