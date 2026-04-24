"""Shared FastAPI dependencies (db pool, redis, config)."""
from __future__ import annotations

from fastapi import Request

from .config import Config


def get_cfg(request: Request) -> Config:
    return request.app.state.cfg


def get_pool(request: Request):
    return request.app.state.pg_pool


def get_redis(request: Request):
    return request.app.state.redis
