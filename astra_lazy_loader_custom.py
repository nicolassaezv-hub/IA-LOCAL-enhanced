import sys
import importlib
import time
from typing import Any, Dict, Optional
from functools import wraps

try:
    import psutil as _psutil
    HAS_PSUTIL = True
except ImportError:
    _psutil = None
    HAS_PSUTIL = False


class LazyLoader:
    def __init__(self):
        self.loaded_modules: Dict[str, Any] = {}
        self.load_times: Dict[str, float] = {}
        self.import_errors: Dict[str, str] = {}

    def load_module(self, module_name: str, package_alias: Optional[str] = None) -> Any:
        alias = package_alias or module_name
        if alias in self.loaded_modules:
            return self.loaded_modules[alias]
        try:
            start = time.time()
            module = importlib.import_module(module_name)
            load_time = time.time() - start
            self.loaded_modules[alias] = module
            self.load_times[alias] = load_time
            return module
        except ImportError as e:
            self.import_errors[alias] = str(e)
            return None

    def load_from_module(self, module_name: str, items: list,
                         package_alias: Optional[str] = None) -> Dict[str, Any]:
        module = self.load_module(module_name, package_alias)
        if module is None:
            return {}
        result = {}
        for item in items:
            try:
                result[item] = getattr(module, item)
            except AttributeError:
                pass
        return result

    def lazy_import(self, module_name: str, package_alias: Optional[str] = None):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                self.load_module(module_name, package_alias)
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def get_status(self) -> Dict[str, Any]:
        return {
            "loaded": len(self.loaded_modules),
            "modules": list(self.loaded_modules.keys()),
            "load_times": self.load_times,
            "errors": self.import_errors
        }

    def print_status(self):
        status = self.get_status()
        print("\n" + "=" * 70)
        print("LAZY LOADER STATUS".center(70))
        print("=" * 70 + "\n")
        print(f"Loaded Modules: {status['loaded']}\n")
        if status['modules']:
            print("Successfully Loaded:")
            for mod_name, load_time in status['load_times'].items():
                print(f"  * {mod_name:30s} ({load_time:.2f}s)")
        if status['errors']:
            print("\nFailed to Load:")
            for mod_name, error in status['errors'].items():
                print(f"  * {mod_name:30s} -> {error}")
        total_time = sum(status['load_times'].values())
        print(f"\nTotal Load Time: {total_time:.2f}s")
        print("=" * 70 + "\n")


global_loader = LazyLoader()


def load_torch():
    return global_loader.load_module('torch')

def load_tensorflow():
    return global_loader.load_module('tensorflow', 'tf')

def load_keras():
    return global_loader.load_module('keras')

def load_sklearn():
    return global_loader.load_module('sklearn')

def load_nltk():
    return global_loader.load_module('nltk')

def load_fastapi():
    return global_loader.load_module('fastapi')

def load_flask():
    return global_loader.load_module('flask')

def load_librosa():
    return global_loader.load_module('librosa')

def load_pydub():
    return global_loader.load_module('pydub')


class BatchLoader:
    def __init__(self):
        self.loader = global_loader

    def load_ml_suite(self):
        return {
            'torch':      self.loader.load_module('torch'),
            'tensorflow': self.loader.load_module('tensorflow'),
            'keras':      self.loader.load_module('keras'),
            'sklearn':    self.loader.load_module('sklearn'),
            'numpy':      self.loader.load_module('numpy'),
            'scipy':      self.loader.load_module('scipy'),
        }

    def load_audio_suite(self):
        return {
            'librosa':    self.loader.load_module('librosa'),
            'sounddevice':self.loader.load_module('sounddevice'),
            'pydub':      self.loader.load_module('pydub'),
            'pyttsx3':    self.loader.load_module('pyttsx3'),
        }

    def load_web_suite(self):
        return {
            'fastapi':   self.loader.load_module('fastapi'),
            'flask':     self.loader.load_module('flask'),
            'httpx':     self.loader.load_module('httpx'),
            'aiohttp':   self.loader.load_module('aiohttp'),
            'websockets':self.loader.load_module('websockets'),
        }


batch_loader = BatchLoader()


class MemoryAwareLoader:
    def __init__(self, min_free_memory_gb: float = 2.0):
        self.loader = global_loader
        self.min_free_memory_gb = min_free_memory_gb

    def get_free_memory(self) -> float:
        if not HAS_PSUTIL:
            return 999.0
        return _psutil.virtual_memory().available / (1024 ** 3)

    def can_load(self, estimated_size_mb: float = 500) -> bool:
        return self.get_free_memory() > (self.min_free_memory_gb + estimated_size_mb / 1024)

    def safe_load(self, module_name: str, estimated_size_mb: float = 500) -> Optional[Any]:
        if self.can_load(estimated_size_mb):
            return self.loader.load_module(module_name)
        print(f"Not enough memory to load {module_name}")
        return None

    def memory_status(self):
        if not HAS_PSUTIL:
            print("psutil not available — cannot report memory status.")
            return
        memory = _psutil.virtual_memory()
        print(f"Total:     {memory.total / (1024**3):.2f} GB")
        print(f"Available: {memory.available / (1024**3):.2f} GB")
        print(f"Used:      {memory.used / (1024**3):.2f} GB ({memory.percent}%)")


memory_loader = MemoryAwareLoader(min_free_memory_gb=2.0)
