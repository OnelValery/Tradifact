import asyncio
import sys

# a subset of commands are handled immediately, all commands are also passed to the main loop (in canonical format)
async def aio_readline(loop, c):
    while c.alive:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        c.cli_commands.append(line)
    return

def start_cli(c):
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(aio_readline(loop, c))
    c.logging.debug("Starting command line")

