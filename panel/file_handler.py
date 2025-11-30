"""
File Handler - Centralized file operations for CSV and media files

Handles:
- CSV file upload and validation (AC-7.1, AC-7.2)
- Media file upload and validation (AC-7.4, AC-7.5)
- CSV file download/send (AC-7.3)
"""

import os
import csv
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path


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
    """
    
    # File size limits (in bytes)
    MAX_CSV_SIZE = 10 * 1024 * 1024  # 10 MB
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
    MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50 MB
    MAX_DOCUMENT_SIZE = 50 * 1024 * 1024  # 50 MB
    
    # Allowed file extensions
    ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
    ALLOWED_DOCUMENT_EXTENSIONS = {'.pdf', '.doc', '.docx', '.txt', '.zip', '.rar'}
    
    def __init__(self, temp_dir: str = "./temp"):
        """
        Initialize file handler
        
        Args:
            temp_dir: Directory for temporary file storage
        """
        self.temp_dir = temp_dir
        self.logger = logging.getLogger("FileHandler")
        
        # Create temp directory if it doesn't exist
        os.makedirs(self.temp_dir, exist_ok=True)
    
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
                error="فایل دارای کاراکترهای نامعتبر است. لطفاً از UTF-8 استفاده کنید"
            )
        except csv.Error as e:
            return CSVValidationResult(
                valid=False,
                error=f"فرمت CSV نامعتبر است: {str(e)}"
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
                    error=f"نوع رسانه نامعتبر: {media_type}"
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
        """
        try:
            with open(output_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                
                # Write headers if provided
                if headers:
                    writer.writerow(headers)
                
                # Write data rows
                writer.writerows(data)
            
            self.logger.info(f"Created CSV file: {output_path}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error creating CSV file: {e}")
            return False
