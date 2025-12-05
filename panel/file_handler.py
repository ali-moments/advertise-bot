"""
File Handler - Centralized file operations for CSV and media files

Handles:
- CSV file upload and validation (Requirements: 7.1, 7.2, 7.3, 13.2)
- Media file upload and validation (Requirements: 7.4, 7.5, 7.6, 7.7)
- CSV generation from scraping results (Requirements: 7.3)
- File cleanup utilities (Requirements: 7.1-7.7)

This module provides comprehensive file handling for the Telegram Bot Control Panel,
including validation, processing, and cleanup of CSV and media files.
"""

import os
import csv
import logging
import mimetypes
import time
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path

# Import validators for additional validation
try:
    from .validators import InputValidator
except ImportError:
    # Fallback if validators not available
    InputValidator = None


@dataclass
class FileValidationResult:
    """Result of file validation"""
    valid: bool
    error: Optional[str] = None
    file_size: int = 0
    file_type: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class CSVValidationResult(FileValidationResult):
    """Result of CSV validation with additional CSV-specific data"""
    row_count: int = 0
    column_count: int = 0
    columns: List[str] = None
    recipients: List[str] = None
    sample_data: List[List[str]] = None
    
    def __post_init__(self):
        super().__post_init__()
        if self.columns is None:
            self.columns = []
        if self.recipients is None:
            self.recipients = []
        if self.sample_data is None:
            self.sample_data = []


