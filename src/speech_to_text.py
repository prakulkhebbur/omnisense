"""
Real-time Speech-to-Text Transcription System
Optimized for accuracy and real-time performance with microphone input
"""

import pyaudio
import wave
import threading
import queue
import json
import time
from datetime import datetime
from pathlib import Path
import numpy as np
import sys

# Import available engines
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
    print("✓ Faster-Whisper available")
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    print("✗ Faster-Whisper not available")

try:
    import whisper
    WHISPER_AVAILABLE = True
    print("✓ OpenAI Whisper available")
except ImportError:
    WHISPER_AVAILABLE = False
    print("✗ OpenAI Whisper not available")

try:
    import speech_recognition as sr
    GOOGLE_SR_AVAILABLE = True
    print("✓ Google Speech Recognition available")
except ImportError:
    GOOGLE_SR_AVAILABLE = False
    print("✗ Google Speech Recognition not available")


class RealtimeSpeechToText:
    """
    Real-time speech-to-text transcription system
    Designed for high accuracy with live microphone input
    """
    
    def __init__(self, 
                 engine="faster-whisper",
                 model_size="base",
                 language="en",
                 chunk_duration=3):
        """
        Initialize the speech-to-text system
        
        Args:
            engine: "faster-whisper", "whisper", or "google"
            model_size: "tiny", "base", "small", "medium", "large" (for Whisper)
            language: Language code (e.g., "en" for English)
            chunk_duration: Audio chunk size in seconds
        """
        self.engine = engine
        self.model_size = model_size
        self.language = language
        self.chunk_duration = chunk_duration
        
        # Audio configuration
        self.RATE = 16000  # 16kHz sample rate for best Whisper performance
        self.CHANNELS = 1  # Mono
        self.FORMAT = pyaudio.paInt16
        self.CHUNK_SIZE = int(self.RATE * chunk_duration)
        
        # Queues for threading
        self.audio_queue = queue.Queue()
        self.text_queue = queue.Queue()
        
        # Control flags
        self.is_running = False
        
        # Storage
        self.transcripts = []
        self.audio_buffer = []
        
        # Initialize PyAudio
        self.audio = pyaudio.PyAudio()
        
        # Load the transcription model
        self._load_model()
    
    def _load_model(self):
        """Load the selected transcription engine"""
        print(f"\n{'='*60}")
        print(f"Loading {self.engine} engine...")
        print(f"{'='*60}")
        
        if self.engine == "faster-whisper" and FASTER_WHISPER_AVAILABLE:
            print(f"Model: {self.model_size}")
            print("Device: CPU (using int8 for speed)")
            print("Loading model... This may take a moment...")
            
            self.model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8"
            )
            print("✓ Faster-Whisper model loaded successfully!")
            
        elif self.engine == "whisper" and WHISPER_AVAILABLE:
            print(f"Model: {self.model_size}")
            print("Loading model... This may take a moment...")
            
            self.model = whisper.load_model(self.model_size)
            print("✓ Whisper model loaded successfully!")
            
        elif self.engine == "google" and GOOGLE_SR_AVAILABLE:
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = 300
            self.recognizer.dynamic_energy_threshold = True
            print("✓ Google Speech Recognition initialized!")
            
        else:
            available = []
            if FASTER_WHISPER_AVAILABLE:
                available.append("faster-whisper")
            if WHISPER_AVAILABLE:
                available.append("whisper")
            if GOOGLE_SR_AVAILABLE:
                available.append("google")
            
            raise ValueError(
                f"Engine '{self.engine}' not available.\n"
                f"Available engines: {', '.join(available) if available else 'None'}\n"
                f"Install with: pip install faster-whisper (or openai-whisper or SpeechRecognition)"
            )
        
        print(f"{'='*60}\n")
    
    def list_microphones(self):
        """List available microphone devices"""
        print("\n" + "="*60)
        print("AVAILABLE MICROPHONE DEVICES")
        print("="*60)
        
        info = self.audio.get_host_api_info_by_index(0)
        numdevices = info.get('deviceCount')
        
        input_devices = []
        for i in range(numdevices):
            device_info = self.audio.get_device_info_by_host_api_device_index(0, i)
            if device_info.get('maxInputChannels') > 0:
                input_devices.append((i, device_info.get('name')))
                print(f"  [{i}] {device_info.get('name')}")
        
        print("="*60 + "\n")
        return input_devices
    
    def start(self, device_index=None):
        """
        Start real-time transcription
        
        Args:
            device_index: Microphone device index (None for default)
        """
        self.is_running = True
        
        print(f"\n{'='*60}")
        print("STARTING REAL-TIME TRANSCRIPTION")
        print(f"{'='*60}")
        print(f"Engine: {self.engine}")
        print(f"Model: {self.model_size if self.engine != 'google' else 'Google Cloud'}")
        print(f"Language: {self.language}")
        print(f"Chunk Duration: {self.chunk_duration}s")
        print(f"Sample Rate: {self.RATE}Hz")
        print(f"{'='*60}\n")
        
        # Start recording thread
        self.record_thread = threading.Thread(
            target=self._record_audio,
            args=(device_index,),
            daemon=True
        )
        self.record_thread.start()
        
        # Start transcription thread
        self.transcribe_thread = threading.Thread(
            target=self._transcribe_audio,
            daemon=True
        )
        self.transcribe_thread.start()
        
        print("🎤 LISTENING... Speak into your microphone")
        print("📝 Transcription will appear below:")
        print("-" * 60)
    
    def _record_audio(self, device_index):
        """Record audio from microphone"""
        try:
            stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.CHUNK_SIZE
            )
            
            chunk_count = 0
            while self.is_running:
                try:
                    # Read audio chunk
                    audio_data = stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
                    self.audio_buffer.append(audio_data)
                    
                    # Add to queue for transcription
                    self.audio_queue.put((audio_data, datetime.now(), chunk_count))
                    chunk_count += 1
                    
                except Exception as e:
                    print(f"Error reading audio: {e}")
                    break
            
            stream.stop_stream()
            stream.close()
            
        except Exception as e:
            print(f"Error opening audio stream: {e}")
            print("Please check your microphone device index")
            self.is_running = False
    
    def _transcribe_audio(self):
        """Transcribe audio chunks in real-time"""
        while self.is_running or not self.audio_queue.empty():
            try:
                # Get audio chunk from queue
                audio_data, timestamp, chunk_num = self.audio_queue.get(timeout=1)
                
                # Convert to numpy array
                audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                
                # Skip if audio is too quiet (silence detection)
                if np.abs(audio_np).mean() < 0.01:
                    continue
                
                # Transcribe based on engine
                start_time = time.time()
                
                if self.engine == "faster-whisper":
                    text = self._transcribe_faster_whisper(audio_np)
                elif self.engine == "whisper":
                    text = self._transcribe_whisper(audio_np)
                elif self.engine == "google":
                    text = self._transcribe_google(audio_data)
                else:
                    text = ""
                
                transcription_time = time.time() - start_time
                
                # Store and display if not empty
                if text.strip():
                    entry = {
                        "chunk": chunk_num,
                        "timestamp": timestamp.isoformat(),
                        "text": text.strip(),
                        "transcription_time": round(transcription_time, 2)
                    }
                    
                    self.transcripts.append(entry)
                    self.text_queue.put(entry)
                    
                    # Display with timing info
                    time_str = timestamp.strftime('%H:%M:%S')
                    print(f"\n[{time_str}] ({transcription_time:.2f}s)")
                    print(f"➜ {text.strip()}")
                    print("-" * 60)
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error during transcription: {e}")
                import traceback
                traceback.print_exc()
    
    def _transcribe_faster_whisper(self, audio_np):
        """Transcribe using Faster-Whisper"""
        segments, info = self.model.transcribe(
            audio_np,
            language=self.language,
            beam_size=5,
            vad_filter=True,  # Voice Activity Detection
        )
        
        text = " ".join([segment.text for segment in segments])
        return text
    
    def _transcribe_whisper(self, audio_np):
        """Transcribe using OpenAI Whisper"""
        result = self.model.transcribe(
            audio_np,
            language=self.language,
            fp16=False
        )
        return result["text"]
    
    def _transcribe_google(self, audio_data):
        """Transcribe using Google Speech Recognition"""
        try:
            audio = sr.AudioData(audio_data, self.RATE, 2)
            text = self.recognizer.recognize_google(
                audio,
                language=f"{self.language}-US"
            )
            return text
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            print(f"Google API error: {e}")
            return ""
    
    def stop(self):
        """Stop transcription"""
        print("\n" + "="*60)
        print("STOPPING TRANSCRIPTION...")
        print("="*60)
        
        self.is_running = False
        
        # Wait for threads to finish
        if hasattr(self, 'record_thread'):
            self.record_thread.join(timeout=2)
        if hasattr(self, 'transcribe_thread'):
            self.transcribe_thread.join(timeout=2)
        
        print("✓ Transcription stopped")
    
    def get_full_transcript(self):
        """Get complete transcript as single string"""
        return " ".join([t["text"] for t in self.transcripts])
    
    def save_transcript(self, filename="transcript"):
        """Save transcript to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save as JSON
        json_path = f"{filename}_{timestamp}.json"
        with open(json_path, 'w') as f:
            json.dump({
                "metadata": {
                    "engine": self.engine,
                    "model": self.model_size if self.engine != "google" else "google",
                    "language": self.language,
                    "total_chunks": len(self.transcripts),
                    "recording_date": timestamp
                },
                "transcripts": self.transcripts,
                "full_text": self.get_full_transcript()
            }, f, indent=2)
        
        # Save as text
        txt_path = f"{filename}_{timestamp}.txt"
        with open(txt_path, 'w') as f:
            f.write(f"Transcription - {timestamp}\n")
            f.write(f"Engine: {self.engine}\n")
            f.write("="*60 + "\n\n")
            
            for entry in self.transcripts:
                ts = datetime.fromisoformat(entry['timestamp']).strftime('%H:%M:%S')
                f.write(f"[{ts}] {entry['text']}\n")
            
            f.write("\n" + "="*60 + "\n")
            f.write("FULL TRANSCRIPT:\n")
            f.write("="*60 + "\n")
            f.write(self.get_full_transcript())
        
        print(f"\n✓ Transcript saved:")
        print(f"  - {json_path}")
        print(f"  - {txt_path}")
        
        return json_path, txt_path
    
    def save_audio(self, filename="recording"):
        """Save recorded audio to WAV file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        wav_path = f"{filename}_{timestamp}.wav"
        
        with wave.open(wav_path, 'wb') as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
            wf.setframerate(self.RATE)
            wf.writeframes(b''.join(self.audio_buffer))
        
        print(f"  - {wav_path}")
        return wav_path
    
    def get_stats(self):
        """Get transcription statistics"""
        if not self.transcripts:
            return None
        
        total_words = sum(len(t["text"].split()) for t in self.transcripts)
        total_time = sum(t["transcription_time"] for t in self.transcripts)
        
        return {
            "total_chunks": len(self.transcripts),
            "total_words": total_words,
            "total_transcription_time": round(total_time, 2),
            "avg_transcription_time": round(total_time / len(self.transcripts), 2),
            "words_per_chunk": round(total_words / len(self.transcripts), 1)
        }
    
    def cleanup(self):
        """Clean up resources"""
        self.audio.terminate()


