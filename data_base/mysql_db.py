import asyncio
import aiomysql
from config.config import get_config_value


pool_config = {
    'host': get_config_value('database', 'host'),
    'port': int(get_config_value('database', 'port')),
    'user': get_config_value('database', 'user'),
    'password': get_config_value('database', 'password'),
    'db': get_config_value('database', 'database'),
    'charset': 'utf8mb4',
    'minsize': 1,  # minimum size of the pool
    'maxsize': 32  # maximum size of the pool
}


async def init_db():
    global pool
    pool = await aiomysql.create_pool(**pool_config, loop=asyncio.get_running_loop())


async def get_stops_levenshtein_distance(pool, stop_name):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("""
                SELECT *
                FROM (
                    SELECT stop_name, add_info, stop_id, levenshtein(stop_name, %s) AS distance
                    FROM stops s 
                ) AS sub
                WHERE distance < 5
                """, stop_name)
            rows = await cursor.fetchall()
    return rows


async def get_stops_by_location(pool, latitude, longitude):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("""
                SELECT stop_name, add_info, stop_id
                FROM stops
                WHERE ST_Distance(ST_GeomFromText('POINT(%s %s)', 4326), geom) <= 100
                ORDER BY stop_id
                """, [latitude, longitude])
            rows = await cursor.fetchall()
    return rows


async def get_route_by_trans_id(pool, trans_id):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("""
                SELECT r.route_id, s.stop_name
                FROM routs AS r
                JOIN stops AS s ON r.cur_stop_id = s.stop_id
                WHERE trans_id = %s 
                ORDER BY r.stop_seq_num
            """, [trans_id])
            rows = await cursor.fetchall()
    return rows


async def get_trans_name_by_num(pool, trans_num, trans_type):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("""
                SELECT trans_id, trans_name
                FROM transport
                WHERE trans_num = %s AND trans_type = %s
            """, [trans_num, trans_type])
            rows = await cursor.fetchall()
    return rows


async def get_trans_by_id(pool, trans_id):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("""
                SELECT *
                FROM transport
                WHERE trans_id = %s
            """, [trans_id])
            row = await cursor.fetchall()
    return row[0]


async def get_stop_by_id(pool, stop_id):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("""
                SELECT *
                FROM stops
                WHERE stop_id = %s
            """, [stop_id])
            row = await cursor.fetchall()
    return row[0]


async def get_schedule_by_route_id(pool, route_id):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("""
                SELECT t.trans_num, t.trans_name, t.trans_type, s.stop_name, r.time_board
                FROM routs AS r
                JOIN transport AS t ON r.trans_id = t.trans_id
                JOIN stops AS s ON r.cur_stop_id = s.stop_id
                WHERE r.route_id = %s
            """, [route_id])
            row = await cursor.fetchall()
    return row[0]


async def get_schedule_by_stop_id(pool, stop_id):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("""
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
            rows = await cursor.fetchall()
    return rows


async def get_stops_by_names(pool, start_stop_name, end_stop_name):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("""
                SELECT stop_id, stop_name 
                FROM stops 
                WHERE stop_name = %s OR stop_name = %s
            """, [start_stop_name, end_stop_name])
            stops = await cursor.fetchall()
    return stops


async def get_all_routs(pool):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("""
                SELECT *
                FROM routs
            """)
            routs = await cursor.fetchall()
    return routs


async def get_nearest_stop(pool, latitude, longitude):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("""
                SELECT stop_id, stop_name, ST_Y(geom) as longitude, ST_X(geom) as latitude, 
                ST_Distance(ST_GeomFromText('POINT(%s %s)', 4326), geom) AS distance
                FROM stops
                ORDER BY distance
                LIMIT 1;
            """, [latitude, longitude])
            nearest_stop = await cursor.fetchall()
        return nearest_stop[0]


async def get_prices(pool):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("""
                SELECT tt.type, l.location, tp.price
                FROM ticket_prices tp
                JOIN ticket_types tt ON tp.ticket_type_id = tt.id
                JOIN locations l ON tp.location_id = l.id
            """)
            prices = await cursor.fetchall()
    return prices


async def save_comment(pool, user_id, comment):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("""
                INSERT INTO comments (user_id, text)
                VALUES (%s, %s)
                """, (user_id, comment))
            conn.commit()
