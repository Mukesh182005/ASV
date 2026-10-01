"""Tests for the temporary proof-of-concept HELLO vs REST demo scripts."""
import pytest
import numpy as np
import pandas as pd
import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ml.training.train_hello_vs_rest import train_hello_vs_rest
from ml.inference.live_hello_demo import LiveHelloDetector


def test_train_hello_vs_rest_missing_rest_validation():
    """Verify that train_hello_vs_rest stops and returns valid=False when REST data is missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        hello_dir = tmp_path / "hello"
        hello_dir.mkdir(parents=True, exist_ok=True)
        
        # Create mock hello file
        df = pd.DataFrame({"timestamp": [100, 102], "ch0": [1000.0, 1050.0]})
        df.to_csv(hello_dir / "rep001.csv", index=False)
        
        result = train_hello_vs_rest(data_dir=tmp_path)
        assert result["valid"] is False
        assert "Missing true REST recordings" in result["reason"]
        assert result["accuracy"] is None
        assert result["f1"] is None


def test_live_hello_demo_simulation_mode():
    """Verify that LiveHelloDetector runs cleanly in simulation mode."""
    detector = LiveHelloDetector(port="FAKE", simulate=True, duration=0.5)
    assert detector.simulate is True
    # Run loop for 0.5s max
    detector.run()
