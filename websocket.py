#!/usr/bin/env python3
# -*- coding: utf8 -*-
# Inspired from https://github.com/aaugustin/websockets/issues/653

import asyncio
import json
import os
import time
import websockets
import yarqueue

from redis              import Redis
from datetime           import datetime

# Shorted definition for actual now() with proper format
def mynow(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Redis variables
REDIS_HOST    = os.environ['SEP_BACKEND_REDIS_SVC_SERVICE_HOST']
REDIS_PORT    = os.environ['SEP_BACKEND_REDIS_SVC_SERVICE_PORT']
REDIS_DB_NAME = os.environ['SEP_REDIS_DB']
REDIS_SLEEP   = float(os.environ['SEP_REDIS_SLEEP']) # We receive env as strings

# WebSocket variables
WSS_HOST      = os.environ['SEP_WSS_HOST']
WSS_PORT      = os.environ['SEP_WSS_PORT']

# Opening Redis connection
try:
    r = Redis(host     = REDIS_HOST,
              port     = REDIS_PORT,
              db       = REDIS_DB_NAME,
              encoding = 'utf-8')
except:
    print(f'{mynow()} [core] Connection to redis:{REDIS_DB_NAME} [✗]')
else:
    print(f'{mynow()} [core] Connection to redis:{REDIS_DB_NAME} [✓]')

# Opening Queue
try:
    yqueue_name = 'broadcast'
    yqueue      = yarqueue.Queue(name=yqueue_name, redis=r)
except:
    print(f'{mynow()} [core] Connection to yarqueue:{yqueue_name} [✗]')
else:
    print(f'{mynow()} [core] Connection to yarqueue:{yqueue_name} [✓]')

CLIENTS = set()

async def broadcast():
    while True:
        if not yqueue.empty():
            data = yqueue.get()
            print(f'{mynow()} [q:broadcast] Consumer got from redis:<{data}>')
            await asyncio.gather(
            *[ws.send(data) for ws in CLIENTS],
            return_exceptions=False,)

        await asyncio.sleep(REDIS_SLEEP)

async def handler(websocket, path):
    # When client connects
    CLIENTS.add(websocket)
    nanotime = time.time_ns()
    print(f'{mynow()} [core] Client connected (@nanotime:{nanotime}) [✓]')

    # Storing in redis client connlog
    try:
        rkey   = f'wsclient:{nanotime}'
        rvalue = json.dumps({"nanotime": nanotime, "date": mynow()})
        r.set(rkey, rvalue)
    except:
        print(f'{mynow()} [core] Client logged    (@nanotime:{nanotime}) [✗]')
    else:
        print(f'{mynow()} [core] Client logged    (@nanotime:{nanotime}) [✓]')

    # Main loop
    try:
        # Receiving messages
        async for msg in websocket:
            # Queuing them
            yqueue.put(msg)
    except websockets.ConnectionClosedError:
        print(f'{mynow()} [core] Connection closed')
    finally:
        # At the end, we remove the connection
        CLIENTS.remove(websocket)
        # We delete in redis client connlog
        try:
            r.delete(f'wsclient:{realip}')
        except:
            print(f'{mynow()} [core] Client removed ({realip}) [✗]')
        else:
            print(f'{mynow()} [core] Client removed ({realip}) [✓]')

loop = asyncio.get_event_loop()
loop.create_task(broadcast())

# Opening Queue
try:
    start_server = websockets.serve(handler, WSS_HOST, WSS_PORT)
except:
    print(f'{mynow()} [core] Starting websocket [✗]')
else:
    print(f'{mynow()} [core] Starting websocket [✓]')

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
        print(f'{mynow()} [core] Cleaned wsclients in redis [✗]')
    else:
        print(f'{mynow()} [core] Cleaned wsclients in redis [✓]')
    finally:
        # We can proprerly exit now
        print(f'{mynow()} [core] Exiting')
