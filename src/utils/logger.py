from loguru import logger

# Configure logger as needed
logger.add(lambda msg: print(msg, end=""))

__all__ = ["logger"]
