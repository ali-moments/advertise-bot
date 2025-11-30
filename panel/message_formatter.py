"""
MessageFormatter - Formats messages for consistent bot UI
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from .persian_text import (
    SYSTEM_STATUS_TEMPLATE, SESSION_DETAILS_TEMPLATE, CHANNEL_LIST_TEMPLATE,
    CHANNEL_ITEM_TEMPLATE, SESSION_LIST_TEMPLATE, SESSION_ITEM_TEMPLATE,
    SUCCESS_SCRAPE, SUCCESS_SEND, SUCCESS_MONITORING_ADDED,
    ERROR_TEMPLATE, CSV_PREVIEW, CONFIRM_SCRAPE, CONFIRM_SEND,
    STATUS_CONNECTED, STATUS_DISCONNECTED, STATUS_ACTIVE, STATUS_INACTIVE,
    STATUS_MONITORING, STATUS_IDLE, PAGINATION_INFO
)


class MessageFormatter:
    """Format messages for bot UI"""
    
    @staticmethod
    def format_scrape_result(result: Dict[str, Any]) -> str:
        """
        Format scraping result message
        
        Args:
            result: Dict with keys: success, member_count, source, duration, file_path, error
        
        Returns:
            Formatted message string
        """
        if not result.get('success', False):
            return MessageFormatter.format_error(
                error_type="اسکرپ",
                description=result.get('error', 'خطای نامشخص'),
                show_retry=True
            )
        
        duration = result.get('duration', 0)
        duration_str = MessageFormatter._format_duration(duration)
        
        return SUCCESS_SCRAPE.format(
            member_count=result.get('member_count', 0),
            source=result.get('source', 'نامشخص'),
            duration=duration_str,
            file_path=result.get('file_path', 'ذخیره نشد')
        )
    
    @staticmethod
    def format_send_result(result: Dict[str, Any]) -> str:
        """
        Format sending result message
        
        Args:
            result: Dict with keys: sent_count, failed_count, total_count, duration
        
        Returns:
            Formatted message string
        """
        duration = result.get('duration', 0)
        duration_str = MessageFormatter._format_duration(duration)
        
        return SUCCESS_SEND.format(
            sent_count=result.get('sent_count', 0),
            failed_count=result.get('failed_count', 0),
            total_count=result.get('total_count', 0),
            duration=duration_str
        )
    
    @staticmethod
    def format_session_stats(stats: Dict[str, Any]) -> str:
        """
        Format session statistics
        
        Args:
            stats: Dict with session statistics
        
        Returns:
            Formatted message string
        """
        phone = stats.get('phone', 'نامشخص')
        connected = stats.get('connected', False)
        monitoring = stats.get('monitoring', False)
        
        connection_status = STATUS_CONNECTED if connected else STATUS_DISCONNECTED
        monitoring_status = STATUS_ACTIVE if monitoring else STATUS_INACTIVE
        
        # Format monitoring channels
        monitoring_channels = ""
        if monitoring and stats.get('monitoring_channels'):
            channels = stats['monitoring_channels']
            monitoring_channels = "\n   • " + "\n   • ".join(channels)
        
        # Format active operations
        active_ops = stats.get('active_operations', [])
        if active_ops:
            ops_text = "\n".join([f"   • {op['type']}: {op.get('progress', 'در حال اجرا')}" for op in active_ops])
        else:
            ops_text = "   • هیچ عملیاتی در حال اجرا نیست"
        
        # Daily stats
        daily_stats = stats.get('daily_stats', {})
        messages_read = daily_stats.get('messages_read', 0)
        daily_limit = daily_stats.get('daily_limit', 500)
        groups_scraped = daily_stats.get('groups_scraped', 0)
        scrape_limit = daily_stats.get('scrape_limit', 10)
        messages_sent = daily_stats.get('messages_sent', 0)
        
        # Health status
        health = stats.get('health', {})
        health_status = "✅ سالم" if health.get('healthy', True) else "⚠️ مشکل دارد"
        last_check = health.get('last_check', 'نامشخص')
        if isinstance(last_check, (int, float)):
            last_check = MessageFormatter._format_time_ago(last_check)
        
        queue_depth = stats.get('queue_depth', 0)
        
        return SESSION_DETAILS_TEMPLATE.format(
            phone=phone,
            connection_status=connection_status,
            monitoring_status=monitoring_status,
            monitoring_channels=monitoring_channels,
            active_operations=ops_text,
            messages_read=messages_read,
            daily_limit=daily_limit,
            groups_scraped=groups_scraped,
            scrape_limit=scrape_limit,
            messages_sent=messages_sent,
            health_status=health_status,
            last_check=last_check,
            queue_depth=queue_depth
        )
    
    @staticmethod
    def format_system_status(status: Dict[str, Any]) -> str:
        """
        Format system status message
        
        Args:
            status: Dict with system-wide statistics
        
        Returns:
            Formatted message string
        """
        now = datetime.now().strftime("%H:%M:%S")
        
        return SYSTEM_STATUS_TEMPLATE.format(
            total_sessions=status.get('total_sessions', 0),
            connected_sessions=status.get('connected_sessions', 0),
            monitoring_sessions=status.get('monitoring_sessions', 0),
            active_scrapes=status.get('active_scrapes', 0),
            active_sends=status.get('active_sends', 0),
            active_monitoring=status.get('active_monitoring', 0),
            messages_read=status.get('messages_read', 0),
            groups_scraped=status.get('groups_scraped', 0),
            messages_sent=status.get('messages_sent', 0),
            reactions_sent=status.get('reactions_sent', 0),
            active_channels=status.get('active_channels', 0),
            reactions_today=status.get('reactions_today', 0),
            last_update=now
        )
    
    @staticmethod
    def format_progress(
        current: int,
        total: int,
        operation: str,
        success: int = 0,
        failed: int = 0,
        elapsed: Optional[float] = None,
        show_detailed: bool = True
    ) -> str:
        """
        Format progress message
        
        Args:
            current: Current progress count
            total: Total items
            operation: Operation name
            success: Success count
            failed: Failed count
            elapsed: Elapsed time in seconds
            show_detailed: Whether to show detailed progress
        
        Returns:
            Formatted progress string
        """
        if not show_detailed:
            percentage = int((current / total * 100)) if total > 0 else 0
            return f"⏳ {operation}: {current}/{total} ({percentage}%)"
        
        percentage = int((current / total * 100)) if total > 0 else 0
        remaining = total - current
        
        elapsed_str = MessageFormatter._format_duration(elapsed) if elapsed else "محاسبه..."
        
        # Calculate ETA
        if elapsed and current > 0:
            avg_time = elapsed / current
            eta_seconds = avg_time * remaining
            eta_str = MessageFormatter._format_duration(eta_seconds)
        else:
            eta_str = "محاسبه..."
        
        from .persian_text import PROGRESS_TEMPLATE
        return PROGRESS_TEMPLATE.format(
            operation=operation,
            current=current,
            total=total,
            percentage=percentage,
            success=success,
            failed=failed,
            remaining=remaining,
            elapsed=elapsed_str,
            eta=eta_str
        )
    
    @staticmethod
    def format_channel_list(channels: List[Dict[str, Any]], page: int = 1, total_pages: int = 1) -> str:
        """
        Format channel list message
        
        Args:
            channels: List of channel dicts
            page: Current page
            total_pages: Total pages
        
        Returns:
            Formatted channel list string
        """
        if not channels:
            return "📺 **کانال‌های مانیتور شده**\n\nهیچ کانالی یافت نشد."
        
        channel_items = []
        for idx, channel in enumerate(channels, 1):
            # Format reactions
            reactions_list = channel.get('reactions', [])
            reactions_str = " ".join([f"{r['emoji']}({r['weight']})" for r in reactions_list])
            
            status = STATUS_ACTIVE if channel.get('enabled', False) else STATUS_INACTIVE
            stats_sent = channel.get('stats', {}).get('reactions_sent', 0)
            
            item = CHANNEL_ITEM_TEMPLATE.format(
                index=idx,
                channel=channel.get('chat_id', 'نامشخص'),
                reactions=reactions_str or "ندارد",
                cooldown=channel.get('cooldown', 0),
                status=status,
                stats_sent=stats_sent
            )
            channel_items.append(item)
        
        channels_text = "\n".join(channel_items)
        
        total_channels = len(channels)
        active_channels = sum(1 for c in channels if c.get('enabled', False))
        
        result = CHANNEL_LIST_TEMPLATE.format(
            channels=channels_text,
            total_channels=total_channels,
            active_channels=active_channels
        )
        
        if total_pages > 1:
            result += f"\n\n{PAGINATION_INFO.format(current=page, total=total_pages)}"
        
        return result
    
    @staticmethod
    def format_session_list(sessions: List[Dict[str, Any]], page: int = 1, total_pages: int = 1) -> str:
        """
        Format session list message
        
        Args:
            sessions: List of session dicts
            page: Current page
            total_pages: Total pages
        
        Returns:
            Formatted session list string
        """
        if not sessions:
            return "👥 **لیست سشن‌ها**\n\nهیچ سشنی یافت نشد."
        
        session_items = []
        for session in sessions:
            phone = session.get('phone', 'نامشخص')
            connected = session.get('connected', False)
            monitoring = session.get('monitoring', False)
            
            status = STATUS_CONNECTED if connected else STATUS_DISCONNECTED
            monitoring_status = STATUS_ACTIVE if monitoring else STATUS_INACTIVE
            
            channel_count = len(session.get('monitoring_channels', []))
            queue_depth = session.get('queue_depth', 0)
            
            daily_stats = session.get('daily_stats', {})
            messages = daily_stats.get('messages_read', 0)
            groups = daily_stats.get('groups_scraped', 0)
            
            item = SESSION_ITEM_TEMPLATE.format(
                phone=phone,
                status=status,
                monitoring=monitoring_status,
                channel_count=channel_count,
                queue_depth=queue_depth,
                messages=messages,
                groups=groups
            )
            session_items.append(item)
        
        sessions_text = "\n".join(session_items)
        
        total_sessions = len(sessions)
        connected_sessions = sum(1 for s in sessions if s.get('connected', False))
        
        result = SESSION_LIST_TEMPLATE.format(
            sessions=sessions_text,
            connected=connected_sessions,
            total=total_sessions,
            page=page,
            total_pages=total_pages
        )
        
        return result
    
    @staticmethod
    def format_error(
        error_type: str,
        description: str,
        show_retry: bool = False
    ) -> str:
        """
        Format error message
        
        Args:
            error_type: Type of error
            description: Error description
            show_retry: Whether to show retry option text
        
        Returns:
            Formatted error string
        """
        retry_option = "\nبرای تلاش مجدد از دکمه زیر استفاده کنید." if show_retry else ""
        
        return ERROR_TEMPLATE.format(
            error_type=error_type,
            description=description,
            retry_option=retry_option
        )
    
    @staticmethod
    def format_csv_preview(row_count: int, columns: List[str], sample_data: List[List[str]]) -> str:
        """
        Format CSV preview message
        
        Args:
            row_count: Number of rows
            columns: Column names
            sample_data: Sample rows (first 3-5)
        
        Returns:
            Formatted CSV preview string
        """
        columns_str = ", ".join(columns)
        
        sample_lines = []
        for row in sample_data[:3]:
            sample_lines.append(" | ".join(str(cell) for cell in row))
        sample_str = "\n".join(sample_lines)
        
        if row_count > 3:
            sample_str += f"\n... و {row_count - 3} ردیف دیگر"
        
        return CSV_PREVIEW.format(
            row_count=row_count,
            columns=columns_str,
            sample_data=sample_str
        )
    
    @staticmethod
    def format_confirm_scrape(
        operation_type: str,
        target_count: int,
        preview: str
    ) -> str:
        """
        Format scrape confirmation message
        
        Args:
            operation_type: Type of scrape operation
            target_count: Number of targets
            preview: Preview text
        
        Returns:
            Formatted confirmation string
        """
        return CONFIRM_SCRAPE.format(
            operation_type=operation_type,
            target_count=target_count,
            preview=preview
        )
    
    @staticmethod
    def format_confirm_send(
        message_type: str,
        recipient_count: int,
        delay: float,
        estimated_time: str
    ) -> str:
        """
        Format send confirmation message
        
        Args:
            message_type: Type of message
            recipient_count: Number of recipients
            delay: Delay between messages
            estimated_time: Estimated completion time
        
        Returns:
            Formatted confirmation string
        """
        return CONFIRM_SEND.format(
            message_type=message_type,
            recipient_count=recipient_count,
            delay=delay,
            estimated_time=estimated_time
        )
    
    @staticmethod
    def format_monitoring_added(channel: str, reactions: List[Dict], cooldown: float) -> str:
        """
        Format monitoring channel added message
        
        Args:
            channel: Channel identifier
            reactions: List of reaction dicts
            cooldown: Cooldown in seconds
        
        Returns:
            Formatted success message
        """
        reactions_str = " ".join([f"{r['emoji']}({r['weight']})" for r in reactions])
        
        return SUCCESS_MONITORING_ADDED.format(
            channel=channel,
            reactions=reactions_str,
            cooldown=cooldown
        )
    
    @staticmethod
    def _format_duration(seconds: Optional[float]) -> str:
        """Format duration in seconds to human-readable Persian string"""
        if seconds is None or seconds < 0:
            return "نامشخص"
        
        if seconds < 60:
            return f"{int(seconds)} ثانیه"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes} دقیقه و {secs} ثانیه"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours} ساعت و {minutes} دقیقه"
    
    @staticmethod
    def _format_time_ago(timestamp: float) -> str:
        """Format timestamp to 'time ago' string in Persian"""
        now = datetime.now().timestamp()
        diff = now - timestamp
        
        if diff < 60:
            return f"{int(diff)} ثانیه پیش"
        elif diff < 3600:
            return f"{int(diff / 60)} دقیقه پیش"
        elif diff < 86400:
            return f"{int(diff / 3600)} ساعت پیش"
        else:
            return f"{int(diff / 86400)} روز پیش"
    
    @staticmethod
    def format_load_distribution(sessions: List[Dict[str, Any]]) -> str:
        """
        Format load distribution visualization
        
        Args:
            sessions: List of session dicts with load info
        
        Returns:
            Formatted load distribution string
        """
        if not sessions:
            return "⚖️ **توزیع بار**\n\nهیچ سشنی یافت نشد."
        
        result = "⚖️ **توزیع بار سشن‌ها**\n\n"
        
        # Find max load for scaling
        max_load = max((s.get('current_load', 0) for s in sessions), default=1)
        
        for session in sessions:
            phone = session.get('phone', 'نامشخص')
            load = session.get('current_load', 0)
            queue = session.get('queue_depth', 0)
            
            # Create text-based bar chart
            bar_length = int((load / max_load * 20)) if max_load > 0 else 0
            bar = "█" * bar_length + "░" * (20 - bar_length)
            
            result += f"📱 {phone}\n"
            result += f"   {bar} {load}\n"
            result += f"   صف: {queue} عملیات\n\n"
        
        return result
