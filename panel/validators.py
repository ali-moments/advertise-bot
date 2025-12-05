"""
Input Validation System - Comprehensive validation for all user inputs

Handles:
- Group identifier validation (Requirements: 13.1)
- CSV content validation (Requirements: 13.2)
- Reaction emoji validation (Requirements: 13.3)
- Range validation for delays and cooldowns (Requirements: 13.4)
- Validation error handling (Requirements: 13.5)

This module provides centralized validation logic for the Telegram Bot Control Panel,
ensuring all user inputs are properly validated before processing.
"""

import re
import unicodedata
from typing import Tuple, Optional, List
from dataclasses import dataclass
from enum import Enum


class ValidationType(Enum):
    """Types of validation"""
    GROUP_IDENTIFIER = "group_identifier"
    CSV_CONTENT = "csv_content"
    REACTION_EMOJI = "reaction_emoji"
    DELAY_RANGE = "delay_range"
    COOLDOWN_RANGE = "cooldown_range"


@dataclass
class ValidationResult:
    """Result of input validation"""
    valid: bool
    error_message: Optional[str] = None
    validation_type: Optional[ValidationType] = None
    normalized_value: Optional[str] = None
    metadata: Optional[dict] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class InputValidator:
    """
    Centralized input validation system
    
    Provides validation for:
    - Group identifiers (username, ID, invite link)
    - CSV content (recipient lists)
    - Reaction emojis (Unicode validation)
    - Numeric ranges (delays, cooldowns)
    
    Requirements: 13.1, 13.2, 13.3, 13.4, 13.5
    """
    
    # Group identifier patterns
    USERNAME_PATTERN = re.compile(r'^@?[a-zA-Z0-9_]{5,32}$')
    NUMERIC_ID_PATTERN = re.compile(r'^-?\d{5,15}$')
    INVITE_LINK_PATTERN = re.compile(
        r'^(?:https?://)?(?:t\.me/|telegram\.me/)?(?:\+|joinchat/)?([a-zA-Z0-9_-]+)$'
    )
    
    # Range limits
    MIN_DELAY = 1.0  # seconds (Requirement 13.4)
    MAX_DELAY = 10.0  # seconds (Requirement 13.4)
    MIN_COOLDOWN = 0.5  # seconds (Requirement 13.4)
    MAX_COOLDOWN = 60.0  # seconds (Requirement 13.4)
    
    @staticmethod
    def validate_group_identifier(identifier: str) -> ValidationResult:
        """
        Validate Telegram group identifier
        
        Supports three formats:
        1. Username: @groupname or groupname (5-32 alphanumeric + underscore)
        2. Numeric ID: -1001234567890 (negative for supergroups)
        3. Invite link: https://t.me/+abc123 or t.me/joinchat/abc123
        
        Args:
            identifier: Group identifier string
        
        Returns:
            ValidationResult with validation status and normalized value
            
        Requirements: AC-13.1
        
        Examples:
            >>> validate_group_identifier("@mygroup")
            ValidationResult(valid=True, normalized_value="mygroup")
            
            >>> validate_group_identifier("-1001234567890")
            ValidationResult(valid=True, normalized_value="-1001234567890")
            
            >>> validate_group_identifier("https://t.me/+abc123")
            ValidationResult(valid=True, normalized_value="+abc123")
        """
        if not identifier or not isinstance(identifier, str):
            return ValidationResult(
                valid=False,
                error_message="شناسه گروه نمی‌تواند خالی باشد",
                validation_type=ValidationType.GROUP_IDENTIFIER
            )
        
        identifier = identifier.strip()
        
        if not identifier:
            return ValidationResult(
                valid=False,
                error_message="شناسه گروه نمی‌تواند خالی باشد",
                validation_type=ValidationType.GROUP_IDENTIFIER
            )
        
        # Try to match username pattern
        if InputValidator.USERNAME_PATTERN.match(identifier):
            # Remove @ if present
            normalized = identifier.lstrip('@')
            return ValidationResult(
                valid=True,
                error_message=None,
                validation_type=ValidationType.GROUP_IDENTIFIER,
                normalized_value=normalized,
                metadata={'format': 'username'}
            )
        
        # Try to match numeric ID pattern
        if InputValidator.NUMERIC_ID_PATTERN.match(identifier):
            return ValidationResult(
                valid=True,
                error_message=None,
                validation_type=ValidationType.GROUP_IDENTIFIER,
                normalized_value=identifier,
                metadata={'format': 'numeric_id'}
            )
        
        # Try to match invite link pattern
        match = InputValidator.INVITE_LINK_PATTERN.match(identifier)
        if match:
            # Extract the invite code
            invite_code = match.group(1)
            # Preserve + prefix if present in original
            if '+' in identifier or 'joinchat' in identifier.lower():
                normalized = f"+{invite_code}" if not invite_code.startswith('+') else invite_code
            else:
                normalized = invite_code
            
            return ValidationResult(
                valid=True,
                error_message=None,
                validation_type=ValidationType.GROUP_IDENTIFIER,
                normalized_value=normalized,
                metadata={'format': 'invite_link'}
            )
        
        # No pattern matched - invalid format
        return ValidationResult(
            valid=False,
            error_message=(
                "❌ فرمت شناسه گروه نامعتبر است\n\n"
                "فرمت‌های معتبر:\n"
                "• نام کاربری: @groupname یا groupname\n"
                "• شناسه عددی: -1001234567890\n"
                "• لینک دعوت: https://t.me/+abc123\n\n"
                "مثال: @mygroup"
            ),
            validation_type=ValidationType.GROUP_IDENTIFIER
        )
    
    @staticmethod
    def validate_csv_recipients(recipients: List[str]) -> ValidationResult:
        """
        Validate CSV recipient list
        
        Checks:
        - List is not empty
        - Contains at least one valid recipient
        - Recipients are non-empty strings
        
        Args:
            recipients: List of recipient identifiers from CSV
        
        Returns:
            ValidationResult with validation status
            
        Requirements: AC-13.2
        """
        if not recipients:
            return ValidationResult(
                valid=False,
                error_message=(
                    "❌ فایل CSV خالی است\n\n"
                    "فایل باید حداقل یک گیرنده معتبر داشته باشد.\n"
                    "گیرنده‌ها باید در ستون اول فایل قرار گیرند."
                ),
                validation_type=ValidationType.CSV_CONTENT
            )
        
        # Filter out empty recipients
        valid_recipients = [r for r in recipients if r and r.strip()]
        
        if not valid_recipients:
            return ValidationResult(
                valid=False,
                error_message=(
                    "❌ هیچ گیرنده معتبری در فایل یافت نشد\n\n"
                    "فایل CSV باید حداقل یک گیرنده معتبر داشته باشد.\n"
                    "مطمئن شوید که ستون اول فایل شامل شناسه‌های گیرنده است."
                ),
                validation_type=ValidationType.CSV_CONTENT
            )
        
        return ValidationResult(
            valid=True,
            error_message=None,
            validation_type=ValidationType.CSV_CONTENT,
            metadata={
                'total_recipients': len(recipients),
                'valid_recipients': len(valid_recipients),
                'empty_rows': len(recipients) - len(valid_recipients)
            }
        )
    
    @staticmethod
    def validate_reaction_emoji(emoji: str) -> ValidationResult:
        """
        Validate reaction emoji
        
        Checks:
        - String is not empty
        - Contains valid Unicode emoji character(s)
        - Is a single emoji (not multiple)
        
        Args:
            emoji: Emoji string to validate
        
        Returns:
            ValidationResult with validation status
            
        Requirements: AC-13.3
        
        Examples:
            >>> validate_reaction_emoji("👍")
            ValidationResult(valid=True)
            
            >>> validate_reaction_emoji("❤️")
            ValidationResult(valid=True)
            
            >>> validate_reaction_emoji("abc")
            ValidationResult(valid=False, error_message="...")
        """
        if not emoji or not isinstance(emoji, str):
            return ValidationResult(
                valid=False,
                error_message="ایموجی نمی‌تواند خالی باشد",
                validation_type=ValidationType.REACTION_EMOJI
            )
        
        emoji = emoji.strip()
        
        if not emoji:
            return ValidationResult(
                valid=False,
                error_message="ایموجی نمی‌تواند خالی باشد",
                validation_type=ValidationType.REACTION_EMOJI
            )
        
        # Check if string contains emoji characters
        # Emoji characters are in specific Unicode ranges
        has_emoji = False
        char_count = 0
        
        for char in emoji:
            char_count += 1
            # Check if character is an emoji
            # Emojis are typically in these Unicode categories:
            # - Emoji_Presentation
            # - Emoji_Modifier
            # - Emoji_Component
            category = unicodedata.category(char)
            name = unicodedata.name(char, '')
            
            # Check for emoji indicators
            if (
                category == 'So' or  # Other Symbol
                'EMOJI' in name or
                'HEART' in name or
                'FACE' in name or
                'HAND' in name or
                '\U0001F300' <= char <= '\U0001F9FF' or  # Emoji range
                '\U00002600' <= char <= '\U000027BF' or  # Misc symbols
                '\U0001F600' <= char <= '\U0001F64F' or  # Emoticons
                '\U0001F680' <= char <= '\U0001F6FF' or  # Transport
                '\U00002700' <= char <= '\U000027BF' or  # Dingbats
                char == '\uFE0F' or  # Variation Selector-16 (emoji presentation)
                char == '\u200D'  # Zero Width Joiner (for combined emojis)
            ):
                has_emoji = True
        
        if not has_emoji:
            return ValidationResult(
                valid=False,
                error_message=(
                    "❌ ایموجی نامعتبر است\n\n"
                    "لطفاً یک ایموجی معتبر وارد کنید.\n"
                    "مثال: 👍 ❤️ 🔥 ⭐"
                ),
                validation_type=ValidationType.REACTION_EMOJI
            )
        
        # Check if it's too long (probably multiple emojis or text)
        # Most single emojis are 1-7 characters (including modifiers and ZWJ)
        if len(emoji) > 10:
            return ValidationResult(
                valid=False,
                error_message=(
                    "❌ لطفاً فقط یک ایموجی وارد کنید\n\n"
                    "ایموجی وارد شده بیش از حد طولانی است."
                ),
                validation_type=ValidationType.REACTION_EMOJI
            )
        
        return ValidationResult(
            valid=True,
            error_message=None,
            validation_type=ValidationType.REACTION_EMOJI,
            normalized_value=emoji,
            metadata={
                'emoji': emoji,
                'length': len(emoji),
                'char_count': char_count
            }
        )
    
    @staticmethod
    def validate_delay(delay_value: str) -> ValidationResult:
        """
        Validate message sending delay
        
        Checks:
        - Value is a valid number
        - Value is within range [1, 10] seconds
        
        Args:
            delay_value: Delay value as string
        
        Returns:
            ValidationResult with validation status and normalized float value
            
        Requirements: AC-13.4
        
        Examples:
            >>> validate_delay("5")
            ValidationResult(valid=True, normalized_value="5.0")
            
            >>> validate_delay("0.5")
            ValidationResult(valid=False, error_message="...")
        """
        if not delay_value or not isinstance(delay_value, str):
            return ValidationResult(
                valid=False,
                error_message="مقدار تاخیر نمی‌تواند خالی باشد",
                validation_type=ValidationType.DELAY_RANGE
            )
        
        delay_value = delay_value.strip()
        
        # Try to parse as float
        try:
            delay = float(delay_value)
        except ValueError:
            return ValidationResult(
                valid=False,
                error_message=(
                    "❌ مقدار تاخیر نامعتبر است\n\n"
                    "لطفاً یک عدد معتبر وارد کنید.\n"
                    "مثال: 5 یا 2.5"
                ),
                validation_type=ValidationType.DELAY_RANGE
            )
        
        # Check range
        if delay < InputValidator.MIN_DELAY or delay > InputValidator.MAX_DELAY:
            return ValidationResult(
                valid=False,
                error_message=(
                    f"❌ تاخیر باید بین {InputValidator.MIN_DELAY} تا "
                    f"{InputValidator.MAX_DELAY} ثانیه باشد\n\n"
                    f"مقدار وارد شده: {delay} ثانیه\n"
                    f"محدوده مجاز: {InputValidator.MIN_DELAY}-{InputValidator.MAX_DELAY} ثانیه"
                ),
                validation_type=ValidationType.DELAY_RANGE,
                metadata={
                    'value': delay,
                    'min': InputValidator.MIN_DELAY,
                    'max': InputValidator.MAX_DELAY
                }
            )
        
        return ValidationResult(
            valid=True,
            error_message=None,
            validation_type=ValidationType.DELAY_RANGE,
            normalized_value=str(delay),
            metadata={'value': delay}
        )
    
    @staticmethod
    def validate_cooldown(cooldown_value: str) -> ValidationResult:
        """
        Validate monitoring cooldown period
        
        Checks:
        - Value is a valid number
        - Value is within range [0.5, 60] seconds
        
        Args:
            cooldown_value: Cooldown value as string
        
        Returns:
            ValidationResult with validation status and normalized float value
            
        Requirements: AC-13.4
        
        Examples:
            >>> validate_cooldown("30")
            ValidationResult(valid=True, normalized_value="30.0")
            
            >>> validate_cooldown("100")
            ValidationResult(valid=False, error_message="...")
        """
        if not cooldown_value or not isinstance(cooldown_value, str):
            return ValidationResult(
                valid=False,
                error_message="مقدار کولداون نمی‌تواند خالی باشد",
                validation_type=ValidationType.COOLDOWN_RANGE
            )
        
        cooldown_value = cooldown_value.strip()
        
        # Try to parse as float
        try:
            cooldown = float(cooldown_value)
        except ValueError:
            return ValidationResult(
                valid=False,
                error_message=(
                    "❌ مقدار کولداون نامعتبر است\n\n"
                    "لطفاً یک عدد معتبر وارد کنید.\n"
                    "مثال: 30 یا 5.5"
                ),
                validation_type=ValidationType.COOLDOWN_RANGE
            )
        
        # Check range
        if cooldown < InputValidator.MIN_COOLDOWN or cooldown > InputValidator.MAX_COOLDOWN:
            return ValidationResult(
                valid=False,
                error_message=(
                    f"❌ کولداون باید بین {InputValidator.MIN_COOLDOWN} تا "
                    f"{InputValidator.MAX_COOLDOWN} ثانیه باشد\n\n"
                    f"مقدار وارد شده: {cooldown} ثانیه\n"
                    f"محدوده مجاز: {InputValidator.MIN_COOLDOWN}-{InputValidator.MAX_COOLDOWN} ثانیه"
                ),
                validation_type=ValidationType.COOLDOWN_RANGE,
                metadata={
                    'value': cooldown,
                    'min': InputValidator.MIN_COOLDOWN,
                    'max': InputValidator.MAX_COOLDOWN
                }
            )
        
        return ValidationResult(
            valid=True,
            error_message=None,
            validation_type=ValidationType.COOLDOWN_RANGE,
            normalized_value=str(cooldown),
            metadata={'value': cooldown}
        )
    
    @staticmethod
    def validate_bulk_group_count(count: int) -> ValidationResult:
        """
        Validate bulk group scraping count
        
        Checks:
        - Count is within limit (max 50 groups)
        
        Args:
            count: Number of groups to scrape
        
        Returns:
            ValidationResult with validation status
            
        Requirements: AC-1.3, AC-12.1
        """
        MAX_BULK_GROUPS = 50
        
        if count <= 0:
            return ValidationResult(
                valid=False,
                error_message="تعداد گروه‌ها باید بیشتر از صفر باشد",
                metadata={'count': count, 'max': MAX_BULK_GROUPS}
            )
        
        if count > MAX_BULK_GROUPS:
            return ValidationResult(
                valid=False,
                error_message=(
                    f"❌ تعداد گروه‌ها بیش از حد مجاز است\n\n"
                    f"حداکثر {MAX_BULK_GROUPS} گروه در هر عملیات مجاز است.\n"
                    f"تعداد وارد شده: {count} گروه"
                ),
                metadata={'count': count, 'max': MAX_BULK_GROUPS}
            )
        
        return ValidationResult(
            valid=True,
            error_message=None,
            metadata={'count': count, 'max': MAX_BULK_GROUPS}
        )


