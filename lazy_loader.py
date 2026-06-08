# lazy_loader.py
# Smart lazy loading system to manage memory and startup time
# Loads packages only when needed to optimize performance

import sys
import importlib
import time
from typing import Any, Dict, Optional
from functools import wraps

class LazyLoader:
    """
    Lazy loader for packages that delays import until first use.
    Reduces startup time and memory usage.
    """
    
    def __init__(self):
        self.loaded_modules: Dict[str, Any] = {}
        self.load_times: Dict[str, float] = {}
        self.import_errors: Dict[str, str] = {}
    
    def load_module(self, module_name: str, package_alias: Optional[str] = None) -> Any:
        """
        Load a module on demand.
        
        Args:
            module_name: Full module name (e.g., 'torch', 'tensorflow')
            package_alias: Optional alias for the module
            
        Returns:
            The imported module
        """
        alias = package_alias or module_name
        
        # Return if already loaded
        if alias in self.loaded_modules:
            return self.loaded_modules[alias]
        
        try:
            start = time.time()
            module = importlib.import_module(module_name)
            load_time = time.time() - start
            
            self.loaded_modules[alias] = module
            self.load_times[alias] = load_time
            
            print(f"✅ Loaded {module_name} ({load_time:.2f}s)")
            return module
            
        except ImportError as e:
            self.import_errors[alias] = str(e)
            print(f"❌ Failed to load {module_name}: {e}")
            return None
    
    def load_from_module(self, module_name: str, items: list, package_alias: Optional[str] = None) -> Dict[str, Any]:
        """
        Load specific items from a module.
        
        Args:
            module_name: Full module name
            items: List of items to import (e.g., ['load', 'save'])
            package_alias: Optional alias for the module
            
        Returns:
            Dictionary of {item_name: imported_item}
        """
        module = self.load_module(module_name, package_alias)
        
        if module is None:
            return {}
        
        result = {}
        for item in items:
            try:
                result[item] = getattr(module, item)
            except AttributeError:
                print(f"⚠️  {module_name} has no attribute '{item}'")
        
        return result
    
    def lazy_import(self, module_name: str, package_alias: Optional[str] = None):
        """
        Decorator for lazy importing.
        
        Usage:
            @lazy_import('torch')
            def use_torch(x):
                pass
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                self.load_module(module_name, package_alias)
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all loaded modules"""
        return {
            "loaded": len(self.loaded_modules),
            "modules": list(self.loaded_modules.keys()),
            "load_times": self.load_times,
            "errors": self.import_errors
        }
    
    def print_status(self):
        """Print status of lazy loader"""
        status = self.get_status()
        print("\n" + "="*70)
        print("LAZY LOADER STATUS".center(70))
        print("="*70 + "\n")
        print(f"Loaded Modules: {status['loaded']}\n")
        
        if status['modules']:
            print("✅ Successfully Loaded:")
            for mod_name, load_time in status['load_times'].items():
                print(f"  • {mod_name:30s} ({load_time:.2f}s)")
        
        if status['errors']:
            print("\n❌ Failed to Load:")
            for mod_name, error in status['errors'].items():
                print(f"  • {mod_name:30s} → {error}")
        
        total_time = sum(status['load_times'].values())
        print(f"\nTotal Load Time: {total_time:.2f}s")
        print("="*70 + "\n")


# Global lazy loader instance
global_loader = LazyLoader()


# ===== LAZY LOADING CONFIGURATIONS =====

# ML/AI Framework loaders
def load_torch():
    """Load PyTorch on demand"""
    return global_loader.load_module('torch')

def load_tensorflow():
    """Load TensorFlow on demand"""
    return global_loader.load_module('tensorflow', 'tf')

def load_keras():
    """Load Keras on demand"""
    return global_loader.load_module('keras')

def load_sklearn():
    """Load scikit-learn on demand"""
    return global_loader.load_module('sklearn')

# NLP loaders
def load_nltk():
    """Load NLTK on demand"""
    return global_loader.load_module('nltk')

def load_spacy():
    """Load spaCy on demand (if installed)"""
    return global_loader.load_module('spacy')

# Web framework loaders
def load_fastapi():
    """Load FastAPI on demand"""
    return global_loader.load_module('fastapi')

def load_flask():
    """Load Flask on demand"""
    return global_loader.load_module('flask')

# Cloud service loaders
def load_azure_blob():
    """Load Azure Blob Storage on demand"""
    items = global_loader.load_from_module(
        'azure.storage.blob',
        ['BlobServiceClient'],
        'azure_blob'
    )
    return items

def load_google_cloud_storage():
    """Load Google Cloud Storage on demand"""
    items = global_loader.load_from_module(
        'google.cloud.storage',
        ['Client'],
        'gcs'
    )
    return items

# Audio loaders
def load_librosa():
    """Load librosa on demand"""
    return global_loader.load_module('librosa')

def load_pydub():
    """Load pydub on demand"""
    return global_loader.load_module('pydub')

# Testing loaders
def load_pytest():
    """Load pytest on demand (dev only)"""
    return global_loader.load_module('pytest')

def load_hypothesis():
    """Load hypothesis on demand (dev only)"""
    return global_loader.load_module('hypothesis')


# ===== BATCH LOADING =====

