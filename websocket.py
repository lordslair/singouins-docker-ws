#!/usr/bin/env python3
# -*- coding: utf8 -*-
# Inspired from https://github.com/aaugustin/websockets/issues/653

import asyncio
import os
import time
import websockets
import yarqueue

from loguru             import logger
from redis              import Redis

# Log System imports
logger.info('[DB:*][core] [✓] System imports')

# Redis variables
REDIS_HOST    = os.environ['SEP_BACKEND_REDIS_SVC_SERVICE_HOST']
REDIS_PORT    = os.environ['SEP_BACKEND_REDIS_SVC_SERVICE_PORT']
REDIS_DB      = os.environ['SEP_REDIS_DB']
REDIS_SLEEP   = float(os.environ['SEP_REDIS_SLEEP']) # We receive env as strings

# WebSocket variables
WSS_HOST      = os.environ['SEP_WSS_HOST']
WSS_PORT      = os.environ['SEP_WSS_PORT']

# Opening Redis connection
try:
    r = Redis(host                   = REDIS_HOST,
              port                   = REDIS_PORT,
              db                     = REDIS_DB,
              encoding               = 'utf-8',
              socket_connect_timeout = 1)
except (exceptions.ConnectionError,
        exceptions.BusyLoadingError):
    logger.error(f'[DB:{REDIS_DB}][core] [✗] Connection to redis:{REDIS_DB}')
else:
    logger.info(f'[DB:{REDIS_DB}][core] [✓] Connection to redis:{REDIS_DB}')

# Opening Queue
try:
    yqueue_name = 'broadcast'
    yqueue      = yarqueue.Queue(name=yqueue_name, redis=r)
except:
    logger.error(f'[DB:{REDIS_DB}][core] [✗] Connection to yarqueue:{yqueue_name}')
else:
    logger.info(f'[DB:{REDIS_DB}][core] [✓] Connection to yarqueue:{yqueue_name}')

CLIENTS = set()

async def broadcast():
    while True:
        if not yqueue.empty():
            data = yqueue.get()
            logger.debug(f'[q:broadcast] Consumer got from redis:<{data}>')
            await asyncio.gather(
            *[ws.send(data) for ws in CLIENTS],
            return_exceptions=False,)

        await asyncio.sleep(REDIS_SLEEP)

async def handler(websocket, path):
    # When client connects
    CLIENTS.add(websocket)
    nanotime = time.time_ns()
    logger.info(f'[loop] [✓] Client connected (@nanotime:{nanotime})')

    # Storing in redis client connlog
    try:
        rkey   = f'wsclient:{nanotime}'
        r.set(rkey, '0')
    except:
        logger.error(f'[loop] [✗] Client logged    (@nanotime:{nanotime})')
    else:
        logger.info(f'[loop] [✓] Client logged    (@nanotime:{nanotime})')

    # Main loop
    try:
        # Receiving messages
        async for msg in websocket:
            # Queuing them
            yqueue.put(msg)
    except websockets.ConnectionClosedError:
        logger.warning(f'[loop] [✗] Client lost      (@nanotime:{nanotime})')
    finally:
        # At the end, we remove the connection
        CLIENTS.remove(websocket)
        # We delete in redis client connlog
        try:
            r.delete(f'wsclient:{nanotime}')
        except:
            logger.error(f'[loop] [✗] Client removed   (@nanotime:{nanotime})')
        else:
            logger.info(f'[loop] [✓] Client removed   (@nanotime:{nanotime})')

loop = asyncio.get_event_loop()
loop.create_task(broadcast())

# Opening Queue
try:
    start_server = websockets.serve(handler, WSS_HOST, WSS_PORT)
except:
    logger.error(f'[core] [✗] Starting websocket')
else:
    logger.info(f'[core] [✓] Starting websocket')

# Looping to daemonize the Queue
try:
    loop.run_until_complete(start_server)
    loop.run_forever()
except KeyboardInterrupt:
    try:
        # We scan to find the connected clients
        for key in r.scan_iter("wsclient:*"):
            # We loop to delete all the redis entries
            r.delete(key)
    except:
        logger.error(f'[core] [✗] Cleaned wsclients in redis')
    else:
        logger.info(f'[core] [✓] Cleaned wsclients in redis')
    finally:
        # We can proprerly exit now
        logger.info(f'[core] [✓] Exiting')
