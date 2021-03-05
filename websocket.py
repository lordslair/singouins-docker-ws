#!/usr/bin/env python3
# -*- coding: utf8 -*-
# Inspired from https://github.com/aaugustin/websockets/issues/653

import asyncio
import os
import time
import websockets
import yarqueue

from redis import Redis

# Redis variables
REDIS_HOST    = os.environ['SEP_BACKEND_REDIS_SVC_SERVICE_HOST']
REDIS_PORT    = os.environ['SEP_BACKEND_REDIS_SVC_SERVICE_PORT']
REDIS_DB_NAME = os.environ['SEP_REDIS_DB']
REDIS_SLEEP   = int(os.environ['SEP_REDIS_SLEEP']) # We receive k8s env as strings

# WebSocket variables
WSS_HOST      = os.environ['SEP_WSS_HOST']
WSS_PORT      = os.environ['SEP_WSS_PORT']

r = Redis(host     = REDIS_HOST,
          port     = REDIS_PORT,
          db       = REDIS_DB_NAME,
          encoding = 'utf-8')

yqueue = yarqueue.Queue(name="broadcast", redis=r)

CLIENTS = set()

async def broadcast():
    while True:
        if not yqueue.empty():
            data = yqueue.get()
            print (f'consumer processing: <{data}>')
            await asyncio.gather(
            *[ws.send(data) for ws in CLIENTS],
            return_exceptions=False,)

        await asyncio.sleep(REDIS_SLEEP)

async def handler(websocket, path):
    CLIENTS.add(websocket)
    print("add client")
    try:
        async for msg in websocket:
            yqueue.put(msg)
    except websockets.ConnectionClosedError:
        print("Connection closed")
    finally:
        CLIENTS.remove(websocket)
        print("remove client")

loop = asyncio.get_event_loop()
loop.create_task(broadcast())

start_server = websockets.serve(handler, WSS_HOST, WSS_PORT)

try:
    loop.run_until_complete(start_server)
    loop.run_forever()
except KeyboardInterrupt:
    print("Exiting")
