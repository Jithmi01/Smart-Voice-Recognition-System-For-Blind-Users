import 'package:flutter/material.dart';
import 'dart:async';
import '../services/api_service.dart';
import '../services/audio_service.dart';

class IdentifyScreen extends StatefulWidget {
  const IdentifyScreen({Key? key}) : super(key: key);

  @override
  State<IdentifyScreen> createState() => _IdentifyScreenState();
}

class _IdentifyScreenState extends State<IdentifyScreen>
    with SingleTickerProviderStateMixin {
  final ApiService _apiService = ApiService();
  final AudioService _audioService = AudioService();
  
  bool _isRecording = false;
  bool _isIdentifying = false;
  int _recordingCountdown = 0;
  final int _recordDuration = 5;
  
  Map<String, dynamic>? _identificationResult;
  late AnimationController _pulseController;
  
  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat(reverse: true);
  }
  
  @override
  void dispose() {
    _pulseController.dispose();
    _audioService.dispose();
    super.dispose();
  }
  
  Future<void> _startIdentification() async {
    // Check permission first
    if (!await _audioService.hasPermission()) {
      final granted = await _audioService.requestPermission();
      if (!granted) {
        _showMessage('Microphone permission is required', isError: true);
        return;
      }
    }
    
    setState(() {
      _isRecording = true;
      _recordingCountdown = _recordDuration;
      _identificationResult = null;
    });
    
    // Start recording
    final started = await _audioService.startRecording();
    
    if (!started) {
      setState(() => _isRecording = false);
      _showMessage('Failed to start recording', isError: true);
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
    
    setState(() {
      _isRecording = false;
      _isIdentifying = true;
    });
    
    if (path != null) {
      // Send to backend for identification
      final result = await _apiService.identifySpeaker(audioFilePath: path);
      
      setState(() => _isIdentifying = false);
      
      if (result['success']) {
        setState(() => _identificationResult = result['result']);
      } else {
        _showMessage(result['error'] ?? 'Identification failed', isError: true);
        setState(() => _identificationResult = null);
      }
      
      // Clean up temp file
      await _audioService.deleteAudioFile(path);
    } else {
      setState(() => _isIdentifying = false);
      _showMessage('Failed to save recording', isError: true);
    }
  }
  
  void _showMessage(String message, {required bool isError}) {
    if (!mounted) return;
    
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isError ? Colors.red : Colors.green,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }
  
  Color _getConfidenceColor(double confidence) {
    if (confidence >= 80) return Colors.green;
    if (confidence >= 60) return Colors.orange;
    return Colors.red;
  }
  
  String _getConfidenceLabel(double confidence) {
    if (confidence >= 90) return 'Excellent';
    if (confidence >= 80) return 'Very Good';
    if (confidence >= 70) return 'Good';
    if (confidence >= 60) return 'Fair';
    return 'Low';
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Identify Speaker'),
      ),
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Theme.of(context).colorScheme.secondaryContainer.withOpacity(0.3),
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
                // Header Icon
                Icon(
                  Icons.search_rounded,
                  size: 64,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(height: 16),
                
                Text(
                  'Speaker Identification',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                  textAlign: TextAlign.center,
                ),
                
                const SizedBox(height: 24),
                
                // Status Card
                if (_isRecording)
                  _buildRecordingCard()
                else if (_isIdentifying)
                  _buildIdentifyingCard()
                else if (_identificationResult != null)
                  _buildResultCard()
                else
                  _buildReadyCard(),
                
                const SizedBox(height: 20),
                
                // Action Button
                if (!_isRecording && !_isIdentifying)
                  ElevatedButton.icon(
                    onPressed: _startIdentification,
                    icon: const Icon(Icons.mic, size: 24),
                    label: Text(
                      _identificationResult != null ? 'Identify Again' : 'Start Identification',
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.all(20),
                      backgroundColor: Theme.of(context).colorScheme.primary,
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
  
  Widget _buildReadyCard() {
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.primaryContainer,
                shape: BoxShape.circle,
              ),
              child: Icon(
                Icons.mic_none_rounded,
                size: 60,
                color: Theme.of(context).colorScheme.primary,
              ),
            ),
            const SizedBox(height: 20),
            Text(
              'Ready to Identify',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              'Tap the button below to start',
              style: Theme.of(context).textTheme.bodyLarge,
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildRecordingCard() {
    return Card(
      color: Colors.red.shade50,
      elevation: 4,
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          children: [
            AnimatedBuilder(
              animation: _pulseController,
              builder: (context, child) {
                return Transform.scale(
                  scale: 1.0 + (_pulseController.value * 0.2),
                  child: Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      color: Colors.red.withOpacity(0.1 + (_pulseController.value * 0.2)),
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      Icons.fiber_manual_record,
                      size: 60,
                      color: Colors.red.withOpacity(0.7 + (_pulseController.value * 0.3)),
                    ),
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
              style: TextStyle(
                fontSize: 48,
                fontWeight: FontWeight.bold,
                color: Colors.red.shade700,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'seconds remaining',
              style: TextStyle(
                fontSize: 16,
                color: Colors.red.shade600,
              ),
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(20),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.mic, size: 20, color: Colors.red),
                  SizedBox(width: 8),
                  Text(
                    'Speak clearly into the microphone',
                    style: TextStyle(fontSize: 14),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildIdentifyingCard() {
    return Card(
      color: Colors.blue.shade50,
      elevation: 4,
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          children: [
            const SizedBox(
              width: 80,
              height: 80,
              child: CircularProgressIndicator(strokeWidth: 6),
            ),
            const SizedBox(height: 20),
            Text(
              'Identifying Speaker...',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: Colors.blue.shade700,
                  ),
            ),
            const SizedBox(height: 12),
            Text(
              'Analyzing voice patterns\nand comparing with database',
              style: Theme.of(context).textTheme.bodyLarge,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            LinearProgressIndicator(
              backgroundColor: Colors.blue.shade100,
              valueColor: AlwaysStoppedAnimation<Color>(Colors.blue.shade600),
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildResultCard() {
    final result = _identificationResult!;
    final isIdentified = result['identified'] ?? false;
    final name = result['name'] ?? 'Unknown';
    final confidence = (result['confidence'] ?? 0.0).toDouble();
    
    // Determine card style based on name and confidence
    Color cardColor;
    Color iconColor;
    Color textColor;
    IconData iconData;
    String statusText;
    
    if (name == "Can't hear someone speaking") {
      // Silence or no voice detected
      cardColor = Colors.grey.shade100;
      iconColor = Colors.grey.shade600;
      textColor = Colors.grey.shade800;
      iconData = Icons.volume_off;
      statusText = 'No Voice Detected';
    } else if (name == "Unknown Person Speaking") {
      // Voice detected but < 30% confidence
      cardColor = Colors.orange.shade50;
      iconColor = Colors.orange.shade700;
      textColor = Colors.orange.shade900;
      iconData = Icons.help_outline;
      statusText = 'Unknown Speaker';
    } else if (isIdentified && confidence >= 30) {
      // Identified with >= 30% confidence
      if (confidence >= 70) {
        // High confidence (70%+)
        cardColor = Colors.green.shade50;
        iconColor = Colors.green.shade700;
        textColor = Colors.green.shade900;
        iconData = Icons.check_circle;
        statusText = 'Speaker Identified!';
      } else {
        // Medium confidence (30-70%)
        cardColor = Colors.blue.shade50;
        iconColor = Colors.blue.shade700;
        textColor = Colors.blue.shade900;
        iconData = Icons.person_search;
        statusText = 'Possible Match';
      }
    } else {
      // Fallback
      cardColor = Colors.grey.shade100;
      iconColor = Colors.grey.shade600;
      textColor = Colors.grey.shade800;
      iconData = Icons.help_outline;
      statusText = 'No Match';
    }
    
    final confidenceColor = _getConfidenceColor(confidence);
    final confidenceLabel = _getConfidenceLabel(confidence);
    
    return Card(
      color: cardColor,
      elevation: 4,
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            // Icon
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: iconColor.withOpacity(0.2),
                shape: BoxShape.circle,
              ),
              child: Icon(
                iconData,
                size: 60,
                color: iconColor,
              ),
            ),
            const SizedBox(height: 16),
            
            // Status
            Text(
              statusText,
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: textColor,
                  ),
            ),
            const SizedBox(height: 12),
            
            // Name Display
            if (name != "Can't hear someone speaking")
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: iconColor.withOpacity(0.3),
                    width: 2,
                  ),
                ),
                child: Text(
                  name,
                  style: TextStyle(
                    fontSize: name == "Unknown Person Speaking" ? 20 : 28,
                    fontWeight: FontWeight.bold,
                    color: textColor,
                  ),
                  textAlign: TextAlign.center,
                ),
              ),
            
            // Message for no voice
            if (name == "Can't hear someone speaking")
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Column(
                  children: [
                    Icon(Icons.mic_off, size: 48, color: Colors.grey.shade400),
                    const SizedBox(height: 12),
                    Text(
                      'No clear voice detected',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: Colors.grey.shade700,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Please speak louder or closer to the microphone',
                      style: TextStyle(
                        fontSize: 14,
                        color: Colors.grey.shade600,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
            
            const SizedBox(height: 20),
            
            // Confidence Score (only if voice was detected)
            if (name != "Can't hear someone speaking")
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text(
                          'Confidence',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                          ),
                        ),
                        Row(
                          children: [
                            Text(
                              '${confidence.toStringAsFixed(1)}%',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 20,
                                color: confidenceColor,
                              ),
                            ),
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8,
                                vertical: 4,
                              ),
                              decoration: BoxDecoration(
                                color: confidenceColor.withOpacity(0.2),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Text(
                                confidenceLabel,
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                  color: confidenceColor,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(8),
                      child: LinearProgressIndicator(
                        value: confidence / 100,
                        minHeight: 12,
                        backgroundColor: Colors.grey.shade200,
                        valueColor: AlwaysStoppedAnimation<Color>(confidenceColor),
                      ),
                    ),
                    
                    // Show interpretation
                    if (confidence < 30)
                      Padding(
                        padding: const EdgeInsets.only(top: 12),
                        child: Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: Colors.orange.shade100,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Row(
                            children: [
                              Icon(Icons.info_outline, size: 16, color: Colors.orange.shade800),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  'Voice doesn\'t match any registered user',
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: Colors.orange.shade800,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            
            // All Matches (if available)
            if (result['all_scores'] != null && 
                result['all_scores'].isNotEmpty &&
                name != "Can't hear someone speaking" &&
                name != "Unknown Person Speaking")
              _buildAllMatchesSection(result['all_scores']),
          ],
        ),
      ),
    );
  }
  
  Widget _buildAllMatchesSection(List allScores) {
    return Column(
      children: [
        const SizedBox(height: 16),
        const Divider(),
        const SizedBox(height: 12),
        
        Row(
          children: [
            Icon(Icons.leaderboard, size: 20, color: Colors.grey.shade700),
            const SizedBox(width: 8),
            Text(
              'All Matches',
              style: TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 16,
                color: Colors.grey.shade700,
              ),
            ),
          ],
        ),
        
        const SizedBox(height: 12),
        
        Container(
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(
            children: allScores.take(5).map((score) {
              final name = score['name'] ?? '';
              final avgScore = ((score['avg_score'] ?? 0.0) * 100).toDouble();
              final isTop = allScores.indexOf(score) == 0;
              
              return Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                decoration: BoxDecoration(
                  border: Border(
                    bottom: BorderSide(
                      color: Colors.grey.shade200,
                      width: allScores.indexOf(score) < allScores.length - 1 ? 1 : 0,
                    ),
                  ),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 32,
                      height: 32,
                      decoration: BoxDecoration(
                        color: isTop ? Colors.amber.shade100 : Colors.grey.shade100,
                        shape: BoxShape.circle,
                      ),
                      child: Center(
                        child: Text(
                          '${allScores.indexOf(score) + 1}',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: isTop ? Colors.amber.shade700 : Colors.grey.shade700,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        name,
                        style: TextStyle(
                          fontWeight: isTop ? FontWeight.bold : FontWeight.normal,
                          fontSize: 15,
                        ),
                      ),
                    ),
                    Text(
                      '${avgScore.toStringAsFixed(1)}%',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 15,
                        color: _getConfidenceColor(avgScore),
                      ),
                    ),
                  ],
                ),
              );
            }).toList(),
          ),
        ),
      ],
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
                  'How to Use',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                    color: Colors.blue.shade700,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            _buildInstruction('1. Tap "Start Identification"'),
            _buildInstruction('2. Speak clearly for $_recordDuration seconds'),
            _buildInstruction('3. Wait for AI analysis'),
            _buildInstruction('4. View identified speaker with confidence score'),
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
                      'Tip: Higher confidence = better match',
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