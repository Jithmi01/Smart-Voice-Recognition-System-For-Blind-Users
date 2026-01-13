import 'package:record/record.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'dart:io';

class AudioService {
  final AudioRecorder _recorder = AudioRecorder();
  
  /// Request microphone permission
  Future<bool> requestPermission() async {
    final status = await Permission.microphone.request();
    return status.isGranted;
  }
  
  /// Check if microphone permission is granted
  Future<bool> hasPermission() async {
    final status = await Permission.microphone.status;
    return status.isGranted;
  }
  
  /// Check microphone permission status
  Future<String> getPermissionStatus() async {
    final status = await Permission.microphone.status;
    
    if (status.isGranted) {
      return 'granted';
    } else if (status.isDenied) {
      return 'denied';
    } else if (status.isPermanentlyDenied) {
      return 'permanently_denied';
    } else {
      return 'not_requested';
    }
  }
  
  /// Open app settings (for permanently denied permission)
  Future<void> openSettings() async {
    await openAppSettings();
  }
  
  /// Start recording audio
  Future<bool> startRecording() async {
    try {
      print('🎤 Starting recording...');
      
      // Check permission
      if (!await hasPermission()) {
        print('⚠️ No microphone permission');
        final granted = await requestPermission();
        if (!granted) {
          print('❌ Permission denied');
          return false;
        }
      }
      
      // Check if already recording
      if (await _recorder.isRecording()) {
        print('⚠️ Already recording, stopping first');
        await _recorder.stop();
      }
      
      // Get temporary directory
      final directory = await getTemporaryDirectory();
      final timestamp = DateTime.now().millisecondsSinceEpoch;
      final path = '${directory.path}/recording_$timestamp.wav';
      
      print('📁 Recording path: $path');
      
      // Start recording with optimal settings for voice recognition
      await _recorder.start(
        const RecordConfig(
          encoder: AudioEncoder.wav,        // WAV format (best quality)
          bitRate: 128000,                  // 128 kbps
          sampleRate: 16000,                // 16kHz (optimal for voice)
          numChannels: 1,                   // Mono
          autoGain: true,                   // Auto gain control
          echoCancel: true,                 // Echo cancellation
          noiseSuppress: true,              // Noise suppression
        ),
        path: path,
      );
      
      print('✅ Recording started');
      return true;
      
    } catch (e) {
      print('❌ Error starting recording: $e');
      return false;
    }
  }
  
  /// Stop recording and return file path
  Future<String?> stopRecording() async {
    try {
      print('🛑 Stopping recording...');
      
      if (!await _recorder.isRecording()) {
        print('⚠️ Not currently recording');
        return null;
      }
      
      final path = await _recorder.stop();
      
      if (path != null) {
        final file = File(path);
        if (await file.exists()) {
          final size = await file.length();
          print('✅ Recording saved: ${size / 1024} KB');
          print('📁 Path: $path');
        } else {
          print('❌ Recording file not found');
          return null;
        }
      }
      
      return path;
      
    } catch (e) {
      print('❌ Error stopping recording: $e');
      return null;
    }
  }
  
  /// Record for a specific duration (in seconds)
  Future<String?> recordForDuration(int seconds) async {
    try {
      print('🎤 Recording for $seconds seconds...');
      
      final started = await startRecording();
      if (!started) {
        print('❌ Failed to start recording');
        return null;
      }
      
      // Wait for specified duration
      await Future.delayed(Duration(seconds: seconds));
      
      final path = await stopRecording();
      return path;
      
    } catch (e) {
      print('❌ Error in recordForDuration: $e');
      return null;
    }
  }
  
  /// Check if currently recording
  Future<bool> isRecording() async {
    try {
      return await _recorder.isRecording();
    } catch (e) {
      print('❌ Error checking recording status: $e');
      return false;
    }
  }
  
  /// Pause recording
  Future<void> pauseRecording() async {
    try {
      if (await _recorder.isRecording()) {
        await _recorder.pause();
        print('⏸️ Recording paused');
      }
    } catch (e) {
      print('❌ Error pausing recording: $e');
    }
  }
  
  /// Resume recording
  Future<void> resumeRecording() async {
    try {
      if (await _recorder.isPaused()) {
        await _recorder.resume();
        print('▶️ Recording resumed');
      }
    } catch (e) {
      print('❌ Error resuming recording: $e');
    }
  }
  
  /// Cancel recording without saving
  Future<void> cancelRecording() async {
    try {
      if (await _recorder.isRecording()) {
        await _recorder.stop();
        print('❌ Recording cancelled');
      }
    } catch (e) {
      print('❌ Error cancelling recording: $e');
    }
  }
  
  /// Dispose recorder
  Future<void> dispose() async {
    try {
      if (await _recorder.isRecording()) {
        await _recorder.stop();
      }
      await _recorder.dispose();
      print('🗑️ Audio recorder disposed');
    } catch (e) {
      print('❌ Error disposing recorder: $e');
    }
  }
  
  /// Delete audio file
  Future<void> deleteAudioFile(String path) async {
    try {
      final file = File(path);
      if (await file.exists()) {
        await file.delete();
        print('🗑️ Deleted audio file: $path');
      }
    } catch (e) {
      print('❌ Error deleting file: $e');
    }
  }
  
  /// Delete multiple audio files
  Future<void> deleteAudioFiles(List<String> paths) async {
    for (final path in paths) {
      await deleteAudioFile(path);
    }
  }
  
  /// Delete all temporary audio files
  Future<void> cleanupTempFiles() async {
    try {
      final directory = await getTemporaryDirectory();
      final files = directory.listSync();
      
      int deletedCount = 0;
      
      for (var file in files) {
        if (file is File) {
          final extension = file.path.split('.').last.toLowerCase();
          if (extension == 'wav' || 
              extension == 'm4a' || 
              extension == 'mp3' ||
              extension == 'aac') {
            await file.delete();
            deletedCount++;
          }
        }
      }
      
      print('🗑️ Cleaned up $deletedCount temporary audio files');
      
    } catch (e) {
      print('❌ Error cleaning up temp files: $e');
    }
  }
  
  /// Get audio file size in KB
  Future<double> getFileSize(String path) async {
    try {
      final file = File(path);
      if (await file.exists()) {
        final bytes = await file.length();
        return bytes / 1024; // Convert to KB
      }
      return 0.0;
    } catch (e) {
      print('❌ Error getting file size: $e');
      return 0.0;
    }
  }
  
  /// Check if file exists
  Future<bool> fileExists(String path) async {
    try {
      final file = File(path);
      return await file.exists();
    } catch (e) {
      return false;
    }
  }
  
  /// Get recording duration (approximate, based on file size)
  Future<double> getRecordingDuration(String path) async {
    try {
      final size = await getFileSize(path);
      // Approximate: 16kHz mono WAV = ~2KB per second
      return size / 2; // Rough estimate in seconds
    } catch (e) {
      return 0.0;
    }
  }
}