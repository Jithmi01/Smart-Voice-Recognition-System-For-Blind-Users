"""
Audio Preprocessing and Enhancement Module
Handles audio loading, noise reduction, normalization, and validation
"""

import librosa
import numpy as np
import soundfile as sf
import noisereduce as nr
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class AudioProcessor:
    """
    Audio preprocessing pipeline for voice recognition
    Improves audio quality and consistency for better recognition accuracy
    """
    
    def __init__(self, target_sr=16000):
        """
        Initialize audio processor
        
        Args:
            target_sr: Target sampling rate in Hz (16kHz optimal for voice)
        """
        self.target_sr = target_sr
        logger.info(f"🎵 Audio Processor initialized | Target SR: {target_sr}Hz")
    
    def load_audio(self, file_path):
        """
        Load audio file and resample to target rate
        
        Args:
            file_path: Path to audio file
            
        Returns:
            tuple: (audio_array, sample_rate)
        """
        try:
            # Load audio with librosa (automatically resamples)
            audio, sr = librosa.load(
                file_path,
                sr=self.target_sr,
                mono=True  # Convert to mono
            )
            
            duration = len(audio) / sr
            logger.info(f"✅ Audio loaded: {Path(file_path).name}")
            logger.info(f"   Duration: {duration:.2f}s | SR: {sr}Hz | Samples: {len(audio)}")
            
            return audio, sr
            
        except Exception as e:
            logger.error(f"❌ Failed to load audio file: {e}")
            raise RuntimeError(f"Audio loading failed: {str(e)}")
    
    def reduce_noise(self, audio, sr, noise_reduction_strength=0.8):
        """
        Remove background noise using spectral gating
        
        Args:
            audio: Audio signal array
            sr: Sample rate
            noise_reduction_strength: Strength of noise reduction (0-1)
            
        Returns:
            numpy.ndarray: Noise-reduced audio
        """
        try:
            logger.info("🔇 Applying noise reduction...")
            
            # Apply noise reduction
            reduced_audio = nr.reduce_noise(
                y=audio,
                sr=sr,
                stationary=True,
                prop_decrease=noise_reduction_strength,
                freq_mask_smooth_hz=500,
                time_mask_smooth_ms=50
            )
            
            # Calculate SNR improvement estimate
            noise_power = np.mean((audio - reduced_audio) ** 2)
            signal_power = np.mean(reduced_audio ** 2)
            
            if noise_power > 0:
                snr_improvement = 10 * np.log10(signal_power / noise_power)
                logger.info(f"✅ Noise reduction applied | SNR improvement: ~{snr_improvement:.1f}dB")
            else:
                logger.info("✅ Noise reduction applied")
            
            return reduced_audio
            
        except Exception as e:
            logger.warning(f"⚠️  Noise reduction failed, using original audio: {e}")
            return audio
    
    def normalize_audio(self, audio, target_level=0.9):
        """
        Normalize audio amplitude to target level
        
        Args:
            audio: Audio signal array
            target_level: Target peak level (0-1)
            
        Returns:
            numpy.ndarray: Normalized audio
        """
        # Find current peak level
        current_peak = np.abs(audio).max()
        
        if current_peak > 0:
            # Calculate normalization factor
            norm_factor = target_level / current_peak
            normalized = audio * norm_factor
            
            logger.info(f"✅ Audio normalized | Peak: {current_peak:.3f} → {target_level}")
        else:
            logger.warning("⚠️  Audio is silent, skipping normalization")
            normalized = audio
        
        return normalized
    
    def trim_silence(self, audio, sr, top_db=20, frame_length=2048, hop_length=512):
        """
        Remove silence from beginning and end of audio
        
        Args:
            audio: Audio signal array
            sr: Sample rate
            top_db: Threshold in decibels below peak to consider as silence
            frame_length: Frame length for energy calculation
            hop_length: Hop length for energy calculation
            
        Returns:
            numpy.ndarray: Trimmed audio
        """
        try:
            original_length = len(audio)
            
            # Trim silence using librosa
            trimmed, trim_indices = librosa.effects.trim(
                audio,
                top_db=top_db,
                frame_length=frame_length,
                hop_length=hop_length
            )
            
            trimmed_length = len(trimmed)
            removed_duration = (original_length - trimmed_length) / sr
            
            logger.info(f"✅ Silence trimmed | Removed: {removed_duration:.2f}s | Length: {trimmed_length/sr:.2f}s")
            
            return trimmed
            
        except Exception as e:
            logger.warning(f"⚠️  Silence trimming failed, using original audio: {e}")
            return audio
    
    def apply_pre_emphasis(self, audio, coef=0.97):
        """
        Apply pre-emphasis filter to boost high frequencies
        Helps improve voice clarity
        
        Args:
            audio: Audio signal array
            coef: Pre-emphasis coefficient (typically 0.95-0.97)
            
        Returns:
            numpy.ndarray: Pre-emphasized audio
        """
        emphasized = np.append(audio[0], audio[1:] - coef * audio[:-1])
        logger.info(f"✅ Pre-emphasis applied | Coefficient: {coef}")
        return emphasized
    
    def remove_dc_offset(self, audio):
        """
        Remove DC offset (center audio around zero)
        
        Args:
            audio: Audio signal array
            
        Returns:
            numpy.ndarray: DC-corrected audio
        """
        dc_offset = np.mean(audio)
        corrected = audio - dc_offset
        
        if abs(dc_offset) > 0.01:
            logger.info(f"✅ DC offset removed | Offset: {dc_offset:.4f}")
        
        return corrected
    
    def preprocess(
        self,
        file_path,
        apply_noise_reduction=True,
        apply_normalization=True,
        apply_trimming=True,
        apply_pre_emphasis=False,
        noise_strength=0.8
    ):
        """
        Complete preprocessing pipeline
        
        Args:
            file_path: Path to audio file
            apply_noise_reduction: Whether to apply noise reduction
            apply_normalization: Whether to normalize amplitude
            apply_trimming: Whether to trim silence
            apply_pre_emphasis: Whether to apply pre-emphasis filter
            noise_strength: Noise reduction strength (0-1)
            
        Returns:
            tuple: (processed_audio, sample_rate)
        """
        logger.info("=" * 60)
        logger.info(f"🔄 AUDIO PREPROCESSING: {Path(file_path).name}")
        logger.info("=" * 60)
        
        # Step 1: Load audio
        audio, sr = self.load_audio(file_path)
        
        # Step 2: Remove DC offset
        audio = self.remove_dc_offset(audio)
        
        # Step 3: Noise reduction
        if apply_noise_reduction:
            audio = self.reduce_noise(audio, sr, noise_strength)
        
        # Step 4: Trim silence
        if apply_trimming:
            audio = self.trim_silence(audio, sr)
        
        # Step 5: Pre-emphasis (optional)
        if apply_pre_emphasis:
            audio = self.apply_pre_emphasis(audio)
        
        # Step 6: Normalize
        if apply_normalization:
            audio = self.normalize_audio(audio)
        
        logger.info(f"✅ Preprocessing completed | Final length: {len(audio)/sr:.2f}s")
        logger.info("=" * 60)
        
        return audio, sr
    
    def save_audio(self, audio, sr, output_path):
        """
        Save processed audio to file
        
        Args:
            audio: Audio signal array
            sr: Sample rate
            output_path: Output file path
        """
        try:
            # Create directory if needed
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save audio file
            sf.write(output_path, audio, sr)
            
            file_size = os.path.getsize(output_path) / 1024  # KB
            logger.info(f"✅ Audio saved: {Path(output_path).name} | Size: {file_size:.1f}KB")
            
        except Exception as e:
            logger.error(f"❌ Failed to save audio: {e}")
            raise RuntimeError(f"Audio saving failed: {str(e)}")
    
    def get_audio_duration(self, file_path):
        """
        Get audio file duration in seconds
        
        Args:
            file_path: Path to audio file
            
        Returns:
            float: Duration in seconds
        """
        try:
            audio, sr = self.load_audio(file_path)
            duration = len(audio) / sr
            return duration
        except Exception as e:
            logger.error(f"❌ Failed to get audio duration: {e}")
            return 0.0
    
    def validate_audio(self, file_path, min_duration=2, max_duration=30):
        """
        Validate audio file for voice recognition
        
        Args:
            file_path: Path to audio file
            min_duration: Minimum acceptable duration (seconds)
            max_duration: Maximum acceptable duration (seconds)
            
        Returns:
            dict: Validation result
        """
        logger.info(f"🔍 Validating audio: {Path(file_path).name}")
        
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                return {
                    "valid": False,
                    "error": "Audio file not found"
                }
            
            # Check file size (max 16MB)
            file_size = os.path.getsize(file_path)
            if file_size > 16 * 1024 * 1024:
                return {
                    "valid": False,
                    "error": f"File too large ({file_size / 1024 / 1024:.1f}MB). Max: 16MB"
                }
            
            # Load and check duration
            audio, sr = self.load_audio(file_path)
            duration = len(audio) / sr
            
            # Check minimum duration
            if duration < min_duration:
                return {
                    "valid": False,
                    "error": f"Audio too short ({duration:.1f}s). Minimum: {min_duration}s",
                    "duration": duration
                }
            
            # Check maximum duration
            if duration > max_duration:
                return {
                    "valid": False,
                    "error": f"Audio too long ({duration:.1f}s). Maximum: {max_duration}s",
                    "duration": duration
                }
            
            # Check if audio is mostly silent
            rms_energy = np.sqrt(np.mean(audio ** 2))
            
            if np.abs(audio).max() < 0.001:
                return {
                    "valid": False,
                    "error": "Audio appears to be silent or too quiet"
                }
            
            # Check if audio has very low energy (might be just noise)
            if rms_energy < 0.01:
                logger.warning(f"⚠️  Very low audio energy detected: {rms_energy:.4f}")
                logger.warning(f"💡 This might be silence or background noise only")
                # Don't reject, but warn
            
            # Check if audio has speech content (basic check)
            # Calculate zero crossing rate - speech typically has moderate ZCR
            zero_crossings = np.sum(np.abs(np.diff(np.sign(audio)))) / (2 * len(audio))
            
            if zero_crossings < 0.01:
                logger.warning(f"⚠️  Very low zero-crossing rate: {zero_crossings:.4f}")
                logger.warning(f"💡 Audio might not contain clear speech")
            
            logger.info(f"✅ Audio validation passed | Duration: {duration:.1f}s | Energy: {rms_energy:.3f}")
            
            return {
                "valid": True,
                "duration": duration,
                "sample_rate": sr,
                "num_samples": len(audio),
                "energy": float(rms_energy),
                "zero_crossing_rate": float(zero_crossings)
            }
            
        except Exception as e:
            logger.error(f"❌ Audio validation failed: {e}")
            return {
                "valid": False,
                "error": f"Validation error: {str(e)}"
            }
    
    def get_audio_stats(self, audio, sr):
        """
        Get detailed statistics about audio signal
        
        Args:
            audio: Audio signal array
            sr: Sample rate
            
        Returns:
            dict: Audio statistics
        """
        return {
            "duration": len(audio) / sr,
            "sample_rate": sr,
            "num_samples": len(audio),
            "peak_amplitude": float(np.abs(audio).max()),
            "rms_energy": float(np.sqrt(np.mean(audio ** 2))),
            "zero_crossing_rate": float(np.mean(librosa.zero_crossings(audio))),
            "spectral_centroid": float(np.mean(librosa.feature.spectral_centroid(y=audio, sr=sr)))
        }
    
    def convert_to_wav(self, input_path, output_path=None):
        """
        Convert audio file to WAV format
        
        Args:
            input_path: Input audio file path
            output_path: Output WAV file path (optional)
            
        Returns:
            str: Path to WAV file
        """
        if output_path is None:
            output_path = str(Path(input_path).with_suffix('.wav'))
        
        try:
            # Load audio
            audio, sr = self.load_audio(input_path)
            
            # Save as WAV
            self.save_audio(audio, sr, output_path)
            
            logger.info(f"✅ Converted to WAV: {Path(output_path).name}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"❌ WAV conversion failed: {e}")
            raise RuntimeError(f"Failed to convert to WAV: {str(e)}")