class ValidationErrorHandler:
    """
    Handles validation errors with user-friendly messages
    
    Provides:
    - Error message formatting
    - Retry prompts
    - Input preservation
    
    Requirements: 13.5
    """
    
    @staticmethod
    def format_validation_error(
        result: ValidationResult,
        context: Optional[str] = None
    ) -> str:
        """
        Format validation error message for display
        
        Args:
            result: ValidationResult with error
            context: Optional context about what was being validated
        
        Returns:
            Formatted error message in Persian
        """
        if result.valid:
            return ""
        
        message = result.error_message or "خطای نامشخص در اعتبارسنجی"
        
        if context:
            message = f"{context}\n\n{message}"
        
        # Add retry prompt
        message += "\n\n💡 لطفاً مقدار صحیح را وارد کنید یا /cancel را برای لغو ارسال کنید."
        
        return message
    
    @staticmethod
    def should_preserve_input(validation_type: ValidationType) -> bool:
        """
        Determine if previous valid inputs should be preserved on error
        
        Args:
            validation_type: Type of validation that failed
        
        Returns:
            True if previous inputs should be preserved
        """
        # For most validation types, preserve previous inputs
        # This allows users to correct only the invalid input
        return True
    
    @staticmethod
    def get_retry_prompt(validation_type: ValidationType) -> str:
        """
        Get retry prompt message for validation type
        
        Args:
            validation_type: Type of validation that failed
        
        Returns:
            Retry prompt message in Persian
        """
        prompts = {
            ValidationType.GROUP_IDENTIFIER: "لطفاً شناسه گروه معتبر وارد کنید:",
            ValidationType.CSV_CONTENT: "لطفاً فایل CSV معتبر آپلود کنید:",
            ValidationType.REACTION_EMOJI: "لطفاً ایموجی معتبر وارد کنید:",
            ValidationType.DELAY_RANGE: "لطفاً تاخیر معتبر (۱-۱۰ ثانیه) وارد کنید:",
            ValidationType.COOLDOWN_RANGE: "لطفاً کولداون معتبر (۰.۵-۶۰ ثانیه) وارد کنید:",
        }
        
        return prompts.get(validation_type, "لطفاً مقدار معتبر وارد کنید:")