class FileHandler:
    """
    Centralized file operations handler
    
    Provides validation and processing for:
    - CSV files (recipient lists)
    - Media files (images, videos, documents)
    - File cleanup and temporary file management
    
    Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7
    """
    
    # File size limits (in bytes) - Requirements: 7.1, 7.4, 7.5, 7.6
    MAX_CSV_SIZE = 20 * 1024 * 1024  # 20 MB (Requirement 7.1)
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB (Requirement 7.4)
    MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50 MB (Requirement 7.5)
    MAX_DOCUMENT_SIZE = 20 * 1024 * 1024  # 20 MB (Requirement 7.6)
    
    # Allowed file extensions - Requirements: 7.4, 7.5, 7.6
    ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}  # Requirement 7.4
    ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.mov'}  # Requirement 7.5
    ALLOWED_DOCUMENT_EXTENSIONS = {'.pdf', '.doc', '.docx', '.txt'}  # Requirement 7.6
    
    def __init__(self, temp_dir: str = "./temp"):
        """
        Initialize file handler
        
        Args:
            temp_dir: Directory for temporary file storage
        """
        self.temp_dir = temp_dir
        self.logger = logging.getLogger("FileHandler")
        
        # Track temporary files for cleanup
        self._temp_files: List[str] = []
        
        # Create temp directory if it doesn't exist
        os.makedirs(self.temp_dir, exist_ok=True)
        
        self.logger.info(f"FileHandler initialized with temp_dir: {self.temp_dir}")
    
    def validate_csv(self, file_path: str) -> CSVValidationResult:
        """
        Validate CSV file format and content
        
        Checks:
        - File exists and is readable
        - File size within limits
        - Valid CSV format
        - Has at least one column
        - Has at least one row of data
        - Extracts recipient list from first column
        
        Args:
            file_path: Path to CSV file
        
        Returns:
            CSVValidationResult with validation status and data
            
        Requirements: AC-7.2
        """
        try:
            # Check file exists
            if not os.path.exists(file_path):
                return CSVValidationResult(
                    valid=False,
                    error="فایل یافت نشد"
                )
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > self.MAX_CSV_SIZE:
                return CSVValidationResult(
                    valid=False,
                    error=f"حجم فایل بیش از حد مجاز است (حداکثر {self.MAX_CSV_SIZE // (1024*1024)} MB)",
                    file_size=file_size
                )
            
            if file_size == 0:
                return CSVValidationResult(
                    valid=False,
                    error="فایل خالی است",
                    file_size=0
                )
            
            # Try to read and parse CSV
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)
            
            if not rows:
                return CSVValidationResult(
                    valid=False,
                    error="فایل CSV خالی است",
                    file_size=file_size
                )
            
            # Get column count from first row
            column_count = len(rows[0]) if rows else 0
            
            if column_count == 0:
                return CSVValidationResult(
                    valid=False,
                    error="فایل CSV هیچ ستونی ندارد",
                    file_size=file_size
                )
            
            # Extract recipients from first column
            recipients = []
            for row in rows:
                if row and len(row) > 0 and row[0].strip():
                    recipients.append(row[0].strip())
            
            if not recipients:
                return CSVValidationResult(
                    valid=False,
                    error="هیچ گیرنده معتبری در فایل یافت نشد",
                    file_size=file_size,
                    row_count=len(rows),
                    column_count=column_count
                )
            
            # Get column names (if first row looks like headers)
            columns = []
            if rows and all(isinstance(cell, str) and not cell.isdigit() for cell in rows[0]):
                columns = rows[0]
            
            # Get sample data (first 3 rows)
            sample_data = rows[:3]
            
            return CSVValidationResult(
                valid=True,
                error=None,
                file_size=file_size,
                file_type='text/csv',
                row_count=len(rows),
                column_count=column_count,
                columns=columns,
                recipients=recipients,
                sample_data=sample_data,
                metadata={
                    'total_recipients': len(recipients),
                    'has_headers': bool(columns)
                }
            )
        
        except UnicodeDecodeError:
            return CSVValidationResult(
                valid=False,
                error=(
                    "❌ فایل دارای کاراکترهای نامعتبر است\n\n"
                    "لطفاً از کدگذاری UTF-8 استفاده کنید.\n"
                    "در Excel: ذخیره به عنوان → CSV UTF-8"
                )
            )
        except csv.Error as e:
            return CSVValidationResult(
                valid=False,
                error=(
                    f"❌ فرمت CSV نامعتبر است\n\n"
                    f"خطا: {str(e)}\n\n"
                    "فایل باید فرمت CSV استاندارد داشته باشد.\n"
                    "مثال:\n"
                    "@username1\n"
                    "@username2\n"
                    "123456789"
                )
            )
        except Exception as e:
            self.logger.error(f"Error validating CSV: {e}")
            return CSVValidationResult(
                valid=False,
                error=f"خطا در اعتبارسنجی فایل: {str(e)}"
            )
    
    def validate_media(
        self,
        file_path: str,
        media_type: str
    ) -> FileValidationResult:
        """
        Validate media file (image, video, document)
        
        Checks:
        - File exists and is readable
        - File size within limits for media type
        - File extension is allowed for media type
        
        Args:
            file_path: Path to media file
            media_type: Type of media ('image', 'video', 'document')
        
        Returns:
            FileValidationResult with validation status
            
        Requirements: AC-7.5
        """
        try:
            # Check file exists
            if not os.path.exists(file_path):
                return FileValidationResult(
                    valid=False,
                    error="فایل یافت نشد"
                )
            
            # Get file info
            file_size = os.path.getsize(file_path)
            file_ext = Path(file_path).suffix.lower()
            
            # Check file size based on media type
            if media_type == 'image':
                max_size = self.MAX_IMAGE_SIZE
                allowed_extensions = self.ALLOWED_IMAGE_EXTENSIONS
                media_name = "تصویر"
            elif media_type == 'video':
                max_size = self.MAX_VIDEO_SIZE
                allowed_extensions = self.ALLOWED_VIDEO_EXTENSIONS
                media_name = "ویدیو"
            elif media_type == 'document':
                max_size = self.MAX_DOCUMENT_SIZE
                allowed_extensions = self.ALLOWED_DOCUMENT_EXTENSIONS
                media_name = "فایل"
            else:
                return FileValidationResult(
                    valid=False,
                    error=(
                        f"❌ نوع رسانه نامعتبر: {media_type}\n\n"
                        "انواع معتبر:\n"
                        "• image: JPEG, PNG, WebP\n"
                        "• video: MP4, MOV\n"
                        "• document: PDF, DOC, DOCX, TXT"
                    )
                )
            
            if file_size > max_size:
                max_size_mb = max_size // (1024 * 1024)
                return FileValidationResult(
                    valid=False,
                    error=f"حجم {media_name} بیش از حد مجاز است (حداکثر {max_size_mb} MB)",
                    file_size=file_size
                )
            
            if file_size == 0:
                return FileValidationResult(
                    valid=False,
                    error=f"{media_name} خالی است",
                    file_size=0
                )
            
            # Check file extension
            if file_ext not in allowed_extensions:
                allowed_str = ', '.join(allowed_extensions)
                return FileValidationResult(
                    valid=False,
                    error=f"فرمت {media_name} پشتیبانی نمی‌شود. فرمت‌های مجاز: {allowed_str}",
                    file_size=file_size,
                    file_type=file_ext
                )
            
            return FileValidationResult(
                valid=True,
                error=None,
                file_size=file_size,
                file_type=file_ext,
                metadata={
                    'media_type': media_type,
                    'extension': file_ext,
                    'size_mb': round(file_size / (1024 * 1024), 2)
                }
            )
        
        except Exception as e:
            self.logger.error(f"Error validating media file: {e}")
            return FileValidationResult(
                valid=False,
                error=f"خطا در اعتبارسنجی فایل: {str(e)}"
            )
    
    def cleanup_file(self, file_path: str) -> bool:
        """
        Delete a temporary file
        
        Args:
            file_path: Path to file to delete
        
        Returns:
            True if file was deleted, False otherwise
        """
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                self.logger.info(f"Cleaned up file: {file_path}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error cleaning up file {file_path}: {e}")
            return False
    
    def get_temp_file_path(self, user_id: int, file_type: str, extension: str) -> str:
        """
        Generate a temporary file path
        
        Args:
            user_id: User ID for unique naming
            file_type: Type of file (csv, image, video, document)
            extension: File extension (with or without dot)
        
        Returns:
            Full path to temporary file
        """
        import time
        
        # Ensure extension has dot
        if not extension.startswith('.'):
            extension = f'.{extension}'
        
        timestamp = int(time.time())
        filename = f"{file_type}_{user_id}_{timestamp}{extension}"
        
        return os.path.join(self.temp_dir, filename)
    
    def read_csv_recipients(self, file_path: str) -> List[str]:
        """
        Read recipient list from CSV file
        
        Extracts values from first column, skipping empty rows
        
        Args:
            file_path: Path to CSV file
        
        Returns:
            List of recipient identifiers
        """
        recipients = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row and row[0].strip():
                        recipients.append(row[0].strip())
        except Exception as e:
            self.logger.error(f"Error reading CSV recipients: {e}")
        
        return recipients
    
    def create_csv_from_data(
        self,
        data: List[List[str]],
        output_path: str,
        headers: Optional[List[str]] = None
    ) -> bool:
        """
        Create a CSV file from data
        
        Args:
            data: List of rows (each row is a list of values)
            output_path: Path where CSV should be saved
            headers: Optional column headers
        
        Returns:
            True if file was created successfully
            
        Requirements: 7.3
        """
        try:
            with open(output_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                
                # Write headers if provided
                if headers:
                    writer.writerow(headers)
                
                # Write data rows
                writer.writerows(data)
            
            self.logger.info(f"Created CSV file: {output_path} with {len(data)} rows")
            return True
        
        except Exception as e:
            self.logger.error(f"Error creating CSV file: {e}")
            return False
    
    async def process_csv_upload(
        self,
        file_path: str,
        user_id: int
    ) -> Tuple[bool, Union[List[str], str]]:
        """
        Process uploaded CSV file
        
        Validates the CSV file and extracts recipient list.
        
        Args:
            file_path: Path to uploaded CSV file
            user_id: User ID for tracking
        
        Returns:
            Tuple of (success, recipients_or_error)
            - If success: (True, List[str] of recipients)
            - If failure: (False, error_message)
            
        Requirements: 7.1, 7.2, 13.2, 13.5
        """
        self.logger.info(f"Processing CSV upload for user {user_id}: {file_path}")
        
        # Validate CSV format and structure
        validation_result = self.validate_csv(file_path)
        
        if not validation_result.valid:
            self.logger.warning(f"CSV validation failed: {validation_result.error}")
            return False, validation_result.error
        
        # Additional validation using InputValidator if available
        if InputValidator:
            recipient_validation = InputValidator.validate_csv_recipients(
                validation_result.recipients
            )
            if not recipient_validation.valid:
                self.logger.warning(
                    f"CSV recipient validation failed: {recipient_validation.error_message}"
                )
                return False, recipient_validation.error_message
        
        # Track temp file for cleanup
        self._temp_files.append(file_path)
        
        self.logger.info(
            f"CSV validated successfully: {len(validation_result.recipients)} recipients"
        )
        
        return True, validation_result.recipients
    
    async def process_media_upload(
        self,
        file_path: str,
        media_type: str,
        user_id: int
    ) -> Tuple[bool, Union[str, str]]:
        """
        Process uploaded media file
        
        Validates the media file and performs integrity checks.
        
        Args:
            file_path: Path to uploaded media file
            media_type: Type of media ('image', 'video', 'document')
            user_id: User ID for tracking
        
        Returns:
            Tuple of (success, file_path_or_error)
            - If success: (True, file_path)
            - If failure: (False, error_message)
            
        Requirements: 7.4, 7.5, 7.6, 7.7
        """
        self.logger.info(
            f"Processing {media_type} upload for user {user_id}: {file_path}"
        )
        
        # Validate media file
        validation_result = self.validate_media(file_path, media_type)
        
        if not validation_result.valid:
            self.logger.warning(f"Media validation failed: {validation_result.error}")
            return False, validation_result.error
        
        # Perform integrity check
        integrity_result = self._check_media_integrity(file_path, media_type)
        
        if not integrity_result.valid:
            self.logger.warning(f"Media integrity check failed: {integrity_result.error}")
            return False, integrity_result.error
        
        # Track temp file for cleanup
        self._temp_files.append(file_path)
        
        self.logger.info(
            f"Media validated successfully: {media_type} "
            f"({validation_result.metadata.get('size_mb', 0)} MB)"
        )
        
        return True, file_path
    
    def _check_media_integrity(
        self,
        file_path: str,
        media_type: str
    ) -> FileValidationResult:
        """
        Check media file integrity
        
        Performs basic integrity checks:
        - File can be opened
        - File has valid header/magic bytes
        - File is not corrupted
        
        Args:
            file_path: Path to media file
            media_type: Type of media ('image', 'video', 'document')
        
        Returns:
            FileValidationResult with integrity check status
            
        Requirements: 7.7
        """
        try:
            # Check if file can be opened and read
            with open(file_path, 'rb') as f:
                # Read first few bytes to check magic numbers
                header = f.read(16)
                
                if not header:
                    return FileValidationResult(
                        valid=False,
                        error="فایل خراب است (هدر خالی)"
                    )
                
                # Basic magic number checks
                if media_type == 'image':
                    # Check for common image formats
                    if header[:2] == b'\xff\xd8':  # JPEG
                        pass
                    elif header[:8] == b'\x89PNG\r\n\x1a\n':  # PNG
                        pass
                    elif header[:6] in (b'GIF87a', b'GIF89a'):  # GIF
                        pass
                    elif header[:4] == b'RIFF' and header[8:12] == b'WEBP':  # WebP
                        pass
                    else:
                        return FileValidationResult(
                            valid=False,
                            error=(
                                "❌ فرمت تصویر نامعتبر یا فایل خراب است\n\n"
                                "فرمت‌های پشتیبانی شده:\n"
                                "• JPEG (.jpg, .jpeg)\n"
                                "• PNG (.png)\n"
                                "• WebP (.webp)\n\n"
                                "لطفاً فایل را بررسی کنید و دوباره آپلود کنید."
                            )
                        )
                
                elif media_type == 'video':
                    # Check for common video formats
                    # MP4/MOV typically start with ftyp
                    if b'ftyp' not in header[:16]:
                        # Some videos might have different headers, be lenient
                        self.logger.warning(
                            f"Video file may have non-standard header: {file_path}"
                        )
                
                elif media_type == 'document':
                    # Check for common document formats
                    if header[:4] == b'%PDF':  # PDF
                        pass
                    elif header[:2] == b'PK':  # ZIP-based (DOCX)
                        pass
                    # For other document types, just check it's not empty
                
                # Try to seek to end to ensure file is complete
                f.seek(0, 2)  # Seek to end
                file_size = f.tell()
                
                if file_size == 0:
                    return FileValidationResult(
                        valid=False,
                        error="فایل خالی است"
                    )
            
            return FileValidationResult(
                valid=True,
                error=None,
                metadata={'integrity_checked': True}
            )
        
        except IOError as e:
            return FileValidationResult(
                valid=False,
                error=f"خطا در خواندن فایل: {str(e)}"
            )
        except Exception as e:
            self.logger.error(f"Error checking media integrity: {e}")
            return FileValidationResult(
                valid=False,
                error=f"خطا در بررسی یکپارچگی فایل: {str(e)}"
            )
    
    def generate_csv_from_scraping_results(
        self,
        results: List[Dict[str, Any]],
        output_path: str
    ) -> bool:
        """
        Generate CSV file from scraping results
        
        Creates a CSV file with member data from scraping operations.
        
        Args:
            results: List of member dictionaries with keys like:
                     'user_id', 'username', 'first_name', 'last_name', 'phone'
            output_path: Path where CSV should be saved
        
        Returns:
            True if file was created successfully
            
        Requirements: 7.3
        """
        try:
            if not results:
                self.logger.warning("No results to generate CSV from")
                return False
            
            # Define headers based on available fields
            headers = ['user_id', 'username', 'first_name', 'last_name', 'phone']
            
            # Convert results to rows
            rows = []
            for member in results:
                row = [
                    str(member.get('user_id', '')),
                    member.get('username', ''),
                    member.get('first_name', ''),
                    member.get('last_name', ''),
                    member.get('phone', '')
                ]
                rows.append(row)
            
            # Create CSV file
            success = self.create_csv_from_data(rows, output_path, headers)
            
            if success:
                self.logger.info(
                    f"Generated CSV from scraping results: {len(rows)} members"
                )
            
            return success
        
        except Exception as e:
            self.logger.error(f"Error generating CSV from scraping results: {e}")
            return False
    
    def cleanup_temp_files(self, file_paths: Optional[List[str]] = None) -> int:
        """
        Clean up temporary files
        
        Deletes specified files or all tracked temporary files.
        
        Args:
            file_paths: Optional list of specific files to delete.
                       If None, deletes all tracked temp files.
        
        Returns:
            Number of files successfully deleted
            
        Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
        """
        files_to_delete = file_paths if file_paths is not None else self._temp_files
        deleted_count = 0
        
        for file_path in files_to_delete:
            if self.cleanup_file(file_path):
                deleted_count += 1
                # Remove from tracked files
                if file_path in self._temp_files:
                    self._temp_files.remove(file_path)
        
        if deleted_count > 0:
            self.logger.info(f"Cleaned up {deleted_count} temporary files")
        
        return deleted_count
    
    def cleanup_on_error(self, user_id: int) -> int:
        """
        Clean up all temporary files for a specific user on error
        
        Args:
            user_id: User ID whose files should be cleaned up
        
        Returns:
            Number of files successfully deleted
            
        Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
        """
        user_files = [
            f for f in self._temp_files
            if f"_{user_id}_" in f
        ]
        
        deleted_count = self.cleanup_temp_files(user_files)
        
        if deleted_count > 0:
            self.logger.info(
                f"Cleaned up {deleted_count} files for user {user_id} on error"
            )
        
        return deleted_count
    
    def get_tracked_files(self) -> List[str]:
        """
        Get list of currently tracked temporary files
        
        Returns:
            List of file paths being tracked
        """
        return self._temp_files.copy()
    
    def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """
        Clean up old temporary files based on age
        
        Args:
            max_age_hours: Maximum age in hours before file is deleted
        
        Returns:
            Number of files successfully deleted
        """
        deleted_count = 0
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        try:
            # Check all files in temp directory
            for filename in os.listdir(self.temp_dir):
                file_path = os.path.join(self.temp_dir, filename)
                
                # Skip if not a file
                if not os.path.isfile(file_path):
                    continue
                
                # Check file age
                file_age = current_time - os.path.getmtime(file_path)
                
                if file_age > max_age_seconds:
                    if self.cleanup_file(file_path):
                        deleted_count += 1
            
            if deleted_count > 0:
                self.logger.info(
                    f"Cleaned up {deleted_count} old files (>{max_age_hours}h)"
                )
        
        except Exception as e:
            self.logger.error(f"Error cleaning up old files: {e}")
        
        return deleted_count
    
    async def send_file_to_user(
        self,
        bot,
        chat_id: int,
        file_path: str,
        caption: str = ""
    ) -> bool:
        """
        Send a file to a user via Telegram
        
        This is a helper method for sending CSV files or other documents
        to users through the bot.
        
        Args:
            bot: Telegram Bot instance
            chat_id: Chat ID to send file to
            file_path: Path to file to send
            caption: Optional caption for the file
        
        Returns:
            True if file was sent successfully
            
        Requirements: 7.3
        """
        try:
            if not os.path.exists(file_path):
                self.logger.error(f"File not found: {file_path}")
                return False
            
            # Determine file type based on extension
            file_ext = Path(file_path).suffix.lower()
            
            with open(file_path, 'rb') as f:
                if file_ext == '.csv':
                    # Send as document
                    await bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        caption=caption,
                        filename=os.path.basename(file_path)
                    )
                elif file_ext in self.ALLOWED_IMAGE_EXTENSIONS:
                    # Send as photo
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=f,
                        caption=caption
                    )
                elif file_ext in self.ALLOWED_VIDEO_EXTENSIONS:
                    # Send as video
                    await bot.send_video(
                        chat_id=chat_id,
                        video=f,
                        caption=caption
                    )
                else:
                    # Send as document
                    await bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        caption=caption,
                        filename=os.path.basename(file_path)
                    )
            
            self.logger.info(f"Sent file to user {chat_id}: {file_path}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error sending file to user: {e}")
            return False
