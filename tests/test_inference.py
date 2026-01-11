import pytest
import asyncio
from src.core.inference import InferenceService

@pytest.mark.asyncio
async def test_inference_initialization_mock():
    # Initialize with a non-existent model path -> Should default to Mock Mode
    service = InferenceService(model_path="non_existent_model.tflite")
    assert service.mock_mode is True

@pytest.mark.asyncio
async def test_inference_prediction_mock():
    service = InferenceService(model_path="non_existent_model.tflite")
    
    # Dummy features [10.0, 20.0, ...]
    features = [0.5] * 10 
    
    score = await service.predict(features)
    assert isinstance(score, float)
    assert score == 0.95 # Mock value

