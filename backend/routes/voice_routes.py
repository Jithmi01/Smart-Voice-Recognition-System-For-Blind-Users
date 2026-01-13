"""
Voice Recognition API Routes
Handles voice registration, identification, and user management
"""

from flask import Blueprint, request, jsonify
import os
import logging
from werkzeug.utils import secure_filename
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
import traceback

logger = logging.getLogger(__name__)

voice_bp = Blueprint('voice', __name__, url_prefix='/api/voice')


def allowed_file(filename, allowed_extensions):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions


def init_voice_routes(audio_processor, voice_service, mongo_uri, db_name, config):
    """
    Initialize voice routes with dependencies
    
    Args:
        audio_processor: AudioProcessor instance
        voice_service: VoiceRecognitionService instance
        mongo_uri: MongoDB connection URI
        db_name: Database name
        config: Configuration object
    """
    
    # Initialize MongoDB connection
    try:
        mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        mongo_client.admin.command('ping')
        db = mongo_client[db_name]
        users_collection = db['users']
        logger.info(f"✅ MongoDB connected | Database: {db_name}")
    except ConnectionFailure as e:
        logger.error(f"❌ MongoDB connection failed: {e}")
        raise
    
    
    @voice_bp.route('/register', methods=['POST'])
    def register_user():
        """
        Register new user with voice samples
        
        Form Data:
            name: User's name (required)
            audio_files: List of audio files (required, 1-5 files)
            
        Returns:
            JSON: Registration result
        """
        logger.info("=" * 60)
        logger.info("📝 NEW REGISTRATION REQUEST")
        logger.info("=" * 60)
        
        try:
            # Validate user name
            if 'name' not in request.form:
                logger.warning("⚠️  Missing 'name' field")
                return jsonify({
                    "success": False,
                    "error": "User name is required"
                }), 400
            
            user_name = request.form['name'].strip()
            
            if not user_name:
                logger.warning("⚠️  Empty user name")
                return jsonify({
                    "success": False,
                    "error": "User name cannot be empty"
                }), 400
            
            if len(user_name) < 2:
                return jsonify({
                    "success": False,
                    "error": "User name must be at least 2 characters"
                }), 400
            
            logger.info(f"👤 User name: {user_name}")
            
            # Check if user already exists
            existing_user = users_collection.find_one({"name": user_name})
            if existing_user:
                logger.warning(f"⚠️  User '{user_name}' already exists")
                return jsonify({
                    "success": False,
                    "error": f"User '{user_name}' is already registered"
                }), 400
            
            # Validate audio files
            if 'audio_files' not in request.files:
                logger.warning("⚠️  No audio files provided")
                return jsonify({
                    "success": False,
                    "error": "Audio files are required"
                }), 400
            
            audio_files = request.files.getlist('audio_files')
            
            if len(audio_files) < 1:
                logger.warning("⚠️  No audio files uploaded")
                return jsonify({
                    "success": False,
                    "error": "At least 1 audio sample is required"
                }), 400
            
            if len(audio_files) > 5:
                logger.warning(f"⚠️  Too many files: {len(audio_files)}")
                return jsonify({
                    "success": False,
                    "error": "Maximum 5 audio samples allowed"
                }), 400
            
            logger.info(f"📊 Number of audio files: {len(audio_files)}")
            
            # Process and save audio files
            audio_paths = []
            processed_paths = []
            
            for i, audio_file in enumerate(audio_files, 1):
                # Validate file extension
                if not allowed_file(audio_file.filename, config.ALLOWED_EXTENSIONS):
                    logger.warning(f"⚠️  Invalid file format: {audio_file.filename}")
                    return jsonify({
                        "success": False,
                        "error": f"Invalid file format: {audio_file.filename}. Allowed: {', '.join(config.ALLOWED_EXTENSIONS)}"
                    }), 400
                
                # Save uploaded file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = secure_filename(f"{user_name}_{timestamp}_sample{i}_{audio_file.filename}")
                filepath = os.path.join(config.UPLOAD_FOLDER, filename)
                
                audio_file.save(filepath)
                audio_paths.append(filepath)
                
                logger.info(f"📁 File {i} saved: {filename}")
                
                # Validate audio
                validation = audio_processor.validate_audio(
                    filepath,
                    min_duration=config.MIN_AUDIO_DURATION,
                    max_duration=config.MAX_AUDIO_DURATION
                )
                
                if not validation['valid']:
                    logger.error(f"❌ Audio validation failed: {validation['error']}")
                    # Clean up saved files
                    for path in audio_paths:
                        if os.path.exists(path):
                            os.remove(path)
                    
                    return jsonify({
                        "success": False,
                        "error": f"Sample {i}: {validation['error']}"
                    }), 400
                
                logger.info(f"✅ Sample {i} validated | Duration: {validation['duration']:.1f}s")
                
                # Preprocess audio
                try:
                    processed_audio, sr = audio_processor.preprocess(
                        filepath,
                        apply_noise_reduction=True,
                        apply_normalization=True,
                        apply_trimming=True
                    )
                    
                    # Save preprocessed audio
                    processed_filename = filename.replace('.', '_processed.')
                    processed_path = os.path.join(config.UPLOAD_FOLDER, processed_filename)
                    audio_processor.save_audio(processed_audio, sr, processed_path)
                    
                    processed_paths.append(processed_path)
                    
                except Exception as e:
                    logger.error(f"❌ Audio preprocessing failed: {e}")
                    # Clean up
                    for path in audio_paths + processed_paths:
                        if os.path.exists(path):
                            os.remove(path)
                    
                    return jsonify({
                        "success": False,
                        "error": f"Audio preprocessing failed: {str(e)}"
                    }), 500
            
            # Extract voice embeddings
            logger.info("🧠 Extracting voice embeddings...")
            registration_result = voice_service.register_voice(processed_paths, user_name)
            
            if not registration_result['success']:
                logger.error(f"❌ Voice registration failed: {registration_result.get('error')}")
                # Clean up files
                for path in audio_paths + processed_paths:
                    if os.path.exists(path):
                        os.remove(path)
                
                return jsonify({
                    "success": False,
                    "error": registration_result.get('error', 'Voice registration failed')
                }), 500
            
            # Save to MongoDB
            logger.info("💾 Saving to database...")
            try:
                user_doc = {
                    "name": user_name,
                    "voice_embeddings": registration_result['embeddings'],
                    "num_samples": registration_result['num_samples'],
                    "avg_inter_similarity": registration_result.get('avg_inter_similarity', 0.0),
                    "registered_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "metadata": {
                        "audio_files": [os.path.basename(p) for p in audio_paths]
                    }
                }
                
                result = users_collection.insert_one(user_doc)
                user_id = str(result.inserted_id)
                
                logger.info(f"✅ User saved to database | ID: {user_id}")
                
            except OperationFailure as e:
                logger.error(f"❌ Database operation failed: {e}")
                # Clean up files
                for path in audio_paths + processed_paths:
                    if os.path.exists(path):
                        os.remove(path)
                
                return jsonify({
                    "success": False,
                    "error": f"Database error: {str(e)}"
                }), 500
            
            # Clean up temporary files
            logger.info("🗑️  Cleaning up temporary files...")
            for path in audio_paths + processed_paths:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception as e:
                    logger.warning(f"⚠️  Failed to delete {path}: {e}")
            
            # Success response
            logger.info("=" * 60)
            logger.info(f"✅ REGISTRATION SUCCESSFUL: {user_name}")
            logger.info("=" * 60)
            
            return jsonify({
                "success": True,
                "message": f"User '{user_name}' registered successfully!",
                "user_id": user_id,
                "num_samples": registration_result['num_samples'],
                "avg_inter_similarity": round(registration_result.get('avg_inter_similarity', 0.0) * 100, 2)
            }), 201
            
        except Exception as e:
            logger.error(f"❌ Registration error: {e}")
            logger.error(traceback.format_exc())
            return jsonify({
                "success": False,
                "error": f"Server error: {str(e)}"
            }), 500
    
    
    @voice_bp.route('/identify', methods=['POST'])
    def identify_speaker():
        """
        Identify speaker from voice sample
        
        Form Data:
            audio_file: Audio file to identify (required)
            threshold: Similarity threshold (optional, default from config)
            
        Returns:
            JSON: Identification result with confidence scores
        """
        logger.info("=" * 60)
        logger.info("🔍 NEW IDENTIFICATION REQUEST")
        logger.info("=" * 60)
        
        try:
            # Check audio file
            if 'audio_file' not in request.files:
                logger.warning("⚠️  No audio file provided")
                return jsonify({
                    "success": False,
                    "error": "Audio file is required"
                }), 400
            
            audio_file = request.files['audio_file']
            
            # Validate file extension
            if not allowed_file(audio_file.filename, config.ALLOWED_EXTENSIONS):
                logger.warning(f"⚠️  Invalid file format: {audio_file.filename}")
                return jsonify({
                    "success": False,
                    "error": f"Invalid file format. Allowed: {', '.join(config.ALLOWED_EXTENSIONS)}"
                }), 400
            
            # Get threshold (optional)
            threshold = float(request.form.get('threshold', config.SIMILARITY_THRESHOLD))
            
            # Save uploaded file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = secure_filename(f"identify_{timestamp}_{audio_file.filename}")
            filepath = os.path.join(config.UPLOAD_FOLDER, filename)
            
            audio_file.save(filepath)
            logger.info(f"📁 Audio file saved: {filename}")
            
            # Validate audio
            validation = audio_processor.validate_audio(
                filepath,
                min_duration=config.MIN_AUDIO_DURATION,
                max_duration=config.MAX_AUDIO_DURATION
            )
            
            if not validation['valid']:
                logger.error(f"❌ Audio validation failed: {validation['error']}")
                os.remove(filepath)
                return jsonify({
                    "success": False,
                    "error": validation['error']
                }), 400
            
            logger.info(f"✅ Audio validated | Duration: {validation['duration']:.1f}s")
            
            # Preprocess audio
            try:
                processed_audio, sr = audio_processor.preprocess(
                    filepath,
                    apply_noise_reduction=True,
                    apply_normalization=True,
                    apply_trimming=True
                )
                
                # Save preprocessed audio
                processed_filename = filename.replace('.', '_processed.')
                processed_path = os.path.join(config.UPLOAD_FOLDER, processed_filename)
                audio_processor.save_audio(processed_audio, sr, processed_path)
                
            except Exception as e:
                logger.error(f"❌ Audio preprocessing failed: {e}")
                os.remove(filepath)
                return jsonify({
                    "success": False,
                    "error": f"Audio preprocessing failed: {str(e)}"
                }), 500
            
            # Get all registered users
            logger.info("📊 Fetching registered users from database...")
            try:
                registered_users = list(users_collection.find({}, {
                    "_id": 1,
                    "name": 1,
                    "voice_embeddings": 1
                }))
                
                logger.info(f"👥 Found {len(registered_users)} registered users")
                
            except OperationFailure as e:
                logger.error(f"❌ Database query failed: {e}")
                os.remove(filepath)
                os.remove(processed_path)
                return jsonify({
                    "success": False,
                    "error": f"Database error: {str(e)}"
                }), 500
            
            # Identify speaker
            result = voice_service.identify_speaker(
                processed_path,
                registered_users,
                threshold=threshold
            )
            
            # Clean up temporary files
            logger.info("🗑️  Cleaning up temporary files...")
            try:
                os.remove(filepath)
                os.remove(processed_path)
            except Exception as e:
                logger.warning(f"⚠️  Failed to delete files: {e}")
            
            # Return result
            logger.info("=" * 60)
            if result['identified']:
                logger.info(f"✅ IDENTIFICATION SUCCESS: {result['name']}")
            else:
                logger.info("❌ UNKNOWN SPEAKER")
            logger.info("=" * 60)
            
            return jsonify({
                "success": True,
                "result": result
            }), 200
            
        except Exception as e:
            logger.error(f"❌ Identification error: {e}")
            logger.error(traceback.format_exc())
            return jsonify({
                "success": False,
                "error": f"Server error: {str(e)}"
            }), 500
    
    
    @voice_bp.route('/users', methods=['GET'])
    def get_users():
        """
        Get all registered users
        
        Returns:
            JSON: List of users with metadata
        """
        try:
            logger.info("📋 Fetching all registered users...")
            
            users = list(users_collection.find({}, {
                "_id": 1,
                "name": 1,
                "num_samples": 1,
                "avg_inter_similarity": 1,
                "registered_at": 1,
                "updated_at": 1
            }))
            
            # Format user data
            users_info = []
            for user in users:
                users_info.append({
                    "id": str(user['_id']),
                    "name": user['name'],
                    "num_samples": user.get('num_samples', 0),
                    "avg_inter_similarity": round(user.get('avg_inter_similarity', 0.0) * 100, 2),
                    "registered_at": user.get('registered_at', '').isoformat() if user.get('registered_at') else None,
                    "updated_at": user.get('updated_at', '').isoformat() if user.get('updated_at') else None
                })
            
            logger.info(f"✅ Found {len(users_info)} users")
            
            return jsonify({
                "success": True,
                "users": users_info,
                "total": len(users_info)
            }), 200
            
        except Exception as e:
            logger.error(f"❌ Get users error: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    
    @voice_bp.route('/users/<user_name>', methods=['DELETE'])
    def delete_user(user_name):
        """
        Delete user by name
        
        Args:
            user_name: Name of user to delete
            
        Returns:
            JSON: Deletion result
        """
        try:
            logger.info(f"🗑️  Deleting user: {user_name}")
            
            result = users_collection.delete_one({"name": user_name})
            
            if result.deleted_count > 0:
                logger.info(f"✅ User '{user_name}' deleted successfully")
                return jsonify({
                    "success": True,
                    "message": f"User '{user_name}' deleted successfully"
                }), 200
            else:
                logger.warning(f"⚠️  User '{user_name}' not found")
                return jsonify({
                    "success": False,
                    "message": f"User '{user_name}' not found"
                }), 404
                
        except Exception as e:
            logger.error(f"❌ Delete user error: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    
    @voice_bp.route('/verify', methods=['POST'])
    def verify_speaker():
        """
        Verify if speaker matches claimed identity
        
        Form Data:
            audio_file: Audio file (required)
            claimed_name: Name claimed by speaker (required)
            threshold: Similarity threshold (optional)
            
        Returns:
            JSON: Verification result
        """
        try:
            # Validate inputs
            if 'audio_file' not in request.files:
                return jsonify({
                    "success": False,
                    "error": "Audio file is required"
                }), 400
            
            if 'claimed_name' not in request.form:
                return jsonify({
                    "success": False,
                    "error": "Claimed name is required"
                }), 400
            
            audio_file = request.files['audio_file']
            claimed_name = request.form['claimed_name'].strip()
            threshold = float(request.form.get('threshold', config.SIMILARITY_THRESHOLD))
            
            logger.info(f"🔐 Verifying identity: {claimed_name}")
            
            # Save and preprocess audio (similar to identify)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = secure_filename(f"verify_{timestamp}_{audio_file.filename}")
            filepath = os.path.join(config.UPLOAD_FOLDER, filename)
            audio_file.save(filepath)
            
            processed_audio, sr = audio_processor.preprocess(filepath)
            processed_path = filepath.replace('.', '_processed.')
            audio_processor.save_audio(processed_audio, sr, processed_path)
            
            # Get all users
            registered_users = list(users_collection.find())
            
            # Verify speaker
            result = voice_service.verify_speaker(
                processed_path,
                claimed_name,
                registered_users,
                threshold
            )
            
            # Clean up
            os.remove(filepath)
            os.remove(processed_path)
            
            return jsonify({
                "success": True,
                "result": result
            }), 200
            
        except Exception as e:
            logger.error(f"❌ Verification error: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    
    return voice_bp