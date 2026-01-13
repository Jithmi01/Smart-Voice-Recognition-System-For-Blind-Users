import 'dart:convert';
import 'dart:io';
import 'dart:async';
import 'package:http/http.dart' as http;

class ApiService {
  // =====================================================================
  // 🔥 IMPORTANT: CHANGE THIS TO YOUR COMPUTER'S IP ADDRESS
  // =====================================================================
  // How to find your IP:
  // 1. Open CMD (Command Prompt)
  // 2. Type: ipconfig
  // 3. Look for "IPv4 Address" under your WiFi adapter
  // 4. Example: 192.168.1.100
  // 5. Replace below:
  
  static const String baseUrl = 'http://192.168.1.104:5000';
  
  // For Android Emulator (testing on same PC):
  // static const String baseUrl = 'http://10.0.2.2:5000';
  
  // For iOS Simulator:
  // static const String baseUrl = 'http://localhost:5000';
  
  // =====================================================================
  
  static const Duration timeoutDuration = Duration(seconds: 60);
  
  /// Test server connection
  Future<bool> testConnection() async {
    try {
      final uri = Uri.parse('$baseUrl/health');
      final response = await http.get(uri).timeout(
        const Duration(seconds: 5),
      );
      
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return data['status'] == 'healthy';
      }
      return false;
    } catch (e) {
      print('Connection test failed: $e');
      return false;
    }
  }
  
  /// Get server health status
  Future<Map<String, dynamic>> getHealth() async {
    try {
      final uri = Uri.parse('$baseUrl/health');
      final response = await http.get(uri).timeout(timeoutDuration);
      
      if (response.statusCode == 200) {
        return {
          'success': true,
          'data': json.decode(response.body),
        };
      } else {
        return {
          'success': false,
          'error': 'Server returned status ${response.statusCode}',
        };
      }
    } catch (e) {
      return {
        'success': false,
        'error': 'Connection failed: ${e.toString()}',
      };
    }
  }
  
  /// Register new user with voice samples
  Future<Map<String, dynamic>> registerUser({
    required String name,
    required List<String> audioFilePaths,
  }) async {
    try {
      print('📤 Registering user: $name');
      print('📊 Audio files: ${audioFilePaths.length}');
      
      final uri = Uri.parse('$baseUrl/api/voice/register');
      final request = http.MultipartRequest('POST', uri);
      
      // Add user name
      request.fields['name'] = name;
      
      // Add audio files
      for (int i = 0; i < audioFilePaths.length; i++) {
        print('📁 Adding file ${i + 1}: ${audioFilePaths[i]}');
        
        final file = File(audioFilePaths[i]);
        
        if (!await file.exists()) {
          print('❌ File not found: ${audioFilePaths[i]}');
          return {
            'success': false,
            'error': 'Audio file not found: ${audioFilePaths[i]}',
          };
        }
        
        final multipartFile = await http.MultipartFile.fromPath(
          'audio_files',
          file.path,
          filename: 'sample_$i.wav',
        );
        request.files.add(multipartFile);
      }
      
      print('⏳ Sending registration request...');
      
      // Send request with longer timeout
      final streamedResponse = await request.send().timeout(
        const Duration(seconds: 120), // 2 minutes for upload + processing
      );
      
      final response = await http.Response.fromStream(streamedResponse);
      
      print('📥 Response status: ${response.statusCode}');
      
      if (response.statusCode == 201) {
        final data = json.decode(response.body);
        print('✅ Registration successful!');
        return {
          'success': true,
          'data': data,
        };
      } else {
        final errorData = json.decode(response.body);
        print('❌ Registration failed: ${errorData['error']}');
        return {
          'success': false,
          'error': errorData['error'] ?? 'Registration failed',
        };
      }
    } on SocketException {
      print('❌ Socket exception - cannot connect');
      return {
        'success': false,
        'error': 'Cannot connect to server. Check:\n'
            '1. Backend is running\n'
            '2. IP address is correct in api_service.dart\n'
            '3. Both devices on same WiFi',
      };
    } on TimeoutException {
      print('❌ Timeout exception');
      return {
        'success': false,
        'error': 'Request timeout. Server is taking too long.\n'
            'Try with shorter audio samples.',
      };
    } catch (e) {
      print('❌ Unexpected error: $e');
      return {
        'success': false,
        'error': 'Error: ${e.toString()}',
      };
    }
  }
  
  /// Identify speaker from voice sample
  Future<Map<String, dynamic>> identifySpeaker({
    required String audioFilePath,
    double? threshold,
  }) async {
    try {
      print('📤 Identifying speaker...');
      print('📁 Audio file: $audioFilePath');
      
      final uri = Uri.parse('$baseUrl/api/voice/identify');
      final request = http.MultipartRequest('POST', uri);
      
      // Add audio file
      final file = File(audioFilePath);
      
      if (!await file.exists()) {
        return {
          'success': false,
          'error': 'Audio file not found',
        };
      }
      
      final multipartFile = await http.MultipartFile.fromPath(
        'audio_file',
        file.path,
        filename: 'identify.wav',
      );
      request.files.add(multipartFile);
      
      // Add threshold if provided
      if (threshold != null) {
        request.fields['threshold'] = threshold.toString();
      }
      
      print('⏳ Sending identification request...');
      
      // Send request
      final streamedResponse = await request.send().timeout(
        const Duration(seconds: 60),
      );
      
      final response = await http.Response.fromStream(streamedResponse);
      
      print('📥 Response status: ${response.statusCode}');
      
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        print('✅ Identification completed');
        return {
          'success': true,
          'result': data['result'],
        };
      } else {
        final errorData = json.decode(response.body);
        print('❌ Identification failed: ${errorData['error']}');
        return {
          'success': false,
          'error': errorData['error'] ?? 'Identification failed',
        };
      }
    } on SocketException {
      return {
        'success': false,
        'error': 'Cannot connect to server. Check connection.',
      };
    } on TimeoutException {
      return {
        'success': false,
        'error': 'Request timeout. Try again.',
      };
    } catch (e) {
      print('❌ Error: $e');
      return {
        'success': false,
        'error': 'Error: ${e.toString()}',
      };
    }
  }
  
  /// Verify speaker identity
  Future<Map<String, dynamic>> verifySpeaker({
    required String audioFilePath,
    required String claimedName,
    double? threshold,
  }) async {
    try {
      final uri = Uri.parse('$baseUrl/api/voice/verify');
      final request = http.MultipartRequest('POST', uri);
      
      // Add fields
      request.fields['claimed_name'] = claimedName;
      if (threshold != null) {
        request.fields['threshold'] = threshold.toString();
      }
      
      // Add audio file
      final file = File(audioFilePath);
      final multipartFile = await http.MultipartFile.fromPath(
        'audio_file',
        file.path,
        filename: 'verify.wav',
      );
      request.files.add(multipartFile);
      
      // Send request
      final streamedResponse = await request.send().timeout(timeoutDuration);
      final response = await http.Response.fromStream(streamedResponse);
      
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return {
          'success': true,
          'result': data['result'],
        };
      } else {
        final errorData = json.decode(response.body);
        return {
          'success': false,
          'error': errorData['error'] ?? 'Verification failed',
        };
      }
    } catch (e) {
      return {
        'success': false,
        'error': 'Error: ${e.toString()}',
      };
    }
  }
  
  /// Get all registered users
  Future<Map<String, dynamic>> getUsers() async {
    try {
      print('📤 Fetching users...');
      
      final uri = Uri.parse('$baseUrl/api/voice/users');
      final response = await http.get(uri).timeout(timeoutDuration);
      
      print('📥 Response status: ${response.statusCode}');
      
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        print('✅ Found ${data['total']} users');
        return {
          'success': true,
          'data': data,
        };
      } else {
        return {
          'success': false,
          'error': 'Failed to fetch users',
        };
      }
    } on SocketException {
      return {
        'success': false,
        'error': 'Cannot connect to server',
      };
    } catch (e) {
      print('❌ Error: $e');
      return {
        'success': false,
        'error': 'Error: ${e.toString()}',
      };
    }
  }
  
  /// Delete user by name
  Future<Map<String, dynamic>> deleteUser(String name) async {
    try {
      final uri = Uri.parse('$baseUrl/api/voice/users/$name');
      final response = await http.delete(uri).timeout(timeoutDuration);
      
      if (response.statusCode == 200) {
        return {
          'success': true,
          'data': json.decode(response.body),
        };
      } else {
        return {
          'success': false,
          'error': 'Failed to delete user',
        };
      }
    } catch (e) {
      return {
        'success': false,
        'error': 'Error: ${e.toString()}',
      };
    }
  }
  
  /// Get server info
  Future<Map<String, dynamic>> getServerInfo() async {
    try {
      final uri = Uri.parse('$baseUrl/');
      final response = await http.get(uri).timeout(
        const Duration(seconds: 5),
      );
      
      if (response.statusCode == 200) {
        return {
          'success': true,
          'data': json.decode(response.body),
        };
      } else {
        return {
          'success': false,
          'error': 'Failed to get server info',
        };
      }
    } catch (e) {
      return {
        'success': false,
        'error': 'Error: ${e.toString()}',
      };
    }
  }
}