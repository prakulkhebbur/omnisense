"""
Quick Test Script for Speech-to-Text
Tests microphone and transcription with a 10-second recording
"""

from speech_to_text import RealtimeSpeechToText
import time

def quick_test():
    """Quick 10-second test of the system"""
    print("\n" + "="*70)
    print("QUICK TEST - 10 SECOND RECORDING")
    print("="*70)
    
    # Initialize with fastest setup
    print("\nInitializing speech-to-text system...")
    
    try:
        # Try faster-whisper first (best option)
        stt = RealtimeSpeechToText(
            engine="faster-whisper",
            model_size="tiny",  # Using tiny for quick testing
            language="en",
            chunk_duration=2
        )
    except:
        try:
            # Fallback to regular whisper
            stt = RealtimeSpeechToText(
                engine="whisper",
                model_size="tiny",
                language="en",
                chunk_duration=2
            )
        except:
            try:
                # Fallback to Google
                stt = RealtimeSpeechToText(
                    engine="google",
                    language="en",
                    chunk_duration=2
                )
            except Exception as e:
                print(f"\n❌ ERROR: Could not initialize any engine!")
                print(f"Error: {e}")
                print("\nPlease install at least one engine:")
                print("  pip install faster-whisper")
                return
    
    # List microphones
    devices = stt.list_microphones()
    if not devices:
        print("❌ No microphone found!")
        return
    
    # Use default microphone
    print("\n✓ Using default microphone")
    
    # Start recording
    print("\n" + "="*70)
    print("🎤 RECORDING FOR 10 SECONDS...")
    print("="*70)
    print("\n💬 Say something like:")
    print("   'Hello, this is a test of the speech to text system.'")
    print("   'The quick brown fox jumps over the lazy dog.'")
    print("   'Testing one two three.'")
    print("\n" + "-"*70)
    
    try:
        stt.start()
        
        # Record for 10 seconds
        time.sleep(50)
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ ERROR during recording: {e}")
    finally:
        # Stop
        stt.stop()
        
        # Show results
        print("\n" + "="*70)
        print("TEST RESULTS")
        print("="*70)
        
        if stt.transcripts:
            print(f"\n✓ Successfully transcribed {len(stt.transcripts)} chunks")
            
            # Show stats
            stats = stt.get_stats()
            if stats:
                print(f"\nStatistics:")
                print(f"  - Total words: {stats['total_words']}")
                print(f"  - Average transcription time: {stats['avg_transcription_time']}s per chunk")
            
            # Show full transcript
            print(f"\n📝 Full Transcript:")
            print("-"*70)
            print(stt.get_full_transcript())
            print("-"*70)
            
            # Save
            print(f"\n💾 Saving results...")
            stt.save_transcript("test_transcript")
            stt.save_audio("test_recording")
            
            print("\n✅ TEST PASSED!")
            print("\nYour speech-to-text system is working correctly!")
            
        else:
            print("\n⚠️  No audio was transcribed")
            print("\nTroubleshooting:")
            print("  1. Check that your microphone is working")
            print("  2. Make sure you spoke loud and clear")
            print("  3. Check microphone permissions")
            print("  4. Try speaking closer to the microphone")
        
        # Cleanup
        stt.cleanup()
    
    print("\n" + "="*70)
    print("Test complete!")
    print("="*70 + "\n")


if __name__ == "__main__":
    quick_test()