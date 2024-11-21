import sqlite3
from datetime import date, datetime
from typing import Union, Optional
from components.tools.chatbots_tools.global_config import GlobalConfig
import pytz
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool


class FlightServiceTool:
    def __init__(self, db_path: str):
        GlobalConfig.set_global_db(db_path)

    @tool
    def fetch_user_flight_information(config: RunnableConfig) -> list[dict]:
        """获取用户的所有机票及对应的航班信息和座位分配。

        Args:
            config (RunnableConfig): 包含 'passenger_id' 的配置。

        Returns:
            list[dict]: 包含机票详情、航班信息和座位分配的字典列表。
        """
        configuration = config.get("configurable", {})
        passenger_id = configuration.get("passenger_id", None)
        if not passenger_id:
            raise ValueError("No passenger ID configured.")

        conn = sqlite3.connect(GlobalConfig.get_global_db())
        cursor = conn.cursor()

        query = """
        SELECT 
            t.ticket_no, t.book_ref,
            f.flight_id, f.flight_no, f.departure_airport, f.arrival_airport, f.scheduled_departure, f.scheduled_arrival,
            bp.seat_no, tf.fare_conditions
        FROM 
            tickets t
            JOIN ticket_flights tf ON t.ticket_no = tf.ticket_no
            JOIN flights f ON tf.flight_id = f.flight_id
            JOIN boarding_passes bp ON bp.ticket_no = t.ticket_no AND bp.flight_id = f.flight_id
        WHERE 
            t.passenger_id = ?
        """
        cursor.execute(query, (passenger_id,))
        rows = cursor.fetchall()
        column_names = [column[0] for column in cursor.description]
        results = [dict(zip(column_names, row)) for row in rows]

        cursor.close()
        conn.close()

        return results

    @tool
    def search_flights(
        departure_airport: Optional[str] = None,
        arrival_airport: Optional[str] = None,
        start_time: Optional[Union[date, datetime]] = None,
        end_time: Optional[Union[date, datetime]] = None,
        limit: int = 20,
    ) -> list[dict]:
        """根据出发机场、到达机场和出发时间范围搜索航班。

        Args:
            departure_airport (Optional[str]): 出发机场代码。
            arrival_airport (Optional[str]): 到达机场代码。
            start_time (Optional[Union[date, datetime]]): 开始时间。
            end_time (Optional[Union[date, datetime]]): 结束时间。
            limit (int): 返回结果的最大数量。

        Returns:
            list[dict]: 航班信息的字典列表。
        """
        conn = sqlite3.connect(GlobalConfig.get_global_db())
        cursor = conn.cursor()

        query = "SELECT * FROM flights WHERE 1 = 1"
        params = []

        if departure_airport:
            query += " AND departure_airport = ?"
            params.append(departure_airport)

        if arrival_airport:
            query += " AND arrival_airport = ?"
            params.append(arrival_airport)

        if start_time:
            query += " AND scheduled_departure >= ?"
            params.append(start_time)

        if end_time:
            query += " AND scheduled_departure <= ?"
            params.append(end_time)
        query += " LIMIT ?"
        params.append(limit)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        column_names = [column[0] for column in cursor.description]
        results = [dict(zip(column_names, row)) for row in rows]

        cursor.close()
        conn.close()

        return results

    @tool
    def update_ticket_to_new_flight(
        ticket_no: str,
        new_flight_id: int,
        *,
        config: RunnableConfig
    ) -> str:
        """将用户的机票更新为新的有效航班。

        Args:
            ticket_no (str): 机票号码。
            new_flight_id (int): 新的航班ID。
            config (RunnableConfig): 包含 'passenger_id' 的配置。

        Returns:
            str: 操作结果信息。
        """
        configuration = config.get("configurable", {})
        passenger_id = configuration.get("passenger_id", None)
        if not passenger_id:
            raise ValueError("No passenger ID configured.")

        conn = sqlite3.connect(GlobalConfig.get_global_db())
        cursor = conn.cursor()

        cursor.execute(
            "SELECT departure_airport, arrival_airport, scheduled_departure FROM flights WHERE flight_id = ?",
            (new_flight_id,),
        )
        new_flight = cursor.fetchone()
        if not new_flight:
            cursor.close()
            conn.close()
            return "Invalid new flight ID provided."
        column_names = [column[0] for column in cursor.description]
        new_flight_dict = dict(zip(column_names, new_flight))
        timezone = pytz.timezone("Etc/GMT-3")
        current_time = datetime.now(tz=timezone)
        departure_time = datetime.strptime(
            new_flight_dict["scheduled_departure"], "%Y-%m-%d %H:%M:%S.%f%z"
        )
        time_until = (departure_time - current_time).total_seconds()
        if time_until < (3 * 3600):
            return f"Not permitted to reschedule to a flight that is less than 3 hours from the current time. Selected flight is at {departure_time}."

        cursor.execute(
            "SELECT flight_id FROM ticket_flights WHERE ticket_no = ?", (ticket_no,)
        )
        current_flight = cursor.fetchone()
        if not current_flight:
            cursor.close()
            conn.close()
            return "No existing ticket found for the given ticket number."

        # 检查当前登录的用户是否拥有这张机票
        cursor.execute(
            "SELECT * FROM tickets WHERE ticket_no = ? AND passenger_id = ?",
            (ticket_no, passenger_id),
        )
        current_ticket = cursor.fetchone()
        if not current_ticket:
            cursor.close()
            conn.close()
            return f"Current signed-in passenger with ID {passenger_id} not the owner of ticket {ticket_no}"

        # 您可以在此添加其他业务逻辑检查

        cursor.execute(
            "UPDATE ticket_flights SET flight_id = ? WHERE ticket_no = ?",
            (new_flight_id, ticket_no),
        )
        conn.commit()

        cursor.close()
        conn.close()
        return "Ticket successfully updated to new flight."

    @tool
    def cancel_ticket(ticket_no: str, *, config: RunnableConfig) -> str:
        """取消用户的机票并从数据库中删除。

        Args:
            ticket_no (str): 机票号码。
            config (RunnableConfig): 包含 'passenger_id' 的配置。

        Returns:
            str: 操作结果信息。
        """
        configuration = config.get("configurable", {})
        passenger_id = configuration.get("passenger_id", None)
        if not passenger_id:
            raise ValueError("No passenger ID configured.")
        conn = sqlite3.connect(GlobalConfig.get_global_db())
        cursor = conn.cursor()

        cursor.execute(
            "SELECT flight_id FROM ticket_flights WHERE ticket_no = ?", (ticket_no,)
        )
        existing_ticket = cursor.fetchone()
        if not existing_ticket:
            cursor.close()
            conn.close()
            return "No existing ticket found for the given ticket number."

        # 检查当前登录的用户是否拥有这张机票
        cursor.execute(
            "SELECT flight_id FROM tickets WHERE ticket_no = ? AND passenger_id = ?",
            (ticket_no, passenger_id),
        )
        current_ticket = cursor.fetchone()
        if not current_ticket:
            cursor.close()
            conn.close()
            return f"Current signed-in passenger with ID {passenger_id} not the owner of ticket {ticket_no}"

        cursor.execute("DELETE FROM ticket_flights WHERE ticket_no = ?", (ticket_no,))
        conn.commit()

        cursor.close()
        conn.close()
        return "Ticket successfully cancelled."

# from flight_service_tool import FlightServiceTool
# from langchain_core.runnables import RunnableConfig

# # 初始化工具类，提供您的SQLite数据库路径
# db_path = '您的数据库路径/travel2.sqlite'
# flight_tool = FlightServiceTool(db_path)

# # 配置，包含乘客ID
# config = RunnableConfig(configurable={'passenger_id': '123456789'})

# # 获取用户的航班信息
# user_flights = flight_tool.fetch_user_flight_information(config=config)
# print(user_flights)

# # 搜索航班
# available_flights = flight_tool.search_flights(
#     departure_airport='JFK',
#     arrival_airport='LAX',
#     start_time='2023-10-01 00:00:00',
#     end_time='2023-10-31 23:59:59'
# )
# print(available_flights)

# # 更新机票到新的航班
# update_result = flight_tool.update_ticket_to_new_flight(
#     ticket_no='ABC123',
#     new_flight_id=456,
#     config=config
# )
# print(update_result)

# # 取消机票
# cancel_result = flight_tool.cancel_ticket(
#     ticket_no='ABC123',
#     config=config
# )
# print(cancel_result)
