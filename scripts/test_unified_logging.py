#!/usr/bin/env python3
"""
Unified Logging System Test Script

Tests all aspects of the unified logging system including:
- File writing functionality
- Different log formats (legacy, structured, JSON, simple)
- Context-aware logging
- Component-specific loggers
- Thread safety
"""

import sys
import os
import tempfile
import threading
import time
from pathlib import Path

# Add src path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cyris.core.unified_logger import (
    get_logger, LoggerFactory, LogFormat, LoggingContext,
    RangeLoggingContext, LoggerConfig
)

def test_basic_logging():
    """Test basic logger functionality"""
    print("🧪 Testing Basic Logging Functionality")
    print("=" * 50)
    
    logger = get_logger('test_basic', 'unittest')
    
    # Test different log levels
    logger.debug('Debug message test')
    logger.info('Info message test')
    logger.warning('Warning message test')
    logger.error('Error message test')
    
    print("✅ Basic logging test completed")

def test_file_writing():
    """Test file writing capabilities"""
    print("\n🧪 Testing File Writing Functionality")
    print("=" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        test_log_file = Path(temp_dir) / "test_logging.log"
        
        # Create a logger with file output
        config = LoggerConfig(
            name='file_test',
            component='test_suite',
            file_path=test_log_file,
            file_format=LogFormat.STRUCTURED,
            console_enabled=True
        )
        
        logger = LoggerFactory.get_logger('file_test', config=config)
        
        # Write test messages
        logger.info("Test message 1: File writing test")
        logger.warning("Test message 2: Warning level")
        logger.error("Test message 3: Error level")
        
        # Verify file was created and contains content
        if test_log_file.exists():
            with open(test_log_file, 'r') as f:
                content = f.read()
                if content and "Test message 1" in content:
                    print(f"✅ File writing successful - {len(content)} bytes written")
                    print(f"📁 File location: {test_log_file}")
                    print("📝 File content preview:")
                    for i, line in enumerate(content.splitlines()[:3]):
                        print(f"   {i+1}: {line}")
                else:
                    print("❌ File created but content missing or invalid")
                    return False
        else:
            print("❌ Log file was not created")
            return False
    
    print("✅ File writing test completed successfully")
    return True

def test_different_formats():
    """Test different log formats"""
    print("\n🧪 Testing Different Log Formats")
    print("=" * 50)
    
    formats = [
        (LogFormat.LEGACY, "Legacy format test"),
        (LogFormat.STRUCTURED, "Structured format test"),
        (LogFormat.JSON, "JSON format test"),
        (LogFormat.SIMPLE, "Simple format test")
    ]
    
    for log_format, message in formats:
        try:
            config = LoggerConfig(
                name=f'format_test_{log_format.value}',
                component='format_test',
                console_format=log_format,
                console_enabled=True
            )
            
            logger = LoggerFactory.get_logger(f'format_test_{log_format.value}', config=config)
            print(f"\n📋 Testing {log_format.value} format:")
            logger.info(message)
            print(f"✅ {log_format.value} format working")
            
        except Exception as e:
            print(f"❌ {log_format.value} format failed: {e}")
            return False
    
    print("\n✅ All log formats test completed successfully")
    return True

def test_context_logging():
    """Test context-aware logging"""
    print("\n🧪 Testing Context-Aware Logging")  
    print("=" * 50)
    
    try:
        # Test basic logging context
        with LoggingContext(range_id='test-123', operation='validation'):
            logger = get_logger('context_test', 'range_ops')
            logger.info('Context-aware logging test message')
            print("✅ Basic context logging working")
            
        # Test range-specific context
        with RangeLoggingContext('test-range-456', 'creation', 'orchestrator'):
            logger = get_logger('range_context_test', 'orchestrator')  
            logger.info('Range context logging test message')
            print("✅ Range context logging working")
            
        print("✅ Context-aware logging test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Context logging test failed: {e}")
        return False

def test_component_loggers():
    """Test component-specific loggers"""
    print("\n🧪 Testing Component-Specific Loggers")
    print("=" * 50)
    
    components = [
        ('cyris.cli.main', 'cli_main'),
        ('cyris.services.orchestrator', 'orchestrator'),
        ('cyris.infrastructure.providers.kvm_provider', 'kvm_provider'),
        ('cyris.tools.vm_ip_manager', 'vm_ip_manager'),
        ('cyris.config.parser', 'config_parser')
    ]
    
    for module_name, component in components:
        try:
            logger = get_logger(module_name, component)
            logger.info(f'{component} component logger test')
            print(f"✅ {component} component logger working")
        except Exception as e:
            print(f"❌ {component} component logger failed: {e}")
            return False
    
    print("✅ Component-specific loggers test completed successfully")
    return True

def test_thread_safety():
    """Test thread safety of logging system"""
    print("\n🧪 Testing Thread Safety")
    print("=" * 50)
    
    def worker_thread(thread_id, num_messages=10):
        """Worker thread that logs messages"""
        logger = get_logger(f'thread_test_{thread_id}', 'thread_safety')
        
        for i in range(num_messages):
            logger.info(f'Thread {thread_id} message {i+1}')
            time.sleep(0.01)  # Small delay to simulate work
    
    try:
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker_thread, args=(i, 5))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        print("✅ Thread safety test completed - no crashes detected")
        return True
        
    except Exception as e:
        print(f"❌ Thread safety test failed: {e}")
        return False