class BatchLoader:
    """Load multiple related packages at once"""
    
    def __init__(self):
        self.loader = global_loader
    
    def load_ml_suite(self):
        """Load all ML/AI frameworks"""
        modules = {}
        modules['torch'] = self.loader.load_module('torch')
        modules['tensorflow'] = self.loader.load_module('tensorflow')
        modules['keras'] = self.loader.load_module('keras')
        modules['sklearn'] = self.loader.load_module('sklearn')
        modules['numpy'] = self.loader.load_module('numpy')
        modules['scipy'] = self.loader.load_module('scipy')
        return modules
    
    def load_audio_suite(self):
        """Load all audio processing packages"""
        modules = {}
        modules['librosa'] = self.loader.load_module('librosa')
        modules['sounddevice'] = self.loader.load_module('sounddevice')
        modules['pydub'] = self.loader.load_module('pydub')
        modules['pyttsx3'] = self.loader.load_module('pyttsx3')
        return modules
    
    def load_web_suite(self):
        """Load all web/networking packages"""
        modules = {}
        modules['fastapi'] = self.loader.load_module('fastapi')
        modules['flask'] = self.loader.load_module('flask')
        modules['httpx'] = self.loader.load_module('httpx')
        modules['aiohttp'] = self.loader.load_module('aiohttp')
        modules['websockets'] = self.loader.load_module('websockets')
        return modules
    
    def load_cloud_suite(self):
        """Load all cloud service packages"""
        modules = {}
        try:
            from azure.storage.blob import BlobServiceClient
            modules['azure_blob'] = BlobServiceClient
        except ImportError:
            print("⚠️  Azure Blob Storage not available")
        
        try:
            from google.cloud import storage
            modules['gcs'] = storage
        except ImportError:
            print("⚠️  Google Cloud Storage not available")
        
        return modules
    
    def load_nlp_suite(self):
        """Load all NLP packages"""
        modules = {}
        modules['nltk'] = self.loader.load_module('nltk')
        modules['regex'] = self.loader.load_module('regex')
        try:
            modules['spacy'] = self.loader.load_module('spacy')
        except:
            print("⚠️  spaCy not available")
        return modules


# Global batch loader instance
batch_loader = BatchLoader()


# ===== MEMORY-AWARE LOADING =====

import psutil

class MemoryAwareLoader:
    """
    Load packages only if system has enough free memory.
    Prevents system from running out of memory.
    """
    
    def __init__(self, min_free_memory_gb: float = 2.0):
        self.loader = global_loader
        self.min_free_memory = min_free_memory_gb * 1024 * 1024 * 1024  # Convert to bytes
        self.loaded_sizes = {}
    
    def get_free_memory(self) -> float:
        """Get current free memory in GB"""
        return psutil.virtual_memory().available / (1024 * 1024 * 1024)
    
    def can_load(self, estimated_size_mb: float = 500) -> bool:
        """Check if there's enough memory to load a package"""
        free_memory = self.get_free_memory()
        required_memory = estimated_size_mb / 1024
        return free_memory > (self.min_free_memory / (1024 * 1024 * 1024) + required_memory)
    
    def safe_load(self, module_name: str, estimated_size_mb: float = 500) -> Optional[Any]:
        """
        Load a module only if enough memory is available.
        
        Args:
            module_name: Module to load
            estimated_size_mb: Estimated size in MB
            
        Returns:
            Module or None if not enough memory
        """
        free_memory = self.get_free_memory()
        required_memory = estimated_size_mb / 1024
        
        print(f"Memory check for {module_name}:")
        print(f"  Free: {free_memory:.2f}GB, Required: {required_memory:.2f}GB")
        
        if self.can_load(estimated_size_mb):
            return self.loader.load_module(module_name)
        else:
            print(f"❌ Not enough memory to load {module_name}")
            return None
    
    def memory_status(self):
        """Print memory status"""
        memory = psutil.virtual_memory()
        print("\n" + "="*70)
        print("MEMORY STATUS".center(70))
        print("="*70)
        print(f"Total:     {memory.total / (1024**3):.2f} GB")
        print(f"Available: {memory.available / (1024**3):.2f} GB")
        print(f"Used:      {memory.used / (1024**3):.2f} GB ({memory.percent}%)")
        print(f"Free:      {memory.free / (1024**3):.2f} GB")
        print("="*70 + "\n")


# Global memory-aware loader
memory_loader = MemoryAwareLoader(min_free_memory_gb=2.0)


# ===== TESTING =====

if __name__ == "__main__":
    print("\n" + "🚀 LAZY LOADER TEST SUITE 🚀".center(70))
    print("="*70 + "\n")
    
    # Test 1: Load single module
    print("Test 1: Loading single module (numpy)...")
    np = global_loader.load_module('numpy', 'np')
    print(f"✅ NumPy version: {np.__version__ if np else 'Failed'}\n")
    
    # Test 2: Memory check
    print("Test 2: Memory status check...")
    memory_loader.memory_status()
    
    # Test 3: Lazy loader status
    print("Test 3: Lazy loader status...")
    global_loader.print_status()
    
    # Test 4: Batch loading
    print("Test 4: Testing batch loader...")
    print("Loading ML suite (torch, tensorflow, keras, sklearn)...")
    ml_modules = batch_loader.load_ml_suite()
    print(f"✅ Loaded {len([m for m in ml_modules.values() if m])} modules\n")
    
    print("="*70)
    print("✅ ALL TESTS COMPLETED".center(70))
    print("="*70 + "\n")
