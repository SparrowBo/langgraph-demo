import sqlite3
from typing import Optional
from langchain_core.tools import tool
from components.tools.chatbots_tools.global_config import GlobalConfig

class TripRecommendationTool:
    def __init__(self, db_path: str):
        GlobalConfig.set_global_db(db_path)

    @tool
    def search_trip_recommendations(
        location: Optional[str] = None,
        name: Optional[str] = None,
        keywords: Optional[str] = None,
    ) -> list[dict]:
        """
        根据位置、名称和关键字搜索旅行推荐。

        Args:
            location (Optional[str]): 旅行推荐的位置。默认为 None。
            name (Optional[str]): 旅行推荐的名称。默认为 None。
            keywords (Optional[str]): 与旅行推荐相关的关键字。默认为 None。

        Returns:
            list[dict]: 匹配搜索条件的旅行推荐字典列表。
        """
        conn = sqlite3.connect(GlobalConfig.get_global_db())
        cursor = conn.cursor()

        query = "SELECT * FROM trip_recommendations WHERE 1=1"
        params = []

        if location:
            query += " AND location LIKE ?"
            params.append(f"%{location}%")
        if name:
            query += " AND name LIKE ?"
            params.append(f"%{name}%")
        if keywords:
            keyword_list = keywords.split(",")
            keyword_conditions = " OR ".join(["keywords LIKE ?" for _ in keyword_list])
            query += f" AND ({keyword_conditions})"
            params.extend([f"%{keyword.strip()}%" for keyword in keyword_list])

        cursor.execute(query, params)
        results = cursor.fetchall()
        column_names = [column[0] for column in cursor.description]

        conn.close()

        return [dict(zip(column_names, row)) for row in results]

    @tool
    def book_excursion(recommendation_id: int) -> str:
        """
        通过推荐ID预订游览。

        Args:
            recommendation_id (int): 要预订的旅行推荐的ID。

        Returns:
            str: 指示旅行推荐是否成功预订的消息。
        """
        conn = sqlite3.connect(GlobalConfig.get_global_db())
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE trip_recommendations SET booked = 1 WHERE id = ?",
            (recommendation_id,)
        )
        conn.commit()

        if cursor.rowcount > 0:
            conn.close()
            return f"Trip recommendation {recommendation_id} successfully booked."
        else:
            conn.close()
            return f"No trip recommendation found with ID {recommendation_id}."

    @tool
    def update_excursion(recommendation_id: int, details: str) -> str:
        """
        通过ID更新旅行推荐的详细信息。

        Args:
            recommendation_id (int): 要更新的旅行推荐的ID。
            details (str): 旅行推荐的新详细信息。

        Returns:
            str: 指示旅行推荐是否成功更新的消息。
        """
        conn = sqlite3.connect(GlobalConfig.get_global_db())
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE trip_recommendations SET details = ? WHERE id = ?",
            (details, recommendation_id),
        )
        conn.commit()

        if cursor.rowcount > 0:
            conn.close()
            return f"Trip recommendation {recommendation_id} successfully updated."
        else:
            conn.close()
            return f"No trip recommendation found with ID {recommendation_id}."

    @tool
    def cancel_excursion(recommendation_id: int) -> str:
        """
        通过ID取消旅行推荐。

        Args:
            recommendation_id (int): 要取消的旅行推荐的ID。

        Returns:
            str: 指示旅行推荐是否成功取消的消息。
        """
        conn = sqlite3.connect(GlobalConfig.get_global_db())
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE trip_recommendations SET booked = 0 WHERE id = ?",
            (recommendation_id,)
        )
        conn.commit()

        if cursor.rowcount > 0:
            conn.close()
            return f"Trip recommendation {recommendation_id} successfully cancelled."
        else:
            conn.close()
            return f"No trip recommendation found with ID {recommendation_id}."
        
# from trip_recommendation_tool import TripRecommendationTool

# # 初始化工具类，提供您的SQLite数据库路径
# db_path = '您的数据库路径/travel2.sqlite'
# trip_tool = TripRecommendationTool(db_path)

# # 搜索旅行推荐
# recommendations = trip_tool.search_trip_recommendations(
#     location='Paris',
#     keywords='museum, art, history'
# )
# print(recommendations)

# # 预订游览
# booking_result = trip_tool.book_excursion(recommendation_id=1)
# print(booking_result)

# # 更新游览详情
# update_result = trip_tool.update_excursion(
#     recommendation_id=1,
#     details='Updated details about the excursion.'
# )
# print(update_result)

# # 取消游览
# cancel_result = trip_tool.cancel_excursion(recommendation_id=1)
# print(cancel_result)