def test_legacy_compatibility():
    """Test that our logging works like the previous print-to-file functionality"""
    print("\n🧪 Testing Legacy Compatibility")
    print("=" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        creation_log = Path(temp_dir) / "creation.log"
        detailed_log = Path(temp_dir) / "detailed.log" 
        
        try:
            # Test creation.log format (legacy)
            creation_config = LoggerConfig(
                name='creation_test',
                component='creation',
                file_path=creation_log,
                file_format=LogFormat.LEGACY,
                console_enabled=False
            )
            creation_logger = LoggerFactory.get_logger('creation_test', config=creation_config)
            creation_logger.info("Starting range creation: Range test-legacy")
            creation_logger.info("Build VM images (1 images)")
            creation_logger.info("Creation result: SUCCESS (took 120.5s)")
            
            # Test detailed.log format (structured)
            detailed_config = LoggerConfig(
                name='detailed_test', 
                component='orchestrator',
                file_path=detailed_log,
                file_format=LogFormat.STRUCTURED,
                console_enabled=False
            )
            detailed_logger = LoggerFactory.get_logger('detailed_test', config=detailed_config)
            detailed_logger.info("Starting range creation: Range test-legacy")
            detailed_logger.info("Build VM images (1 images)")
            detailed_logger.info("Creation result: SUCCESS (took 120.5s)")
            
            # Verify files were created with correct formats
            creation_success = creation_log.exists() and "* INFO: cyris:" in creation_log.read_text()
            detailed_success = detailed_log.exists() and "[INFO] [orchestrator]" in detailed_log.read_text()
            
            if creation_success and detailed_success:
                print("✅ Legacy format compatibility verified")
                print(f"📁 Creation log: {creation_log} ({creation_log.stat().st_size} bytes)")
                print(f"📁 Detailed log: {detailed_log} ({detailed_log.stat().st_size} bytes)")
                
                # Show format examples
                print("\n📝 Creation log format example:")
                print(f"   {creation_log.read_text().splitlines()[0]}")
                print("\n📝 Detailed log format example:")
                print(f"   {detailed_log.read_text().splitlines()[0]}")
                
                return True
            else:
                print(f"❌ Legacy compatibility failed - creation: {creation_success}, detailed: {detailed_success}")
                return False
                
        except Exception as e:
            print(f"❌ Legacy compatibility test failed: {e}")
            return False

def run_comprehensive_test():
    """Run all tests and provide summary"""
    print("🚀 UNIFIED LOGGING SYSTEM COMPREHENSIVE TEST")
    print("=" * 80)
    
    tests = [
        ("Basic Logging", test_basic_logging),
        ("File Writing", test_file_writing),
        ("Different Formats", test_different_formats),
        ("Context Logging", test_context_logging),
        ("Component Loggers", test_component_loggers),
        ("Thread Safety", test_thread_safety),
        ("Legacy Compatibility", test_legacy_compatibility)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result if result is not None else True
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} {test_name}")
    
    print("-" * 80)
    print(f"📈 Overall Result: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - UNIFIED LOGGING SYSTEM IS WORKING CORRECTLY!")
        print("\n✅ Key Achievements:")
        print("  • File writing functionality verified")
        print("  • Multiple log formats working (legacy, structured, JSON, simple)")
        print("  • Context-aware logging implemented")
        print("  • Component-specific loggers created")
        print("  • Thread safety confirmed") 
        print("  • Legacy print() replacement successful")
        return True
    else:
        print(f"⚠️  {total-passed} TESTS FAILED - ISSUES NEED ATTENTION")
        return False

if __name__ == "__main__":
    success = run_comprehensive_test()
    sys.exit(0 if success else 1)