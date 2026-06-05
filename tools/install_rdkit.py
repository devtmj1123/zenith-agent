"""Install RDKit for molecule analysis."""

import subprocess
import sys

def install_rdkit():
    """Install RDKit using pip."""
    try:
        print("Installing RDKit...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "rdkit", "-q"])
        print("RDKit installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install RDKit: {e}")
        return False

if __name__ == "__main__":
    success = install_rdkit()
    if success:
        print("Testing import...")
        try:
            from rdkit import Chem
            print("RDKit import successful!")
        except ImportError as e:
            print(f"Import failed: {e}")
