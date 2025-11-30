"""
Data models for message sending and validation
"""

import time
import re
import os
import tempfile
import asyncio
import random
import csv
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, AsyncIterator, Set, Callable
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
from enum import Enum
from collections import deque


@dataclass
class MessageResult:
    """Result of a single message send operation"""
    recipient: str
    success: bool
    session_used: str
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class BulkSendResult:
    """Result of a bulk send operation"""
    total: int
    succeeded: int
    failed: int
    results: Dict[str, MessageResult]
    duration: float
    operation_id: str


@dataclass
class ValidationError:
    """Represents a validation error"""
    field: str
    value: Any
    rule: str
    message: str


@dataclass
class ValidationResult:
    """Result of validation"""
    valid: bool
    errors: List[ValidationError] = field(default_factory=list)


@dataclass
class SendPreview:
    """Preview of a message sending operation"""
    recipients: List[str]
    recipient_count: int
    session_distribution: Dict[str, int]
    estimated_duration: float
    validation_result: ValidationResult


@dataclass
class ReactionConfig:
    """Configuration for a single reaction"""
    emoji: str
    weight: int = 1
    
    def __post_init__(self):
        """Validate weight is positive"""
        if self.weight < 1:
            raise ValueError(f"Weight must be at least 1, got {self.weight}")


@dataclass
class ReactionPool:
    """Pool of reactions with weights for random selection"""
    reactions: List[ReactionConfig]
    
    def __post_init__(self):
        """Validate reaction pool"""
        if not self.reactions:
            raise ValueError("Reaction pool cannot be empty")
        
        # Validate all reactions
        validation_result = self.validate()
        if not validation_result.valid:
            error_messages = [error.message for error in validation_result.errors]
            raise ValueError(f"Invalid reaction pool: {'; '.join(error_messages)}")
    
    def select_random(self) -> str:
        """
        Select reaction using weighted random selection
        
        Returns:
            Selected emoji string
        """
        # Build weighted list
        weighted_reactions = []
        for reaction in self.reactions:
            weighted_reactions.extend([reaction.emoji] * reaction.weight)
        
        # Select randomly
        return random.choice(weighted_reactions)
    
    def select_uniform(self) -> str:
        """
        Select reaction using uniform random selection (ignoring weights)
        
        Returns:
            Selected emoji string
        """
        return random.choice([reaction.emoji for reaction in self.reactions])
    
    def validate(self) -> ValidationResult:
        """
        Validate all reactions in the pool
        
        Returns:
            ValidationResult with validation status and errors
        """
        errors = []
        
        # Check if pool is empty
        if not self.reactions:
            errors.append(ValidationError(
                field='reactions',
                value=self.reactions,
                rule='not_empty',
                message='Reaction pool cannot be empty'
            ))
            return ValidationResult(valid=False, errors=errors)
        
        # Validate each reaction
        for i, reaction in enumerate(self.reactions):
            # Validate emoji is not empty
            if not reaction.emoji or not reaction.emoji.strip():
                errors.append(ValidationError(
                    field=f'reactions[{i}].emoji',
                    value=reaction.emoji,
                    rule='not_empty',
                    message=f'Reaction emoji at index {i} cannot be empty'
                ))
            
            # Validate weight is positive
            if reaction.weight < 1:
                errors.append(ValidationError(
                    field=f'reactions[{i}].weight',
                    value=reaction.weight,
                    rule='positive_weight',
                    message=f'Reaction weight at index {i} must be at least 1, got {reaction.weight}'
                ))
            
            # Basic emoji validation - check if it's a valid unicode character
            # This is a simple check; more sophisticated validation could be added
            try:
                # Try to encode as unicode
                reaction.emoji.encode('utf-8')
            except UnicodeEncodeError:
                errors.append(ValidationError(
                    field=f'reactions[{i}].emoji',
                    value=reaction.emoji,
                    rule='valid_unicode',
                    message=f'Reaction emoji at index {i} is not valid unicode'
                ))
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors
        )


