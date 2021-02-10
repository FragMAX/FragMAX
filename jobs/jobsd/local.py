import asyncio
import logging
from asyncio.subprocess import PIPE
from jobs.jobsd.errs import JobFailedException

log = logging.getLogger(__name__)


def append_to_log(log_file, message):
    with open(log_file, "ab") as log:
        log.write(f"{message}\n".encode())


async def log_output(stream, log_file):
    with open(log_file, "wb") as log:
        while True:
            buf = await stream.read(1024 * 4)
            if not buf:
                break

            log.write(buf)
            log.flush()


async def run_job(program, stdout_log, stderr_log):
    try:
        log.info(f"'{program}' started")

        proc = await asyncio.create_subprocess_exec(program, stdout=PIPE, stderr=PIPE)

        await asyncio.gather(
            log_output(proc.stdout, stdout_log), log_output(proc.stderr, stderr_log)
        )

    except asyncio.CancelledError:
        proc.terminate()
        append_to_log(stderr_log, "Job terminated by the user.")
        raise JobFailedException()
    except OSError as ex:
        append_to_log(stderr_log, f"Failed to launch job:\n{ex}")
        raise JobFailedException()
    finally:
        log.info(f"'{program}' done")
