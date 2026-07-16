#!/data/data/com.termux/files/usr/bin/env python
import os
import sys
import subprocess
import shutil


def shrink_pdf_mobile(file_path):
    # Ensure the file exists
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)

    # Verify ghostscript is installed / accessible
    gs_executable = "gs"
    if not shutil.which(gs_executable):
        if shutil.which("gswin64c"):
            gs_executable = "gswin64c"
        else:
            print("Error: Ghostscript ('gs' or 'gswin64c') is not installed or not in your PATH.")
            sys.exit(1)

    orig_size = os.path.getsize(file_path)
    print(f"Original size: {orig_size / 1024 / 1024:.2f} MB")
    print("Compressing for mobile viewing... (72 DPI + Linearization)")

    temp_path = file_path + ".tmp"

    # Ghostscript arguments tuned specifically for mobile devices
    gs_args = [
        gs_executable,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        "-dPDFSETTINGS=/screen",  # Forces max compression / 72 DPI for mobile
        "-dFastWebView=true",  # Linearizes PDF for instant "web/mobile stream" viewing
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        f"-sOutputFile={temp_path}",
        file_path,
    ]

    try:
        # Run Ghostscript process
        result = subprocess.run(gs_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            print(f"Ghostscript Error:\n{result.stderr}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            sys.exit(1)

        new_size = os.path.getsize(temp_path)

        # In-place update check
        if new_size < orig_size:
            os.replace(temp_path, file_path)
            print("Success! Inplace update complete.")
            print(f"New mobile-optimized size: {new_size / 1024 / 1024:.2f} MB")
            print(f"Saved: {((orig_size - new_size) / orig_size) * 100:.1f}% space")
        else:
            print("Compression did not reduce file size. Original file kept intact.")
            if os.path.exists(temp_path):
                os.remove(temp_path)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python shrink_pdf.py <filename.pdf>")
        sys.exit(1)

    filename = sys.argv[1]
    shrink_pdf_mobile(filename)