class RecipientValidator:
    """Utility class for validating recipient identifiers"""
    
    # Telegram username pattern: 5-32 characters, alphanumeric and underscores
    USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]{5,32}$')
    
    # Telegram user ID: positive integer
    # Telegram user IDs are typically 6+ digits (started around 100000)
    USER_ID_MIN = 100000  # Minimum realistic Telegram user ID
    USER_ID_MAX = 9999999999  # Telegram's max user ID
    
    @classmethod
    def validate_recipient(cls, recipient: str) -> ValidationResult:
        """
        Validate a single recipient identifier
        
        Args:
            recipient: Username (string) or user ID (string representation of int)
            
        Returns:
            ValidationResult with validation status and errors
        """
        errors = []
        
        # Check if empty
        if not recipient or not str(recipient).strip():
            errors.append(ValidationError(
                field='recipient',
                value=recipient,
                rule='not_empty',
                message='Recipient identifier cannot be empty'
            ))
            return ValidationResult(valid=False, errors=errors)
        
        recipient_str = str(recipient).strip()
        
        # Try to parse as user ID (integer)
        try:
            user_id = int(recipient_str)
            if user_id < cls.USER_ID_MIN or user_id > cls.USER_ID_MAX:
                errors.append(ValidationError(
                    field='recipient',
                    value=recipient,
                    rule='user_id_range',
                    message=f'User ID must be between {cls.USER_ID_MIN} and {cls.USER_ID_MAX}'
                ))
                return ValidationResult(valid=False, errors=errors)
            # Valid user ID
            return ValidationResult(valid=True, errors=[])
        except ValueError:
            # Not a user ID, check if valid username
            pass
        
        # Validate as username
        # Remove @ prefix if present
        if recipient_str.startswith('@'):
            recipient_str = recipient_str[1:]
        
        if not cls.USERNAME_PATTERN.match(recipient_str):
            errors.append(ValidationError(
                field='recipient',
                value=recipient,
                rule='username_format',
                message='Username must be 5-32 characters, alphanumeric and underscores only'
            ))
            return ValidationResult(valid=False, errors=errors)
        
        # Valid username
        return ValidationResult(valid=True, errors=[])
    
    @classmethod
    def validate_recipients(cls, recipients: List[str]) -> ValidationResult:
        """
        Validate a list of recipient identifiers
        
        Args:
            recipients: List of recipient identifiers
            
        Returns:
            ValidationResult with validation status and all errors
        """
        errors = []
        
        # Check if list is empty
        if not recipients:
            errors.append(ValidationError(
                field='recipients',
                value=recipients,
                rule='not_empty',
                message='Recipient list cannot be empty'
            ))
            return ValidationResult(valid=False, errors=errors)
        
        # Validate each recipient
        for i, recipient in enumerate(recipients):
            result = cls.validate_recipient(recipient)
            if not result.valid:
                # Add index information to errors
                for error in result.errors:
                    errors.append(ValidationError(
                        field=f'recipients[{i}]',
                        value=error.value,
                        rule=error.rule,
                        message=f'Index {i}: {error.message}'
                    ))
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors
        )
    
    @classmethod
    def filter_valid_recipients(cls, recipients: List[str]) -> tuple[List[str], List[str]]:
        """
        Filter recipients into valid and invalid lists
        
        Args:
            recipients: List of recipient identifiers
            
        Returns:
            Tuple of (valid_recipients, invalid_recipients)
        """
        valid = []
        invalid = []
        
        for recipient in recipients:
            result = cls.validate_recipient(recipient)
            if result.valid:
                valid.append(recipient)
            else:
                invalid.append(recipient)
        
        return valid, invalid



