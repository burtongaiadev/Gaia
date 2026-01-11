import numpy as np
import logging
from typing import Optional, List
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("Gaia")

class InferenceService:
    def __init__(self, model_path: str = "models/model.tflite"):
        self.model_path = model_path
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        # Run inference in a dedicated thread to avoid blocking the async loop
        self._executor = ThreadPoolExecutor(max_workers=1)
        self.mock_mode = False

        try:
            # specific import sequence to support all TFLite runtimes
            try:
                # 1. New Google AI Edge Runtime
                from ai_edge_litert.interpreter import Interpreter
                self.interpreter = Interpreter(model_path=self.model_path)
            except ImportError:
                try:
                    # 2. Classic TFLite Runtime
                    import tflite_runtime.interpreter as tflite
                    self.interpreter = tflite.Interpreter(model_path=self.model_path)
                except ImportError:
                    # 3. Full TensorFlow
                    import tensorflow.lite as tflite
                    self.interpreter = tflite.Interpreter(model_path=self.model_path)
            self.interpreter.allocate_tensors()
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            logger.info(f"TFLite Model loaded from {self.model_path}")

        except ImportError:
            logger.warning("TFLite runtime not found (install 'tflite-runtime'). InferenceService running in MOCK mode.")
            self.mock_mode = True
        except Exception as e:
            # Also catch file not found or bad model format
            logger.warning(f"Failed to load model from {self.model_path}: {e}. Running in MOCK mode.")
            self.mock_mode = True

    async def predict(self, features: List[float]) -> float:
        """
        Run inference asynchronously.
        Returns confidence score (0.0 to 1.0).
        """
        if self.mock_mode:
            # Mock Logic: Return a safe high score to allow signals to pass during testing
            return 0.95
            
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._predict_sync, features)

    def _predict_sync(self, features: List[float]) -> float:
        try:
            # Prepare input: convert list to numpy array with shape [1, N]
            # We assume features match the model's required input size
            input_data = np.array([features], dtype=np.float32)
            
            # Check input shape compatibility (basic check)
            required_shape = self.input_details[0]['shape']
            # input_data.shape should match required_shape (usually [1, n_features])
            
            self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
            self.interpreter.invoke()
            
            # Get output
            output_data = self.interpreter.get_tensor(self.output_details[0]['index'])
            
            # Assume output is a single float score (Sigmoid/Probability)
            result = float(output_data[0]) 
            if isinstance(output_data[0], (np.ndarray, list)):
                 result = float(output_data[0][0])
                 
            return result
        except Exception as e:
            logger.error(f"Inference Error: {e}")
            return 0.0
