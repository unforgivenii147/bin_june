#!/data/data/com.termux/files/usr/bin/env python

"""Module for audio2text.py."""

import os
import signal
import sys
import tempfile
import time

import speech_recognition as sr
from pydub import AudioSegment

# Global flag for graceful shutdown
interrupted = False
output_file_global = "out.txt"


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global interrupted
    print("\n\n⚠️  Interrupt received. Saving progress and exiting...")
    interrupted = True


def wav_to_text_chunked(input_file, output_file="out.txt", chunk_duration_ms=30000):
    """
    Convert WAV audio file to text in chunks and save progress
    """
    global output_file_global
    output_file_global = output_file

    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)

    # Check file extension
    if not input_file.lower().endswith(".wav"):
        print("Warning: Input file doesn't have .wav extension. Continuing anyway...")

    print(f"Processing: {input_file}")
    print(f"Chunk duration: {chunk_duration_ms / 1000} seconds")
    print(f"Output file: {output_file}")
    print("Press Ctrl+C to save progress and exit\n")

    try:
        # Load the audio file
        print("Loading audio file...")
        audio = AudioSegment.from_file(input_file, format="wav")

        # Calculate total duration
        total_duration_ms = len(audio)
        total_duration_sec = total_duration_ms / 1000
        print(f"Audio duration: {total_duration_sec:.2f} seconds")

        # Calculate number of chunks
        num_chunks = (total_duration_ms + chunk_duration_ms - 1) // chunk_duration_ms
        print(f"Processing in {num_chunks} chunk(s)\n")

        # Initialize recognizer
        recognizer = sr.Recognizer()

        # Clear output file
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("")

        full_text = []

        # Process each chunk
        for i in range(num_chunks):
            if interrupted:
                print("\nExiting due to interrupt...")
                break

            start_ms = i * chunk_duration_ms
            end_ms = min((i + 1) * chunk_duration_ms, total_duration_ms)

            chunk_start_sec = start_ms / 1000
            chunk_end_sec = end_ms / 1000

            print(f"Processing chunk {i + 1}/{num_chunks} ({chunk_start_sec:.1f}s - {chunk_end_sec:.1f}s)...")

            try:
                # Extract chunk
                chunk = audio[start_ms:end_ms]

                # Export chunk to temporary WAV file
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
                    temp_wav_path = temp_wav.name

                chunk.export(temp_wav_path, format="wav")

                # Transcribe chunk
                with sr.AudioFile(temp_wav_path) as source:
                    audio_data = recognizer.record(source)

                try:
                    text = recognizer.recognize_google(audio_data)

                    if text.strip():
                        # Append to full text
                        full_text.append(text)

                        # Save progress to file
                        with open(output_file, "a", encoding="utf-8") as f:
                            f.write(text + " ")

                        print(
                            f"  ✓ Chunk {i + 1} transcribed: {text[:100]}..."
                            if len(text) > 100
                            else f"  ✓ Chunk {i + 1} transcribed: {text}"
                        )
                    else:
                        print(f"  - Chunk {i + 1}: No speech detected")

                except sr.UnknownValueError:
                    print(f"  - Chunk {i + 1}: Could not understand audio")
                except sr.RequestError as e:
                    print(f"  - Chunk {i + 1}: API error - {e}")

            except Exception as e:
                print(f"  ✗ Error processing chunk {i + 1}: {e}")

            finally:
                # Clean up temporary file
                if "temp_wav_path" in locals() and os.path.exists(temp_wav_path):
                    os.unlink(temp_wav_path)

            # Small delay between API calls to avoid rate limiting
            if i < num_chunks - 1 and not interrupted:
                time.sleep(1)

        # Print summary
        print(f"\n{'=' * 50}")
        if interrupted:
            print(f"⚠️  Process interrupted. Progress saved to: {output_file}")
            print(f"Completed: {i + 1}/{num_chunks} chunks")
        else:
            print(f"✓ Full transcription saved to: {output_file}")
            print(f"Completed: {num_chunks}/{num_chunks} chunks")

        # Show preview of transcription
        if full_text:
            combined_text = " ".join(full_text)
            preview = combined_text[:300] + "..." if len(combined_text) > 300 else combined_text
            print(f"\nTranscription preview:\n{preview}")

    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 4:
        print("Usage: python wav_to_text.py <input_file.wav> [output_file.txt] [chunk_duration_seconds]")
        print("Example: python wav_to_text.py recording.wav")
        print("Example: python wav_to_text.py recording.wav output.txt 30")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) >= 3 else "out.txt"
    chunk_duration = int(sys.argv[3]) * 1000 if len(sys.argv) == 4 else 30000  # Default 30 seconds

    wav_to_text_chunked(input_file, output_file, chunk_duration)
