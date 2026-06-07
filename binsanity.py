#!/usr/bin/env python3
"""
Binary File Analyzer - Finds executables in current directory that fail to run
Uses concurrent.futures for parallel processing
Outputs results to ~/tmp/err
"""

import os
import subprocess
import concurrent.futures
from pathlib import Path
from typing import List, Tuple, Optional

def is_executable(filepath: str) -> bool:
    """Check if file is executable"""
    return os.path.isfile(filepath) and os.access(filepath, os.X_OK)

def is_binary(filepath: str) -> bool:
    """Check if file is a binary executable (ELF or script with shebang)"""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(4)
            # Check for ELF magic number
            if header[:4] == b'\x7fELF':
                return True
            # Check for shebang
            if header[:2] == b'#!':
                return True
    except (IOError, OSError):
        pass
    return False

def get_binary_files(directory: str) -> List[str]:
    """Get all executable binary files in a directory"""
    binaries = []
    try:
        for item in os.listdir(directory):
            filepath = os.path.join(directory, item)
            if is_executable(filepath) and is_binary(filepath):
                binaries.append(filepath)
    except PermissionError:
        pass
    return binaries

def test_executable(filepath: str) -> Tuple[str, Optional[str]]:
    """Test if executable runs successfully, returns (filepath, error_msg)"""
    # Common safe test arguments
    test_args = ['--help', '-h', '--version', '-v', '--info']
    
    for test_arg in test_args:
        try:
            result = subprocess.run(
                [filepath, test_arg],
                capture_output=True,
                text=True,
                timeout=2
            )
            # Check stderr for library errors even if exit code is 0
            if result.stderr:
                error_lower = result.stderr.lower()
                if any(pattern in error_lower for pattern in [
                    'error while loading shared libraries',
                    'cannot open shared object file',
                    'no such file',
                    'not found',
                    'failed to load'
                ]):
                    return filepath, result.stderr.strip()[:200]
            # If we got here with success, binary is fine
            if result.returncode == 0:
                return filepath, None
                
        except subprocess.TimeoutExpired:
            # Binary might be working but hanging on --help
            # Consider it working if it at least started
            return filepath, None
        except FileNotFoundError:
            return filepath, "File not found"
        except PermissionError:
            return filepath, "Permission denied"
        except OSError as e:
            if 'exec format error' in str(e):
                return filepath, "Exec format error (wrong architecture)"
            return filepath, str(e)
    
    # If all test args failed, try running with no arguments
    try:
        result = subprocess.run(
            [filepath],
            capture_output=True,
            text=True,
            timeout=1
        )
        # Check for library errors in stderr
        if result.stderr:
            error_lower = result.stderr.lower()
            if any(pattern in error_lower for pattern in [
                'error while loading shared libraries',
                'cannot open shared object file',
                'no such file'
            ]):
                return filepath, result.stderr.strip()[:200]
        return filepath, None
    except subprocess.TimeoutExpired:
        return filepath, None
    except Exception as e:
        return filepath, str(e)[:200]

def main():
    """Main function with parallel processing"""
    # Setup output file
    output_dir = Path.home() / 'tmp'
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / 'err'
    
    # Get current directory
    current_dir = os.getcwd()
    print(f"Scanning directory: {current_dir}")
    
    # Find all binary files
    print("Finding executable binaries...")
    binaries = get_binary_files(current_dir)
    
    if not binaries:
        print("No executable binaries found in current directory")
        with open(output_file, 'w') as f:
            f.write("No executable binaries found in current directory\n")
        return
    
    print(f"Found {len(binaries)} binaries to test")
    print("Testing binaries in parallel...")
    
    # Test binaries in parallel
    failed_binaries = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        # Submit all tests
        future_to_binary = {
            executor.submit(test_executable, binary): binary 
            for binary in binaries
        }
        
        # Process results as they complete
        for i, future in enumerate(concurrent.futures.as_completed(future_to_binary), 1):
            binary = future_to_binary[future]
            try:
                filepath, error_msg = future.result()
                if error_msg:
                    failed_binaries.append((filepath, error_msg))
                    print(f"  [{i}/{len(binaries)}] ❌ {os.path.basename(binary)} - FAILED")
                else:
                    print(f"  [{i}/{len(binaries)}] ✅ {os.path.basename(binary)} - OK")
            except Exception as e:
                failed_binaries.append((binary, f"Test exception: {str(e)[:100]}"))
                print(f"  [{i}/{len(binaries)}] ⚠️ {os.path.basename(binary)} - ERROR")
    
    # Write results to output file
    with open(output_file, 'w') as f:
        f.write(f"Binary Analysis Results\n")
        f.write(f"Directory: {current_dir}\n")
        f.write(f"Total binaries tested: {len(binaries)}\n")
        f.write(f"Failed binaries: {len(failed_binaries)}\n")
        f.write("=" * 70 + "\n\n")
        
        if failed_binaries:
            for filepath, error_msg in failed_binaries:
                f.write(f"Binary: {filepath}\n")
                f.write(f"Error:  {error_msg}\n")
                f.write("-" * 70 + "\n")
        else:
            f.write("✓ All binaries tested successfully!\n")
    
    # Print summary
    print("\n" + "=" * 70)
    print(f"Total binaries tested: {len(binaries)}")
    print(f"Failed: {len(failed_binaries)}")
    print(f"Success: {len(binaries) - len(failed_binaries)}")
    
    if failed_binaries:
        print(f"\n❌ Failed binaries written to: {output_file}")
        print("\nFirst 5 failures:")
        for filepath, error_msg in failed_binaries[:5]:
            print(f"  • {os.path.basename(filepath)}")
            print(f"    → {error_msg[:100]}")
    else:
        print(f"\n✅ All binaries are working correctly!")
        print(f"Report written to: {output_file}")
    
    print("=" * 70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nScan interrupted by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
