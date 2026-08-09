#!/usr/bin/env python3
"""
setup_windows.py

Guía y verificación de setup para ASTRA en Windows 10/11

Uso:
    python setup_windows.py verify     # Verificar instalación actual
    python setup_windows.py install    # Instalar dependencias
    python setup_windows.py mt5        # Instrucciones para MetaTrader5
"""

import sys
import subprocess
import platform
from pathlib import Path

class WindowsSetup:
    
    @staticmethod
    def check_os():
        """Verificar que estamos en Windows"""
        if not sys.platform.startswith('win'):
            print("❌ Este script es para Windows únicamente.")
            print(f"   SO detectado: {sys.platform}")
            return False
        return True
    
    @staticmethod
    def check_python():
        """Verificar versión de Python"""
        version = sys.version_info
        print(f"\n✓ Python {version.major}.{version.minor}.{version.micro}")
        
        if version.major < 3 or (version.major == 3 and version.minor < 9):
            print(f"❌ Se requiere Python 3.9+")
            print(f"   Descargar desde: https://www.python.org/downloads/")
            return False
        return True
    
    @staticmethod
    def check_pip():
        """Verificar pip"""
        try:
            result = subprocess.run([sys.executable, "-m", "pip", "--version"], 
                                   capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✓ {result.stdout.strip()}")
                return True
        except:
            pass
        
        print("❌ pip no encontrado")
        return False
    
    @staticmethod
    def check_required_packages():
        """Verificar paquetes críticos"""
        required = {
            "pandas": "2.0+",
            "numpy": "1.24+",
            "sklearn": "1.3+",
            "xgboost": "2.0+",
            "lightgbm": "4.3+",
        }
        
        missing = []
        
        print("\n📦 Checking critical packages...")
        
        for package, min_version in required.items():
            try:
                __import__(package)
                print(f"  ✓ {package}")
            except ImportError:
                print(f"  ❌ {package} (required: {min_version})")
                missing.append(package)
        
        return len(missing) == 0, missing
    
    @staticmethod
    def check_mt5():
        """Verificar MetaTrader5"""
        print("\n🏦 Checking MetaTrader5...")
        
        try:
            import MetaTrader5 as mt5
            print("  ✓ MetaTrader5 module installed")
            return True
        except ImportError:
            print("  ⚠️  MetaTrader5 module NOT installed")
            print("     (Optional - only needed to download market data)")
            return False
    
    @staticmethod
    def check_folders():
        """Verificar estructura de carpetas"""
        print("\n📁 Checking folders...")
        
        required_folders = [
            "forex",
            "forex/prediction",
            "forex/business",
            "attached_assets",
        ]
        
        all_ok = True
        for folder in required_folders:
            if Path(folder).exists():
                print(f"  ✓ {folder}/")
            else:
                print(f"  ❌ {folder}/ (missing)")
                all_ok = False
        
        return all_ok
    
    @staticmethod
    def check_csv_data():
        """Verificar datos de ejemplo"""
        print("\n📊 Checking example data...")
        
        csv_path = Path("attached_assets/USD_JPY_H1_YTD_2026_(1)_1781885306995.csv")
        
        if csv_path.exists():
            size_mb = csv_path.stat().st_size / 1024 / 1024
            print(f"  ✓ {csv_path.name} ({size_mb:.1f} MB)")
            return True
        else:
            print(f"  ❌ {csv_path} (missing)")
            print("     Download example data from: [ask Claude to provide link]")
            return False
    
    @staticmethod
    def verify_all():
        """Ejecutar todas las verificaciones"""
        print("\n" + "="*60)
        print("ASTRA Windows Setup Verification".center(60))
        print("="*60)
        
        checks = [
            ("Windows OS", WindowsSetup.check_os),
            ("Python 3.9+", WindowsSetup.check_python),
            ("pip", WindowsSetup.check_pip),
            ("Folders", WindowsSetup.check_folders),
            ("CSV Data", WindowsSetup.check_csv_data),
        ]
        
        results = {}
        
        for name, check_func in checks:
            try:
                if name in ["Windows OS", "Python 3.9+", "pip", "Folders", "CSV Data"]:
                    result = check_func()
                    results[name] = result
            except Exception as e:
                print(f"  ❌ Error: {e}")
                results[name] = False
        
        # Critical packages
        pkg_ok, missing = WindowsSetup.check_required_packages()
        results["Critical Packages"] = pkg_ok
        
        # MT5 (optional)
        WindowsSetup.check_mt5()
        
        # Summary
        print("\n" + "="*60)
        print("SUMMARY".center(60))
        print("="*60)
        
        all_ok = all(results.values())
        
        for name, result in results.items():
            status = "✅" if result else "❌"
            print(f"{status} {name}")
        
        print("\n" + "-"*60)
        
        if all_ok:
            print("\n✅ Setup is complete! You can now run:")
            print("\n   python test_complete_pipeline.py")
            print("   python main.py")
            print("\n📘 For more info, see:")
            print("   • MANUAL.md (User guide)")
            print("   • README.md (Full documentation)")
            print("   • EVALUACION_COMPLETA_IA_LOCAL.md (Technical evaluation)")
        else:
            print("\n⚠️  Some issues found. Run:")
            print("   python setup_windows.py install")
        
        print("-"*60 + "\n")
        return all_ok
    
    @staticmethod
    def install_dependencies():
        """Instalar dependencias"""
        print("\n" + "="*60)
        print("Installing ASTRA Dependencies".center(60))
        print("="*60 + "\n")
        
        print("This will install all required packages for ASTRA.")
        print("You may need administrator privileges.\n")
        
        response = input("Continue? (y/n): ").lower()
        if response != 'y':
            print("Installation cancelled.")
            return False
        
        # Install requirements
        print("\nInstalling from requirements.txt...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            capture_output=False
        )
        
        if result.returncode == 0:
            print("\n✅ Dependencies installed successfully!")
            return True
        else:
            print("\n❌ Installation failed.")
            return False
    
    @staticmethod
    def show_mt5_instructions():
        """Mostrar instrucciones para MetaTrader5"""
        print("\n" + "="*60)
        print("MetaTrader5 Installation Guide".center(60))
        print("="*60)
        
        print("""
MetaTrader5 is OPTIONAL and only needed if you want to download
market data directly from a broker's server (using creando.py).

Without MetaTrader5, you can:
✓ Analyze existing CSV files
✓ Train ML models
✓ Generate trading signals
✓ Run backtests

You CANNOT (without MT5):
✗ Download live market data (creando.py will fail)

═══════════════════════════════════════════════════════════════════

INSTALLATION STEPS:

1. Download MetaTrader5:
   https://www.metatrader5.com/en/download

2. Install on Windows:
   • Run the installer
   • Create or link to a broker account
   • Choose a broker (e.g., IC Markets, Deriv, etc.)

3. Find your broker's symbol names:
   • Open MetaTrader5 terminal
   • Market Watch → right-click → Symbols
   • Note the exact symbol names (e.g., EURUSD, XAUUSD)

4. Update market_universe.py if needed:
   If your broker uses different symbols, update the MT5_SYMBOL_MAP
   in forex/market_universe.py

5. Test the connection:
   python creando.py
   
   If it works, you'll see:
   ✓ "MT5 initialized"
   ✓ Downloading symbols...
   ✓ Saving CSVs to /CSVs/

═══════════════════════════════════════════════════════════════════

TROUBLESHOOTING:

"No se pudo conectar a MT5":
→ Make sure MetaTrader5 terminal is running
→ Check that MetaTrader5 is properly installed
→ Restart MetaTrader5 and try again

"Symbol not found":
→ Check the exact symbol name in MT5 terminal
→ Update forex/market_universe.py MT5_SYMBOL_MAP
→ Some brokers use different names (e.g., EURUSD vs EURUSD.m)

"Module not found (MetaTrader5)":
→ pip install MetaTrader5
→ May require Windows admin privileges
→ Requires Python 3.9+ 64-bit

═══════════════════════════════════════════════════════════════════

RECOMMENDED BROKERS FOR METATRADER5:

Free/Low-cost:
• Deriv (https://deriv.com) - $1 minimum deposit
• IC Markets (https://www.icmarkets.com) - Great spreads
• XM (https://xm.com) - No minimum deposit

Demo Accounts:
• All major brokers offer free demo accounts
• Perfect for testing without real money

═══════════════════════════════════════════════════════════════════
""")
        
        print("\nFor more help, see README.md")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python setup_windows.py verify     # Check installation")
        print("  python setup_windows.py install    # Install dependencies")
        print("  python setup_windows.py mt5        # MT5 instructions")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "verify":
        if not WindowsSetup.verify_all():
            sys.exit(1)
    
    elif command == "install":
        if not WindowsSetup.install_dependencies():
            sys.exit(1)
    
    elif command == "mt5":
        WindowsSetup.show_mt5_instructions()
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
