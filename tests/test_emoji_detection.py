#!/usr/bin/env python3
"""
Test script for emoji detection and fallback functionality
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_emoji_detection():
    """Test emoji detection in different environments"""
    print("Testing Emoji Detection and Fallback System")
    print("=" * 60)
    
    # Import here to avoid scoping issues
    from cyris.cli.main import _detect_terminal_capabilities, get_status_indicator
    
    # Test current environment
    caps = _detect_terminal_capabilities()
    print(f"Current Environment:")
    print(f"   Encoding: {caps['encoding']}")
    print(f"   UTF-8 Support: {caps['utf8_support']}")
    print(f"   Color Support: {caps['supports_color']}")  
    print(f"   Emoji Support: {caps['supports_emoji']}")
    print(f"   TERM: {caps['term']}")
    print()
    
    # Test status indicators in current environment
    print(f"Status Indicators (Auto-detected):")
    statuses = ['active', 'creating', 'error', 'ok', 'fail', 'warning', 'info']
    for status in statuses:
        indicator = get_status_indicator(status)
        print(f"   {status.capitalize()}: {indicator}")
    print()
    
    # Test forced ASCII mode
    print(f"Status Indicators (ASCII Mode):")
    for status in statuses:
        indicator = get_status_indicator(status, use_emoji=False)
        print(f"   {status.capitalize()}: {indicator}")
    print()
    
    # Test environment variable overrides
    print(f"Testing Environment Variable Overrides:")
    
    # Save original values
    original_no_color = os.environ.get('NO_COLOR', '')
    original_term = os.environ.get('TERM', '')
    original_emoji = os.environ.get('CYRIS_ENABLE_EMOJI', '')
    
    test_configs = [
        ('Default (no emoji)', {}),
        ('CYRIS_ENABLE_EMOJI=1', {'CYRIS_ENABLE_EMOJI': '1'}),
        ('NO_COLOR=1', {'NO_COLOR': '1'}),
        ('TERM=dumb', {'TERM': 'dumb'}), 
        ('TERM=linux', {'TERM': 'linux'}),
    ]
    
    for desc, env_vars in test_configs:
        # Set test environment
        for key, value in env_vars.items():
            os.environ[key] = value
        
        # Reload the module to re-detect capabilities
        import importlib
        import cyris.cli.main
        importlib.reload(cyris.cli.main)
        from cyris.cli.main import _detect_terminal_capabilities, get_status_indicator
        
        test_caps = _detect_terminal_capabilities()
        
        print(f"   {desc}: {'ASCII' if not test_caps['supports_emoji'] else 'Emoji'} mode")
        print(f"     Active: {get_status_indicator('active')}")
        print(f"     Error:  {get_status_indicator('error')}")
    
    # Restore original values
    if original_no_color:
        os.environ['NO_COLOR'] = original_no_color
    elif 'NO_COLOR' in os.environ:
        del os.environ['NO_COLOR']
        
    if original_term:
        os.environ['TERM'] = original_term
    elif 'TERM' in os.environ:
        del os.environ['TERM']
        
    if original_emoji:
        os.environ['CYRIS_ENABLE_EMOJI'] = original_emoji
    elif 'CYRIS_ENABLE_EMOJI' in os.environ:
        del os.environ['CYRIS_ENABLE_EMOJI']
        
    print()
    print("Configuration Summary:")
    print("- Default: ASCII mode ([ACTIVE], [ERROR]) for maximum compatibility")  
    print("- Emoji mode: Set CYRIS_ENABLE_EMOJI=1 to enable emoji indicators")
    print("- Override: NO_COLOR=1 always forces ASCII mode")
    print("- Recommendation: Use ASCII mode to avoid terminal corruption issues")

if __name__ == "__main__":
    test_emoji_detection()