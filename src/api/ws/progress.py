"""WebSocket endpoint for real-time pipeline progress."""
import asyncio
import logging
import queue

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.api.services.run_state import get_run

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/progress/{run_id}")
async def progress_stream(websocket: WebSocket, run_id: str):
    run = get_run(run_id)
    if run is None:
        await websocket.close(code=4004, reason=f"Run {run_id} not found")
        return

    await websocket.accept()

    try:
        while True:
            while True:
                try:
                    event = run.progress_queue.get_nowait()

                    if event.is_terminal:
                        if event.is_error:
                            run.status = "error"
                            run.error = event.metadata.get("error", "Unknown error")
                            await websocket.send_json({
                                "type": "error",
                                "agent": event.agent_name,
                                "message": event.message,
                                "traceback": event.metadata.get("traceback", ""),
                            })
                        else:
                            run.status = "complete"
                            run.result = event.metadata.get("result", {})
                            await websocket.send_json({
                                "type": "complete",
                                "agent": event.agent_name,
                                "message": event.message,
                                "result": run.result,
                            })
                        await websocket.close()
                        return
                    else:
                        await websocket.send_json({
                            "type": "progress",
                            "agent": event.agent_name,
                            "message": event.message,
                            "timestamp": event.timestamp,
                            "attempt": event.metadata.get("attempt", 0),
                        })

                except queue.Empty:
                    break

            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket error for run %s: %s", run_id, e)
        try:
            await websocket.close(code=1011, reason=str(e))
        except Exception:
            pass
