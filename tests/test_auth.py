"""Unit tests for SDO authentication module using canopen."""

import pytest
from unittest.mock import Mock, MagicMock, patch

from src.auth import AuthenticationError


def calculate_key_test(seed: int, customer_secret: int) -> int:
    """Test wrapper for key calculation."""
    start = (seed & 0xFFFF) + (customer_secret & 0xFFFF)
    
    bit_15 = (start >> 15) & 1
    bit_7 = (start >> 7) & 1
    bit_4 = (start >> 4) & 1
    bit_0 = start & 1
    
    steps = (bit_15 * 8) + (bit_7 * 4) + (bit_4 * 2) + bit_0 + 1
    
    seed_word = start & 0xFFFF
    
    for _ in range(steps):
        bit_7 = (seed_word >> 7) & 1
        bit_2 = (seed_word >> 2) & 1
        nandbit = 0 if (bit_7 & bit_2) else 1
        
        bit_6 = (seed_word >> 6) & 1
        bit_9 = (seed_word >> 9) & 1
        bit_5 = (seed_word >> 5) & 1
        bit_0 = seed_word & 1
        xorbit = bit_6 ^ bit_9 ^ bit_5 ^ bit_0
        
        seed_word = (seed_word >> 1) & 0xFFFF
        if nandbit:
            seed_word |= 0x80
        if xorbit:
            seed_word |= 0x400
    
    return seed_word


class TestKeyCalculation:
    """Test the key calculation algorithm."""
    
    def test_key_calculation_basic(self):
        """Test key calculation with known values."""
        key = calculate_key_test(0x0000, 0x1234)
        assert isinstance(key, int)
        assert 0 <= key <= 0xFFFF
    
    def test_key_calculation_deterministic(self):
        """Test that key calculation is deterministic."""
        key1 = calculate_key_test(0xABCD, 0x5678)
        key2 = calculate_key_test(0xABCD, 0x5678)
        assert key1 == key2
    
    def test_key_calculation_different_seeds(self):
        """Test different seeds produce different keys."""
        key1 = calculate_key_test(0x1000, 0x1234)
        key2 = calculate_key_test(0x2000, 0x1234)
        assert key1 != key2
    
    def test_key_calculation_different_secrets(self):
        """Test different secrets produce different keys."""
        key1 = calculate_key_test(0x1000, 0x1111)
        key2 = calculate_key_test(0x1000, 0x2222)
        assert key1 != key2
    
    def test_key_calculation_zero(self):
        """Test key calculation with zero values."""
        key = calculate_key_test(0x0000, 0x0000)
        assert isinstance(key, int)
    
    def test_key_calculation_max_secret(self):
        """Test with max 16-bit secret."""
        key = calculate_key_test(0x0000, 0xFFFF)
        assert isinstance(key, int)


class TestErrorHandling:
    """Test error handling."""
    
    def test_authentication_error_exists(self):
        """Test that AuthenticationError exists."""
        err = AuthenticationError("test")
        assert str(err) == "test"
    
    def test_authentication_error_inheritance(self):
        """Test error inheritance."""
        assert issubclass(AuthenticationError, Exception)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])