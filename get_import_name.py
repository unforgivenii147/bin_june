#!/data/data/com.termux/files/home/.local/bin/python
"""

import subprocess
import sys
import importlib
def get_import_name(install_name):


    try:
        print(f"Attempting to install {install_name}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", install_name])
        print(f"Installation of {install_name} complete.")

        try:
            importlib.import_module(install_name.replace('-', '_'))
            return install_name.replace('-', '_')
        except ImportError:
            pass

        common_patterns = [
            install_name.lower(),
            install_name.replace('-', ''),
            ''.join(word.capitalize() for word in install_name.split('-')),

        ]
        for pattern in common_patterns:
            try:
                importlib.import_module(pattern)
                return pattern
            except ImportError:
                pass
        return "Unable to determine import name automatically."
    except Exception as e:
        return f"Error during installation or import: {e}"
    finally:

        try:
            print(f"Uninstalling {install_name}...")
            subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", install_name])
            print(f"Uninstallation of {install_name} complete.")
        except Exception as e:
            print(f"Error uninstalling {install_name}: {e}")




"""
