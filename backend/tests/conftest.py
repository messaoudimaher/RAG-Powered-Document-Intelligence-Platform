import sys
from unittest.mock import MagicMock

# Mock torch and its components to avoid DLL loading errors in non-AVX2 or restricted environments
class MockModule(MagicMock):
    @classmethod
    def __getattr__(cls, name):
        return MagicMock()

# Setup sys.modules mocks before imports occur
sys.modules['torch'] = MockModule()
sys.modules['torch.cuda'] = MockModule()
sys.modules['torch.nn'] = MockModule()
sys.modules['torch.utils'] = MockModule()
sys.modules['torch.utils.data'] = MockModule()

sys.modules['transformers'] = MockModule()
sys.modules['transformers.tokenization_utils_base'] = MockModule()

sys.modules['sentence_transformers'] = MockModule()
