"""
Application Configuration
Loads settings from .env file
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration loaded from environment variables"""
    
    # ========================================================================
    # MONGODB CONFIGURATION
    # ========================================================================
    MONGODB_URI = os.getenv('MONGODB_URI')
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'voice_recognition_db')
    
    # ========================================================================
    # FLASK CONFIGURATION
    # ========================================================================
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() in ('true', '1', 'yes')
    PORT = int(os.getenv('FLASK_PORT', 5000))
    
    # ========================================================================
    # FILE UPLOAD CONFIGURATION
    # ========================================================================
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'wav', 'mp3', 'm4a', 'ogg', 'flac'}
    
    # ========================================================================
    # VOICE RECOGNITION CONFIGURATION
    # ========================================================================
    SIMILARITY_THRESHOLD = float(os.getenv('SIMILARITY_THRESHOLD', 0.65))
    
    # Audio validation
    MIN_AUDIO_DURATION = int(os.getenv('MIN_AUDIO_DURATION', 2))  # seconds
    MAX_AUDIO_DURATION = int(os.getenv('MAX_AUDIO_DURATION', 30))  # seconds
    
    # ========================================================================
    # MODEL CONFIGURATION
    # ========================================================================
    MODEL_NAME = os.getenv('MODEL_NAME', 'speechbrain/spkrec-ecapa-voxceleb')
    MODEL_SAVE_DIR = os.getenv('MODEL_SAVE_DIR', 'pretrained_models')
    
    # ========================================================================
    # LOGGING CONFIGURATION
    # ========================================================================
    LOG_FILE = 'app.log'
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @staticmethod
    def init_app(app):
        """
        Initialize Flask app with configuration
        
        Args:
            app: Flask application instance
        """
        # Set Flask config
        app.config.from_object(Config)
        
        # Create required directories
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.MODEL_SAVE_DIR, exist_ok=True)
        
        # Create .gitignore for uploads folder
        gitignore_path = os.path.join(Config.UPLOAD_FOLDER, '.gitignore')
        if not os.path.exists(gitignore_path):
            with open(gitignore_path, 'w') as f:
                f.write('*\n!.gitignore\n')
    
    @staticmethod
    def validate():
        """
        Validate configuration settings
        
        Returns:
            tuple: (is_valid, error_messages)
        """
        errors = []
        
        # Check MongoDB URI
        if not Config.MONGODB_URI:
            errors.append("MONGODB_URI is not set in .env file")
        
        # Check threshold range
        if not (0.0 <= Config.SIMILARITY_THRESHOLD <= 1.0):
            errors.append(f"SIMILARITY_THRESHOLD must be between 0.0 and 1.0, got {Config.SIMILARITY_THRESHOLD}")
        
        # Check duration values
        if Config.MIN_AUDIO_DURATION <= 0:
            errors.append(f"MIN_AUDIO_DURATION must be positive, got {Config.MIN_AUDIO_DURATION}")
        
        if Config.MAX_AUDIO_DURATION <= Config.MIN_AUDIO_DURATION:
            errors.append(f"MAX_AUDIO_DURATION must be greater than MIN_AUDIO_DURATION")
        
        return (len(errors) == 0, errors)
    
    @staticmethod
    def print_config():
        """Print current configuration (for debugging)"""
        print("\n" + "=" * 70)
        print("📋 CURRENT CONFIGURATION")
        print("=" * 70)
        print(f"Database: {Config.DATABASE_NAME}")
        print(f"MongoDB URI: {Config.MONGODB_URI[:50]}..." if Config.MONGODB_URI else "MongoDB URI: NOT SET")
        print(f"Port: {Config.PORT}")
        print(f"Debug: {Config.DEBUG}")
        print(f"Similarity Threshold: {Config.SIMILARITY_THRESHOLD}")
        print(f"Min Audio Duration: {Config.MIN_AUDIO_DURATION}s")
        print(f"Max Audio Duration: {Config.MAX_AUDIO_DURATION}s")
        print(f"Model: {Config.MODEL_NAME}")
        print(f"Allowed Formats: {', '.join(Config.ALLOWED_EXTENSIONS)}")
        print("=" * 70 + "\n")


# Validate config on import
is_valid, errors = Config.validate()
if not is_valid:
    print("\n⚠️  CONFIGURATION ERRORS:")
    for error in errors:
        print(f"   - {error}")
    print("\n💡 Fix errors in .env file before starting the server\n")