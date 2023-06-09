import mysql.connector.pooling
from config.config import get_config_value


pool_config = {
    'host': get_config_value('database', 'host'),
    'port': get_config_value('database', 'port'),
    'user': get_config_value('database', 'user'),
    'password': get_config_value('database', 'password'),
    'database': get_config_value('database', 'database'),
    'charset': 'utf8mb4',
    'pool_name': 'mypool',
    'pool_size': 32,
}

cnxpool = mysql.connector.pooling.MySQLConnectionPool(**pool_config)


def get_stops_levenshtein_distance(stop_name):
    with cnxpool.get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT *
                FROM (
                    SELECT stop_name, add_info, stop_id, levenshtein(stop_name, %s) AS distance
                    FROM stops s 
                ) AS sub
                WHERE distance < 5
                """, [stop_name])
            rows = cursor.fetchall()
    return rows


def get_stops_by_location(latitude, longitude):
    with cnxpool.get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT stop_name, add_info, stop_id
                FROM stops
                WHERE ST_Distance(ST_GeomFromText('POINT(%s %s)', 4326), geom) <= 100
                ORDER BY stop_id
                """, [latitude, longitude])
            rows = cursor.fetchall()
    return rows


def get_route_by_trans_id(trans_id):
    with cnxpool.get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT r.route_id, s.stop_name
                FROM routs AS r
                JOIN stops AS s ON r.cur_stop_id = s.stop_id
                WHERE trans_id = %s 
                ORDER BY r.stop_seq_num
            """, [trans_id])
            rows = cursor.fetchall()
    return rows


def get_trans_name_by_num(trans_num, trans_type):
    with cnxpool.get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT trans_id, trans_name
                FROM transport
                WHERE trans_num = %s AND trans_type = %s
            """, [trans_num, trans_type])
            rows = cursor.fetchall()
    return rows


def get_trans_by_id(trans_id):
    with cnxpool.get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT *
                FROM transport
                WHERE trans_id = %s
            """, [trans_id])
            row = cursor.fetchall()
    return row[0]


def get_stop_by_id(stop_id):
    with cnxpool.get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT *
                FROM stops
                WHERE stop_id = %s
            """, [stop_id])
            row = cursor.fetchall()
    return row[0]


def get_schedule_by_route_id(route_id):
    with cnxpool.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT t.trans_num, t.trans_name, t.trans_type, s.stop_name, r.time_board
                FROM routs AS r
                JOIN transport AS t ON r.trans_id = t.trans_id
                JOIN stops AS s ON r.cur_stop_id = s.stop_id
                WHERE r.route_id = %s
            """, [route_id])
            row = cursor.fetchall()
    return row[0]


def get_schedule_by_stop_id(stop_id):
    with cnxpool.get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT
                s.stop_name,
                s.add_info,
                t.trans_num,
                t.trans_type,
                t.trans_name,
                r.time_board
                FROM
                    stops s
                JOIN routs r ON s.stop_id = r.cur_stop_id
                JOIN transport t ON r.trans_id = t.trans_id
                WHERE
                    s.stop_id = %s
            """, [stop_id])
            rows = cursor.fetchall()
    return rows


def get_stops_by_names(start_stop_name, end_stop_name):
    with cnxpool.get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT stop_id, stop_name 
                FROM stops 
                WHERE stop_name = %s OR stop_name = %s
            """, [start_stop_name, end_stop_name])
            stops = cursor.fetchall()
    return stops


def get_all_routs():
    with cnxpool.get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT *
                FROM routs
            """)
            routs = cursor.fetchall()
    return routs


def get_nearest_stop(latitude, longitude):
    with cnxpool.get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT stop_id, stop_name, ST_Y(geom) as longitude, ST_X(geom) as latitude, 
                ST_Distance(ST_GeomFromText('POINT(%s %s)', 4326), geom) AS distance
                FROM stops
                ORDER BY distance
                LIMIT 1;
            """, [latitude, longitude])
            nearest_stop = cursor.fetchall()
        return nearest_stop[0]


def get_prices():
    with cnxpool.get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT tt.type, l.location, tp.price
                FROM ticket_prices tp
                JOIN ticket_types tt ON tp.ticket_type_id = tt.id
                JOIN locations l ON tp.location_id = l.id
            """)
            prices = cursor.fetchall()
    return prices


def save_comment(user_id, comment):
    with cnxpool.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO comments (user_id, text)
                VALUES (%s, %s)
                """, (user_id, comment))
            conn.commit()
