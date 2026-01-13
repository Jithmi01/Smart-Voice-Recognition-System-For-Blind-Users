"""
Voice Recognition Service using SpeechBrain ECAPA-TDNN
High-accuracy speaker identification and verification
FIXED: JSON serialization + Always show best match name
"""

from speechbrain.pretrained import EncoderClassifier
import numpy as np
from scipy.spatial.distance import cosine, euclidean
import logging
import os
import torch

logger = logging.getLogger(__name__)


class VoiceRecognitionService:
    """
    Voice recognition service with speaker identification and verification
    Uses SpeechBrain ECAPA-TDNN model for state-of-the-art accuracy
    """
    
    def __init__(self, model_name="speechbrain/spkrec-ecapa-voxceleb", model_save_dir="pretrained_models"):
        """
        Initialize voice recognition model
        
        Args:
            model_name: SpeechBrain model identifier
            model_save_dir: Directory to save/load pretrained model
        """
        logger.info("=" * 60)
        logger.info("🧠 Initializing Voice Recognition Service")
        logger.info("=" * 60)
        logger.info(f"📦 Model: {model_name}")
        logger.info(f"💾 Save Directory: {model_save_dir}")
        
        try:
            # Create save directory
            os.makedirs(model_save_dir, exist_ok=True)
            
            # Check for GPU availability
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"🖥️  Device: {device.upper()}")
            
            # Load pretrained ECAPA-TDNN encoder
            logger.info("⏳ Loading SpeechBrain ECAPA-TDNN model...")
            logger.info("   (First run: ~500MB download, takes 2-5 minutes)")
            
            self.encoder = EncoderClassifier.from_hparams(
                source=model_name,
                savedir=model_save_dir,
                run_opts={"device": device}
            )
            
            logger.info("✅ Voice recognition model loaded successfully!")
            logger.info(f"✅ Embedding dimension: 192")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Failed to load voice recognition model: {e}")
            logger.error("💡 Solution: Check internet connection for model download")
            raise
    
    def extract_embedding(self, audio_path):
        """
        Extract voice embedding from audio file
        
        Args:
            audio_path: Path to audio file (WAV format recommended)
            
        Returns:
            numpy.ndarray: Voice embedding vector (192 dimensions)
        """
        try:
            logger.info(f"🔍 Extracting embedding from: {os.path.basename(audio_path)}")
            
            # Load and process audio file
            import torchaudio
            
            # Load audio file
            signal, fs = torchaudio.load(audio_path)
            
            # Resample if necessary (ECAPA-TDNN expects 16kHz)
            if fs != 16000:
                resampler = torchaudio.transforms.Resample(fs, 16000)
                signal = resampler(signal)
            
            # Extract embedding using SpeechBrain (encode_batch expects batch format)
            embedding = self.encoder.encode_batch(signal)
            
            # Convert to numpy array
            embedding_np = embedding.squeeze().cpu().detach().numpy()
            
            logger.info(f"✅ Embedding extracted successfully | Shape: {embedding_np.shape}")
            
            return embedding_np
            
        except Exception as e:
            logger.error(f"❌ Embedding extraction failed: {e}")
            raise RuntimeError(f"Failed to extract voice embedding: {str(e)}")
    
    def calculate_similarity_cosine(self, embedding1, embedding2):
        """
        Calculate cosine similarity between two embeddings
        
        Args:
            embedding1: First voice embedding
            embedding2: Second voice embedding
            
        Returns:
            float: Similarity score (0-1, higher = more similar)
        """
        # Cosine similarity: 1 - cosine_distance
        similarity = 1 - cosine(embedding1, embedding2)
        return float(similarity)
    
    def calculate_similarity_euclidean(self, embedding1, embedding2):
        """
        Calculate Euclidean distance-based similarity
        
        Args:
            embedding1: First voice embedding
            embedding2: Second voice embedding
            
        Returns:
            float: Similarity score (0-1, higher = more similar)
        """
        # Normalize Euclidean distance to 0-1 range
        distance = euclidean(embedding1, embedding2)
        # Convert distance to similarity (inverse relationship)
        similarity = 1 / (1 + distance)
        return float(similarity)
    
    def calculate_similarity(self, embedding1, embedding2, method="cosine"):
        """
        Calculate similarity between embeddings
        
        Args:
            embedding1: First voice embedding
            embedding2: Second voice embedding
            method: Similarity method ("cosine" or "euclidean")
            
        Returns:
            float: Similarity score (0-1)
        """
        if method == "cosine":
            return self.calculate_similarity_cosine(embedding1, embedding2)
        elif method == "euclidean":
            return self.calculate_similarity_euclidean(embedding1, embedding2)
        else:
            raise ValueError(f"Unknown similarity method: {method}")
    
    def register_voice(self, audio_paths, user_name):
        """
        Register user voice with multiple samples
        
        Args:
            audio_paths: List of audio file paths
            user_name: Name of the user
            
        Returns:
            dict: Registration result with embeddings
        """
        logger.info("=" * 60)
        logger.info(f"📝 Registering voice for: {user_name}")
        logger.info(f"📊 Number of samples: {len(audio_paths)}")
        logger.info("=" * 60)
        
        try:
            embeddings = []
            
            for i, audio_path in enumerate(audio_paths, 1):
                logger.info(f"🔄 Processing sample {i}/{len(audio_paths)}: {os.path.basename(audio_path)}")
                
                # Extract embedding
                embedding = self.extract_embedding(audio_path)
                
                # Convert to list for JSON/MongoDB storage
                embeddings.append(embedding.tolist())
                
                logger.info(f"✅ Sample {i} processed successfully")
            
            # Calculate inter-sample similarity (quality check)
            avg_similarity = 1.0  # Default for single sample
            
            if len(embeddings) > 1:
                similarities = []
                for i in range(len(embeddings)):
                    for j in range(i + 1, len(embeddings)):
                        sim = self.calculate_similarity(
                            np.array(embeddings[i]),
                            np.array(embeddings[j])
                        )
                        similarities.append(sim)
                
                avg_similarity = float(np.mean(similarities))
                logger.info(f"📊 Inter-sample similarity: {avg_similarity:.2%}")
                
                if avg_similarity < 0.5:
                    logger.warning("⚠️  Low inter-sample similarity detected!")
                    logger.warning("💡 Recommendation: Re-record in quieter environment")
            
            logger.info(f"✅ Voice registration completed for '{user_name}'")
            logger.info("=" * 60)
            
            return {
                "success": True,
                "embeddings": embeddings,
                "num_samples": len(embeddings),
                "avg_inter_similarity": avg_similarity
            }
            
        except Exception as e:
            logger.error(f"❌ Voice registration failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def identify_speaker(self, audio_path, registered_users, threshold=0.65, method="cosine"):
        """
        Identify speaker from voice sample
        
        Args:
            audio_path: Path to audio file
            registered_users: List of user dictionaries from database
            threshold: Minimum similarity score for positive identification (0-1 range)
            method: Similarity calculation method
            
        Returns:
            dict: Identification result with confidence scores
        """
        logger.info("=" * 60)
        logger.info("🔍 Starting Speaker Identification")
        logger.info("=" * 60)
        logger.info(f"🎤 Audio file: {os.path.basename(audio_path)}")
        logger.info(f"👥 Registered users: {len(registered_users)}")
        logger.info(f"🎯 Threshold: {threshold:.2%}")
        logger.info(f"📏 Method: {method}")
        
        try:
            # Check if any users are registered
            if not registered_users or len(registered_users) == 0:
                logger.warning("⚠️  No users registered in database")
                return {
                    "identified": False,
                    "name": "No users registered",
                    "confidence": 0.0,
                    "all_scores": [],
                    "threshold": float(threshold * 100)
                }
            
            # Extract embedding from new audio
            logger.info("🔄 Extracting embedding from input audio...")
            new_embedding = self.extract_embedding(audio_path)
            
            best_match = None
            best_score = 0.0
            all_scores = []
            
            # Compare with all registered users
            logger.info(f"🔄 Comparing with {len(registered_users)} registered users...")
            
            for user in registered_users:
                user_name = user['name']
                user_embeddings = user['voice_embeddings']
                
                logger.info(f"   Comparing with: {user_name} ({len(user_embeddings)} samples)")
                
                # Calculate similarity with all embeddings of this user
                similarities = []
                for stored_embedding in user_embeddings:
                    score = self.calculate_similarity(
                        new_embedding,
                        np.array(stored_embedding),
                        method=method
                    )
                    similarities.append(score)
                
                # Use average similarity (more robust than max)
                avg_score = float(np.mean(similarities))
                max_score = float(np.max(similarities))
                min_score = float(np.min(similarities))
                
                logger.info(f"      → Avg: {avg_score:.2%} | Max: {max_score:.2%} | Min: {min_score:.2%}")
                
                # Store scores for detailed results
                all_scores.append({
                    "name": user_name,
                    "avg_score": avg_score,
                    "max_score": max_score,
                    "min_score": min_score,
                    "num_samples": int(len(similarities))
                })
                
                # Update best match
                if avg_score > best_score:
                    best_score = avg_score
                    best_match = user_name
            
            # Sort scores by avg_score (descending)
            all_scores.sort(key=lambda x: x['avg_score'], reverse=True)
            
            # Ensure Python native types
            best_score = float(best_score)
            threshold = float(threshold)
            
            # CUSTOM LOGIC:
            # - >= 30%: Show best match name
            # - < 30%: Show "Unknown Person Speaking"
            # Note: Very low scores (near 0) might indicate silent/no audio
            
            MIN_DETECTION_THRESHOLD = 0.30  # 30% minimum
            SILENCE_THRESHOLD = 0.05        # 5% likely silence/no voice
            
            confidence_percentage = best_score * 100
            
            # Determine identification status and name
            if best_score < SILENCE_THRESHOLD:
                # Likely silence or no clear voice detected
                identified = False
                result_name = "Can't hear someone speaking"
                status_msg = "NO VOICE DETECTED"
                logger.info("=" * 60)
                logger.info(f"⚠️  {status_msg}")
                logger.info(f"📊 Maximum score: {best_score:.2%} (too low)")
                logger.info(f"💡 Possible causes: silence, background noise, or unclear audio")
                logger.info("=" * 60)
                
            elif best_score < MIN_DETECTION_THRESHOLD:
                # Voice detected but confidence too low
                identified = False
                result_name = "Unknown Person Speaking"
                status_msg = "UNKNOWN SPEAKER"
                logger.info("=" * 60)
                logger.info(f"⚠️  {status_msg}")
                logger.info(f"📊 Best match: {best_match} ({best_score:.2%})")
                logger.info(f"🎯 Below 30% threshold")
                logger.info(f"💡 This person is not registered or audio quality is poor")
                logger.info("=" * 60)
                
            elif best_score >= MIN_DETECTION_THRESHOLD and best_score < threshold:
                # Confidence above 30% but below main threshold (e.g., 65%)
                identified = True  # We can identify, but with lower confidence
                result_name = best_match
                status_msg = "LOW CONFIDENCE MATCH"
                logger.info("=" * 60)
                logger.info(f"⚠️  {status_msg}")
                logger.info(f"📊 Speaker: {best_match}")
                logger.info(f"📊 Confidence: {best_score:.2%}")
                logger.info(f"🎯 Above 30% (show name) but below {threshold:.0%} (main threshold)")
                logger.info("=" * 60)
                
            else:
                # High confidence match
                identified = True
                result_name = best_match
                status_msg = "SPEAKER IDENTIFIED"
                logger.info("=" * 60)
                logger.info(f"✅ {status_msg}")
                logger.info(f"📊 Speaker: {best_match}")
                logger.info(f"📊 Confidence: {best_score:.2%}")
                logger.info(f"🎯 Above threshold: {threshold:.2%}")
                logger.info("=" * 60)
            
            logger.info(f"🔍 Final: identified={identified}, name={result_name}, confidence={confidence_percentage:.2f}%")
            
            return {
                "identified": bool(identified),
                "name": result_name,
                "confidence": round(confidence_percentage, 2),
                "all_scores": all_scores,
                "threshold": round(threshold * 100, 2),
                "method": method
            }
            
        except Exception as e:
            logger.error(f"❌ Speaker identification failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "identified": False,
                "name": "Error",
                "confidence": 0.0,
                "error": str(e),
                "all_scores": []
            }
    
    def verify_speaker(self, audio_path, claimed_name, registered_users, threshold=0.65):
        """
        Verify if speaker matches claimed identity (1:1 verification)
        
        Args:
            audio_path: Path to audio file
            claimed_name: Name claimed by speaker
            registered_users: List of users from database
            threshold: Minimum similarity score
            
        Returns:
            dict: Verification result
        """
        logger.info("=" * 60)
        logger.info(f"🔐 Verifying speaker identity: {claimed_name}")
        logger.info("=" * 60)
        
        try:
            # Find claimed user in database
            claimed_user = next(
                (u for u in registered_users if u['name'] == claimed_name),
                None
            )
            
            if not claimed_user:
                logger.warning(f"⚠️  User '{claimed_name}' not found in database")
                return {
                    "verified": False,
                    "message": f"User '{claimed_name}' not registered",
                    "confidence": 0.0
                }
            
            # Extract embedding from input audio
            new_embedding = self.extract_embedding(audio_path)
            
            # Compare with claimed user's embeddings
            similarities = []
            for stored_embedding in claimed_user['voice_embeddings']:
                score = self.calculate_similarity(
                    new_embedding,
                    np.array(stored_embedding)
                )
                similarities.append(score)
            
            avg_score = float(np.mean(similarities))
            max_score = float(np.max(similarities))
            
            logger.info(f"📊 Verification scores:")
            logger.info(f"   Average: {avg_score:.2%}")
            logger.info(f"   Maximum: {max_score:.2%}")
            logger.info(f"   Threshold: {threshold:.2%}")
            
            # Verify against threshold
            verified = bool(avg_score >= threshold)
            
            if verified:
                logger.info(f"✅ VERIFIED: Voice matches '{claimed_name}'")
                message = f"Voice verified as '{claimed_name}'"
            else:
                logger.info(f"❌ REJECTED: Voice does not match '{claimed_name}'")
                message = f"Voice does not match '{claimed_name}'"
            
            logger.info("=" * 60)
            
            return {
                "verified": verified,
                "message": message,
                "confidence": round(avg_score * 100, 2),
                "max_confidence": round(max_score * 100, 2)
            }
            
        except Exception as e:
            logger.error(f"❌ Speaker verification failed: {e}")
            return {
                "verified": False,
                "message": f"Verification error: {str(e)}",
                "confidence": 0.0
            }
    
    def calculate_optimal_threshold(self, user_embeddings):
        """
        Calculate optimal threshold based on user's own voice variations
        
        Args:
            user_embeddings: List of embeddings for a single user
            
        Returns:
            float: Recommended threshold value
        """
        if len(user_embeddings) < 2:
            return 0.65  # Default threshold
        
        # Calculate all pairwise similarities
        similarities = []
        for i in range(len(user_embeddings)):
            for j in range(i + 1, len(user_embeddings)):
                sim = self.calculate_similarity(
                    np.array(user_embeddings[i]),
                    np.array(user_embeddings[j])
                )
                similarities.append(sim)
        
        # Use mean - 1 standard deviation as threshold
        mean_sim = float(np.mean(similarities))
        std_sim = float(np.std(similarities))
        
        optimal_threshold = mean_sim - std_sim
        
        # Ensure threshold is within reasonable range
        optimal_threshold = max(0.5, min(0.8, optimal_threshold))
        
        logger.info(f"📊 Optimal threshold calculated: {optimal_threshold:.2%}")
        logger.info(f"   Based on {len(similarities)} pairwise comparisons")
        
        return float(optimal_threshold)
    
    def get_embedding_statistics(self, embeddings):
        """
        Get statistics about a set of embeddings
        
        Args:
            embeddings: List of embedding arrays
            
        Returns:
            dict: Statistics about embeddings
        """
        if not embeddings:
            return {}
        
        embeddings_np = [np.array(e) for e in embeddings]
        
        # Calculate pairwise similarities
        similarities = []
        for i in range(len(embeddings_np)):
            for j in range(i + 1, len(embeddings_np)):
                sim = self.calculate_similarity(embeddings_np[i], embeddings_np[j])
                similarities.append(sim)
        
        return {
            "num_embeddings": int(len(embeddings)),
            "embedding_dimension": int(len(embeddings_np[0])) if embeddings_np else 0,
            "avg_similarity": float(np.mean(similarities)) if similarities else 0.0,
            "std_similarity": float(np.std(similarities)) if similarities else 0.0,
            "min_similarity": float(np.min(similarities)) if similarities else 0.0,
            "max_similarity": float(np.max(similarities)) if similarities else 0.0
        }