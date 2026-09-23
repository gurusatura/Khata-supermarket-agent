"""
test_stage10_memory.py — Nebula Supermarket Ops Agent
======================================================
Tests persistent preferences to ensure values survive 
and overwrite correctly.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.memory import set_preference, get_preference

def run_test():
    print("Stage 10: Memory & Preferences Test\n")
    
    # Test 1: Get non-existent key
    val = get_preference("unknown_key", "default_value")
    assert val == "default_value", "Default value not returned for missing key"
    print("TEST 1: Default fallback for missing key passed.")
    
    # Test 2: Set and Get a key
    set_preference("language", "Tamil")
    val = get_preference("language")
    assert val == "Tamil", f"Expected 'Tamil', got '{val}'"
    print("TEST 2: Set and Get new key passed.")
    
    # Test 3: Upsert (overwrite) an existing key
    set_preference("language", "English")
    val = get_preference("language")
    assert val == "English", f"Expected 'English', got '{val}'"
    print("TEST 3: Upsert (overwrite) existing key passed.")
    
    print("\nALL STAGE 10 TESTS PASSED!")

if __name__ == "__main__":
    run_test()
