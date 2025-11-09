"""Entry point for running Game Tools service."""
import asyncio
import logging
import sys
from pathlib import Path

from src.ptcg_ai.database import DatabaseClient, build_postgres_dsn

from .service import create_server

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Run the Game Tools gRPC server."""
    # Initialize state store and database
    state_store = {}
    dsn = build_postgres_dsn()
    db = DatabaseClient(dsn=dsn)
    
    # Create server
    server = create_server(
        state_store=state_store,
        db=db,
        port=50051,
        allowed_referee_ids=["referee"],  # Configure allowed referee IDs
    )
    
    # Start server
    server.start()
    logger.info("Game Tools gRPC 服务器已启动，端口: 50051")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("正在关闭服务器...")
        server.stop(0)


if __name__ == "__main__":
    main()