class MediaHandler:
    """Handles media file operations and validation"""
    
    # Supported formats
    SUPPORTED_IMAGE_FORMATS = ['jpg', 'jpeg', 'png', 'gif', 'webp']
    SUPPORTED_VIDEO_FORMATS = ['mp4', 'mov', 'avi']
    SUPPORTED_DOCUMENT_FORMATS = ['pdf', 'doc', 'docx', 'txt', 'zip']
    
    # Size limits (in bytes)
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_VIDEO_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
    MAX_DOCUMENT_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
    
    @classmethod
    def validate_format(cls, file_path: str, media_type: str) -> ValidationResult:
        """
        Validate media file format
        
        Args:
            file_path: Path to the media file
            media_type: Type of media ('image', 'video', 'document')
            
        Returns:
            ValidationResult with validation status and errors
        """
        errors = []
        
        # Check if file exists
        if not os.path.exists(file_path):
            errors.append(ValidationError(
                field='file_path',
                value=file_path,
                rule='file_exists',
                message=f'File does not exist: {file_path}'
            ))
            return ValidationResult(valid=False, errors=errors)
        
        # Get file extension
        file_extension = Path(file_path).suffix.lower().lstrip('.')
        
        # Validate based on media type
        if media_type == 'image':
            if file_extension not in cls.SUPPORTED_IMAGE_FORMATS:
                errors.append(ValidationError(
                    field='file_format',
                    value=file_extension,
                    rule='supported_format',
                    message=f'Unsupported image format: {file_extension}. Supported formats: {", ".join(cls.SUPPORTED_IMAGE_FORMATS)}'
                ))
        elif media_type == 'video':
            if file_extension not in cls.SUPPORTED_VIDEO_FORMATS:
                errors.append(ValidationError(
                    field='file_format',
                    value=file_extension,
                    rule='supported_format',
                    message=f'Unsupported video format: {file_extension}. Supported formats: {", ".join(cls.SUPPORTED_VIDEO_FORMATS)}'
                ))
        elif media_type == 'document':
            if file_extension not in cls.SUPPORTED_DOCUMENT_FORMATS:
                errors.append(ValidationError(
                    field='file_format',
                    value=file_extension,
                    rule='supported_format',
                    message=f'Unsupported document format: {file_extension}. Supported formats: {", ".join(cls.SUPPORTED_DOCUMENT_FORMATS)}'
                ))
        else:
            errors.append(ValidationError(
                field='media_type',
                value=media_type,
                rule='valid_media_type',
                message=f'Invalid media type: {media_type}. Must be one of: image, video, document'
            ))
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors
        )
    
    @classmethod
    def validate_size(cls, file_path: str, media_type: str) -> ValidationResult:
        """
        Validate media file size
        
        Args:
            file_path: Path to the media file
            media_type: Type of media ('image', 'video', 'document')
            
        Returns:
            ValidationResult with validation status and errors
        """
        errors = []
        
        # Check if file exists
        if not os.path.exists(file_path):
            errors.append(ValidationError(
                field='file_path',
                value=file_path,
                rule='file_exists',
                message=f'File does not exist: {file_path}'
            ))
            return ValidationResult(valid=False, errors=errors)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Validate based on media type
        max_size = None
        if media_type == 'image':
            max_size = cls.MAX_IMAGE_SIZE
        elif media_type == 'video':
            max_size = cls.MAX_VIDEO_SIZE
        elif media_type == 'document':
            max_size = cls.MAX_DOCUMENT_SIZE
        else:
            errors.append(ValidationError(
                field='media_type',
                value=media_type,
                rule='valid_media_type',
                message=f'Invalid media type: {media_type}. Must be one of: image, video, document'
            ))
            return ValidationResult(valid=False, errors=errors)
        
        if file_size > max_size:
            # Convert to human-readable format
            def format_size(size_bytes):
                if size_bytes < 1024:
                    return f'{size_bytes} B'
                elif size_bytes < 1024 * 1024:
                    return f'{size_bytes / 1024:.2f} KB'
                elif size_bytes < 1024 * 1024 * 1024:
                    return f'{size_bytes / (1024 * 1024):.2f} MB'
                else:
                    return f'{size_bytes / (1024 * 1024 * 1024):.2f} GB'
            
            errors.append(ValidationError(
                field='file_size',
                value=file_size,
                rule='max_size',
                message=f'File size {format_size(file_size)} exceeds maximum allowed size {format_size(max_size)} for {media_type}'
            ))
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors
        )
    
    @classmethod
    async def download_from_url(cls, url: str, media_type: str = 'image') -> str:
        """
        Download media from URL to temporary file
        
        Args:
            url: URL to download from
            media_type: Type of media for validation
            
        Returns:
            Path to temporary file
            
        Raises:
            ValueError: If URL is invalid or download fails
            ValidationError: If downloaded content is invalid
        """
        # Create temporary file
        suffix = ''
        if media_type == 'image':
            suffix = '.jpg'  # Default to jpg
        elif media_type == 'video':
            suffix = '.mp4'  # Default to mp4
        elif media_type == 'document':
            suffix = '.pdf'  # Default to pdf
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_path = temp_file.name
        temp_file.close()
        
        try:
            # Download file using urllib in a thread to avoid blocking
            def _download():
                try:
                    with urlopen(url, timeout=30) as response:
                        if response.status != 200:
                            raise ValueError(f'Failed to download from URL: HTTP {response.status}')
                        
                        # Write to temporary file
                        with open(temp_path, 'wb') as f:
                            while True:
                                chunk = response.read(8192)
                                if not chunk:
                                    break
                                f.write(chunk)
                except HTTPError as e:
                    raise ValueError(f'HTTP error {e.code}: {e.reason}')
                except URLError as e:
                    raise ValueError(f'URL error: {e.reason}')
            
            # Run download in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _download)
            
            # Try to detect actual format from content if possible
            # For now, we'll rely on the file extension from URL or default
            
            return temp_path
            
        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise ValueError(f'Failed to download from URL: {str(e)}')
    
    @classmethod
    def cleanup_temp_files(cls, file_paths: List[str]) -> None:
        """
        Clean up temporary files
        
        Args:
            file_paths: List of file paths to delete
        """
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception as e:
                # Log error but don't raise - cleanup is best effort
                print(f'Warning: Failed to cleanup temporary file {file_path}: {str(e)}')



