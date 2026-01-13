import 'package:flutter/material.dart';
import 'dart:async';
import '../services/api_service.dart';
import '../services/audio_service.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({Key? key}) : super(key: key);

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen>
    with SingleTickerProviderStateMixin {
  final TextEditingController _nameController = TextEditingController();
  final ApiService _apiService = ApiService();
  final AudioService _audioService = AudioService();
  
  final List<String> _recordedSamples = [];
  final int _requiredSamples = 3;
  final int _recordDuration = 5;
  
  bool _isRecording = false;
  bool _isRegistering = false;
  int _recordingCountdown = 0;
  String? _permissionStatus;
  
  late AnimationController _pulseController;
  
  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1000),
    )..repeat(reverse: true);
    
    _checkPermission();
  }
  
  @override
  void dispose() {
    _nameController.dispose();
    _pulseController.dispose();
    _audioService.dispose();
    
    // Clean up recorded samples
    for (final path in _recordedSamples) {
      _audioService.deleteAudioFile(path);
    }
    
    super.dispose();
  }
  
  Future<void> _checkPermission() async {
    final status = await _audioService.getPermissionStatus();
    setState(() => _permissionStatus = status);
    
    if (status == 'permanently_denied') {
      _showPermissionDialog();
    }
  }
  
  void _showPermissionDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.mic_off, color: Colors.red),
            SizedBox(width: 8),
            Text('Microphone Permission'),
          ],
        ),
        content: const Text(
          'Microphone permission is required to record voice samples.\n\n'
          'Please enable it in Settings → Apps → Voice Recognition → Permissions.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              _audioService.openSettings();
            },
            child: const Text('Open Settings'),
          ),
        ],
      ),
    );
  }
  
  Future<void> _recordSample() async {
    if (_nameController.text.trim().isEmpty) {
      _showMessage('Please enter a name first', isError: true);
      return;
    }
    
    if (_recordedSamples.length >= _requiredSamples) {
      _showMessage('All samples recorded! Tap Register to continue.', isError: false);
      return;
    }
    
    // Check permission
    if (!await _audioService.hasPermission()) {
      final granted = await _audioService.requestPermission();
      if (!granted) {
        _showMessage('Microphone permission is required', isError: true);
        _checkPermission();
        return;
      }
    }
    
    setState(() {
      _isRecording = true;
      _recordingCountdown = _recordDuration;
    });
    
    // Start recording
    final started = await _audioService.startRecording();
    
    if (!started) {
      setState(() => _isRecording = false);
      _showMessage('Failed to start recording. Check microphone permission.', isError: true);
      return;
    }
    
    // Countdown timer
    Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }
      
      if (_recordingCountdown > 0) {
        setState(() => _recordingCountdown--);
      } else {
        timer.cancel();
      }
    });
    
    // Record for duration
    await Future.delayed(Duration(seconds: _recordDuration));
    
    if (!mounted) return;
    
    // Stop recording
    final path = await _audioService.stopRecording();
    
    setState(() => _isRecording = false);
    
    if (path != null) {
      // Check file exists
      if (await _audioService.fileExists(path)) {
        final size = await _audioService.getFileSize(path);
        print('✅ Sample recorded: ${size.toStringAsFixed(1)} KB');
        
        setState(() => _recordedSamples.add(path));
        
        _showMessage(
          'Sample ${_recordedSamples.length}/$_requiredSamples recorded successfully!',
          isError: false,
        );
        
        // Auto-vibrate on success (if available)
        // HapticFeedback.mediumImpact();
      } else {
        _showMessage('Recording file not found', isError: true);
      }
    } else {
      _showMessage('Failed to save recording', isError: true);
    }
  }
  
  Future<void> _deleteSample(int index) async {
    final path = _recordedSamples[index];
    await _audioService.deleteAudioFile(path);
    
    setState(() {
      _recordedSamples.removeAt(index);
    });
    
    _showMessage('Sample ${index + 1} deleted', isError: false);
  }
  
  Future<void> _registerUser() async {
    if (_nameController.text.trim().isEmpty) {
      _showMessage('Please enter a name', isError: true);
      return;
    }
    
    if (_recordedSamples.length < _requiredSamples) {
      _showMessage('Please record all $_requiredSamples samples', isError: true);
      return;
    }
    
    setState(() => _isRegistering = true);
    
    try {
      final result = await _apiService.registerUser(
        name: _nameController.text.trim(),
        audioFilePaths: _recordedSamples,
      );
      
      setState(() => _isRegistering = false);
      
      if (result['success']) {
        _showMessage('${_nameController.text} registered successfully!', isError: false);
        
        // Wait a bit then go back
        await Future.delayed(const Duration(seconds: 2));
        
        if (mounted) {
          Navigator.pop(context, true); // Return true to indicate success
        }
      } else {
        _showMessage(result['error'] ?? 'Registration failed', isError: true);
      }
    } catch (e) {
      setState(() => _isRegistering = false);
      _showMessage('Error: $e', isError: true);
    }
  }
  
  void _showMessage(String message, {required bool isError}) {
    if (!mounted) return;
    
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isError ? Colors.red : Colors.green,
        behavior: SnackBarBehavior.floating,
        duration: Duration(seconds: isError ? 4 : 2),
      ),
    );
  }
  
  @override
  Widget build(BuildContext context) {
    final progress = _recordedSamples.length / _requiredSamples;
    
    return Scaffold(
      appBar: AppBar(
        title: const Text('Register Voice'),
        actions: [
          if (_recordedSamples.isNotEmpty && !_isRecording && !_isRegistering)
            IconButton(
              icon: const Icon(Icons.delete_outline),
              tooltip: 'Clear All',
              onPressed: () async {
                final confirm = await showDialog<bool>(
                  context: context,
                  builder: (context) => AlertDialog(
                    title: const Text('Clear All Samples?'),
                    content: const Text('This will delete all recorded samples.'),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(context, false),
                        child: const Text('Cancel'),
                      ),
                      ElevatedButton(
                        onPressed: () => Navigator.pop(context, true),
                        style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
                        child: const Text('Clear All'),
                      ),
                    ],
                  ),
                );
                
                if (confirm == true) {
                  for (final path in _recordedSamples) {
                    await _audioService.deleteAudioFile(path);
                  }
                  setState(() => _recordedSamples.clear());
                }
              },
            ),
        ],
      ),
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Theme.of(context).colorScheme.primaryContainer.withOpacity(0.3),
              Theme.of(context).scaffoldBackgroundColor,
            ],
          ),
        ),
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Icon
                Icon(
                  Icons.person_add_rounded,
                  size: 64,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(height: 16),
                
                Text(
                  'Add New User',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                  textAlign: TextAlign.center,
                ),
                
                const SizedBox(height: 24),
                
                // Name Input
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Enter Your Name',
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                              ),
                        ),
                        const SizedBox(height: 12),
                        TextField(
                          controller: _nameController,
                          decoration: InputDecoration(
                            hintText: 'e.g., Jithmi',
                            prefixIcon: const Icon(Icons.person),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(12),
                            ),
                            filled: true,
                          ),
                          enabled: !_isRecording && !_isRegistering,
                          textCapitalization: TextCapitalization.words,
                          onChanged: (value) {
                            // Auto-capitalize first letter
                            if (value.isNotEmpty) {
                              final words = value.split(' ');
                              final capitalized = words.map((word) {
                                if (word.isEmpty) return word;
                                return word[0].toUpperCase() + word.substring(1).toLowerCase();
                              }).join(' ');
                              
                              if (capitalized != value) {
                                _nameController.value = _nameController.value.copyWith(
                                  text: capitalized,
                                  selection: TextSelection.collapsed(offset: capitalized.length),
                                );
                              }
                            }
                          },
                        ),
                      ],
                    ),
                  ),
                ),
                
                const SizedBox(height: 20),
                
                // Progress
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              'Recording Progress',
                              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                    fontWeight: FontWeight.bold,
                                  ),
                            ),
                            Text(
                              '${_recordedSamples.length}/$_requiredSamples',
                              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                                    color: Theme.of(context).colorScheme.primary,
                                    fontWeight: FontWeight.bold,
                                  ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        ClipRRect(
                          borderRadius: BorderRadius.circular(8),
                          child: LinearProgressIndicator(
                            value: progress,
                            minHeight: 10,
                            backgroundColor: Colors.grey.shade200,
                          ),
                        ),
                        const SizedBox(height: 16),
                        
                        // Sample list
                        ...List.generate(_requiredSamples, (index) {
                          final isRecorded = index < _recordedSamples.length;
                          return Padding(
                            padding: const EdgeInsets.only(bottom: 8),
                            child: Row(
                              children: [
                                Icon(
                                  isRecorded ? Icons.check_circle : Icons.circle_outlined,
                                  color: isRecorded ? Colors.green : Colors.grey,
                                  size: 24,
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Text(
                                    'Sample ${index + 1}',
                                    style: TextStyle(
                                      fontSize: 16,
                                      color: isRecorded ? null : Colors.grey,
                                      fontWeight: isRecorded ? FontWeight.w600 : null,
                                    ),
                                  ),
                                ),
                                if (isRecorded)
                                  IconButton(
                                    icon: const Icon(Icons.delete_outline, size: 20),
                                    color: Colors.red,
                                    onPressed: () => _deleteSample(index),
                                    tooltip: 'Delete Sample',
                                  ),
                              ],
                            ),
                          );
                        }),
                      ],
                    ),
                  ),
                ),
                
                const SizedBox(height: 20),
                
                // Recording Button or Status
                if (_isRecording)
                  _buildRecordingCard()
                else if (_isRegistering)
                  _buildRegisteringCard()
                else
                  _buildRecordButton(),
                
                const SizedBox(height: 16),
                
                // Register Button
                if (_recordedSamples.length >= _requiredSamples && !_isRecording && !_isRegistering)
                  ElevatedButton.icon(
                    onPressed: _registerUser,
                    icon: const Icon(Icons.check_circle),
                    label: const Text(
                      'Complete Registration',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.all(20),
                      backgroundColor: Colors.green,
                      foregroundColor: Colors.white,
                    ),
                  ),
                
                const SizedBox(height: 20),
                
                // Instructions
                _buildInstructions(),
              ],
            ),
          ),
        ),
      ),
    );
  }
  
  Widget _buildRecordingCard() {
    return Card(
      color: Colors.red.shade50,
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          children: [
            AnimatedBuilder(
              animation: _pulseController,
              builder: (context, child) {
                return Transform.scale(
                  scale: 1.0 + (_pulseController.value * 0.3),
                  child: Icon(
                    Icons.fiber_manual_record,
                    size: 80,
                    color: Colors.red.withOpacity(0.6 + (_pulseController.value * 0.4)),
                  ),
                );
              },
            ),
            const SizedBox(height: 20),
            Text(
              'Recording...',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: Colors.red,
                  ),
            ),
            const SizedBox(height: 12),
            Text(
              '$_recordingCountdown',
              style: Theme.of(context).textTheme.displayMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: Colors.red.shade700,
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              'seconds remaining',
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    color: Colors.red.shade600,
                  ),
            ),
            const SizedBox(height: 16),
            const Text(
              '🎤 Speak clearly and naturally',
              style: TextStyle(fontSize: 14),
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildRegisteringCard() {
    return Card(
      color: Colors.blue.shade50,
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          children: [
            const SizedBox(
              width: 60,
              height: 60,
              child: CircularProgressIndicator(strokeWidth: 6),
            ),
            const SizedBox(height: 20),
            Text(
              'Registering...',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: Colors.blue.shade700,
                  ),
            ),
            const SizedBox(height: 12),
            Text(
              'Processing voice samples\nand creating voice profile',
              style: Theme.of(context).textTheme.bodyLarge,
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildRecordButton() {
    return ElevatedButton.icon(
      onPressed: _recordSample,
      icon: const Icon(Icons.mic, size: 24),
      label: Text(
        _recordedSamples.length >= _requiredSamples
            ? 'All Samples Recorded ✓'
            : 'Record Sample ${_recordedSamples.length + 1}',
        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
      ),
      style: ElevatedButton.styleFrom(
        padding: const EdgeInsets.all(20),
        backgroundColor: _recordedSamples.length >= _requiredSamples
            ? Colors.grey
            : Theme.of(context).colorScheme.primary,
        foregroundColor: Colors.white,
      ),
    );
  }
  
  Widget _buildInstructions() {
    return Card(
      color: Colors.blue.shade50,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.info_outline, color: Colors.blue.shade700),
                const SizedBox(width: 8),
                Text(
                  'Instructions',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                    color: Colors.blue.shade700,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            _buildInstruction('1. Enter your name'),
            _buildInstruction('2. Record $_requiredSamples voice samples ($_recordDuration seconds each)'),
            _buildInstruction('3. Speak clearly in a quiet environment'),
            _buildInstruction('4. Use different sentences for each sample'),
            _buildInstruction('5. Tap "Complete Registration" when done'),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.amber.shade100,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Icon(Icons.tips_and_updates, size: 20, color: Colors.amber.shade900),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Tip: Record in a quiet place for best accuracy',
                      style: TextStyle(fontSize: 13, color: Colors.amber.shade900),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildInstruction(String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('• ', style: TextStyle(fontSize: 16)),
          Expanded(child: Text(text)),
        ],
      ),
    );
  }
}