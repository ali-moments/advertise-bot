"""
Example: File Operations with FileHandler

Demonstrates CSV and media file validation, processing, and cleanup.
"""

import os
import sys
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from panel.file_handler import FileHandler


def example_csv_operations():
    """Example CSV file operations"""
    print("=" * 60)
    print("CSV File Operations Example")
    print("=" * 60)
    
    # Initialize FileHandler
    file_handler = FileHandler(temp_dir="./temp")
    
    # Create a sample CSV file
    csv_data = [
        ['user1', 'User One'],
        ['user2', 'User Two'],
        ['user3', 'User Three'],
        ['user4', 'User Four'],
        ['user5', 'User Five']
    ]
    headers = ['recipient', 'name']
    
    csv_path = file_handler.get_temp_file_path(999, 'csv', '.csv')
    
    print(f"\n1. Creating CSV file at: {csv_path}")
    success = file_handler.create_csv_from_data(csv_data, csv_path, headers)
    print(f"   Created: {success}")
    
    # Validate the CSV
    print(f"\n2. Validating CSV file...")
    result = file_handler.validate_csv(csv_path)
    
    if result.valid:
        print(f"   ✅ Valid CSV file")
        print(f"   - Rows: {result.row_count}")
        print(f"   - Columns: {result.column_count}")
        print(f"   - Recipients: {len(result.recipients)}")
        print(f"   - File size: {result.file_size} bytes")
        print(f"   - Sample recipients: {result.recipients[:3]}")
    else:
        print(f"   ❌ Invalid CSV: {result.error}")
    
    # Read recipients
    print(f"\n3. Reading recipients from CSV...")
    recipients = file_handler.read_csv_recipients(csv_path)
    print(f"   Found {len(recipients)} recipients:")
    for i, recipient in enumerate(recipients[:5], 1):
        print(f"   {i}. {recipient}")
    
    # Cleanup
    print(f"\n4. Cleaning up temporary file...")
    cleaned = file_handler.cleanup_file(csv_path)
    print(f"   Cleaned: {cleaned}")
    print(f"   File exists: {os.path.exists(csv_path)}")


def example_media_validation():
    """Example media file validation"""
    print("\n" + "=" * 60)
    print("Media File Validation Example")
    print("=" * 60)
    
    file_handler = FileHandler(temp_dir="./temp")
    
    # Test different media types
    media_tests = [
        ('image', '.jpg', b'fake image data' * 100),
        ('video', '.mp4', b'fake video data' * 1000),
        ('document', '.pdf', b'fake pdf data' * 500)
    ]
    
    for media_type, extension, data in media_tests:
        print(f"\n{media_type.upper()} Validation:")
        
        # Create temporary file
        fd, path = tempfile.mkstemp(suffix=extension)
        os.close(fd)
        
        try:
            # Write data
            with open(path, 'wb') as f:
                f.write(data)
            
            # Validate
            result = file_handler.validate_media(path, media_type)
            
            if result.valid:
                print(f"   ✅ Valid {media_type}")
                print(f"   - File type: {result.file_type}")
                print(f"   - File size: {result.file_size} bytes")
                print(f"   - Size (MB): {result.metadata['size_mb']}")
            else:
                print(f"   ❌ Invalid {media_type}: {result.error}")
        
        finally:
            if os.path.exists(path):
                os.remove(path)


def example_validation_errors():
    """Example validation error handling"""
    print("\n" + "=" * 60)
    print("Validation Error Handling Example")
    print("=" * 60)
    
    file_handler = FileHandler(temp_dir="./temp")
    
    # Test 1: Non-existent file
    print("\n1. Non-existent file:")
    result = file_handler.validate_csv('/nonexistent/file.csv')
    print(f"   Valid: {result.valid}")
    print(f"   Error: {result.error}")
    
    # Test 2: Empty CSV
    print("\n2. Empty CSV file:")
    fd, path = tempfile.mkstemp(suffix='.csv')
    os.close(fd)
    
    try:
        result = file_handler.validate_csv(path)
        print(f"   Valid: {result.valid}")
        print(f"   Error: {result.error}")
    finally:
        os.remove(path)
    
    # Test 3: Wrong media extension
    print("\n3. Wrong media extension:")
    fd, path = tempfile.mkstemp(suffix='.exe')
    os.close(fd)
    
    try:
        with open(path, 'wb') as f:
            f.write(b'data')
        
        result = file_handler.validate_media(path, 'image')
        print(f"   Valid: {result.valid}")
        print(f"   Error: {result.error}")
    finally:
        os.remove(path)


def example_full_workflow():
    """Example complete workflow"""
    print("\n" + "=" * 60)
    print("Complete File Operations Workflow")
    print("=" * 60)
    
    file_handler = FileHandler(temp_dir="./temp")
    
    print("\nWorkflow: Create → Validate → Process → Cleanup")
    
    # Step 1: Create CSV
    print("\n1. Creating CSV with recipient data...")
    csv_path = file_handler.get_temp_file_path(12345, 'csv', '.csv')
    
    data = [
        ['+201234567890'],
        ['+201234567891'],
        ['+201234567892'],
        ['@username1'],
        ['@username2']
    ]
    
    created = file_handler.create_csv_from_data(data, csv_path)
    print(f"   Created: {created}")
    
    # Step 2: Validate
    print("\n2. Validating CSV...")
    validation = file_handler.validate_csv(csv_path)
    print(f"   Valid: {validation.valid}")
    print(f"   Recipients: {len(validation.recipients)}")
    
    # Step 3: Process (read recipients)
    print("\n3. Processing recipients...")
    recipients = file_handler.read_csv_recipients(csv_path)
    print(f"   Extracted {len(recipients)} recipients")
    print(f"   Sample: {recipients[:3]}")
    
    # Step 4: Cleanup
    print("\n4. Cleaning up...")
    cleaned = file_handler.cleanup_file(csv_path)
    print(f"   Cleaned: {cleaned}")
    print(f"   File removed: {not os.path.exists(csv_path)}")
    
    print("\n✅ Workflow completed successfully!")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("FileHandler Examples")
    print("=" * 60)
    
    try:
        example_csv_operations()
        example_media_validation()
        example_validation_errors()
        example_full_workflow()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully! ✅")
        print("=" * 60)
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