class CSVProcessor:
    """Handles CSV file parsing with streaming support"""
    
    # Streaming threshold: 100MB
    STREAMING_THRESHOLD = 100 * 1024 * 1024  # 100MB
    
    @classmethod
    def should_use_streaming(cls, csv_path: str) -> bool:
        """
        Determine if streaming should be used based on file size
        
        Args:
            csv_path: Path to the CSV file
            
        Returns:
            True if file size exceeds streaming threshold, False otherwise
            
        Raises:
            FileNotFoundError: If file does not exist
        """
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f'CSV file does not exist: {csv_path}')
        
        file_size = os.path.getsize(csv_path)
        return file_size > cls.STREAMING_THRESHOLD
    
    @classmethod
    async def parse_in_memory(cls, csv_path: str) -> List[str]:
        """
        Parse CSV file in memory for small files
        
        Args:
            csv_path: Path to the CSV file
            
        Returns:
            List of user identifiers extracted from CSV
            
        Raises:
            FileNotFoundError: If file does not exist
            ValueError: If CSV format is invalid
        """
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f'CSV file does not exist: {csv_path}')
        
        user_identifiers = []
        
        def _parse():
            """Synchronous parsing function to run in executor"""
            identifiers = []
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    
                    # Try to detect if first row is header
                    first_row = next(reader, None)
                    if first_row is None:
                        return identifiers
                    
                    # Check if first row looks like a header
                    # Headers typically contain exact words like 'username', 'user_id', 'phone', etc.
                    # Must be an exact match (case-insensitive) to avoid false positives
                    header_indicators = {'username', 'user_id', 'userid', 'phone', 'identifier', 'user', 'id', 'name'}
                    is_header = any(
                        str(cell).strip().lower() in header_indicators
                        for cell in first_row
                    )
                    
                    # If not a header, process the first row
                    if not is_header:
                        # Extract first non-empty cell as identifier
                        for cell in first_row:
                            cell_str = str(cell).strip()
                            if cell_str:
                                identifiers.append(cell_str)
                                break
                    
                    # Process remaining rows
                    for row_num, row in enumerate(reader, start=2 if is_header else 1):
                        try:
                            # Extract first non-empty cell as identifier
                            for cell in row:
                                cell_str = str(cell).strip()
                                if cell_str:
                                    identifiers.append(cell_str)
                                    break
                        except Exception as e:
                            # Log malformed row but continue processing
                            print(f'Warning: Malformed CSV row {row_num}: {e}')
                            continue
                
                return identifiers
                
            except Exception as e:
                raise ValueError(f'Failed to parse CSV file: {str(e)}')
        
        # Run parsing in executor to avoid blocking
        loop = asyncio.get_event_loop()
        user_identifiers = await loop.run_in_executor(None, _parse)
        
        return user_identifiers
    
    @classmethod
    async def parse_streaming(cls, csv_path: str, batch_size: int = 1000) -> AsyncIterator[List[str]]:
        """
        Parse CSV file using streaming for large files
        
        Args:
            csv_path: Path to the CSV file
            batch_size: Number of identifiers to yield per batch
            
        Yields:
            Batches of user identifiers
            
        Raises:
            FileNotFoundError: If file does not exist
            ValueError: If CSV format is invalid
        """
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f'CSV file does not exist: {csv_path}')
        
        def _parse_batch():
            """Generator function for synchronous parsing"""
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    
                    # Try to detect if first row is header
                    first_row = next(reader, None)
                    if first_row is None:
                        return
                    
                    # Check if first row looks like a header
                    header_indicators = {'username', 'user_id', 'userid', 'phone', 'identifier', 'user', 'id', 'name'}
                    is_header = any(
                        str(cell).strip().lower() in header_indicators
                        for cell in first_row
                    )
                    
                    batch = []
                    
                    # If not a header, process the first row
                    if not is_header:
                        for cell in first_row:
                            cell_str = str(cell).strip()
                            if cell_str:
                                batch.append(cell_str)
                                break
                    
                    # Process remaining rows
                    row_num = 2 if is_header else 1
                    for row in reader:
                        row_num += 1
                        try:
                            # Extract first non-empty cell as identifier
                            for cell in row:
                                cell_str = str(cell).strip()
                                if cell_str:
                                    batch.append(cell_str)
                                    break
                            
                            # Yield batch when it reaches batch_size
                            if len(batch) >= batch_size:
                                yield batch
                                batch = []
                                
                        except Exception as e:
                            # Log malformed row but continue processing
                            print(f'Warning: Malformed CSV row {row_num}: {e}')
                            continue
                    
                    # Yield remaining items
                    if batch:
                        yield batch
                        
            except Exception as e:
                raise ValueError(f'Failed to parse CSV file: {str(e)}')
        
        # Run parsing in executor and yield batches
        loop = asyncio.get_event_loop()
        
        # Create a queue to pass batches from executor to async context
        queue = asyncio.Queue()
        
        async def _producer():
            """Producer that runs sync generator in executor"""
            try:
                for batch in await loop.run_in_executor(None, lambda: list(_parse_batch())):
                    await queue.put(batch)
            except Exception as e:
                await queue.put(e)
            finally:
                await queue.put(None)  # Sentinel to indicate completion
        
        # Start producer task
        producer_task = asyncio.create_task(_producer())
        
        try:
            # Consume batches from queue
            while True:
                batch = await queue.get()
                
                if batch is None:
                    # Sentinel received, we're done
                    break
                
                if isinstance(batch, Exception):
                    # Error occurred in producer
                    raise batch
                
                yield batch
        finally:
            # Ensure producer task is cleaned up
            if not producer_task.done():
                producer_task.cancel()
                try:
                    await producer_task
                except asyncio.CancelledError:
                    pass
    
    @classmethod
    async def parse_csv(
        cls,
        csv_path: str,
        batch_size: int = 1000
    ) -> AsyncIterator[List[str]]:
        """
        Parse CSV file, automatically choosing between in-memory and streaming
        
        Args:
            csv_path: Path to the CSV file
            batch_size: Number of identifiers per batch (for streaming)
            
        Yields:
            Batches of user identifiers (single batch for in-memory parsing)
            
        Raises:
            FileNotFoundError: If file does not exist
            ValueError: If CSV format is invalid
        """
        if cls.should_use_streaming(csv_path):
            # Use streaming for large files
            async for batch in cls.parse_streaming(csv_path, batch_size):
                yield batch
        else:
            # Use in-memory parsing for small files
            identifiers = await cls.parse_in_memory(csv_path)
            # Yield as single batch
            if identifiers:
                yield identifiers


