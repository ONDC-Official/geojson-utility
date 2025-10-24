import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any
from datetime import datetime
import weakref

logger = logging.getLogger(__name__)


class SSEEventManager:
    """Manages Server-Sent Events for CSV processing status updates"""
    
    def __init__(self):
        self._subscribers: Dict[int, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()
    
    async def subscribe(self, csv_id: int) -> asyncio.Queue:
        """Subscribe to events for a specific CSV ID"""
        async with self._lock:
            if csv_id not in self._subscribers:
                self._subscribers[csv_id] = set()
            
            queue = asyncio.Queue(maxsize=100)
            self._subscribers[csv_id].add(queue)
            logger.info(f"New subscriber for CSV {csv_id}. Total subscribers: {len(self._subscribers[csv_id])}")
            return queue
    
    async def unsubscribe(self, csv_id: int, queue: asyncio.Queue):
        """Unsubscribe from events for a specific CSV ID"""
        async with self._lock:
            if csv_id in self._subscribers and queue in self._subscribers[csv_id]:
                self._subscribers[csv_id].discard(queue)
                if not self._subscribers[csv_id]:
                    del self._subscribers[csv_id]
                logger.info(f"Unsubscribed from CSV {csv_id}")
    
    def broadcast_sync(self, csv_id: int, event_type: str, data: Dict[str, Any]):
        """Thread-safe method to broadcast events from sync context"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._broadcast_async(csv_id, event_type, data))
            else:
                loop.run_until_complete(self._broadcast_async(csv_id, event_type, data))
        except RuntimeError:
            # No event loop in current thread, create a new one
            try:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(self._run_in_new_loop, csv_id, event_type, data)
                    future.result(timeout=1)
            except Exception as e:
                logger.error(f"Failed to broadcast event: {e}")
    
    def _run_in_new_loop(self, csv_id: int, event_type: str, data: Dict[str, Any]):
        """Run broadcast in a new event loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._broadcast_async(csv_id, event_type, data))
        finally:
            loop.close()
    
    async def _broadcast_async(self, csv_id: int, event_type: str, data: Dict[str, Any]):
        """Internal method to broadcast events"""
        if csv_id not in self._subscribers:
            return
        
        event_data = {
            "type": event_type,
            "csv_id": csv_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            **data
        }
        
        message = f"data: {json.dumps(event_data)}\n\n"
        
        # Get copy of subscribers to avoid modification during iteration
        async with self._lock:
            subscribers = self._subscribers.get(csv_id, set()).copy()
        
        # Send to all subscribers
        dead_queues = []
        for queue in subscribers:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning(f"Queue full for CSV {csv_id}, dropping event")
                dead_queues.append(queue)
            except Exception as e:
                logger.error(f"Error sending event to subscriber: {e}")
                dead_queues.append(queue)
        
        # Clean up dead queues
        if dead_queues:
            async with self._lock:
                for queue in dead_queues:
                    self._subscribers.get(csv_id, set()).discard(queue)
        
        logger.debug(f"Broadcasted {event_type} event to {len(subscribers) - len(dead_queues)} subscribers for CSV {csv_id}")
    
    async def send_heartbeat(self, csv_id: int):
        """Send heartbeat to keep connections alive"""
        await self._broadcast_async(csv_id, "heartbeat", {})
    
    def broadcast_start(self, csv_id: int, total_rows: int):
        """Broadcast processing start event"""
        self.broadcast_sync(csv_id, "start", {
            "total_rows": total_rows,
            "status": "processing"
        })
    
    def broadcast_progress(self, csv_id: int, completed: int, total: int, failed: int = 0):
        """Broadcast progress update event"""
        percentage = round((completed / total) * 100, 1) if total > 0 else 0
        self.broadcast_sync(csv_id, "progress", {
            "completed": completed,
            "total": total,
            "failed": failed,
            "percentage": percentage
        })
    
    def broadcast_complete(self, csv_id: int, status: str, error: Optional[str] = None):
        """Broadcast processing complete event"""
        data = {"status": status}
        if error:
            data["error"] = error
        self.broadcast_sync(csv_id, "complete", data)
    
    def get_subscriber_count(self, csv_id: int) -> int:
        """Get number of subscribers for a CSV ID"""
        return len(self._subscribers.get(csv_id, set()))


# Global SSE manager instance
sse_manager = SSEEventManager()