def main():
    """Main function to run the transcription system"""
    print("\n" + "="*60)
    print("REAL-TIME SPEECH-TO-TEXT TRANSCRIPTION")
    print("="*60)
    
    # Check what's available
    engines = []
    if FASTER_WHISPER_AVAILABLE:
        engines.append("faster-whisper (Recommended)")
    if WHISPER_AVAILABLE:
        engines.append("whisper")
    if GOOGLE_SR_AVAILABLE:
        engines.append("google")
    
    if not engines:
        print("\n❌ ERROR: No transcription engine available!")
        print("\nPlease install one of the following:")
        print("  pip install faster-whisper  (Recommended - Fast & Accurate)")
        print("  pip install openai-whisper  (Very Accurate)")
        print("  pip install SpeechRecognition  (Simple & Free)")
        return
    
    print(f"\nAvailable engines: {', '.join(engines)}")
    
    # Choose engine
    if FASTER_WHISPER_AVAILABLE:
        engine = "faster-whisper"
        model_size = "base"  # Good balance of speed and accuracy
    elif WHISPER_AVAILABLE:
        engine = "whisper"
        model_size = "base"
    else:
        engine = "google"
        model_size = None
    
    print(f"Using: {engine}")
    
    # Initialize
    try:
        stt = RealtimeSpeechToText(
            engine=engine,
            model_size=model_size,
            language="en",
            chunk_duration=3
        )
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return
    
    # List microphones
    devices = stt.list_microphones()
    
    if not devices:
        print("❌ No microphone devices found!")
        return
    
    # Select microphone
    if len(devices) == 1:
        device_index = devices[0][0]
        print(f"Using microphone: {devices[0][1]}")
    else:
        try:
            choice = input("\nSelect microphone index (or press Enter for default): ").strip()
            device_index = int(choice) if choice else None
        except ValueError:
            device_index = None
    
    # Start transcription
    try:
        stt.start(device_index=device_index)
        
        # Run for specified duration or until user stops
        print("\n💡 TIP: Speak clearly into your microphone")
        print("💡 TIP: Press Ctrl+C to stop\n")
        
        # Keep running until interrupted
        try:
            while stt.is_running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\n⏹️  Stopping...")
    
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Stop and save
        stt.stop()
        
        # Display stats
        stats = stt.get_stats()
        if stats:
            print("\n" + "="*60)
            print("TRANSCRIPTION STATISTICS")
            print("="*60)
            print(f"Total chunks processed: {stats['total_chunks']}")
            print(f"Total words: {stats['total_words']}")
            print(f"Average words per chunk: {stats['words_per_chunk']}")
            print(f"Total transcription time: {stats['total_transcription_time']}s")
            print(f"Average time per chunk: {stats['avg_transcription_time']}s")
            print("="*60)
        
        # Save results
        if stt.transcripts:
            print("\n" + "="*60)
            print("SAVING RESULTS")
            print("="*60)
            stt.save_transcript()
            stt.save_audio()
            print("="*60)
            
            # Show full transcript
            print("\n" + "="*60)
            print("FULL TRANSCRIPT")
            print("="*60)
            print(stt.get_full_transcript())
            print("="*60)
        else:
            print("\n⚠️  No audio was transcribed")
        
        # Cleanup
        stt.cleanup()
        print("\n✓ Done!\n")


if __name__ == "__main__":
    main()