@dataclass
class OperationProgress:
    """Tracks progress of a bulk operation"""
    operation_id: str
    total_items: int
    completed_items: int
    failed_items: int
    checkpoint_file: str
    start_time: float
    
    def percentage_complete(self) -> float:
        """
        Calculate percentage of completion
        
        Returns:
            Percentage complete (0-100)
        """
        if self.total_items == 0:
            return 100.0
        return (self.completed_items / self.total_items) * 100.0
    
    def estimated_time_remaining(self) -> float:
        """
        Calculate estimated time remaining in seconds
        
        Returns:
            Estimated seconds remaining, or 0 if no progress yet
        """
        if self.completed_items == 0:
            return 0.0
        
        elapsed_time = time.time() - self.start_time
        time_per_item = elapsed_time / self.completed_items
        remaining_items = self.total_items - self.completed_items
        
        return time_per_item * remaining_items


class ProgressTracker:
    """Manages progress tracking and checkpointing for bulk operations"""
    
    def __init__(self, checkpoint_dir: str = '.checkpoints'):
        """
        Initialize progress tracker
        
        Args:
            checkpoint_dir: Directory to store checkpoint files
        """
        self.checkpoint_dir = checkpoint_dir
        self._progress_cache: Dict[str, OperationProgress] = {}
        
        # Create checkpoint directory if it doesn't exist
        os.makedirs(self.checkpoint_dir, exist_ok=True)
    
    def _get_checkpoint_path(self, operation_id: str) -> str:
        """
        Get the checkpoint file path for an operation
        
        Args:
            operation_id: Unique operation identifier
            
        Returns:
            Path to checkpoint file
        """
        return os.path.join(self.checkpoint_dir, f'{operation_id}.json')
    
    async def create_checkpoint(self, operation_id: str, total_items: int) -> str:
        """
        Create a new checkpoint file for an operation
        
        Args:
            operation_id: Unique operation identifier
            total_items: Total number of items to process
            
        Returns:
            Path to created checkpoint file
        """
        checkpoint_path = self._get_checkpoint_path(operation_id)
        
        # Create checkpoint data
        checkpoint_data = {
            'operation_id': operation_id,
            'total_items': total_items,
            'completed_items': 0,
            'failed_items': 0,
            'start_time': time.time(),
            'completed_recipients': [],
            'failed_recipients': []
        }
        
        # Write checkpoint file
        def _write():
            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, indent=2)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _write)
        
        # Cache progress
        self._progress_cache[operation_id] = OperationProgress(
            operation_id=operation_id,
            total_items=total_items,
            completed_items=0,
            failed_items=0,
            checkpoint_file=checkpoint_path,
            start_time=checkpoint_data['start_time']
        )
        
        return checkpoint_path
    
    async def update_checkpoint(
        self,
        operation_id: str,
        completed: List[str],
        failed: Optional[List[str]] = None
    ) -> None:
        """
        Update checkpoint file with completed recipients
        
        Args:
            operation_id: Unique operation identifier
            completed: List of successfully completed recipient identifiers
            failed: Optional list of failed recipient identifiers
        """
        checkpoint_path = self._get_checkpoint_path(operation_id)
        
        if not os.path.exists(checkpoint_path):
            raise FileNotFoundError(f'Checkpoint file not found: {checkpoint_path}')
        
        failed = failed or []
        
        def _update():
            # Read existing checkpoint
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
            
            # Update with new completed recipients
            checkpoint_data['completed_recipients'].extend(completed)
            checkpoint_data['completed_items'] = len(checkpoint_data['completed_recipients'])
            
            # Update with failed recipients if provided
            if failed:
                checkpoint_data['failed_recipients'].extend(failed)
                checkpoint_data['failed_items'] = len(checkpoint_data['failed_recipients'])
            
            # Write updated checkpoint
            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, indent=2)
            
            return checkpoint_data
        
        loop = asyncio.get_event_loop()
        checkpoint_data = await loop.run_in_executor(None, _update)
        
        # Update cache
        if operation_id in self._progress_cache:
            progress = self._progress_cache[operation_id]
            progress.completed_items = checkpoint_data['completed_items']
            progress.failed_items = checkpoint_data['failed_items']
    
    async def load_checkpoint(self, operation_id: str) -> Set[str]:
        """
        Load checkpoint and return set of completed recipient identifiers
        
        Args:
            operation_id: Unique operation identifier
            
        Returns:
            Set of completed recipient identifiers
            
        Raises:
            FileNotFoundError: If checkpoint file doesn't exist
        """
        checkpoint_path = self._get_checkpoint_path(operation_id)
        
        if not os.path.exists(checkpoint_path):
            raise FileNotFoundError(f'Checkpoint file not found: {checkpoint_path}')
        
        def _load():
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
            return checkpoint_data
        
        loop = asyncio.get_event_loop()
        checkpoint_data = await loop.run_in_executor(None, _load)
        
        # Update cache
        self._progress_cache[operation_id] = OperationProgress(
            operation_id=operation_id,
            total_items=checkpoint_data['total_items'],
            completed_items=checkpoint_data['completed_items'],
            failed_items=checkpoint_data['failed_items'],
            checkpoint_file=checkpoint_path,
            start_time=checkpoint_data['start_time']
        )
        
        # Return set of completed recipients
        return set(checkpoint_data['completed_recipients'])
    
    async def remove_checkpoint(self, operation_id: str) -> None:
        """
        Remove checkpoint file for completed operation
        
        Args:
            operation_id: Unique operation identifier
        """
        checkpoint_path = self._get_checkpoint_path(operation_id)
        
        def _remove():
            if os.path.exists(checkpoint_path):
                os.unlink(checkpoint_path)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _remove)
        
        # Remove from cache
        if operation_id in self._progress_cache:
            del self._progress_cache[operation_id]
    
    def get_progress(self, operation_id: str) -> Optional[OperationProgress]:
        """
        Get current progress for an operation
        
        Args:
            operation_id: Unique operation identifier
            
        Returns:
            OperationProgress if operation exists, None otherwise
        """
        return self._progress_cache.get(operation_id)



