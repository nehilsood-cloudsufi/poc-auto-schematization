"""WebSocket endpoint for real-time pipeline progress."""
import asyncio
import json
import logging
import queue
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.api.services.run_state import get_run, write_run_info

logger = logging.getLogger(__name__)
router = APIRouter()


def _safe_serialize(obj, _depth: int = 0):
    """Make an object JSON-serializable by converting non-standard types."""
    if _depth > 20:
        return str(obj)
    if isinstance(obj, float) and (obj != obj or obj == float("inf") or obj == float("-inf")):
        return None  # NaN/inf are not valid JSON
    if isinstance(obj, dict):
        return {k: _safe_serialize(v, _depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(item, _depth + 1) for item in obj]
    if isinstance(obj, Path):
        return str(obj)
    if hasattr(obj, "get_file_summary"):
        return obj.get_file_summary()
    if hasattr(obj, "__dict__") and not isinstance(obj, (str, int, float, bool)):
        return {k: _safe_serialize(v, _depth + 1) for k, v in obj.__dict__.items() if not k.startswith("_")}
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)


@router.websocket("/ws/progress/{run_id}")
async def progress_stream(websocket: WebSocket, run_id: str):
    run = get_run(run_id)
    if run is None:
        await websocket.accept()
        await websocket.send_json({"type": "error", "agent": "system", "message": f"Run {run_id} not found"})
        await websocket.close(code=4004)
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
                        elif event.metadata.get("exit_reason") == "user_cancelled":
                            # Don't overwrite "stopped" status set by stop_run()
                            if run.status != "stopped":
                                run.status = "stopped"
                            await websocket.send_json({
                                "type": "complete",
                                "agent": event.agent_name,
                                "message": event.message,
                            })
                        else:
                            result = _safe_serialize(event.metadata.get("result", {}))
                            is_plan_only = isinstance(result, dict) and result.get("phase") == "plan"
                            is_plan_failed = isinstance(result, dict) and result.get("status") == "plan_failed"
                            if run.status != "stopped":
                                if is_plan_failed:
                                    run.status = "plan_ready"  # UI can still regenerate
                                    run.error = "Plan generation failed (LLM timeout or crash)"
                                elif is_plan_only:
                                    run.status = "plan_ready"
                                else:
                                    run.status = "complete"
                            run.result = result
                            await websocket.send_json({
                                "type": "complete",
                                "agent": event.agent_name,
                                "message": event.message,
                                "result": run.result,
                            })
                        # Persist terminal status so server restarts don't show stale "running"
                        try:
                            write_run_info(Path(run.run_dir), {"status": run.status})
                        except Exception:
                            pass
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

            # Guard against zombie connections: if the pipeline thread has
            # exited and the queue is empty, close the WebSocket.
            thread_dead = run.thread is not None and not run.thread.is_alive()
            thread_absent = run.thread is None and run.status in ("complete", "error", "stopped", "plan_ready")
            if (thread_dead or thread_absent) and run.progress_queue.empty():
                if run.status == "running":
                    run.status = "error"
                    run.error = "Pipeline thread exited unexpectedly"
                    try:
                        write_run_info(Path(run.run_dir), {"status": "error"})
                    except Exception:
                        pass
                    await websocket.send_json({
                        "type": "error",
                        "agent": "system",
                        "message": "Pipeline thread exited unexpectedly",
                    })
                await websocket.close()
                return

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket error for run %s: %s", run_id, e)
        try:
            await websocket.close(code=1011, reason=str(e))
        except Exception:
            pass