class OperationPriority(Enum):
    """Priority levels for operations"""
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class QueuedOperation:
    """Represents a queued operation"""
    operation_id: str
    priority: OperationPriority
    operation_func: Callable
    args: tuple
    kwargs: dict
    timestamp: float = field(default_factory=time.time)


class OperationQueue:
    """Priority queue for operations with FIFO ordering within each priority level"""
    
    def __init__(self):
        """Initialize operation queue with separate queues per priority"""
        self.queues = {
            OperationPriority.HIGH: deque(),
            OperationPriority.NORMAL: deque(),
            OperationPriority.LOW: deque()
        }
    
    def enqueue(self, operation: QueuedOperation) -> None:
        """
        Add operation to appropriate priority queue
        
        Args:
            operation: QueuedOperation to enqueue
        """
        if not isinstance(operation.priority, OperationPriority):
            raise ValueError(f"Invalid priority: {operation.priority}. Must be OperationPriority enum value")
        
        self.queues[operation.priority].append(operation)
    
    def dequeue(self) -> Optional[QueuedOperation]:
        """
        Retrieve highest-priority operation (HIGH > NORMAL > LOW)
        Within same priority, operations are dequeued in FIFO order
        
        Returns:
            QueuedOperation if queue is not empty, None otherwise
        """
        # Check queues in priority order
        for priority in [OperationPriority.HIGH, OperationPriority.NORMAL, OperationPriority.LOW]:
            if self.queues[priority]:
                return self.queues[priority].popleft()
        
        return None
    
    def is_empty(self) -> bool:
        """
        Check if all queues are empty
        
        Returns:
            True if all queues are empty, False otherwise
        """
        return all(len(queue) == 0 for queue in self.queues.values())
    
    def size(self) -> int:
        """
        Get total number of operations across all priority queues
        
        Returns:
            Total number of queued operations
        """
        return sum(len(queue) for queue in self.queues.values())
